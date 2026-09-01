"""Local quote identity. No provider calls and no plaintext inputs in receipts."""
from __future__ import annotations

import hashlib
import json
import functools
import threading
from pathlib import Path
from typing import Any

QUOTE_RECOVERY_VERSION = "jyd.h3-quote-recovery.v1"
_action_locks = [threading.RLock() for _ in range(64)]


def serialized_quote_action(method):
    @functools.wraps(method)
    def run(self, owner_user_id, project_id, *args, **kwargs):
        # Shared across per-request coordinators; bounded stripes avoid a growing registry.
        with _action_locks[hash((owner_user_id, project_id)) % len(_action_locks)]:
            return method(self, owner_user_id, project_id, *args, **kwargs)
    return run


class H3QuoteConflict(ValueError):
    def __init__(self, message: str, batches: list[dict[str, Any]]):
        super().__init__(message)
        self.detail = {"code": "H3_QUOTE_CONFLICT", "message": message, "batches": batches}


def digest(value: object) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                    separators=(",", ":")).encode()).hexdigest()


def asset_identity(asset: dict[str, Any] | None) -> dict[str, Any]:
    asset = asset or {}
    path = Path(str(asset.get("managed_path") or ""))
    if not path.is_file():
        raise ValueError("报价关联的素材文件缺失，请先恢复素材")
    with path.open("rb") as stream:
        sha = hashlib.file_digest(stream, "sha256").hexdigest()
    return {"id": asset.get("asset_id") or asset.get("image_id"), "sha256": sha}


def input_binding(project: dict[str, Any], items: list[dict[str, Any]], audio_for) -> dict[str, Any]:
    defaults = project.get("settings", {}).get("h3", {}).get("defaults", {})
    identities = []
    for item in items:
        audio = audio_for(item)
        if not audio or item.get("status") in {"AUDIO_QUEUED", "AUDIO_RUNNING"}:
            raise ValueError("声音尚未准备完成，不能确认旧报价")
        params = {"continuity_mode": "loop_anchor", "generation_tail_seconds": 0.1,
                  "aspect_ratio": "9:16 (Portrait Widescreen)", "megapixels": 1.0, "multiple": 32,
                  **defaults, **item.get("settings", {}).get("h3", {}).get("overrides", {})}
        # Normalize numeric settings so saving 1 as 1.0 does not invalidate a quote.
        for key in ("megapixels", "generation_tail_seconds"):
            params[key] = float(params[key])
        identities.append({
            "item_id": item["item_id"], "row_id": item["row_key"],
            "fingerprint": digest({
                "script": item.get("script_text", ""), "audio": asset_identity(audio),
                "audio_ref": audio.get("external_ref", {}),
                "image": asset_identity(item.get("inputs", {}).get("image")),
                "video": asset_identity(item.get("inputs", {}).get("h3_reference_video")),
                "params": params,
            }),
        })
    identities.sort(key=lambda item: item["item_id"])
    return {"schema": QUOTE_RECOVERY_VERSION, "items": identities, "sha256": digest(identities)}


def describe_quote(project, record, snapshot, selected_ids, audio_for):
    binding = record.get("quote_binding") or {}
    bound = binding.get("items") or []
    # Legacy quotes cannot be proven equivalent. Retain them for explicit cloud cancellation.
    rows = [str(item.get("row_id") or "") for item in snapshot.get("items", [])]
    item_ids = [str(item["item_id"]) for item in bound] if bound else [
        str(item["item_id"]) for item in project.get("items", [])
        if str(item.get("row_key")) in rows
        or item.get("settings", {}).get("h3", {}).get("remote_batch_id") == snapshot["batch_id"]
    ]
    changed = "旧预览缺少素材版本凭据，无法安全确认，请取消旧预览后重新计算"
    if binding.get("schema") == QUOTE_RECOVERY_VERSION:
        try:
            items = [item for item in project.get("items", []) if item["item_id"] in item_ids]
            current = input_binding(project, items, audio_for)
            changed = "" if current == binding else "脚本、声音、图片、参考视频或生成参数已变化"
        except OSError:
            changed = "报价关联的素材文件无法读取，请先恢复素材"
        except (ValueError, TypeError, KeyError) as exc:
            changed = str(exc)
    status = str(snapshot.get("status") or "").upper()
    same_selection = set(item_ids) == set(selected_ids)
    pending = status == "AWAITING_COST_CONFIRMATION"
    capability = snapshot.get("quote_recovery") or {}
    return {
        "batch_id": snapshot["batch_id"], "status": status, "row_ids": rows,
        "item_ids": item_ids, "same_selection": same_selection,
        "input_matches": not changed, "input_change_reason": changed,
        "can_resume": pending and same_selection and not changed,
        "can_cancel_quote": pending and capability.get("can_cancel_quote") is True,
        "quote_token": capability.get("quote_token"),
        "binding_sha256": binding.get("sha256"), "fee_snapshot": snapshot.get("fee_snapshot"),
    }
