from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
import hashlib
from typing import Any, Mapping

from .auth_center import AuthCenterClient, AuthCenterError
from .project_music import ProjectMusicSelector
from .project_store import ProjectStore


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


class ProjectContentAnalysisCoordinator:
    """Analyze project scripts independently while preserving per-item snapshots."""

    def __init__(
        self,
        store: ProjectStore,
        client: AuthCenterClient,
        *,
        max_concurrency: int = CONTENT_ANALYSIS_BATCH_CONCURRENCY,
        music_selector: ProjectMusicSelector | None = None,
    ) -> None:
        self.store = store
        self.client = client
        self.max_concurrency = max(
            1, min(int(max_concurrency), CONTENT_ANALYSIS_BATCH_CONCURRENCY)
        )
        self.music_selector = music_selector

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
            is_current = previous.get("script_sha256") == script_hash
            if (
                not force_refresh
                and is_current
                and str(previous.get("overall_status") or "")
                in _UNCHANGED_SCRIPT_STATUSES
            ):
                continue
            targets.append(_Target(item_id, script, script_hash, previous))

        for target in targets:
            self.store.mark_item_content_analysis_pending(
                owner_user_id,
                project_id,
                target.item_id,
                expected_script_sha256=target.script_sha256,
            )

        if not targets:
            return self.store.get_project(owner_user_id, project_id)

        workers = min(self.max_concurrency, len(targets))
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = {
                pool.submit(
                    self.client.analyze_workbench_content,
                    token,
                    target.original_script,
                    force_refresh=force_refresh,
                ): target
                for target in targets
            }
            for future in as_completed(futures):
                target = futures[future]
                try:
                    remote = future.result()
                    validated = _validated_remote_result(
                        remote, original_script=target.original_script
                    )
                    self.store.complete_item_content_analysis(
                        owner_user_id,
                        project_id,
                        target.item_id,
                        expected_script_sha256=target.script_sha256,
                        result=validated,
                        previous=target.previous,
                    )
                except Exception as exc:
                    self.store.fail_item_content_analysis(
                        owner_user_id,
                        project_id,
                        target.item_id,
                        expected_script_sha256=target.script_sha256,
                        error=_safe_error(exc),
                        previous=target.previous,
                    )
        project = self.store.get_project(owner_user_id, project_id)
        if self.music_selector is not None:
            targets_by_id = {target.item_id: target for target in targets}
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
                    continue
                identity, selection = self.music_selector.resolve_for_analysis(
                    project, item
                )
                self.store.save_item_auto_music_selection(
                    owner_user_id,
                    project_id,
                    item_id,
                    expected_script_sha256=str(analysis.get("script_sha256") or ""),
                    bgm_identity=identity,
                    music_selection=selection,
                )
            project = self.store.get_project(owner_user_id, project_id)
        return project
