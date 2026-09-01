"""Queue checks preserve unstarted work, independent of provider failures."""

from __future__ import annotations

from functools import wraps
import json
import logging
import os
from pathlib import Path
import tempfile

from .device_auth_protocol import DeviceAuthorizationError
from .device_identity_windows import DeviceIdentityError
from .device_local_execution import (
    authorized_local_unit,
    local_authorization_context,
    render_operation_scopes,
    requires_device_authorization,
)


def sync_authorization_status(path, status):
    """DB is authoritative. A transient file lock must not strand queue work."""
    path, temporary = Path(path), None
    try:
        if not path.is_file():
            return
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=path.parent,
            prefix=".device-status-",
            suffix=".tmp",
            delete=False,
        ) as output:
            temporary = Path(output.name)
            json.dump(status, output, ensure_ascii=False, indent=2)
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary, path)
    except OSError:
        logging.getLogger("jyd_probe.device_auth").warning(
            "本地授权等待状态已保存到数据库，状态文件暂无法同步"
        )
    finally:
        if temporary is not None:
            try:
                temporary.unlink(missing_ok=True)
            except OSError:
                pass


def device_guarded_queue_job(function):
    @wraps(function)
    def execute(queue, job_id, *args, **kwargs):
        if not requires_device_authorization():
            return function(queue, job_id, *args, **kwargs)
        try:
            authorizer = getattr(queue, "_device_authorizers", {}).get(job_id)
            payload = queue.store.get_job_payload(job_id)
            with local_authorization_context(authorizer):
                with authorized_local_unit(
                    render_operation_scopes(payload)
                ) as decision:
                    stored = (queue.store.get_status(job_id) or {}).get(
                        "device_authorization"
                    ) or {}
                    if stored.get("user_id") != decision.user_id:
                        raise DeviceAuthorizationError(
                            "DEVICE_ACCOUNT_MISMATCH", "排队任务的设备账号不一致"
                        )
                    if decision.mode == "ENFORCE" and not stored.get("thumbprint"):
                        raise DeviceAuthorizationError(
                            "DEVICE_LOCAL_REBIND_REQUIRED",
                            "该历史任务需要所属账号确认本机授权后继续",
                        )
                    if (
                        decision.mode == "ENFORCE"
                        and stored["thumbprint"] != decision.thumbprint
                    ):
                        raise DeviceAuthorizationError(
                            "DEVICE_IDENTITY_MISMATCH", "排队任务需要原处理机授权"
                        )
                    result = function(queue, job_id, *args, **kwargs)
            queue._device_authorizers.pop(job_id, None)
            return result
        except (DeviceAuthorizationError, DeviceIdentityError) as exc:
            status = queue.store.pause_for_device_authorization(job_id, exc.code)
            # Existing UI reads both the database and this per-job status file.
            status_path = (
                Path(queue.settings.storage_root) / "jobs" / job_id / "status.json"
            )
            sync_authorization_status(status_path, status)
            return None

    return execute
