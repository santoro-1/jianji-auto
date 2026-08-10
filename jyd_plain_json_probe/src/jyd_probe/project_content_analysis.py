from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
import hashlib
from typing import Any, Mapping

from .auth_center import AuthCenterClient, AuthCenterError
from .project_music import ProjectMusicSelector, automatic_music_identity_counts
from .project_store import ProjectStore
from .semantic_subtitles import SemanticSubtitleMappingError
from .semantic_visuals import SemanticVisualCatalog
from .unified_visual_plan import (
    UnifiedVisualInput,
    build_local_visual_result,
    candidate_set_sha256,
    empty_visual_recipe,
    prepare_unified_visual_input,
    remap_saved_visual_plan,
    validate_remote_visual_plan,
)


CONTENT_ANALYSIS_BATCH_CONCURRENCY = 10
_UNCHANGED_SCRIPT_STATUSES = {"PENDING", "SUCCESS", "PARTIAL", "FAILED"}
_BRANCH_STATUSES = {"SUCCESS", "FAILED"}


def _script_sha256(script: str) -> str:
    return hashlib.sha256(script.encode("utf-8")).hexdigest()


def _safe_error(error: object) -> dict[str, str]:
    if isinstance(error, AuthCenterError):
        code = f"DIGITAL_HUMAN_HTTP_{error.status_code}"
    else:
        code = type(error).__name__.upper()[:100] or "CONTENT_ANALYSIS_FAILED"
    summary = str(error).strip() or "内容分析请求失败"
    return {"code": code, "summary": summary[:500]}


def _branch_error(payload: Mapping[str, Any], branch: str) -> dict[str, str] | None:
    errors = payload.get("errors")
    raw = errors.get(branch) if isinstance(errors, Mapping) else None
    if not isinstance(raw, Mapping):
        return None
    code = str(raw.get("code") or "").strip()[:100]
    summary = str(raw.get("summary") or "").strip()[:500]
    if not code and not summary:
        return None
    return {"code": code or "CONTENT_ANALYSIS_FAILED", "summary": summary}


def _validated_remote_result(
    payload: Mapping[str, Any], *, original_script: str
) -> dict[str, Any]:
    expected_hash = _script_sha256(original_script)
    if str(payload.get("script_sha256") or "") != expected_hash:
        raise ValueError("数字人网站返回的内容分析脚本摘要不匹配")
    if int(payload.get("script_length") or -1) != len(original_script):
        raise ValueError("数字人网站返回的内容分析脚本长度不匹配")

    music_status = str(payload.get("music_analysis_status") or "").upper()
    subtitle_status = str(payload.get("subtitle_analysis_status") or "").upper()
    if music_status not in _BRANCH_STATUSES or subtitle_status not in _BRANCH_STATUSES:
        raise ValueError("数字人网站返回的内容分析分支状态无效")

    music_intent = payload.get("music_intent")
    if music_status == "SUCCESS" and not isinstance(music_intent, Mapping):
        raise ValueError("音乐分析成功但缺少 music_intent")
    subtitle_units = payload.get("subtitle_units")
    if subtitle_status == "SUCCESS":
        if not isinstance(subtitle_units, list) or not subtitle_units:
            raise ValueError("字幕分析成功但缺少 subtitle_units")
        texts: list[str] = []
        for unit in subtitle_units:
            if not isinstance(unit, Mapping) or not isinstance(unit.get("text"), str):
                raise ValueError("subtitle_units 结构无效")
            texts.append(str(unit["text"]))
        if "".join(texts) != original_script:
            raise ValueError("subtitle_units 未逐字符重建原始脚本")

    return {
        "schema_version": str(payload.get("schema_version") or "")[:100],
        "prompt_version": str(payload.get("prompt_version") or "")[:100],
        "model": str(payload.get("model") or "")[:200],
        "music_analysis_status": music_status,
        "subtitle_analysis_status": subtitle_status,
        "music_intent": dict(music_intent) if isinstance(music_intent, Mapping) else None,
        "subtitle_units": subtitle_units if isinstance(subtitle_units, list) else None,
        "errors": {
            "music": _branch_error(payload, "music"),
            "subtitle": _branch_error(payload, "subtitle"),
        },
        "provider_request_id": (
            str(payload.get("provider_request_id"))[:200]
            if payload.get("provider_request_id")
            else None
        ),
        "provider_attempts": max(0, int(payload.get("provider_attempts") or 0)),
        "cache_hit": payload.get("cache_hit") is True,
        "cacheable": payload.get("cacheable") is True,
    }


@dataclass(frozen=True)
class _Target:
    item_id: str
    original_script: str
    script_sha256: str
    previous: dict[str, Any]
    visual: UnifiedVisualInput | None


class ProjectContentAnalysisCoordinator:
    """Analyze project scripts independently while preserving per-item snapshots."""

    def __init__(
        self,
        store: ProjectStore,
        client: AuthCenterClient,
        *,
        max_concurrency: int = CONTENT_ANALYSIS_BATCH_CONCURRENCY,
        music_selector: ProjectMusicSelector | None = None,
        visual_catalog: SemanticVisualCatalog | None = None,
    ) -> None:
        self.store = store
        self.client = client
        self.max_concurrency = max(
            1, min(int(max_concurrency), CONTENT_ANALYSIS_BATCH_CONCURRENCY)
        )
        self.music_selector = music_selector
        self.visual_catalog = visual_catalog

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
        requested = {
            str(item_id).strip()
            for item_id in (item_ids or [])
            if str(item_id).strip()
        }
        known = {str(item["item_id"]) for item in project["items"]}
        if requested.difference(known):
            raise KeyError("项目脚本行不存在")

        if self.visual_catalog is not None and not force_refresh:
            remapped = False
            for item in project["items"]:
                item_id = str(item["item_id"])
                visual_snapshot = item.get("visual_analysis") or {}
                if requested and item_id not in requested:
                    continue
                if (
                    visual_snapshot.get("analysis_status") == "SUCCESS"
                    and visual_snapshot.get("mapping_status") != "SUCCESS"
                ):
                    remapped = (
                        remap_saved_visual_plan(
                            self.store,
                            owner_user_id=owner_user_id,
                            project_id=project_id,
                            item=item,
                            catalog=self.visual_catalog,
                        )
                        or remapped
                    )
            if remapped:
                project = self.store.get_project(owner_user_id, project_id)

        targets: list[_Target] = []
        for item in project["items"]:
            item_id = str(item["item_id"])
            if requested and item_id not in requested:
                continue
            if not item.get("allowed_actions", {}).get("analyze_content", False):
                raise ValueError(f"任务 {item.get('row_key')} 正在生成或分析，请稍后重试")
            script = str(item["script_text"])
            script_hash = _script_sha256(script)
            previous = dict(item.get("content_analysis") or {})
            visual = (
                prepare_unified_visual_input(item, self.visual_catalog)
                if self.visual_catalog is not None
                else None
            )
            is_current = previous.get("script_sha256") == script_hash
            visual_is_current = True
            if visual is not None:
                previous_visual = visual.previous
                visual_is_current = (
                    previous_visual.get("script_sha256") == script_hash
                    and previous_visual.get("catalog_version")
                    == visual.candidate_request["catalog_version"]
                    and previous_visual.get("candidate_set_sha256")
                    == candidate_set_sha256(visual.candidate_request)
                    and previous_visual.get("analysis_status") in {"SUCCESS", "FAILED"}
                )
            if (
                not force_refresh
                and is_current
                and visual_is_current
                and str(previous.get("overall_status") or "")
                in _UNCHANGED_SCRIPT_STATUSES
            ):
                continue
            targets.append(_Target(item_id, script, script_hash, previous, visual))

        for target in targets:
            self.store.mark_item_content_analysis_pending(
                owner_user_id,
                project_id,
                target.item_id,
                expected_script_sha256=target.script_sha256,
            )
            if target.visual is not None:
                self.store.mark_item_visual_analysis_pending(
                    owner_user_id,
                    project_id,
                    target.item_id,
                    expected_script_sha256=target.script_sha256,
                    candidate_request=target.visual.candidate_request,
                )

        if not targets:
            return self.store.get_project(owner_user_id, project_id)

        workers = min(self.max_concurrency, len(targets))
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = {}
            for target in targets:
                kwargs: dict[str, Any] = {"force_refresh": force_refresh}
                if target.visual is not None and target.visual.visual_context["anchors"]:
                    kwargs["visual_context"] = target.visual.visual_context
                future = pool.submit(
                    self.client.analyze_workbench_content,
                    token,
                    target.original_script,
                    **kwargs,
                )
                futures[future] = target
            for future in as_completed(futures):
                target = futures[future]
                content_completed = False
                try:
                    remote = future.result()
                    validated = _validated_remote_result(
                        remote, original_script=target.original_script
                    )
                    content_completed = self.store.complete_item_content_analysis(
                        owner_user_id,
                        project_id,
                        target.item_id,
                        expected_script_sha256=target.script_sha256,
                        result=validated,
                        previous=target.previous,
                    )
                    if target.visual is not None and self.visual_catalog is not None:
                        visual = (
                            validate_remote_visual_plan(
                                remote,
                                candidate_request=target.visual.candidate_request,
                            )
                            if target.visual.candidate_request["candidates"]
                            else {
                                "analysis_status": "SUCCESS",
                                "visual_plan": [],
                                "error": None,
                            }
                        )
                        if visual["analysis_status"] != "SUCCESS":
                            self.store.fail_item_visual_analysis(
                                owner_user_id,
                                project_id,
                                target.item_id,
                                expected_script_sha256=target.script_sha256,
                                expected_catalog_version=target.visual.candidate_request[
                                    "catalog_version"
                                ],
                                expected_candidate_set_sha256=candidate_set_sha256(
                                    target.visual.candidate_request
                                ),
                                error=dict(visual["error"]),
                            )
                        else:
                            try:
                                latest_project = self.store.get_project(
                                    owner_user_id, project_id
                                )
                                latest_item = next(
                                    (
                                        item
                                        for item in latest_project.get("items", [])
                                        if item.get("item_id") == target.item_id
                                    ),
                                    None,
                                )
                                latest_visual = (
                                    prepare_unified_visual_input(
                                        latest_item, self.visual_catalog
                                    )
                                    if isinstance(latest_item, Mapping)
                                    else target.visual
                                )
                                visual_result, recipe = build_local_visual_result(
                                    script=target.original_script,
                                    visual_input=latest_visual,
                                    plan=visual["visual_plan"],
                                    catalog=self.visual_catalog,
                                    provider_payload=remote,
                                )
                                self.store.complete_item_visual_analysis(
                                    owner_user_id,
                                    project_id,
                                    target.item_id,
                                    expected_script_sha256=target.script_sha256,
                                    result=visual_result,
                                    recipe=recipe,
                                    mapping_status="SUCCESS",
                                )
                            except SemanticSubtitleMappingError as exc:
                                self.store.complete_item_visual_analysis(
                                    owner_user_id,
                                    project_id,
                                    target.item_id,
                                    expected_script_sha256=target.script_sha256,
                                    result={
                                        "analysis_status": "SUCCESS",
                                        "catalog_version": target.visual.candidate_request[
                                            "catalog_version"
                                        ],
                                        "candidate_set_sha256": candidate_set_sha256(
                                            target.visual.candidate_request
                                        ),
                                        "visual_plan": visual["visual_plan"],
                                        "decisions": [],
                                        "mapped_candidates": [],
                                        "provider_request_id": remote.get(
                                            "provider_request_id"
                                        ),
                                        "provider_attempts": int(
                                            remote.get("provider_attempts") or 0
                                        ),
                                        "cache_hit": remote.get("cache_hit") is True,
                                        "cacheable": remote.get("cacheable") is True,
                                    },
                                    recipe=empty_visual_recipe(
                                        target.visual, self.visual_catalog
                                    ),
                                    mapping_status="FAILED",
                                    mapping_error=_safe_error(exc),
                                )
                                current_project = self.store.get_project(
                                    owner_user_id, project_id
                                )
                                current_item = next(
                                    (
                                        item
                                        for item in current_project.get("items", [])
                                        if item.get("item_id") == target.item_id
                                    ),
                                    None,
                                )
                                if isinstance(current_item, Mapping):
                                    remap_saved_visual_plan(
                                        self.store,
                                        owner_user_id=owner_user_id,
                                        project_id=project_id,
                                        item=current_item,
                                        catalog=self.visual_catalog,
                                    )
                except Exception as exc:
                    if not content_completed:
                        self.store.fail_item_content_analysis(
                            owner_user_id,
                            project_id,
                            target.item_id,
                            expected_script_sha256=target.script_sha256,
                            error=_safe_error(exc),
                            previous=target.previous,
                        )
                    if target.visual is not None:
                        self.store.fail_item_visual_analysis(
                            owner_user_id,
                            project_id,
                            target.item_id,
                            expected_script_sha256=target.script_sha256,
                            expected_catalog_version=target.visual.candidate_request[
                                "catalog_version"
                            ],
                            expected_candidate_set_sha256=candidate_set_sha256(
                                target.visual.candidate_request
                            ),
                            error=_safe_error(exc),
                        )
        project = self.store.get_project(owner_user_id, project_id)
        if self.music_selector is not None:
            targets_by_id = {target.item_id: target for target in targets}
            recent_identity_counts = automatic_music_identity_counts(
                project, excluded_item_ids=set(targets_by_id)
            )
            for item in project["items"]:
                item_id = str(item["item_id"])
                target = targets_by_id.get(item_id)
                if target is None:
                    continue
                analysis = item.get("content_analysis") or {}
                if analysis.get("music_analysis_status") != "SUCCESS":
                    continue
                postprocess = (item.get("settings") or {}).get("postprocess") or {}
                if postprocess.get("bgm_selection_mode") == "manual":
                    continue
                previous_selection = postprocess.get("music_selection") or {}
                same_script_retry = (
                    target.previous.get("script_sha256")
                    == analysis.get("script_sha256")
                )
                has_saved_auto_music = bool(
                    str(postprocess.get("bgm_identity") or "").strip()
                    and previous_selection.get("status") in {"SUCCESS", "STALE"}
                )
                if same_script_retry and has_saved_auto_music:
                    # Retrying subtitle analysis for unchanged copy must not make
                    # the already-approved automatic BGM jump to a different track.
                    saved_identity = str(postprocess.get("bgm_identity") or "").strip()
                    if saved_identity:
                        recent_identity_counts[saved_identity] = (
                            recent_identity_counts.get(saved_identity, 0) + 1
                        )
                    continue
                identity, selection = self.music_selector.resolve_for_analysis(
                    project,
                    item,
                    recent_identity_counts=recent_identity_counts,
                )
                self.store.save_item_auto_music_selection(
                    owner_user_id,
                    project_id,
                    item_id,
                    expected_script_sha256=str(analysis.get("script_sha256") or ""),
                    bgm_identity=identity,
                    music_selection=selection,
                )
                if identity:
                    recent_identity_counts[identity] = (
                        recent_identity_counts.get(identity, 0) + 1
                    )
            project = self.store.get_project(owner_user_id, project_id)
        return project
