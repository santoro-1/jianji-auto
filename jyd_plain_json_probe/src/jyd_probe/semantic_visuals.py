"""Local semantic-visual catalog, deterministic recall and timing policy."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping

from .caption_alignment import CaptionAlignmentError, script_tokens
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
FIXED_NAMEPLATE_BUNDLE = Path("fixed") / "nameplate_zhangluo"
FIXED_NAMEPLATE_PREVIEW_URL = "/api/new/fixed-visuals/nameplate/preview"
# Keep the fixed nameplate clear of uniforms/logos on the upper right chest.
# At scale 0.60, transform_x=-0.40 aligns its left edge with the video frame.
FIXED_NAMEPLATE_SCALE = 0.60
FIXED_NAMEPLATE_TRANSFORM_X = -0.40
FIXED_NAMEPLATE_TRANSFORM_Y = -0.26
MEDIA_POLICIES = frozenset(
    {"image_only", "video_only", "prefer_image", "prefer_video", "mixed"}
)
VISUAL_CORNERS = frozenset(
    {
        "top_left",
        "top_right",
        "bottom_left",
        "bottom_right",
        "bottom_center",
        "center",
    }
)
VISUAL_PHRASE_BOUNDARIES = frozenset("，,。！？!?；;：:\n\r")
VISUAL_HOLD_AFTER_MATCH_US = 400_000
VISUAL_DEFAULT_AUTO_DURATION_US = 1_500_000
VISUAL_MAX_AUTO_DURATION_US = 2_500_000
VISUAL_MIN_AUTO_START_GAP_US = 1_500_000
VISUAL_MAX_AUTO_PER_MINUTE = 24
VISUAL_KEYWORD_LEAD_US = 300_000
VISUAL_OPENING_PROTECTION_US = 1_200_000
VISUAL_ENRICHMENT_MIN_GAP_US = 20_000_000
VISUAL_ENRICHMENT_MAX_PER_MINUTE = 2
VISUAL_ENRICHMENT_CHAR_INTERVAL = 100
VISUAL_ENRICHMENT_MAX_ANCHORS = 6
VISUAL_ENRICHMENT_TAGS = frozenset({"空镜", "相关素材", "b-roll", "broll", "enrichment"})
VISUAL_IMAGE_DEFAULT_CORNER = "bottom_center"
VISUAL_IMAGE_DEFAULT_SCALE = 0.78
VISUAL_ACTION_VIDEO_DEFAULT_CORNER = "bottom_center"
VISUAL_ACTION_VIDEO_DEFAULT_SCALE = 0.615
VISUAL_BROLL_DEFAULT_CORNER = "center"
VISUAL_BROLL_DEFAULT_SCALE = 1.0
VISUAL_ALIAS_EXCLUDED_COMPOUNDS = {
    "鸡蛋": ("鸡蛋糕",),
    "蔬菜": ("蔬菜沙拉", "蔬菜色拉"),
    "青菜": ("青菜沙拉", "青菜色拉"),
}


class SemanticVisualCatalogError(ValueError):
    pass


def fixed_nameplate_overlay(library_root: str | Path) -> dict[str, Any]:
    """Return the portable, non-editable nameplate recipe used by every project video."""

    bundle = Path(library_root).expanduser().resolve() / FIXED_NAMEPLATE_BUNDLE
    return {
        "enabled": True,
        "bundle_path": str(bundle),
        "preview_url": FIXED_NAMEPLATE_PREVIEW_URL,
        "start_us": 0,
        "duration_us": 0,
        "corner": "center",
        "scale": FIXED_NAMEPLATE_SCALE,
        "transform_x": FIXED_NAMEPLATE_TRANSFORM_X,
        "transform_y": FIXED_NAMEPLATE_TRANSFORM_Y,
        "opacity": 1.0,
        "track_name": "固定人名牌",
    }


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
            or corner not in VISUAL_CORNERS
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
        corner not in VISUAL_CORNERS
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


def _apply_product_visual_layout(
    defaults: Mapping[str, Any], *, media_type: str, tags: Iterable[str]
) -> dict[str, Any]:
    """Keep automatic talking-head visuals on the accepted product layout.

    Catalog manifests retain asset provenance and duration defaults, but placement is
    a product-level rule.  Centralizing it here also refreshes untouched recipes from
    older catalogs without overwriting manual or locked project edits.
    """

    normalized = dict(defaults)
    if media_type == "image":
        normalized.update(
            corner=VISUAL_IMAGE_DEFAULT_CORNER,
            scale=VISUAL_IMAGE_DEFAULT_SCALE,
        )
        return normalized
    enrichment = any(str(tag).strip().lower() in VISUAL_ENRICHMENT_TAGS for tag in tags)
    normalized.update(
        corner=(VISUAL_BROLL_DEFAULT_CORNER if enrichment else VISUAL_ACTION_VIDEO_DEFAULT_CORNER),
        scale=(VISUAL_BROLL_DEFAULT_SCALE if enrichment else VISUAL_ACTION_VIDEO_DEFAULT_SCALE),
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
    normalized_defaults = _apply_product_visual_layout(
        _normalized_visual_defaults(defaults, video=False),
        media_type="image",
        tags=common["tags"],
    )
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
    normalized_defaults = _apply_product_visual_layout(
        _normalized_visual_defaults(defaults, video=True),
        media_type="video",
        tags=common["tags"],
    )
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


def _alias_is_excluded_compound(
    script: str, *, start: int, end: int, alias: str
) -> bool:
    for compound in VISUAL_ALIAS_EXCLUDED_COMPOUNDS.get(alias, ()):
        first = max(0, start - len(compound) + len(alias))
        for compound_start in range(first, start + 1):
            compound_end = compound_start + len(compound)
            if (
                compound_start <= start
                and end <= compound_end
                and script[compound_start:compound_end] == compound
            ):
                return True
    return False


def visual_candidate_context(
    script: str, *, start: int, end: int, maximum_length: int = 60
) -> str:
    left = start
    while left > 0 and script[left - 1] not in VISUAL_PHRASE_BOUNDARIES:
        left -= 1
    right = end
    while right < len(script) and script[right] not in VISUAL_PHRASE_BOUNDARIES:
        right += 1
    context = script[left:right].strip()
    if len(context) <= maximum_length:
        return context
    padding = max(0, (maximum_length - (end - start)) // 2)
    return script[max(left, start - padding) : min(right, end + padding)].strip()


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
            end = start + len(alias)
            if not _alias_is_excluded_compound(
                original_script, start=start, end=end, alias=alias
            ):
                matches.append((start, end, alias, allowed))
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

    enrichment_concept_ids = {
        concept_id
        for asset in catalog.assets
        if any(str(tag).strip().lower() in VISUAL_ENRICHMENT_TAGS for tag in asset.get("tags", []))
        for concept_id in asset.get("concept_ids", [])
    }
    concept_by_id = {str(item["concept_id"]): item for item in catalog.concepts}
    enrichment_allowed = [
        {
            "concept_id": concept_id,
            "description": str(concept_by_id[concept_id]["description"]),
        }
        for concept_id in sorted(enrichment_concept_ids)
        if concept_id in concept_by_id
    ][:8]
    occupied_starts = {int(item["char_start"]) for item in candidates}
    if enrichment_allowed and len(original_script) >= VISUAL_ENRICHMENT_CHAR_INTERVAL:
        for target in range(
            VISUAL_ENRICHMENT_CHAR_INTERVAL,
            len(original_script),
            VISUAL_ENRICHMENT_CHAR_INTERVAL,
        ):
            if sum(
                str(item.get("candidate_id") or "").startswith("ve_")
                for item in candidates
            ) >= VISUAL_ENRICHMENT_MAX_ANCHORS:
                break
            start = target
            while start < len(original_script) and original_script[start - 1] not in VISUAL_PHRASE_BOUNDARIES:
                start += 1
            while start < len(original_script) and (
                original_script[start].isspace() or original_script[start] in VISUAL_PHRASE_BOUNDARIES
            ):
                start += 1
            if start >= len(original_script) or start in occupied_starts:
                continue
            end = start
            while (
                end < len(original_script)
                and end - start < 40
                and original_script[end] not in VISUAL_PHRASE_BOUNDARIES
            ):
                end += 1
            if end <= start:
                continue
            text = original_script[start:end]
            identity = json.dumps(
                [
                    script_sha256,
                    "enrichment",
                    start,
                    end,
                    [item["concept_id"] for item in enrichment_allowed],
                ],
                ensure_ascii=False,
                separators=(",", ":"),
            )
            candidates.append(
                {
                    "candidate_id": "ve_" + hashlib.sha256(identity.encode("utf-8")).hexdigest()[:24],
                    "text": text,
                    "char_start": start,
                    "char_end": end,
                    "allowed_concepts": enrichment_allowed,
                }
            )
            occupied_starts.add(start)
    candidates.sort(key=lambda item: (int(item["char_start"]), int(item["char_end"])))
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


def _asr_candidate_time_range(
    original_script: str,
    raw_cues: Iterable[object],
    asr_alignment: Mapping[str, Any] | None,
    *,
    start: int,
    end: int,
) -> tuple[int, int] | None:
    if not isinstance(asr_alignment, Mapping) or asr_alignment.get("status") != "SUCCESS":
        return None
    raw_ranges = asr_alignment.get("ranges")
    if not isinstance(raw_ranges, list):
        return None
    try:
        _cues, tokens = script_tokens(original_script, raw_cues)
        aligned = {
            int(item["token_index"]): item
            for item in raw_ranges
            if isinstance(item, Mapping) and "token_index" in item
        }
        overlapping = [
            token for token in tokens if token.start < end and token.end > start
        ]
        if not overlapping or any(token.index not in aligned for token in overlapping):
            return None
        first = aligned[overlapping[0].index]
        last = aligned[overlapping[-1].index]
        start_us = int(first["start_us"])
        end_us = int(last["end_us"])
        if end_us <= start_us:
            return None
        return start_us, end_us
    except (CaptionAlignmentError, KeyError, TypeError, ValueError):
        return None


def map_visual_candidates_to_raw_cues(
    original_script: str,
    candidates: Iterable[Mapping[str, Any]],
    raw_cues: Iterable[object],
    *,
    video_duration_us: int | None = None,
    asr_alignment: Mapping[str, Any] | None = None,
    cover_offset_us: int = 0,
    lead_us: int = 0,
    default_duration_us: int = VISUAL_DEFAULT_AUTO_DURATION_US,
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
        usage = str(
            candidate.get("usage")
            or ("enrichment" if str(candidate.get("candidate_id") or "").startswith("ve_") else "explicit")
        )
        precise_range = _asr_candidate_time_range(
            original_script,
            raw_cues,
            asr_alignment,
            start=start,
            end=end,
        )
        anchor_start_us = precise_range[0] if precise_range else ranges[start][0]
        anchor_end_us = precise_range[1] if precise_range else ranges[end - 1][1]
        automatic_lead_us = VISUAL_KEYWORD_LEAD_US if usage == "explicit" else 0
        start_us = (
            max(0, anchor_start_us - automatic_lead_us - max(0, lead_us))
            + max(0, cover_offset_us)
        )
        matched_end_us = anchor_end_us + max(0, cover_offset_us)
        duration_us = min(
            VISUAL_MAX_AUTO_DURATION_US,
            max(default_duration_us, matched_end_us - start_us + VISUAL_HOLD_AFTER_MATCH_US),
        )
        if video_duration_us is not None:
            duration_us = min(duration_us, max(0, int(video_duration_us) - start_us))
        if duration_us <= 0:
            raise SemanticSubtitleMappingError(
                "VISUAL_TIME_OUT_OF_RANGE", "语义图片映射时间超出视频范围"
            )
        mapped.append(
            {
                **dict(candidate),
                "start_us": start_us,
                "duration_us": duration_us,
                "matched_end_us": matched_end_us,
                "video_duration_us": video_duration_us,
                "phrase_char_start": start,
                "phrase_text": original_script[start:end],
                "timing_source": (
                    "funasr_word_timestamps"
                    if precise_range is not None
                    else "minimax_raw_cue_keyword_start"
                ),
            }
        )
    return mapped


def _assets_for_media_policy(
    catalog: SemanticVisualCatalog,
    concept_id: str,
    media_policy: str,
    *,
    usage: str = "explicit",
) -> list[dict[str, Any]]:
    if media_policy not in MEDIA_POLICIES:
        raise ValueError("未知的语义视觉媒体策略")
    available = [
        item for item in catalog.assets if concept_id in item["concept_ids"]
    ]
    enrichment_assets = [
        item
        for item in available
        if any(
            str(tag).strip().lower() in VISUAL_ENRICHMENT_TAGS
            for tag in item.get("tags", [])
        )
    ]
    if usage == "enrichment":
        available = enrichment_assets
    else:
        explicit_assets = [item for item in available if item not in enrichment_assets]
        available = explicit_assets or available
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
    # Motion concepts benefit from actual movement when both media types are
    # available. Static objects remain image-first. Either branch falls back
    # locally without adding fields to the model response.
    return videos + images if concept_id.startswith("activity.") else images + videos


def visual_overlay_conflicts(
    candidate: Mapping[str, Any], selected: Iterable[Mapping[str, Any]]
) -> bool:
    """Apply the shared automatic visual-occupancy and density rules."""

    start_us = int(candidate.get("start_us") or 0)
    duration_us = int(candidate.get("duration_us") or 0)
    concept_id = str(candidate.get("concept_id") or "")
    asset_id = str(candidate.get("asset_id") or "")
    active = [item for item in selected if item.get("enabled") is not False]
    if any(
        start_us < int(item.get("start_us") or 0) + int(item.get("duration_us") or 0)
        and int(item.get("start_us") or 0) < start_us + duration_us
        for item in active
    ):
        return True
    if any(
        abs(start_us - int(item.get("start_us") or 0))
        < VISUAL_MIN_AUTO_START_GAP_US
        for item in active
    ):
        return True
    if (
        sum(
            abs(start_us - int(item.get("start_us") or 0)) < 60_000_000
            for item in active
        )
        >= VISUAL_MAX_AUTO_PER_MINUTE
    ):
        return True
    if concept_id and any(
        str(item.get("concept_id") or "") == concept_id
        and abs(start_us - int(item.get("start_us") or 0)) < 20_000_000
        for item in active
    ):
        return True
    return bool(
        asset_id
        and any(
            str(item.get("asset_id") or "") == asset_id
            and abs(start_us - int(item.get("start_us") or 0)) < 20_000_000
            for item in active
        )
    )


def validate_visual_occupancy(overlays: Iterable[Mapping[str, Any]]) -> None:
    """Reject a frozen recipe that would render two semantic visuals at once."""

    enabled = sorted(
        (item for item in overlays if item.get("enabled") is not False),
        key=lambda item: int(item.get("start_us") or 0),
    )
    for previous, current in zip(enabled, enabled[1:]):
        if int(current.get("start_us") or 0) < int(previous.get("start_us") or 0) + int(
            previous.get("duration_us") or 0
        ):
            raise ValueError("同一时间只能显示一个语义视觉素材")


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
            1 if str(item.get("usage") or "explicit") == "enrichment" else 0,
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
        usage = str(
            decision.get("usage")
            or candidate.get("usage")
            or (
                "enrichment"
                if str(candidate.get("candidate_id") or "").startswith("ve_")
                else "explicit"
            )
        )
        assets = _assets_for_media_policy(
            catalog, concept_id, media_policy, usage=usage
        )
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
        if start_us < VISUAL_OPENING_PROTECTION_US:
            matched_end_us = int(
                candidate.get("matched_end_us", start_us + duration_us)
            )
            if matched_end_us <= VISUAL_OPENING_PROTECTION_US:
                continue
            start_us = VISUAL_OPENING_PROTECTION_US
            mapped_video_duration_us = candidate.get("video_duration_us")
            if isinstance(mapped_video_duration_us, int) and mapped_video_duration_us > 0:
                duration_us = min(duration_us, mapped_video_duration_us - start_us)
            if duration_us <= 0:
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
            "usage": usage,
            "reason_code": decision.get("reason_code"),
            "timing_source": str(
                candidate.get("timing_source") or "minimax_raw_cue_phrase_start"
            ),
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
        if usage == "enrichment":
            previous_end_us = max(
                (
                    int(item.get("start_us") or 0) + int(item.get("duration_us") or 0)
                    for item in selected
                    if int(item.get("start_us") or 0) < start_us
                ),
                default=0,
            )
            if start_us - previous_end_us < VISUAL_ENRICHMENT_MIN_GAP_US:
                continue
            if sum(
                str(item.get("usage") or "") == "enrichment"
                and abs(start_us - int(item.get("start_us") or 0)) < 60_000_000
                for item in selected
            ) >= VISUAL_ENRICHMENT_MAX_PER_MINUTE:
                continue
        if visual_overlay_conflicts(overlay, selected):
            continue
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
    current_catalog = None
    if resolved_root is not None:
        try:
            current_catalog = load_semantic_visual_catalog(resolved_root)
        except SemanticVisualCatalogError:
            current_catalog = None
    result: list[dict[str, Any]] = []
    for raw in recipe.get("overlays", []):
        if (
            not isinstance(raw, Mapping)
            or raw.get("enabled") is False
            or raw.get("requires_review") is True
        ):
            continue
        overlay = dict(raw)
        # Product defaults may evolve while a project is still under review.
        # Refresh only untouched automatic selections; manual/locked recipes remain frozen.
        if (
            current_catalog is not None
            and overlay.get("selection_mode") == "auto"
            and overlay.get("manual") is not True
            and overlay.get("locked") is not True
        ):
            current_asset = current_catalog.asset(str(overlay.get("asset_id") or ""))
            if current_asset is not None:
                defaults = current_asset["defaults"]
                resource = current_asset["resource"]
                overlay.update(
                    {
                        "asset_name": current_asset["name"],
                        "preview_url": current_asset["preview_url"],
                        "media_type": current_asset["media_type"],
                        "renderer": current_asset["renderer"],
                        "resource_path": (
                            resource["bundle"]
                            if current_asset["media_type"] == "image"
                            else resource["video"]
                        ),
                        "corner": defaults["corner"],
                        "scale": defaults["scale"],
                        "opacity": defaults["opacity"],
                    }
                )
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
    validate_visual_occupancy(result)
    return result
