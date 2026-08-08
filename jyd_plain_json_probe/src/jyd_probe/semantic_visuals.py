"""Local semantic-visual catalog, deterministic recall and timing policy."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping

from .semantic_subtitles import SemanticSubtitleMappingError


CATALOG_SCHEMA_V1 = "jyd.semantic-visual-catalog.v1"
CATALOG_SCHEMA_V2 = "jyd.semantic-visual-catalog.v2"
CATALOG_SCHEMAS = frozenset({CATALOG_SCHEMA_V1, CATALOG_SCHEMA_V2})
# Import-compatible alias for callers that still mean the legacy schema.
CATALOG_SCHEMA = CATALOG_SCHEMA_V1
CANDIDATE_SCHEMA = "jyd.semantic-visual-candidates.v1"
RECIPE_SCHEMA_V1 = "jyd.semantic-visual-recipe.v1"
RECIPE_SCHEMA_V2 = "jyd.semantic-visual-recipe.v2"
RECIPE_SCHEMAS = frozenset({RECIPE_SCHEMA_V1, RECIPE_SCHEMA_V2})
RECIPE_SCHEMA = RECIPE_SCHEMA_V2
DEFAULT_LIBRARY_ID = "jyd.semantic-visual-library.default"
MEDIA_POLICIES = frozenset(
    {"image_only", "video_only", "prefer_image", "prefer_video", "mixed"}
)


class SemanticVisualCatalogError(ValueError):
    pass


@dataclass(frozen=True)
class SemanticVisualCatalog:
    root: Path
    schema: str
    library_id: str | None
    catalog_version: str
    concepts: tuple[dict[str, Any], ...]
    assets: tuple[dict[str, Any], ...]

    def concept(self, concept_id: str) -> dict[str, Any] | None:
        return next(
            (item for item in self.concepts if item["concept_id"] == concept_id),
            None,
        )

    def asset(self, asset_id: str) -> dict[str, Any] | None:
        return next((item for item in self.assets if item["asset_id"] == asset_id), None)

    def public_payload(self) -> dict[str, Any]:
        payload = {
            "schema": self.schema,
            "catalog_version": self.catalog_version,
            "concepts": [dict(item) for item in self.concepts],
            "assets": [
                {
                    key: value
                    for key, value in item.items()
                    if key
                    not in {
                        "bundle_path",
                        "image_path",
                        "resource_path",
                        "preview_path",
                    }
                }
                for item in self.assets
            ],
        }
        if self.library_id is not None:
            payload["library_id"] = self.library_id
        return payload


def _safe_child(root: Path, raw: str, *, kind: str) -> Path:
    candidate = (root / raw).resolve()
    try:
        candidate.relative_to(root)
    except ValueError as exc:
        raise SemanticVisualCatalogError(f"{kind} path escapes catalog root") from exc
    if not candidate.is_file() and not candidate.is_dir():
        raise SemanticVisualCatalogError(f"{kind} path is missing")
    return candidate


def _safe_relative_child(root: Path, raw: object, *, kind: str) -> tuple[str, Path]:
    relative = str(raw).strip()
    if not relative or Path(relative).is_absolute():
        raise SemanticVisualCatalogError(f"{kind} path must be relative")
    return relative, _safe_child(root, relative, kind=kind)


def _update_file_hash(digest: Any, path: Path) -> None:
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)


def _load_semantic_visual_catalog_v1(root: str | Path) -> SemanticVisualCatalog:
    catalog_root = Path(root).expanduser().resolve()
    manifest_path = catalog_root / "catalog.json"
    try:
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise SemanticVisualCatalogError("semantic visual catalog is unreadable") from exc
    if not isinstance(payload, dict) or payload.get("schema") != CATALOG_SCHEMA_V1:
        raise SemanticVisualCatalogError("unsupported semantic visual catalog schema")
    concepts = payload.get("concepts")
    assets = payload.get("assets")
    if not isinstance(concepts, list) or not isinstance(assets, list):
        raise SemanticVisualCatalogError("catalog concepts/assets must be arrays")

    normalized_concepts: list[dict[str, Any]] = []
    concept_ids: set[str] = set()
    for raw in concepts:
        if not isinstance(raw, dict) or set(raw) != {
            "concept_id",
            "label",
            "description",
            "aliases",
        }:
            raise SemanticVisualCatalogError("invalid catalog concept")
        concept_id = str(raw["concept_id"]).strip()
        label = str(raw["label"]).strip()
        description = str(raw["description"]).strip()
        aliases = raw["aliases"]
        if (
            not concept_id
            or not label
            or not description
            or concept_id in concept_ids
            or not isinstance(aliases, list)
            or not aliases
            or any(
                not isinstance(alias, str) or not alias or alias != alias.strip()
                for alias in aliases
            )
        ):
            raise SemanticVisualCatalogError("invalid concept id or aliases")
        concept_ids.add(concept_id)
        normalized_concepts.append(
            {
                "concept_id": concept_id,
                "label": label,
                "description": description,
                "aliases": list(dict.fromkeys(aliases)),
            }
        )

    normalized_assets: list[dict[str, Any]] = []
    asset_ids: set[str] = set()
    for raw in assets:
        required = {
            "asset_id",
            "concept_id",
            "name",
            "bundle",
            "image",
            "default_corner",
            "default_scale",
            "default_opacity",
        }
        if not isinstance(raw, dict) or set(raw) != required:
            raise SemanticVisualCatalogError("invalid catalog asset")
        asset_id = str(raw["asset_id"]).strip()
        concept_id = str(raw["concept_id"]).strip()
        name = str(raw["name"]).strip()
        corner = str(raw["default_corner"]).strip()
        try:
            scale = float(raw["default_scale"])
            opacity = float(raw["default_opacity"])
        except (TypeError, ValueError) as exc:
            raise SemanticVisualCatalogError("invalid asset defaults") from exc
        if (
            not asset_id
            or not name
            or asset_id in asset_ids
            or concept_id not in concept_ids
            or corner not in {"top_left", "top_right"}
            or not 0.05 <= scale <= 2.0
            or not 0.0 <= opacity <= 1.0
        ):
            raise SemanticVisualCatalogError("invalid asset id or concept")
        bundle_path = _safe_child(catalog_root, str(raw["bundle"]), kind="bundle")
        image_path = _safe_child(catalog_root, str(raw["image"]), kind="image")
        if not bundle_path.is_dir() or not image_path.is_file():
            raise SemanticVisualCatalogError("asset bundle/image type is invalid")
        if not (bundle_path / "sticker.json").is_file():
            raise SemanticVisualCatalogError("asset bundle has no sticker.json")
        asset_ids.add(asset_id)
        normalized_assets.append(
            {
                "asset_id": asset_id,
                "concept_id": concept_id,
                "name": name,
                "bundle": str(raw["bundle"]),
                "image": str(raw["image"]),
                "preview_url": f"/api/new/semantic-visuals/{asset_id}/preview",
                "default_corner": corner,
                "default_scale": scale,
                "default_opacity": opacity,
                "bundle_path": str(bundle_path),
                "image_path": str(image_path),
            }
        )
    available_concepts = {item["concept_id"] for item in normalized_assets}
    normalized_concepts = [
        item for item in normalized_concepts if item["concept_id"] in available_concepts
    ]
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    version_digest = hashlib.sha256(canonical.encode("utf-8"))
    for asset in sorted(normalized_assets, key=lambda item: item["asset_id"]):
        _update_file_hash(version_digest, Path(asset["bundle_path"]) / "sticker.json")
        _update_file_hash(version_digest, Path(asset["image_path"]))
    catalog_version = "sha256:" + version_digest.hexdigest()
    return SemanticVisualCatalog(
        root=catalog_root,
        schema=CATALOG_SCHEMA_V1,
        library_id=None,
        catalog_version=catalog_version,
        concepts=tuple(normalized_concepts),
        assets=tuple(normalized_assets),
    )


def _with_unified_v1_assets(catalog: SemanticVisualCatalog) -> SemanticVisualCatalog:
    assets: list[dict[str, Any]] = []
    for raw in catalog.assets:
        asset = dict(raw)
        asset.update(
            {
                "concept_ids": [asset["concept_id"]],
                "description": asset["name"],
                "media_type": "image",
                "renderer": "jyd_sticker_bundle",
                "tags": [],
                "resource": {
                    "bundle": asset["bundle"],
                    "preview": asset["image"],
                },
                "defaults": {
                    "corner": asset["default_corner"],
                    "scale": asset["default_scale"],
                    "opacity": asset["default_opacity"],
                    "duration_us": 1_800_000,
                },
                "resource_path": asset["bundle_path"],
                "preview_path": asset["image_path"],
            }
        )
        assets.append(asset)
    return SemanticVisualCatalog(
        root=catalog.root,
        schema=catalog.schema,
        library_id=catalog.library_id,
        catalog_version=catalog.catalog_version,
        concepts=catalog.concepts,
        assets=tuple(assets),
    )


def _normalize_v2_concepts(raw_concepts: object) -> tuple[list[dict[str, Any]], set[str]]:
    if not isinstance(raw_concepts, list):
        raise SemanticVisualCatalogError("catalog concepts must be an array")
    concepts: list[dict[str, Any]] = []
    concept_ids: set[str] = set()
    for raw in raw_concepts:
        if not isinstance(raw, dict) or set(raw) != {
            "concept_id",
            "label",
            "description",
            "aliases",
        }:
            raise SemanticVisualCatalogError("invalid catalog concept")
        concept_id = str(raw["concept_id"]).strip()
        label = str(raw["label"]).strip()
        description = str(raw["description"]).strip()
        aliases = raw["aliases"]
        if (
            not concept_id
            or not label
            or not description
            or concept_id in concept_ids
            or not isinstance(aliases, list)
            or not aliases
            or any(
                not isinstance(alias, str) or not alias or alias != alias.strip()
                for alias in aliases
            )
        ):
            raise SemanticVisualCatalogError("invalid concept id or aliases")
        concept_ids.add(concept_id)
        concepts.append(
            {
                "concept_id": concept_id,
                "label": label,
                "description": description,
                "aliases": list(dict.fromkeys(aliases)),
            }
        )
    return concepts, concept_ids


def _normalize_v2_identity(
    raw: Mapping[str, Any],
    *,
    asset_ids: set[str],
    concept_ids: set[str],
) -> tuple[str, list[str], str, str, list[str]]:
    asset_id = str(raw["asset_id"]).strip()
    name = str(raw["name"]).strip()
    description = str(raw["description"]).strip()
    raw_concept_ids = raw["concept_ids"]
    tags = raw["tags"]
    if not isinstance(raw_concept_ids, list) or not isinstance(tags, list):
        raise SemanticVisualCatalogError("asset concept_ids/tags must be arrays")
    normalized_concept_ids = list(
        dict.fromkeys(str(value).strip() for value in raw_concept_ids)
    )
    if (
        not asset_id
        or asset_id in asset_ids
        or not name
        or not description
        or not normalized_concept_ids
        or any(not value or value not in concept_ids for value in normalized_concept_ids)
        or any(
            not isinstance(tag, str) or not tag or tag != tag.strip()
            for tag in tags
        )
    ):
        raise SemanticVisualCatalogError("invalid asset identity")
    asset_ids.add(asset_id)
    return asset_id, normalized_concept_ids, name, description, list(dict.fromkeys(tags))


def _normalized_visual_defaults(
    raw: Mapping[str, Any], *, video: bool
) -> dict[str, Any]:
    expected = {"corner", "scale", "opacity", "duration_us"}
    if video:
        expected |= {"source_start_us", "mute", "loop", "fit"}
    if set(raw) != expected:
        raise SemanticVisualCatalogError("invalid asset defaults")
    try:
        corner = str(raw["corner"]).strip()
        scale = float(raw["scale"])
        opacity = float(raw["opacity"])
        duration_us = int(raw["duration_us"])
    except (TypeError, ValueError) as exc:
        raise SemanticVisualCatalogError("invalid asset defaults") from exc
    normalized: dict[str, Any] = {
        "corner": corner,
        "scale": scale,
        "opacity": opacity,
        "duration_us": duration_us,
    }
    if (
        corner not in {"top_left", "top_right"}
        or not 0.05 <= scale <= 2.0
        or not 0.0 <= opacity <= 1.0
        or duration_us <= 0
    ):
        raise SemanticVisualCatalogError("invalid asset defaults")
    if not video:
        return normalized
    try:
        source_start_us = int(raw["source_start_us"])
    except (TypeError, ValueError) as exc:
        raise SemanticVisualCatalogError("invalid video defaults") from exc
    mute = raw["mute"]
    loop = raw["loop"]
    fit = str(raw["fit"]).strip()
    if (
        source_start_us < 0
        or not isinstance(mute, bool)
        or not isinstance(loop, bool)
        or fit not in {"cover", "contain"}
    ):
        raise SemanticVisualCatalogError("invalid video defaults")
    normalized.update(
        {
            "source_start_us": source_start_us,
            "mute": mute,
            "loop": loop,
            "fit": fit,
        }
    )
    return normalized


def _normalize_v2_image(
    raw: Mapping[str, Any],
    *,
    catalog_root: Path,
    common: dict[str, Any],
) -> tuple[dict[str, Any], list[Path]]:
    resource = raw["resource"]
    defaults = raw["defaults"]
    if (
        not isinstance(resource, Mapping)
        or set(resource) != {"bundle", "preview"}
        or not isinstance(defaults, Mapping)
    ):
        raise SemanticVisualCatalogError("invalid image asset resource")
    bundle, bundle_path = _safe_relative_child(
        catalog_root, resource["bundle"], kind="bundle"
    )
    preview, preview_path = _safe_relative_child(
        catalog_root, resource["preview"], kind="preview"
    )
    sticker_path = bundle_path / "sticker.json"
    if not bundle_path.is_dir() or not preview_path.is_file() or not sticker_path.is_file():
        raise SemanticVisualCatalogError("invalid image asset files")
    normalized_defaults = _normalized_visual_defaults(defaults, video=False)
    asset_id = common["asset_id"]
    normalized = {
        **common,
        "media_type": "image",
        "renderer": "jyd_sticker_bundle",
        "resource": {"bundle": bundle, "preview": preview},
        "defaults": normalized_defaults,
        # Compatibility aliases used by the current v1 recipe/web handlers.
        "concept_id": common["concept_ids"][0],
        "bundle": bundle,
        "image": preview,
        "preview_url": f"/api/new/semantic-visuals/{asset_id}/preview",
        "default_corner": normalized_defaults["corner"],
        "default_scale": normalized_defaults["scale"],
        "default_opacity": normalized_defaults["opacity"],
        "bundle_path": str(bundle_path),
        "image_path": str(preview_path),
        "resource_path": str(bundle_path),
        "preview_path": str(preview_path),
    }
    return normalized, [sticker_path, preview_path]


def _normalize_v2_video(
    raw: Mapping[str, Any],
    *,
    catalog_root: Path,
    common: dict[str, Any],
) -> tuple[dict[str, Any], list[Path]]:
    resource = raw["resource"]
    defaults = raw["defaults"]
    required = {"video", "preview", "duration_us", "width", "height", "has_audio"}
    if (
        not isinstance(resource, Mapping)
        or frozenset(resource) not in {frozenset(required), frozenset(required | {"metadata"})}
        or not isinstance(defaults, Mapping)
    ):
        raise SemanticVisualCatalogError("invalid video asset resource")
    video, video_path = _safe_relative_child(
        catalog_root, resource["video"], kind="video"
    )
    preview, preview_path = _safe_relative_child(
        catalog_root, resource["preview"], kind="preview"
    )
    if not video_path.is_file() or not preview_path.is_file():
        raise SemanticVisualCatalogError("invalid video asset files")
    try:
        source_duration_us = int(resource["duration_us"])
        width = int(resource["width"])
        height = int(resource["height"])
    except (TypeError, ValueError) as exc:
        raise SemanticVisualCatalogError("invalid video asset metadata") from exc
    has_audio = resource["has_audio"]
    if (
        source_duration_us <= 0
        or width <= 0
        or height <= 0
        or not isinstance(has_audio, bool)
    ):
        raise SemanticVisualCatalogError("invalid video asset metadata")
    normalized_defaults = _normalized_visual_defaults(defaults, video=True)
    if (
        not normalized_defaults["loop"]
        and normalized_defaults["source_start_us"] + normalized_defaults["duration_us"]
        > source_duration_us
    ):
        raise SemanticVisualCatalogError("video default range exceeds source duration")
    normalized_resource: dict[str, Any] = {
        "video": video,
        "preview": preview,
        "duration_us": source_duration_us,
        "width": width,
        "height": height,
        "has_audio": has_audio,
    }
    version_paths = [video_path, preview_path]
    if "metadata" in resource:
        metadata, metadata_path = _safe_relative_child(
            catalog_root, resource["metadata"], kind="metadata"
        )
        if not metadata_path.is_file():
            raise SemanticVisualCatalogError("invalid video metadata file")
        normalized_resource["metadata"] = metadata
        version_paths.append(metadata_path)
    asset_id = common["asset_id"]
    normalized = {
        **common,
        "media_type": "video",
        "renderer": "video_overlay",
        "resource": normalized_resource,
        "defaults": normalized_defaults,
        "concept_id": common["concept_ids"][0],
        "preview_url": f"/api/new/semantic-visuals/{asset_id}/preview",
        "resource_path": str(video_path),
        "preview_path": str(preview_path),
        # Preview endpoint compatibility; a video intentionally has no bundle_path.
        "image_path": str(preview_path),
        "default_corner": normalized_defaults["corner"],
        "default_scale": normalized_defaults["scale"],
        "default_opacity": normalized_defaults["opacity"],
    }
    return normalized, version_paths


def _load_semantic_visual_catalog_v2(
    catalog_root: Path, payload: Mapping[str, Any]
) -> SemanticVisualCatalog:
    if set(payload) != {"schema", "library_id", "concepts", "assets"}:
        raise SemanticVisualCatalogError("invalid semantic visual catalog v2 root")
    library_id = str(payload["library_id"]).strip()
    if not library_id:
        raise SemanticVisualCatalogError("catalog library_id is required")
    concepts, concept_ids = _normalize_v2_concepts(payload["concepts"])
    raw_assets = payload["assets"]
    if not isinstance(raw_assets, list):
        raise SemanticVisualCatalogError("catalog assets must be an array")
    expected_asset_fields = {
        "asset_id",
        "concept_ids",
        "name",
        "description",
        "media_type",
        "renderer",
        "tags",
        "resource",
        "defaults",
    }
    assets: list[dict[str, Any]] = []
    asset_ids: set[str] = set()
    version_paths: list[Path] = []
    for raw in raw_assets:
        if not isinstance(raw, dict) or set(raw) != expected_asset_fields:
            raise SemanticVisualCatalogError("invalid catalog v2 asset")
        asset_id, linked_concepts, name, description, tags = _normalize_v2_identity(
            raw, asset_ids=asset_ids, concept_ids=concept_ids
        )
        common = {
            "asset_id": asset_id,
            "concept_ids": linked_concepts,
            "name": name,
            "description": description,
            "tags": tags,
        }
        pair = (str(raw["media_type"]).strip(), str(raw["renderer"]).strip())
        if pair == ("image", "jyd_sticker_bundle"):
            asset, paths = _normalize_v2_image(
                raw, catalog_root=catalog_root, common=common
            )
        elif pair == ("video", "video_overlay"):
            asset, paths = _normalize_v2_video(
                raw, catalog_root=catalog_root, common=common
            )
        else:
            raise SemanticVisualCatalogError("unsupported media_type/renderer pair")
        assets.append(asset)
        version_paths.extend(paths)
    available_concepts = {
        concept_id for asset in assets for concept_id in asset["concept_ids"]
    }
    concepts = [item for item in concepts if item["concept_id"] in available_concepts]
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    version_digest = hashlib.sha256(canonical.encode("utf-8"))
    for path in sorted(version_paths, key=lambda item: str(item).casefold()):
        _update_file_hash(version_digest, path)
    return SemanticVisualCatalog(
        root=catalog_root,
        schema=CATALOG_SCHEMA_V2,
        library_id=library_id,
        catalog_version="sha256:" + version_digest.hexdigest(),
        concepts=tuple(concepts),
        assets=tuple(assets),
    )


def load_semantic_visual_catalog(root: str | Path) -> SemanticVisualCatalog:
    catalog_root = Path(root).expanduser().resolve()
    manifest_path = catalog_root / "catalog.json"
    try:
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise SemanticVisualCatalogError("semantic visual catalog is unreadable") from exc
    if not isinstance(payload, dict) or payload.get("schema") not in CATALOG_SCHEMAS:
        raise SemanticVisualCatalogError("unsupported semantic visual catalog schema")
    if payload["schema"] == CATALOG_SCHEMA_V1:
        if set(payload) != {"schema", "concepts", "assets"}:
            raise SemanticVisualCatalogError("invalid semantic visual catalog v1 root")
        return _with_unified_v1_assets(_load_semantic_visual_catalog_v1(catalog_root))
    return _load_semantic_visual_catalog_v2(catalog_root, payload)


def recall_semantic_visual_candidates(
    original_script: str,
    catalog: SemanticVisualCatalog,
) -> dict[str, Any]:
    """Recall longest, non-overlapping aliases with stable exact character spans."""

    alias_concepts: dict[str, list[dict[str, Any]]] = {}
    for concept in catalog.concepts:
        compact = {
            "concept_id": concept["concept_id"],
            "description": concept["description"],
        }
        for alias in concept["aliases"]:
            alias_concepts.setdefault(alias, []).append(compact)

    matches: list[tuple[int, int, str, list[dict[str, Any]]]] = []
    for alias, allowed in alias_concepts.items():
        cursor = 0
        while True:
            start = original_script.find(alias, cursor)
            if start < 0:
                break
            matches.append((start, start + len(alias), alias, allowed))
            cursor = start + max(1, len(alias))
    matches.sort(key=lambda item: (item[0], -(item[1] - item[0]), item[2]))

    selected: list[tuple[int, int, str, list[dict[str, Any]]]] = []
    for match in matches:
        start, end, _alias, _allowed = match
        if any(start < kept_end and end > kept_start for kept_start, kept_end, *_ in selected):
            continue
        selected.append(match)
    selected.sort(key=lambda item: (item[0], item[1]))

    script_sha256 = hashlib.sha256(original_script.encode("utf-8")).hexdigest()
    candidates: list[dict[str, Any]] = []
    for start, end, text, allowed in selected:
        allowed_sorted = sorted(allowed, key=lambda item: item["concept_id"])
        identity = json.dumps(
            [script_sha256, start, end, text, [x["concept_id"] for x in allowed_sorted]],
            ensure_ascii=False,
            separators=(",", ":"),
        )
        candidates.append(
            {
                "candidate_id": "vc_" + hashlib.sha256(identity.encode("utf-8")).hexdigest()[:24],
                "text": text,
                "char_start": start,
                "char_end": end,
                "allowed_concepts": allowed_sorted,
            }
        )
    return {
        "schema_version": "jyd.visual-analysis.request.v1",
        "original_script": original_script,
        "script_sha256": script_sha256,
        "catalog_version": catalog.catalog_version,
        "candidates": candidates,
    }


def _character_time_ranges(
    original_script: str, raw_cues: Iterable[object]
) -> list[tuple[int, int]]:
    # Reuse the thoroughly tested MiniMax alignment implementation. One-character
    # units expose its private range calculation without inventing a second mapper.
    from .semantic_subtitles import map_subtitle_units_to_raw_cues

    units = [
        {
            "start": index,
            "end": index + 1,
            "text": character,
            "kind": "whitespace" if character.isspace() else "phrase",
            "bind": "none",
            "break_after": "allow",
        }
        for index, character in enumerate(original_script)
    ]
    timed = map_subtitle_units_to_raw_cues(original_script, units, raw_cues)
    return [(int(item["start_us"]), int(item["end_us"])) for item in timed]


def map_visual_candidates_to_raw_cues(
    original_script: str,
    candidates: Iterable[Mapping[str, Any]],
    raw_cues: Iterable[object],
    *,
    video_duration_us: int | None = None,
    cover_offset_us: int = 0,
    lead_us: int = 120_000,
    default_duration_us: int = 1_800_000,
) -> list[dict[str, Any]]:
    ranges = _character_time_ranges(original_script, raw_cues)
    mapped: list[dict[str, Any]] = []
    for candidate in candidates:
        start = int(candidate["char_start"])
        end = int(candidate["char_end"])
        if start < 0 or end <= start or end > len(ranges):
            raise SemanticSubtitleMappingError(
                "VISUAL_CANDIDATE_RANGE_INVALID", "语义图片候选字符范围无效"
            )
        start_us = max(0, ranges[start][0] - max(0, lead_us)) + max(0, cover_offset_us)
        duration_us = default_duration_us
        if video_duration_us is not None:
            duration_us = min(duration_us, max(0, int(video_duration_us) - start_us))
        if duration_us <= 0:
            raise SemanticSubtitleMappingError(
                "VISUAL_TIME_OUT_OF_RANGE", "语义图片映射时间超出视频范围"
            )
        mapped.append({**dict(candidate), "start_us": start_us, "duration_us": duration_us})
    return mapped


def _assets_for_media_policy(
    catalog: SemanticVisualCatalog,
    concept_id: str,
    media_policy: str,
) -> list[dict[str, Any]]:
    if media_policy not in MEDIA_POLICIES:
        raise ValueError("未知的语义视觉媒体策略")
    available = [
        item for item in catalog.assets if concept_id in item["concept_ids"]
    ]
    images = [item for item in available if item["media_type"] == "image"]
    videos = [item for item in available if item["media_type"] == "video"]
    if media_policy == "image_only":
        return images
    if media_policy == "video_only":
        return videos
    if media_policy == "prefer_image":
        return images or videos
    if media_policy == "prefer_video":
        return videos or images
    return available


def build_visual_recipe(
    *,
    catalog: SemanticVisualCatalog,
    mapped_candidates: Iterable[Mapping[str, Any]],
    decisions: Iterable[Mapping[str, Any]],
    media_policy: str = "image_only",
) -> dict[str, Any]:
    """Apply confidence gates and density limits to create one frozen recipe."""

    mapped = {str(item["candidate_id"]): dict(item) for item in mapped_candidates}
    selected: list[dict[str, Any]] = []
    for decision in sorted(
        decisions,
        key=lambda item: (
            -float(item.get("importance", 0.0) or 0.0),
            -float(item.get("confidence", 0.0) or 0.0),
            mapped.get(str(item.get("candidate_id")), {}).get("start_us", 0),
        ),
    ):
        candidate = mapped.get(str(decision.get("candidate_id")))
        if candidate is None:
            continue
        confidence = float(decision.get("confidence", 0.0) or 0.0)
        if decision.get("decision") != "SHOW" or confidence < 0.85:
            continue
        concept_id = str(decision.get("concept_id") or "")
        assets = _assets_for_media_policy(catalog, concept_id, media_policy)
        if not assets:
            continue
        occurrence = sum(
            1
            for item in mapped.values()
            if int(item.get("start_us", 0)) < int(candidate["start_us"])
            and any(
                concept.get("concept_id") == concept_id
                for concept in item.get("allowed_concepts", [])
                if isinstance(concept, Mapping)
            )
        )
        asset = assets[occurrence % len(assets)]
        start_us = int(candidate["start_us"])
        duration_us = int(candidate["duration_us"])
        if any(
            start_us < item["start_us"] + item["duration_us"]
            and item["start_us"] < start_us + duration_us
            for item in selected
        ):
            continue
        if any(abs(start_us - item["start_us"]) < 6_000_000 for item in selected):
            continue
        if sum(abs(start_us - item["start_us"]) < 60_000_000 for item in selected) >= 5:
            continue
        if any(
            item["concept_id"] == concept_id
            and abs(start_us - item["start_us"]) < 20_000_000
            for item in selected
        ):
            continue
        if any(
            item["asset_id"] == asset["asset_id"]
            and abs(start_us - item["start_us"]) < 20_000_000
            for item in selected
        ):
            continue
        defaults = asset["defaults"]
        resource = asset["resource"]
        media_type = asset["media_type"]
        overlay = {
            "overlay_id": "vo_" + str(candidate["candidate_id"]).removeprefix("vc_"),
            "candidate_id": candidate["candidate_id"],
            "concept_id": concept_id,
            "asset_id": asset["asset_id"],
            "asset_name": asset["name"],
            "preview_url": asset["preview_url"],
            "media_type": media_type,
            "renderer": asset["renderer"],
            "resource_path": (
                resource["bundle"] if media_type == "image" else resource["video"]
            ),
            "enabled": True,
            "selection_mode": "auto",
            "manual": False,
            "locked": False,
            "corner": defaults["corner"],
            "scale": defaults["scale"],
            "opacity": defaults["opacity"],
            "start_us": start_us,
            "duration_us": duration_us,
            "confidence": confidence,
            "importance": float(decision.get("importance", 0.0) or 0.0),
            "reason_code": decision.get("reason_code"),
            "timing_source": "minimax_raw_cue_interpolation",
        }
        if media_type == "video":
            overlay.update(
                {
                    "source_start_us": defaults["source_start_us"],
                    "mute": defaults["mute"],
                    "loop": defaults["loop"],
                    "fit": defaults["fit"],
                }
            )
        selected.append(overlay)
    selected.sort(key=lambda item: (item["start_us"], item["overlay_id"]))
    return {
        "schema": RECIPE_SCHEMA,
        "library_id": catalog.library_id or DEFAULT_LIBRARY_ID,
        "catalog_version": catalog.catalog_version,
        "media_policy": media_policy,
        "overlays": selected,
    }


def frozen_visual_overlays(
    item: Mapping[str, Any], *, library_root: str | Path | None = None
) -> list[dict[str, Any]]:
    """Return enabled overlays and resolve v2 paths only at render-job time."""

    analysis = item.get("visual_analysis")
    recipe = analysis.get("recipe") if isinstance(analysis, Mapping) else None
    if not isinstance(recipe, Mapping) or recipe.get("schema") not in RECIPE_SCHEMAS:
        return []
    schema = str(recipe["schema"])
    resolved_root = Path(library_root).expanduser().resolve() if library_root else None
    result: list[dict[str, Any]] = []
    for raw in recipe.get("overlays", []):
        if (
            not isinstance(raw, Mapping)
            or raw.get("enabled") is False
            or raw.get("requires_review") is True
        ):
            continue
        overlay = dict(raw)
        if schema == RECIPE_SCHEMA_V2 and resolved_root is not None:
            try:
                _relative, resource_path = _safe_relative_child(
                    resolved_root, overlay.get("resource_path"), kind="recipe resource"
                )
            except SemanticVisualCatalogError:
                # A semantic overlay is optional enhancement; one missing or unsafe
                # resource must not break the base video, voice, captions or BGM.
                continue
            renderer = str(overlay.get("renderer") or "")
            if renderer == "jyd_sticker_bundle":
                if not resource_path.is_dir() or not (resource_path / "sticker.json").is_file():
                    continue
                overlay["bundle_path"] = str(resource_path)
            elif renderer == "video_overlay":
                if not resource_path.is_file():
                    continue
                overlay["video_path"] = str(resource_path)
            else:
                continue
        result.append(overlay)
    return result
