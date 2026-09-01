"""Read-only cloud receipt recovery for interrupted workbench audio commands."""
from __future__ import annotations

from collections import defaultdict
import hashlib
import logging
from typing import Any

from .auth_center import AuthCenterClient, AuthCenterError
from .logging_config import log_event
from .project_store import ProjectStore


logger = logging.getLogger("jyd_probe.workbench")


def audio_request_key(project_id: str, idempotency_key: str, voice_id: str) -> str:
    digest = hashlib.sha256(
        f"{project_id}\0{idempotency_key.strip()}\0{voice_id}".encode("utf-8")
    ).hexdigest()[:48]
    return f"workbench-audio-{digest}"


def recover_audio_submissions(
    store: ProjectStore, client: AuthCenterClient,
    owner_user_id: str, project_id: str, token: str,
) -> None:
    store.recover_interrupted_audio_submissions(owner_user_id, project_id)
    project = store.get_project(owner_user_id, project_id)
    latest = {op["item_id"]: op for op in project["operations"]
              if op["operation_type"] == "AUDIO_GENERATE"}
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for operation in latest.values():
        payload = operation.get("payload", {})
        if (operation["status"] == "FAILED"
                and operation.get("error_code") == "AUDIO_SUBMISSION_UNKNOWN"
                and payload.get("submission_contract") == "jyd.audio-submission.v1"):
            groups[audio_request_key(project_id, operation["idempotency_key"], payload["voice_asset_id"])].append(operation)
    if not groups:
        return
    # Old servers may not expose lookup yet. There is deliberately no fallback
    # to create/retry: a missing receipt never proves that a request was unpaid.
    lookup = getattr(client, "lookup_workbench_audio_batch", None)
    if lookup is None:
        return
    local_items = {item["item_id"]: item for item in project["items"]}
    for request_key, operations in groups.items():
        try:
            response = lookup(token, request_key)
            if (not isinstance(response, dict)
                    or response.get("schema") != "runninghub.workbench-audio-lookup.v1"
                    or response.get("found") is not True):
                continue
            if response.get("request_key") != request_key:
                raise ValueError("声音恢复请求标识不一致")
            batch = response.get("batch")
            if (not isinstance(batch, dict) or not batch.get("batch_id")
                    or batch.get("source_channel") != "new_workbench"):
                raise ValueError("声音恢复批次不完整")
            rows = batch.get("items")
            if not isinstance(rows, list) or not all(isinstance(row, dict) for row in rows):
                raise ValueError("声音恢复行数据不完整")
            by_row = {row.get("row_key"): row for row in rows}
            if len(by_row) != len(rows) or len({row.get("item_id") for row in rows}) != len(rows):
                raise ValueError("声音恢复行记录重复")
            bindings = response.get("input_bindings")
            if not isinstance(bindings, dict):
                raise ValueError("声音恢复缺少输入摘要")
            recovered = []
            # Validate every remaining row before accepting any receipt.
            for operation in operations:
                payload = operation["payload"]
                row = by_row.get(local_items[operation["item_id"]]["row_key"])
                binding = bindings.get(row.get("item_id")) if row else None
                expected_speech = {key: payload["speech_settings"].get(key) for key in (
                    "model", "speed", "volume", "pitch", "languageBoost", "outputFormat"
                )}
                if (not row or not row.get("item_id") or not isinstance(binding, dict)
                        or batch.get("correlation_id") != operation["correlation_id"]
                        or binding.get("script_sha256") != payload["script_sha256"]
                        or binding.get("voice_asset_id") != payload["voice_asset_id"]
                        or binding.get("speech_settings") != expected_speech):
                    raise ValueError("声音恢复记录与原始输入不一致")
                recovered.append((operation, row))
            for operation, row in recovered:
                store.accept_audio_submission(
                    owner_user_id, project_id, operation["item_id"],
                    operation_id=operation["operation_id"], recovering=True,
                    result={"batch_id": batch["batch_id"], "item_id": row["item_id"],
                            "provider_status": row.get("status")},
                )
        except (AuthCenterError, OSError, ValueError, KeyError, TypeError) as exc:
            log_event(
                logger, "workbench.audio_receipt_recovery_deferred",
                "声音提交回执尚未核对成功，保留原素材且不重新计费",
                level=logging.WARNING, component="workbench", user_id=owner_user_id,
                project_id=project_id, error_type=type(exc).__name__,
            )
