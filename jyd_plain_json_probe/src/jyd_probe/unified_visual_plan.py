"""Adapt the compact cloud visual plan to the existing local visual pipeline."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from typing import Any, Mapping

from .caption_alignment import alignment_matches
from .project_video_source import project_segment_boundaries
from .semantic_visuals import (
    DEFAULT_LIBRARY_ID,
    RECIPE_SCHEMA,
    SemanticVisualCatalog,
    build_visual_recipe,
    map_visual_candidates_to_raw_cues,
    recall_semantic_visual_candidates,
    visual_candidate_context,
)


def candidate_set_sha256(candidate_request: Mapping[str, Any]) -> str:
    encoded = json.dumps(
        candidate_request.get("candidates", []),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def build_content_visual_context(candidate_request: Mapping[str, Any]) -> dict[str, Any]:
    """Convert local recall output to the small, path-free cloud input."""

    concepts: dict[str, dict[str, str]] = {}
    anchors: list[dict[str, Any]] = []
    original_script = str(candidate_request.get("original_script") or "")
    for candidate in candidate_request.get("candidates", []):
        if not isinstance(candidate, Mapping):
            continue
        allowed_ids: list[str] = []
        for concept in candidate.get("allowed_concepts", []):
            if not isinstance(concept, Mapping):
                continue
            concept_id = str(concept.get("concept_id") or "").strip()
            description = str(concept.get("description") or "").strip()
            if not concept_id or not description:
                continue
            concepts.setdefault(
                concept_id,
                {"concept_id": concept_id, "description": description},
            )
            allowed_ids.append(concept_id)
        if not allowed_ids:
            continue
        char_start = int(candidate["char_start"])
        anchors.append(
            {
                "anchor_id": "START" if char_start == 0 else f"B{char_start}",
                "char_start": char_start,
                "char_end": int(candidate["char_end"]),
                "text": str(candidate["text"]),
                "context": visual_candidate_context(
                    original_script,
                    start=char_start,
                    end=int(candidate["char_end"]),
                ),
                "usage": str(
                    candidate.get("usage")
                    or (
                        "enrichment"
                        if str(candidate.get("candidate_id") or "").startswith("ve_")
                        else "explicit"
                    )
                ),
                "allowed_concepts": allowed_ids,
            }
        )
    return {
        "catalog_version": str(candidate_request.get("catalog_version") or "none"),
        "concepts": sorted(concepts.values(), key=lambda item: item["concept_id"]),
        "anchors": anchors,
    }


@dataclass(frozen=True)
class UnifiedVisualInput:
    candidate_request: dict[str, Any]
    visual_context: dict[str, Any]
    raw_cues: list[dict[str, Any]]
    video_duration_us: int | None
    previous: dict[str, Any]
    asr_alignment: dict[str, Any] | None = None
    segment_boundaries: list[dict[str, Any]] | None = None


def prepare_unified_visual_input(
    item: Mapping[str, Any],
    catalog: SemanticVisualCatalog,
) -> UnifiedVisualInput:
    script = str(item.get("script_text") or "")
    candidate_request = recall_semantic_visual_candidates(script, catalog)
    base_video = (item.get("outputs") or {}).get("base_video") or {}
    audio = (item.get("outputs") or {}).get("audio") or {}
    subtitles = item.get("subtitles") or {}
    metadata = base_video.get("metadata") if isinstance(base_video, Mapping) else {}
    duration = metadata.get("duration_us") if isinstance(metadata, Mapping) else None
    alignment = subtitles.get("asr_alignment") if isinstance(subtitles, Mapping) else None
    if not (
        isinstance(audio, Mapping)
        and alignment_matches(
            alignment,
            script=script,
            audio_asset_id=str(audio.get("asset_id") or ""),
            audio_version=audio.get("version"),
        )
    ):
        alignment = None
    return UnifiedVisualInput(
        candidate_request=candidate_request,
        visual_context=build_content_visual_context(candidate_request),
        raw_cues=list(subtitles.get("raw_cues") or []),
        video_duration_us=(
            int(duration) if isinstance(duration, int) and duration > 0 else None
        ),
        previous=dict(item.get("visual_analysis") or {}),
        asr_alignment=(dict(alignment) if isinstance(alignment, Mapping) else None),
        segment_boundaries=project_segment_boundaries(dict(item)),
    )


def validate_remote_visual_plan(
    payload: Mapping[str, Any],
    *,
    candidate_request: Mapping[str, Any],
) -> dict[str, Any]:
    """Validate selected-only anchors without accepting cloud timing or asset data."""

    status = str(payload.get("visual_analysis_status") or "FAILED").upper()
    if status != "SUCCESS":
        errors = payload.get("errors")
        error = errors.get("visual") if isinstance(errors, Mapping) else None
        return {
            "analysis_status": "FAILED",
            "visual_plan": [],
            "error": (
                {
                    "code": str(error.get("code") or "VISUAL_ANALYSIS_FAILED")[:100],
                    "summary": str(error.get("summary") or "云端视觉分析失败")[:500],
                }
                if isinstance(error, Mapping)
                else {
                    "code": "VISUAL_ANALYSIS_FAILED",
                    "summary": "云端视觉分析失败",
                }
            ),
        }
    expected_catalog = str(candidate_request.get("catalog_version") or "")
    if str(payload.get("visual_catalog_version") or "") != expected_catalog:
        raise ValueError("数字人网站返回的视觉素材目录版本不匹配")

    candidates_by_anchor: dict[str, Mapping[str, Any]] = {}
    for candidate in candidate_request.get("candidates", []):
        if not isinstance(candidate, Mapping):
            continue
        char_start = int(candidate["char_start"])
        anchor_id = "START" if char_start == 0 else f"B{char_start}"
        candidates_by_anchor[anchor_id] = candidate

    raw_plan = payload.get("visual_plan")
    if not isinstance(raw_plan, list):
        raise ValueError("数字人网站返回的视觉计划不是数组")
    seen: set[str] = set()
    plan: list[dict[str, Any]] = []
    for raw in raw_plan:
        if not isinstance(raw, Mapping) or set(raw) != {
            "anchor_id",
            "concept_id",
            "priority",
        }:
            raise ValueError("数字人网站返回的视觉计划字段无效")
        anchor_id = str(raw.get("anchor_id") or "")
        concept_id = str(raw.get("concept_id") or "")
        priority = raw.get("priority")
        candidate = candidates_by_anchor.get(anchor_id)
        if candidate is None or anchor_id in seen:
            raise ValueError("数字人网站返回了未知或重复的视觉锚点")
        allowed = {
            str(item.get("concept_id") or "")
            for item in candidate.get("allowed_concepts", [])
            if isinstance(item, Mapping)
        }
        if concept_id not in allowed:
            raise ValueError("数字人网站返回了锚点范围外的视觉概念")
        if isinstance(priority, bool) or not isinstance(priority, int) or priority not in {0, 1, 2}:
            raise ValueError("数字人网站返回了无效的视觉优先级")
        seen.add(anchor_id)
        usage = str(
            candidate.get("usage")
            or (
                "enrichment"
                if str(candidate.get("candidate_id") or "").startswith("ve_")
                else "explicit"
            )
        )
        # Enrichment is optional by definition.  Only a key visual (priority 2)
        # may enter an automatic recipe; weaker selections stay review-only.
        normalized_priority = 0 if usage == "enrichment" and priority < 2 else priority
        plan.append(
            {
                "anchor_id": anchor_id,
                "concept_id": concept_id,
                "priority": normalized_priority,
            }
        )
    return {"analysis_status": "SUCCESS", "visual_plan": plan, "error": None}


def _compatibility_decisions(
    plan: list[dict[str, Any]],
    candidate_request: Mapping[str, Any],
) -> list[dict[str, Any]]:
    candidates = {}
    for candidate in candidate_request.get("candidates", []):
        if not isinstance(candidate, Mapping):
            continue
        char_start = int(candidate["char_start"])
        candidates["START" if char_start == 0 else f"B{char_start}"] = candidate
    decisions: list[dict[str, Any]] = []
    for item in plan:
        candidate = candidates[item["anchor_id"]]
        priority = int(item["priority"])
        decisions.append(
            {
                "candidate_id": str(candidate["candidate_id"]),
                "decision": "REVIEW" if priority == 0 else "SHOW",
                "concept_id": item["concept_id"],
                "priority": priority,
                "usage": (
                    "enrichment"
                    if str(candidate.get("candidate_id") or "").startswith("ve_")
                    else "explicit"
                ),
                "importance": {0: 0.4, 1: 0.75, 2: 1.0}[priority],
                "confidence": 1.0,
                "reason_code": None,
            }
        )
    return decisions


def _locked_overlays(
    snapshot: Mapping[str, Any],
    catalog: SemanticVisualCatalog,
) -> list[dict[str, Any]]:
    recipe = snapshot.get("recipe") if isinstance(snapshot.get("recipe"), Mapping) else {}
    locked: list[dict[str, Any]] = []
    for raw in recipe.get("overlays", []):
        if not isinstance(raw, Mapping) or raw.get("manual") is not True or raw.get("locked") is not True:
            continue
        overlay = dict(raw)
        asset = catalog.asset(str(overlay.get("asset_id") or ""))
        for key in ("bundle_path", "image_path", "video_path"):
            overlay.pop(key, None)
        if asset is None:
            overlay["requires_review"] = True
        else:
            media_type = asset["media_type"]
            overlay.update(
                {
                    "media_type": media_type,
                    "renderer": asset["renderer"],
                    "resource_path": (
                        asset["resource"]["bundle"]
                        if media_type == "image"
                        else asset["resource"]["video"]
                    ),
                }
            )
        locked.append(overlay)
    return locked


def build_local_visual_result(
    *,
    script: str,
    visual_input: UnifiedVisualInput,
    plan: list[dict[str, Any]],
    catalog: SemanticVisualCatalog,
    provider_payload: Mapping[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Reuse local raw-cue mapping, asset selection and frozen recipe generation."""

    candidate_request = visual_input.candidate_request
    decisions = _compatibility_decisions(plan, candidate_request)
    selected_ids = {str(item["candidate_id"]) for item in decisions}
    selected_candidates = [
        dict(item)
        for item in candidate_request.get("candidates", [])
        if isinstance(item, Mapping) and str(item.get("candidate_id")) in selected_ids
    ]
    mapped = (
        map_visual_candidates_to_raw_cues(
            script,
            selected_candidates,
            visual_input.raw_cues,
            video_duration_us=visual_input.video_duration_us,
            asr_alignment=visual_input.asr_alignment,
        )
        if selected_candidates
        else []
    )
    locked = _locked_overlays(visual_input.previous, catalog)
    recipe = build_visual_recipe(
        catalog=catalog,
        mapped_candidates=mapped,
        decisions=decisions,
        media_policy="mixed",
        locked_overlays=locked,
        segment_boundaries=visual_input.segment_boundaries or [],
        final_video_duration_us=visual_input.video_duration_us,
    )
    result = {
        "analysis_status": "SUCCESS",
        "catalog_version": candidate_request["catalog_version"],
        "candidate_set_sha256": candidate_set_sha256(candidate_request),
        "visual_plan": plan,
        "decisions": decisions,
        "mapped_candidates": mapped,
        "provider_request_id": provider_payload.get("provider_request_id"),
        "provider_attempts": int(provider_payload.get("provider_attempts") or 0),
        "cache_hit": provider_payload.get("cache_hit") is True,
        "cacheable": provider_payload.get("cacheable") is True,
        "error": None,
    }
    return result, recipe


def empty_visual_recipe(
    visual_input: UnifiedVisualInput,
    catalog: SemanticVisualCatalog,
) -> dict[str, Any]:
    overlays = _locked_overlays(visual_input.previous, catalog)
    return {
        "schema": RECIPE_SCHEMA,
        "library_id": catalog.library_id or DEFAULT_LIBRARY_ID,
        "catalog_version": catalog.catalog_version,
        "media_policy": "mixed",
        "timing_policy_version": "sentence-v1",
        "used_asset_ids": sorted(
            {
                str(item.get("asset_id") or "")
                for item in overlays
                if item.get("enabled") is not False and str(item.get("asset_id") or "")
            }
        ),
        "overlays": overlays,
    }


def remap_saved_visual_plan(
    store: Any,
    *,
    owner_user_id: str,
    project_id: str,
    item: Mapping[str, Any],
    catalog: SemanticVisualCatalog,
) -> bool:
    """Rebind a saved semantic decision after MiniMax raw cues change, without Ark."""

    previous = item.get("visual_analysis")
    if not isinstance(previous, Mapping) or previous.get("analysis_status") != "SUCCESS":
        return False
    plan = previous.get("visual_plan")
    stored_request = previous.get("candidate_request")
    if not isinstance(plan, list) or not isinstance(stored_request, Mapping):
        return False
    visual_input = prepare_unified_visual_input(item, catalog)
    if (
        stored_request.get("catalog_version")
        != visual_input.candidate_request.get("catalog_version")
        or candidate_set_sha256(stored_request)
        != candidate_set_sha256(visual_input.candidate_request)
    ):
        return False
    script = str(item.get("script_text") or "")
    script_sha256 = hashlib.sha256(script.encode("utf-8")).hexdigest()
    if not store.mark_item_visual_analysis_pending(
        owner_user_id,
        project_id,
        str(item["item_id"]),
        expected_script_sha256=script_sha256,
        candidate_request=visual_input.candidate_request,
    ):
        return False
    try:
        result, recipe = build_local_visual_result(
            script=script,
            visual_input=visual_input,
            plan=[dict(value) for value in plan if isinstance(value, Mapping)],
            catalog=catalog,
            provider_payload=previous,
        )
        return store.complete_item_visual_analysis(
            owner_user_id,
            project_id,
            str(item["item_id"]),
            expected_script_sha256=script_sha256,
            result=result,
            recipe=recipe,
            mapping_status="SUCCESS",
        )
    except Exception as exc:
        code = getattr(exc, "code", type(exc).__name__.upper())
        summary = getattr(exc, "summary", str(exc) or "语义视觉时间映射失败")
        return store.complete_item_visual_analysis(
            owner_user_id,
            project_id,
            str(item["item_id"]),
            expected_script_sha256=script_sha256,
            result={
                "analysis_status": "SUCCESS",
                "catalog_version": visual_input.candidate_request["catalog_version"],
                "candidate_set_sha256": candidate_set_sha256(
                    visual_input.candidate_request
                ),
                "visual_plan": list(plan),
                "decisions": [],
                "mapped_candidates": [],
                "provider_request_id": previous.get("provider_request_id"),
                "provider_attempts": int(previous.get("provider_attempts") or 0),
                "cache_hit": previous.get("cache_hit") is True,
                "cacheable": previous.get("cacheable") is True,
            },
            recipe=empty_visual_recipe(visual_input, catalog),
            mapping_status="FAILED",
            mapping_error={
                "code": str(code)[:100],
                "summary": str(summary)[:500],
            },
        )
