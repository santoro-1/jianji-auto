from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from .auth_center import AuthCenterClient
from .project_store import ProjectStore


REMOTE_COMPOSITION_ACTIVE = {
    "COMPOSITION_QUEUED",
    "DIGITAL_HUMAN_RUNNING",
    "VIDEO_ENHANCING",
    "VIDEO_MERGING",
}


def _current_audio_item_links(
    links: list[dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    newest_by_item: dict[str, dict[str, Any]] = {}
    for link in links:
        if (
            link.get("system") == "runninghub"
            and link.get("relation") == "digital_human_audio_item"
            and link.get("item_id")
        ):
            newest_by_item[str(link["item_id"])] = link
    return newest_by_item


def _composition_operations(project: dict[str, Any]) -> dict[str, dict[str, Any]]:
    latest: dict[str, dict[str, Any]] = {}
    for operation in project.get("operations", []):
        if (
            operation.get("operation_type") == "COMPOSITION_GENERATE"
            and operation.get("item_id")
        ):
            latest[str(operation["item_id"])] = operation
    return latest


def _normalized_execution_account_ids(
    value: list[int] | None,
) -> list[int] | None:
    if value is None:
        return None
    if (
        not value
        or any(type(account_id) is not int or account_id <= 0 for account_id in value)
        or len(set(value)) != len(value)
    ):
        raise ValueError("RunningHub 执行账号 ID 必须是非空且不重复的正整数列表")
    return sorted(value)


class ProjectCompositionCoordinator:
    """Bridge workbench projects to the existing digital-human workers.

    Module 4A deliberately stops at a normalized base video. Provider segment
    outputs are retained as immutable source assets; captions, BGM, variants,
    Jianying drafts, and publishing are not part of this coordinator.
    """

    def __init__(
        self,
        store: ProjectStore,
        client: AuthCenterClient,
        *,
        storage_root: Path,
        max_video_bytes: int,
    ) -> None:
        self.store = store
        self.client = client
        self.storage_root = Path(storage_root).resolve()
        self.max_video_bytes = int(max_video_bytes)

    def start(
        self,
        owner_user_id: str,
        project_id: str,
        token: str,
        *,
        idempotency_key: str,
        resolution: str = "1024",
        runninghub_execution_account_ids: list[int] | None = None,
        item_ids: list[str] | None = None,
    ) -> dict[str, Any]:
        project = self.store.get_project(owner_user_id, project_id)
        clean_key = str(idempotency_key or "").strip()
        if not clean_key:
            raise ValueError("画面生成请求缺少幂等键")
        clean_resolution = str(resolution or "1024").strip()
        try:
            if int(clean_resolution) <= 0:
                raise ValueError
        except (TypeError, ValueError) as exc:
            raise ValueError("数字人最长边分辨率必须是正整数") from exc

        if item_ids is not None:
            requested_ids = [str(value or "").strip() for value in item_ids]
            if (
                not requested_ids
                or any(not value for value in requested_ids)
                or len(set(requested_ids)) != len(requested_ids)
            ):
                raise ValueError("单条画面生成必须指定非空且不重复的脚本行 ID")
            by_id = {str(item["item_id"]): item for item in project["items"]}
            missing = [value for value in requested_ids if value not in by_id]
            if missing:
                raise KeyError("项目脚本行不存在")
            target_items = [by_id[value] for value in requested_ids]
            blocked = [
                item for item in target_items
                if item.get("outputs", {}).get("base_video") is None
                and not item.get("allowed_actions", {}).get("start_composition")
            ]
            if blocked:
                raise ValueError(f"任务 {blocked[0]['row_key']} 尚未准备好生成画面")
            # Explicit row requests reuse a current base video.  Postprocess
            # can still run independently if only subtitle/BGM changed.
            target_items = [
                item for item in target_items
                if item.get("outputs", {}).get("base_video") is None
            ]
            if not target_items:
                return project
        else:
            if not project["allowed_actions"]["start_composition"]:
                raise ValueError("当前项目状态不能开始画面生成")
            target_items = project["items"]

        selected_account_ids = _normalized_execution_account_ids(
            runninghub_execution_account_ids
        )
        for existing in project.get("operations", []):
            if (
                existing.get("operation_type") == "COMPOSITION_GENERATE"
                and existing.get("idempotency_key") == clean_key
                and (
                    existing.get("payload", {}).get(
                        "runninghub_execution_account_ids"
                    ) != selected_account_ids
                    or str(existing.get("payload", {}).get("resolution") or "1024")
                    != clean_resolution
                )
            ):
                raise ValueError(
                    "该画面生成操作的执行账号或分辨率快照已锁定，不能修改"
                )
        links_by_item = _current_audio_item_links(project["links"])

        for item in target_items:
            backfill_seedvr2 = (
                item.get("settings", {}).get("composition_invalidated_reason")
                == "DIGITAL_HUMAN_RESOLUTION_CHANGED"
            )
            link = links_by_item.get(str(item["item_id"]))
            if link is None:
                raise ValueError(f"任务 {item['row_key']} 缺少数字人声音任务关联")
            batch_id = str(link.get("metadata", {}).get("batch_id") or "")
            correlation_id = str(
                link.get("metadata", {}).get("correlation_id") or ""
            ).strip()
            remote_item_id = str(link.get("external_id") or "")
            if not batch_id or not remote_item_id:
                raise ValueError(f"任务 {item['row_key']} 的数字人任务关联不完整")
            image: dict[str, Any] = {}
            image_path: Path | None = None
            image_sha256 = ""
            if not backfill_seedvr2:
                raw_image = item.get("inputs", {}).get("image")
                if (
                    not isinstance(raw_image, dict)
                    or not raw_image.get("managed_path")
                ):
                    raise ValueError(f"任务 {item['row_key']} 尚未分配图片")
                image = raw_image
                image_path = Path(str(image["managed_path"])).resolve()
                if not image_path.is_file():
                    raise ValueError(f"任务 {item['row_key']} 的图片文件不存在")
                image_sha256 = str(
                    image.get("metadata", {}).get("sha256") or ""
                ).strip().lower()
                if not image_sha256:
                    image_sha256 = hashlib.sha256(
                        image_path.read_bytes()
                    ).hexdigest()
            operation_payload = {
                "batch_id": batch_id,
                "remote_item_id": remote_item_id,
                "scope": (
                    "seedvr2_backfill_only"
                    if backfill_seedvr2
                    else "base_video_only"
                ),
                "resolution": clean_resolution,
                "runninghub_execution_account_ids": selected_account_ids,
            }
            if not backfill_seedvr2:
                operation_payload.update(
                    {
                        "input_image_asset_id": str(image.get("asset_id") or ""),
                        "input_image_sha256": image_sha256,
                    }
                )
            operation = self.store.create_operation(
                owner_user_id=owner_user_id,
                project_id=project_id,
                item_id=item["item_id"],
                operation_type="COMPOSITION_GENERATE",
                idempotency_key=clean_key,
                payload=operation_payload,
                correlation_id=correlation_id or None,
            )
            if operation.get("payload", {}).get(
                "runninghub_execution_account_ids"
            ) != selected_account_ids:
                raise ValueError(
                    "该画面生成操作的 RunningHub 执行账号快照已锁定，不能修改"
                )
            if (
                not backfill_seedvr2
                and operation.get("payload", {}).get("input_image_sha256")
                != image_sha256
            ):
                raise ValueError("同一画面生成幂等键不能用于不同的项目图片")
            if str(operation.get("payload", {}).get("resolution") or "1024") != clean_resolution:
                raise ValueError("同一画面生成幂等键不能用于不同的分辨率")
            try:
                staged_image: dict[str, Any] = {}
                if backfill_seedvr2:
                    remote = self.client.backfill_workbench_video_enhancement(
                        token,
                        remote_item_id,
                        idempotency_key=f"{clean_key}:{item['item_id']}",
                    )
                else:
                    assert image_path is not None
                    staged_image = self.client.upload_workbench_batch_asset(
                        token,
                        image_path,
                        kind="image",
                        filename=str(image.get("filename") or image_path.name),
                    )
                    remote = self.client.start_workbench_composition(
                        token,
                        batch_id,
                        remote_item_id,
                        idempotency_key=f"{clean_key}:{item['item_id']}",
                        image_asset_id=str(staged_image.get("asset_id") or ""),
                        image_sha256=image_sha256,
                        resolution=clean_resolution,
                        correlation_id=operation["correlation_id"],
                        runninghub_execution_account_ids=selected_account_ids,
                    )
                composition = remote.get("composition", {})
                remote_status = str(composition.get("status") or "COMPOSITION_QUEUED")
                self.store.transition_operation(
                    owner_user_id,
                    project_id,
                    item["item_id"],
                    operation_type="COMPOSITION_GENERATE",
                    status="RUNNING",
                    item_status=(
                        remote_status
                        if remote_status in REMOTE_COMPOSITION_ACTIVE
                        else "COMPOSITION_QUEUED"
                    ),
                    result={
                        "batch_id": batch_id,
                        "remote_item_id": remote_item_id,
                        "remote_status": remote_status,
                        "operation_id": operation["operation_id"],
                        "image_asset_id": staged_image.get("asset_id"),
                        "input_image_sha256": image_sha256,
                        "seedvr2_backfill_only": backfill_seedvr2,
                        "runninghub_execution_account_ids": selected_account_ids,
                    },
                )
            except Exception as exc:
                self.store.transition_operation(
                    owner_user_id,
                    project_id,
                    item["item_id"],
                    operation_type="COMPOSITION_GENERATE",
                    status="FAILED",
                    item_status="COMPOSITION_FAILED",
                    error_code=type(exc).__name__,
                    error_message=str(exc),
                )
        return self.sync(owner_user_id, project_id, token)

    def sync(
        self, owner_user_id: str, project_id: str, token: str
    ) -> dict[str, Any]:
        project = self.store.get_project(owner_user_id, project_id)
        links_by_item = _current_audio_item_links(project["links"])
        operations = _composition_operations(project)
        for item in project["items"]:
            item_id = str(item["item_id"])
            link = links_by_item.get(item_id)
            operation = operations.get(item_id)
            if link is None or operation is None:
                continue
            # Terminal 4A operations are immutable history. Re-querying every
            # completed row on each browser poll multiplies cloud requests and
            # lets one stale row abort the status refresh for the active row.
            if operation.get("status") not in {"PENDING", "RUNNING"}:
                continue
            remote_item_id = str(link.get("external_id") or "")
            if not remote_item_id:
                continue
            remote = self.client.get_workbench_task(token, remote_item_id)
            composition = remote.get("composition", {})
            if not isinstance(composition, dict):
                composition = {}
            remote_status = str(composition.get("status") or "")
            expected_image_sha256 = str(
                operation.get("payload", {}).get("input_image_sha256") or ""
            ).strip().lower()
            remote_image_sha256 = str(
                composition.get("image_sha256") or ""
            ).strip().lower()
            if expected_image_sha256 and remote_image_sha256 != expected_image_sha256:
                self.store.transition_operation(
                    owner_user_id,
                    project_id,
                    item_id,
                    operation_type="COMPOSITION_GENERATE",
                    status="FAILED",
                    item_status="COMPOSITION_FAILED",
                    result={
                        "remote_item_id": remote_item_id,
                        "remote_status": remote_status,
                        "expected_image_sha256": expected_image_sha256,
                        "remote_image_sha256": remote_image_sha256 or None,
                    },
                    error_code="REMOTE_IMAGE_VERSION_MISMATCH",
                    error_message="云端返回的视频未绑定当前项目图片，请更新云端服务后重试",
                )
                continue

            project = self.store.get_project(owner_user_id, project_id)
            local_item = next(
                value for value in project["items"] if value["item_id"] == item_id
            )
            self._download_ready_segments(
                owner_user_id,
                project_id,
                local_item,
                remote_item_id,
                remote,
                token,
            )

            if remote_status == "BASE_VIDEO_READY":
                project = self.store.get_project(owner_user_id, project_id)
                local_item = next(
                    value for value in project["items"] if value["item_id"] == item_id
                )
                self._download_base_video(
                    owner_user_id,
                    project_id,
                    local_item,
                    remote_item_id,
                    remote,
                    token,
                )
                self.store.transition_operation(
                    owner_user_id,
                    project_id,
                    item_id,
                    operation_type="COMPOSITION_GENERATE",
                    status="SUCCEEDED",
                    item_status="BASE_VIDEO_READY",
                    result={
                        "remote_item_id": remote_item_id,
                        "remote_status": remote_status,
                        "segment_count": int(composition.get("segment_count") or 0),
                    },
                )
            elif remote_status == "COMPOSITION_FAILED":
                self.store.transition_operation(
                    owner_user_id,
                    project_id,
                    item_id,
                    operation_type="COMPOSITION_GENERATE",
                    status="FAILED",
                    item_status="COMPOSITION_FAILED",
                    result={"remote_item_id": remote_item_id},
                    error_code="REMOTE_COMPOSITION_FAILED",
                    error_message=str(
                        composition.get("error_message") or "数字人画面生成失败"
                    ),
                )
            elif remote_status in REMOTE_COMPOSITION_ACTIVE:
                self.store.transition_operation(
                    owner_user_id,
                    project_id,
                    item_id,
                    operation_type="COMPOSITION_GENERATE",
                    status="RUNNING",
                    item_status=remote_status,
                    result={
                        "remote_item_id": remote_item_id,
                        "remote_status": remote_status,
                        "segment_count": int(composition.get("segment_count") or 0),
                    },
                )
        return self.store.get_project(owner_user_id, project_id)

    def retry(
        self,
        owner_user_id: str,
        project_id: str,
        item_id: str,
        token: str,
        *,
        idempotency_key: str,
    ) -> dict[str, Any]:
        project = self.store.get_project(owner_user_id, project_id)
        item = next(
            (value for value in project["items"] if value["item_id"] == item_id),
            None,
        )
        if item is None:
            raise KeyError("项目脚本行不存在")
        if not item["allowed_actions"]["retry_composition"]:
            raise ValueError("当前画面任务没有可重试的失败阶段")
        link = _current_audio_item_links(project["links"]).get(item_id)
        if link is None:
            raise ValueError("当前脚本行没有数字人任务")
        clean_key = str(idempotency_key or "").strip()
        if not clean_key:
            raise ValueError("画面重试请求缺少幂等键")
        seedvr2_backfill = (
            item.get("settings", {}).get("composition_invalidated_reason")
            == "DIGITAL_HUMAN_RESOLUTION_CHANGED"
        )
        operation = self.store.create_operation(
            owner_user_id=owner_user_id,
            project_id=project_id,
            item_id=item_id,
            operation_type="COMPOSITION_GENERATE",
            idempotency_key=clean_key,
            payload={
                "retry": True,
                "remote_item_id": link["external_id"],
                "scope": (
                    "seedvr2_backfill_only"
                    if seedvr2_backfill
                    else "failed_remote_stage"
                ),
            },
        )
        if operation.get("status") == "PENDING":
            if seedvr2_backfill:
                self.client.backfill_workbench_video_enhancement(
                    token,
                    str(link["external_id"]),
                    idempotency_key=f"{clean_key}:{item_id}",
                )
            else:
                self.client.retry_workbench_composition(
                    token, str(link["external_id"])
                )
            self.store.transition_operation(
                owner_user_id,
                project_id,
                item_id,
                operation_type="COMPOSITION_GENERATE",
                status="RUNNING",
                item_status="COMPOSITION_QUEUED",
                result={
                    "remote_item_id": link["external_id"],
                    "retry": True,
                    "seedvr2_backfill_only": seedvr2_backfill,
                },
            )
        return self.sync(owner_user_id, project_id, token)

    def _download_ready_segments(
        self,
        owner_user_id: str,
        project_id: str,
        item: dict[str, Any],
        remote_item_id: str,
        remote: dict[str, Any],
        token: str,
    ) -> None:
        existing_task_ids = {
            str(asset.get("external_ref", {}).get("remote_task_id") or "")
            for asset in item.get("asset_history", {}).get(
                "original_video_segment", []
            )
        }
        videos = remote.get("source", {}).get("videos", [])
        if not isinstance(videos, list):
            return
        for video in videos:
            if not isinstance(video, dict) or str(video.get("status") or "") != "SUCCESS":
                continue
            task_id = str(video.get("task_id") or "")
            index = int(video.get("index") or 0)
            if not task_id or index < 1 or task_id in existing_task_ids:
                continue
            directory = (
                self.storage_root
                / "projects"
                / str(owner_user_id)
                / project_id
                / str(item["item_id"])
                / "composition"
                / remote_item_id
                / "segments"
            )
            task_suffix = hashlib.sha256(task_id.encode("utf-8")).hexdigest()[:12]
            target = directory / f"segment-{index:03d}-{task_suffix}.mp4"
            temporary = target.with_suffix(".mp4.tmp")
            try:
                self.client.download_workbench_video(
                    token,
                    remote_item_id,
                    index,
                    temporary,
                    max_bytes=self.max_video_bytes,
                )
                target.parent.mkdir(parents=True, exist_ok=True)
                temporary.replace(target)
            except BaseException:
                temporary.unlink(missing_ok=True)
                raise
            self.store.add_asset(
                owner_user_id=owner_user_id,
                project_id=project_id,
                item_id=item["item_id"],
                asset_type="original_video_segment",
                source_type="runninghub",
                status="READY",
                filename=f"{item['row_key']}-segment-{index:03d}.mp4",
                managed_path=str(target),
                external_ref={
                    "remote_item_id": remote_item_id,
                    "remote_task_id": task_id,
                    "video_index": index,
                },
                metadata={
                    "start_seconds": video.get("start_seconds"),
                    "end_seconds": video.get("end_seconds"),
                    "script_text": video.get("script_text"),
                    "quality_variant": video.get("quality_variant"),
                    "enhanced_by": (
                        "runninghub_seedvr2"
                        if video.get("quality_variant") == "seedvr2_upscaled"
                        else None
                    ),
                    "source_is_available_on_cloud": bool(
                        video.get("source_download_url")
                    ),
                },
            )
            existing_task_ids.add(task_id)

    def _download_base_video(
        self,
        owner_user_id: str,
        project_id: str,
        item: dict[str, Any],
        remote_item_id: str,
        remote: dict[str, Any],
        token: str,
    ) -> None:
        videos = remote.get("source", {}).get("videos", [])
        task_ids = [
            str(video.get("task_id") or "")
            for video in videos
            if isinstance(video, dict) and video.get("task_id")
        ] if isinstance(videos, list) else []
        signature = {
            "remote_item_id": remote_item_id,
            "source_task_ids": task_ids,
            "remote_updated_at": str(remote.get("updated_at") or ""),
            "image_sha256": str(
                remote.get("composition", {}).get("image_sha256") or ""
            ),
        }
        current = item.get("outputs", {}).get("base_video")
        if isinstance(current, dict) and current.get("external_ref") == signature:
            return
        directory = (
            self.storage_root
            / "projects"
            / str(owner_user_id)
            / project_id
            / str(item["item_id"])
            / "composition"
            / remote_item_id
            / "base"
        )
        signature_hash = hashlib.sha256(
            json.dumps(signature, sort_keys=True).encode("utf-8")
        ).hexdigest()[:12]
        target = directory / f"base-{signature_hash}.mp4"
        temporary = target.with_suffix(".mp4.tmp")
        try:
            self.client.download_workbench_base_video(
                token,
                remote_item_id,
                temporary,
                max_bytes=self.max_video_bytes,
            )
            target.parent.mkdir(parents=True, exist_ok=True)
            temporary.replace(target)
        except BaseException:
            temporary.unlink(missing_ok=True)
            raise
        self.store.add_asset(
            owner_user_id=owner_user_id,
            project_id=project_id,
            item_id=item["item_id"],
            asset_type="base_video",
            source_type=(
                "runninghub_single" if len(task_ids) <= 1 else "runninghub_merge"
            ),
            status="READY",
            filename=f"{item['row_key']}-base.mp4",
            managed_path=str(target),
            external_ref=signature,
            metadata={
                "segment_count": len(task_ids),
                "normalized_to_approved_audio": True,
                "input_image_asset_id": str(
                    item.get("inputs", {}).get("image", {}).get("asset_id") or ""
                ),
                "input_image_sha256": signature["image_sha256"],
                "module": "4A",
            },
            make_current=True,
        )
