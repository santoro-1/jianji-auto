from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
import hashlib
import json
from typing import Any, Mapping

from .auth_center import AuthCenterClient, AuthCenterError
from .project_store import ProjectStore
from .semantic_subtitles import SemanticSubtitleMappingError
from .semantic_visuals import (
    DEFAULT_LIBRARY_ID,
    RECIPE_SCHEMA,
    SemanticVisualCatalog,
    build_visual_recipe,
    map_visual_candidates_to_raw_cues,
    recall_semantic_visual_candidates,
)


VISUAL_ANALYSIS_BATCH_CONCURRENCY = 10
_DECISION_KEYS = {
    "candidate_id",
    "decision",
    "concept_id",
    "usage",
    "importance",
    "confidence",
    "reason_code",
}
_DECISIONS = {"SHOW", "REVIEW", "SKIP"}
_USAGES = {
    "literal",
    "ingredient",
    "meal_example",
    "idiom",
    "metaphor",
    "negated",
    "meta_mention",
    "passing_mention",
    "uncertain",
    "no_asset",
}
_REASON_CODES = {
    "LITERAL_CONCRETE_OBJECT",
    "SKIP_IDIOM",
    "SKIP_METAPHOR",
    "SKIP_NEGATED",
    "SKIP_META_MENTION",
    "SKIP_PASSING_MENTION",
    "SKIP_UNCERTAIN",
    "SKIP_NO_ASSET",
}


def _candidate_set_sha256(request: Mapping[str, Any]) -> str:
    return hashlib.sha256(
        json.dumps(
            request.get("candidates", []),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()


def _safe_error(error: object) -> dict[str, str]:
    if isinstance(error, AuthCenterError):
        code = f"DIGITAL_HUMAN_HTTP_{error.status_code}"
    elif isinstance(error, SemanticSubtitleMappingError):
        code = error.code
    else:
        code = type(error).__name__.upper()[:100] or "VISUAL_ANALYSIS_FAILED"
    summary = str(error).strip() or "语义视觉分析失败"
    return {"code": code, "summary": summary[:500]}


def _validated_remote_result(
    payload: Mapping[str, Any], *, candidate_request: Mapping[str, Any]
) -> dict[str, Any]:
    expected_ids = {
        str(item["candidate_id"]): item
        for item in candidate_request.get("candidates", [])
        if isinstance(item, Mapping)
    }
    if payload.get("analysis_status") != "SUCCESS":
        error = payload.get("error")
        if not isinstance(error, Mapping):
            error = {"code": "VISUAL_ANALYSIS_FAILED", "summary": "云端视觉分析失败"}
        return {
            **dict(payload),
            "analysis_status": "FAILED",
            "decisions": [],
            "error": {
                "code": str(error.get("code") or "VISUAL_ANALYSIS_FAILED")[:100],
                "summary": str(error.get("summary") or "云端视觉分析失败")[:500],
            },
        }
    if payload.get("schema_version") != "jyd.visual-analysis.v1":
        raise ValueError("数字人网站返回了未知的视觉分析契约")
    if payload.get("script_sha256") != candidate_request.get("script_sha256"):
        raise ValueError("数字人网站返回的视觉分析脚本摘要不匹配")
    if payload.get("catalog_version") != candidate_request.get("catalog_version"):
        raise ValueError("数字人网站返回的视觉素材目录版本不匹配")
    decisions = payload.get("decisions")
    if not isinstance(decisions, list):
        raise ValueError("数字人网站返回的视觉决策不是数组")
    seen: set[str] = set()
    validated: list[dict[str, Any]] = []
    for raw in decisions:
        if not isinstance(raw, Mapping) or set(raw) != _DECISION_KEYS:
            raise ValueError("数字人网站返回的视觉决策字段无效")
        candidate_id = str(raw.get("candidate_id") or "")
        if not candidate_id or candidate_id in seen or candidate_id not in expected_ids:
            raise ValueError("数字人网站返回了未知或重复的视觉候选")
        allowed = {
            str(item.get("concept_id") or "")
            for item in expected_ids[candidate_id].get("allowed_concepts", [])
            if isinstance(item, Mapping)
        }
        concept_id = str(raw.get("concept_id") or "")
        if concept_id not in allowed:
            raise ValueError("数字人网站返回了候选范围外的视觉概念")
        if raw.get("decision") not in _DECISIONS or raw.get("usage") not in _USAGES:
            raise ValueError("数字人网站返回了未知的视觉判定枚举")
        if raw.get("reason_code") not in _REASON_CODES:
            raise ValueError("数字人网站返回了未知的视觉原因码")
        importance = raw.get("importance")
        confidence = raw.get("confidence")
        if (
            isinstance(importance, bool)
            or not isinstance(importance, (int, float))
            or not 0 <= float(importance) <= 1
            or isinstance(confidence, bool)
            or not isinstance(confidence, (int, float))
            or not 0 <= float(confidence) <= 1
        ):
            raise ValueError("数字人网站返回的视觉评分无效")
        seen.add(candidate_id)
        validated.append(dict(raw))
    if seen != set(expected_ids):
        raise ValueError("数字人网站没有逐一返回全部视觉候选")
    return {**dict(payload), "decisions": validated, "error": None}


@dataclass(frozen=True)
class _Target:
    item_id: str
    script: str
    request: dict[str, Any]
    raw_cues: list[dict[str, Any]]
    video_duration_us: int | None
    previous: dict[str, Any]


class ProjectVisualAnalysisCoordinator:
    """Own local recall/timing and use the cloud only for context decisions."""

    def __init__(
        self,
        store: ProjectStore,
        client: AuthCenterClient,
        catalog: SemanticVisualCatalog,
        *,
        max_concurrency: int = VISUAL_ANALYSIS_BATCH_CONCURRENCY,
    ) -> None:
        self.store = store
        self.client = client
        self.catalog = catalog
        self.max_concurrency = max(
            1, min(int(max_concurrency), VISUAL_ANALYSIS_BATCH_CONCURRENCY)
        )

    def analyze(
        self,
        owner_user_id: str,
        project_id: str,
        token: str,
        *,
        item_ids: list[str] | None = None,
        force_refresh: bool = False,
    ) -> dict[str, Any]:
        project = self.store.get_project(owner_user_id, project_id)
        requested = {str(item_id).strip() for item_id in (item_ids or []) if str(item_id).strip()}
        known = {str(item["item_id"]) for item in project["items"]}
        if requested.difference(known):
            raise KeyError("项目脚本行不存在")
        targets: list[_Target] = []
        for item in project["items"]:
            item_id = str(item["item_id"])
            if requested and item_id not in requested:
                continue
            if not item.get("allowed_actions", {}).get("analyze_visuals", False):
                raise ValueError(f"任务 {item.get('row_key')} 正在生成或分析，请稍后重试")
            script = str(item["script_text"])
            candidate_request = recall_semantic_visual_candidates(script, self.catalog)
            previous = dict(item.get("visual_analysis") or {})
            if (
                not force_refresh
                and previous.get("script_sha256") == candidate_request["script_sha256"]
                and previous.get("catalog_version") == self.catalog.catalog_version
                and previous.get("analysis_status") in {"SUCCESS", "FAILED"}
            ):
                continue
            base_video = item.get("outputs", {}).get("base_video") or {}
            metadata = base_video.get("metadata") if isinstance(base_video, Mapping) else {}
            duration = metadata.get("duration_us") if isinstance(metadata, Mapping) else None
            targets.append(
                _Target(
                    item_id=item_id,
                    script=script,
                    request=candidate_request,
                    raw_cues=list(item.get("subtitles", {}).get("raw_cues") or []),
                    video_duration_us=(int(duration) if isinstance(duration, int) and duration > 0 else None),
                    previous=previous,
                )
            )
        for target in targets:
            self.store.mark_item_visual_analysis_pending(
                owner_user_id,
                project_id,
                target.item_id,
                expected_script_sha256=target.request["script_sha256"],
                candidate_request=target.request,
            )
        if not targets:
            return self.store.get_project(owner_user_id, project_id)

        local_only = [target for target in targets if not target.request["candidates"]]
        remote_targets = [target for target in targets if target.request["candidates"]]
        for target in local_only:
            self.store.complete_item_visual_analysis(
                owner_user_id,
                project_id,
                target.item_id,
                expected_script_sha256=target.request["script_sha256"],
                result={
                    "analysis_status": "SUCCESS",
                    "catalog_version": self.catalog.catalog_version,
                    "candidate_set_sha256": _candidate_set_sha256(target.request),
                    "decisions": [],
                    "cache_hit": True,
                    "cacheable": True,
                },
                recipe={
                    "schema": RECIPE_SCHEMA,
                    "library_id": self.catalog.library_id or DEFAULT_LIBRARY_ID,
                    "catalog_version": self.catalog.catalog_version,
                    "media_policy": "image_only",
                    "overlays": self._locked_overlays(target.previous),
                },
                mapping_status="SUCCESS",
            )

        workers = min(self.max_concurrency, len(remote_targets)) if remote_targets else 0
        if workers:
            with ThreadPoolExecutor(max_workers=workers) as pool:
                futures = {
                    pool.submit(
                        self.client.analyze_workbench_visuals,
                        token,
                        target.request,
                        force_refresh=force_refresh,
                    ): target
                    for target in remote_targets
                }
                for future in as_completed(futures):
                    target = futures[future]
                    try:
                        result = _validated_remote_result(
                            future.result(), candidate_request=target.request
                        )
                        result["candidate_set_sha256"] = _candidate_set_sha256(
                            target.request
                        )
                        if result["analysis_status"] != "SUCCESS":
                            self.store.fail_item_visual_analysis(
                                owner_user_id,
                                project_id,
                                target.item_id,
                                expected_script_sha256=target.request["script_sha256"],
                                expected_catalog_version=target.request["catalog_version"],
                                expected_candidate_set_sha256=_candidate_set_sha256(
                                    target.request
                                ),
                                error=dict(result["error"]),
                            )
                            continue
                        mapped = map_visual_candidates_to_raw_cues(
                            target.script,
                            target.request["candidates"],
                            target.raw_cues,
                            video_duration_us=target.video_duration_us,
                        )
                        recipe = build_visual_recipe(
                            catalog=self.catalog,
                            mapped_candidates=mapped,
                            decisions=result["decisions"],
                        )
                        locked = self._locked_overlays(target.previous)
                        locked_ids = {item.get("overlay_id") for item in locked}
                        recipe["overlays"] = locked + [
                            item
                            for item in recipe["overlays"]
                            if item.get("overlay_id") not in locked_ids
                            and not any(
                                int(item.get("start_us") or 0)
                                < int(saved.get("start_us") or 0)
                                + int(saved.get("duration_us") or 0)
                                and int(saved.get("start_us") or 0)
                                < int(item.get("start_us") or 0)
                                + int(item.get("duration_us") or 0)
                                for saved in locked
                                if saved.get("enabled") is not False
                            )
                        ]
                        self.store.complete_item_visual_analysis(
                            owner_user_id,
                            project_id,
                            target.item_id,
                            expected_script_sha256=target.request["script_sha256"],
                            result={**result, "mapped_candidates": mapped},
                            recipe=recipe,
                            mapping_status="SUCCESS",
                        )
                    except SemanticSubtitleMappingError as exc:
                        self.store.complete_item_visual_analysis(
                            owner_user_id,
                            project_id,
                            target.item_id,
                            expected_script_sha256=target.request["script_sha256"],
                            result={
                                **result,
                                "candidate_set_sha256": _candidate_set_sha256(
                                    target.request
                                ),
                                "mapped_candidates": [],
                            },
                            recipe={
                                "schema": RECIPE_SCHEMA,
                                "library_id": self.catalog.library_id or DEFAULT_LIBRARY_ID,
                                "catalog_version": self.catalog.catalog_version,
                                "media_policy": "image_only",
                                "overlays": self._locked_overlays(target.previous),
                            },
                            mapping_status="FAILED",
                            mapping_error=_safe_error(exc),
                        )
                    except Exception as exc:
                        self.store.fail_item_visual_analysis(
                            owner_user_id,
                            project_id,
                            target.item_id,
                            expected_script_sha256=target.request["script_sha256"],
                            expected_catalog_version=target.request["catalog_version"],
                            expected_candidate_set_sha256=_candidate_set_sha256(
                                target.request
                            ),
                            error=_safe_error(exc),
                        )
        return self.store.get_project(owner_user_id, project_id)

    def _locked_overlays(self, snapshot: Mapping[str, Any]) -> list[dict[str, Any]]:
        recipe = snapshot.get("recipe") if isinstance(snapshot.get("recipe"), Mapping) else {}
        locked: list[dict[str, Any]] = []
        for item in recipe.get("overlays", []):
            if (
                not isinstance(item, Mapping)
                or item.get("manual") is not True
                or item.get("locked") is not True
            ):
                continue
            overlay = dict(item)
            asset = self.catalog.asset(str(overlay.get("asset_id") or ""))
            for absolute_key in ("bundle_path", "image_path", "video_path"):
                overlay.pop(absolute_key, None)
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
