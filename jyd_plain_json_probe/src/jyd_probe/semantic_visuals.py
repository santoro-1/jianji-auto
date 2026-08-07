"""Local semantic-visual catalog, deterministic recall and timing policy."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping

from .semantic_subtitles import SemanticSubtitleMappingError


CATALOG_SCHEMA = "jyd.semantic-visual-catalog.v1"
CANDIDATE_SCHEMA = "jyd.semantic-visual-candidates.v1"
RECIPE_SCHEMA = "jyd.semantic-visual-recipe.v1"


class SemanticVisualCatalogError(ValueError):
    pass


@dataclass(frozen=True)
class SemanticVisualCatalog:
    root: Path
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
        return {
            "schema": CATALOG_SCHEMA,
            "catalog_version": self.catalog_version,
            "concepts": [dict(item) for item in self.concepts],
            "assets": [
                {
                    key: value
                    for key, value in item.items()
                    if key not in {"bundle_path", "image_path"}
                }
                for item in self.assets
            ],
        }


def _safe_child(root: Path, raw: str, *, kind: str) -> Path:
    candidate = (root / raw).resolve()
    try:
        candidate.relative_to(root)
    except ValueError as exc:
        raise SemanticVisualCatalogError(f"{kind} path escapes catalog root") from exc
    if not candidate.is_file() and not candidate.is_dir():
        raise SemanticVisualCatalogError(f"{kind} path is missing")
    return candidate


def _update_file_hash(digest: Any, path: Path) -> None:
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)


def load_semantic_visual_catalog(root: str | Path) -> SemanticVisualCatalog:
    catalog_root = Path(root).expanduser().resolve()
    manifest_path = catalog_root / "catalog.json"
    try:
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise SemanticVisualCatalogError("semantic visual catalog is unreadable") from exc
    if not isinstance(payload, dict) or payload.get("schema") != CATALOG_SCHEMA:
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
        catalog_version=catalog_version,
        concepts=tuple(normalized_concepts),
        assets=tuple(normalized_assets),
    )


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


def build_visual_recipe(
    *,
    catalog: SemanticVisualCatalog,
    mapped_candidates: Iterable[Mapping[str, Any]],
    decisions: Iterable[Mapping[str, Any]],
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
        assets = [item for item in catalog.assets if item["concept_id"] == concept_id]
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
        overlay = {
            "overlay_id": "vo_" + str(candidate["candidate_id"]).removeprefix("vc_"),
            "candidate_id": candidate["candidate_id"],
            "concept_id": concept_id,
            "asset_id": asset["asset_id"],
            "asset_name": asset["name"],
            "preview_url": asset["preview_url"],
            "bundle_path": asset["bundle_path"],
            "enabled": True,
            "selection_mode": "auto",
            "manual": False,
            "locked": False,
            "corner": asset["default_corner"],
            "scale": asset["default_scale"],
            "opacity": asset["default_opacity"],
            "start_us": start_us,
            "duration_us": duration_us,
            "confidence": confidence,
            "importance": float(decision.get("importance", 0.0) or 0.0),
            "reason_code": decision.get("reason_code"),
        }
        selected.append(overlay)
    selected.sort(key=lambda item: (item["start_us"], item["overlay_id"]))
    return {
        "schema": RECIPE_SCHEMA,
        "catalog_version": catalog.catalog_version,
        "overlays": selected,
    }


def frozen_visual_overlays(item: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Return the enabled recipe verbatim for both browser and 4B consumers."""

    analysis = item.get("visual_analysis")
    recipe = analysis.get("recipe") if isinstance(analysis, Mapping) else None
    if not isinstance(recipe, Mapping) or recipe.get("schema") != RECIPE_SCHEMA:
        return []
    result: list[dict[str, Any]] = []
    for raw in recipe.get("overlays", []):
        if (
            not isinstance(raw, Mapping)
            or raw.get("enabled") is False
            or raw.get("requires_review") is True
        ):
            continue
        result.append(dict(raw))
    return result
