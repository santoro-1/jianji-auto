"""Transactional Agent identity, start receipts and idempotent result reporting.

Only verified in-process decisions enter here. Job input and Agent details are
never a source of permissions. A lost lease is not proof that rendering stopped.
"""

from __future__ import annotations

import re

from .device_agent_protocol import fail
from .device_agent_queue import require_assignment, require_decision
from .device_auth_protocol import canonical_json, sha256_b64
from .device_local_execution import render_operation_scopes
from .task_store import _future, _json, _now, _object


def execution_id_value(value):
    if not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{32}", value):
        fail("INVALID_AGENT_EXECUTION", "处理机执行回执编号无效", 422)
    return value


def require_agent_binding(connection, agent_id, decision):
    row = connection.execute(
        "SELECT * FROM agents WHERE agent_id=?", (agent_id,)
    ).fetchone()
    if row is None:
        fail("DEVICE_AGENT_REGISTRATION_REQUIRED", "请先以当前账号注册处理机", 409)
    details = _object(row["details_json"], {})
    binding = details.get("_device_binding") if isinstance(details, dict) else None
    if (
        not isinstance(binding, dict)
        or type(binding.get("user_id")) is not int
        or binding["user_id"] != decision.user_id
        or binding.get("thumbprint") != decision.thumbprint
    ):
        fail("DEVICE_AGENT_ASSIGNMENT_MISMATCH", "处理机编号不属于此账号和设备", 409)
    return row


def register_agent(store, agent_id, data, decision):
    now = _now()
    with store._transaction() as connection:
        require_decision(decision, "execute")
        previous = connection.execute(
            "SELECT * FROM agents WHERE agent_id=?", (agent_id,)
        ).fetchone()
        if previous is not None:
            details = _object(previous["details_json"], {})
            binding = (
                details.get("_device_binding") if isinstance(details, dict) else None
            )
            if binding is not None:
                # An idle same-account observation registration may acquire its
                # original device identity after rollout; never downgrade a key.
                upgrade = (
                    isinstance(binding, dict)
                    and type(binding.get("user_id")) is int
                    and binding["user_id"] == decision.user_id
                    and binding.get("thumbprint") is None
                    and decision.thumbprint is not None
                    and previous["current_job_id"] is None
                )
                if not upgrade:
                    require_agent_binding(connection, agent_id, decision)
            if previous["current_job_id"]:
                job = connection.execute(
                    "SELECT status_json FROM jobs WHERE job_id=?",
                    (previous["current_job_id"],),
                ).fetchone()
                if job is None:
                    fail(
                        "DEVICE_AGENT_EXECUTION_UNCERTAIN",
                        "原任务分配异常，请核对后恢复",
                        409,
                    )
                require_assignment(_object(job["status_json"], {}), decision)
        details = {
            "_device_binding": {
                "user_id": decision.user_id,
                "thumbprint": decision.thumbprint,
            }
        }
        connection.execute(
            "INSERT INTO agents(agent_id,name,status,registered_at,last_heartbeat_at,hostname,version,capabilities_json,details_json) "
            "VALUES(?,?,'idle',?,?,?,?,?,?) ON CONFLICT(agent_id) DO UPDATE SET "
            "name=excluded.name, status=CASE WHEN agents.current_job_id IS NULL THEN 'idle' ELSE 'busy' END, "
            "last_heartbeat_at=excluded.last_heartbeat_at,hostname=excluded.hostname,version=excluded.version,"
            "capabilities_json=excluded.capabilities_json,details_json=excluded.details_json",
            (
                agent_id,
                str(data.get("name") or agent_id)[:160],
                now,
                now,
                str(data.get("hostname") or "")[:160],
                str(data.get("version") or "")[:80],
                _json(data.get("capabilities") or {}),
                _json(details),
            ),
        )
    # Do not return another job's details through registration responses.
    return {"agent_id": agent_id, "registered": True}


def heartbeat_agent(store, agent_id, decision):
    with store._transaction() as connection:
        require_decision(decision, "execute")
        require_agent_binding(connection, agent_id, decision)
        connection.execute(
            "UPDATE agents SET last_heartbeat_at=?, status=CASE WHEN current_job_id IS NULL THEN 'idle' ELSE 'busy' END WHERE agent_id=?",
            (_now(), agent_id),
        )
    return {"agent_id": agent_id, "ok": True}


def _assigned(connection, agent_id, job_id, decision):
    row = connection.execute(
        "SELECT * FROM jobs WHERE job_id=? AND assigned_agent_id=?", (job_id, agent_id)
    ).fetchone()
    if row is None:
        fail("DEVICE_AGENT_ASSIGNMENT_MISMATCH", "原任务不属于此账号和执行机", 409)
    status = _object(row["status_json"], {})
    require_assignment(status, decision)
    return row, status


def start_job(store, agent_id, job_id, execution_id, decision, *, lease_seconds=120):
    execution_id_value(execution_id)
    with store._transaction() as connection:
        require_decision(decision, "execute")
        require_agent_binding(connection, agent_id, decision)
        row, status = _assigned(connection, agent_id, job_id, decision)
        if row["status"] == "cancelled" and not status.get("agent_execution"):
            return {
                "job_id": job_id,
                "execution_id": execution_id,
                "started": False,
                "cancelled": True,
            }
        if row["status"] != "running" or row["cancel_requested"]:
            fail("DEVICE_AGENT_START_DENIED", "原任务已结束或请求取消，未启动渲染", 409)
        if (
            not render_operation_scopes(_object(row["payload_json"], {}))
            <= decision.scopes
        ):
            fail("DEVICE_SCOPE_DENIED", "此执行机没有原任务所需权限")
        execution = status.get("agent_execution")
        if execution is not None and (
            not isinstance(execution, dict)
            or execution.get("execution_id") != execution_id
        ):
            fail(
                "DEVICE_AGENT_EXECUTION_UNCERTAIN",
                "原任务已有另一执行回执，未重复启动",
                409,
            )
        now, lease = _now(), _future(lease_seconds)
        if execution is None:
            status["agent_execution"] = {
                "execution_id": execution_id,
                "phase": "started",
                "started_at": now,
            }
        status.pop("agent_recovery_required", None)
        status.pop("recovery_reason", None)
        status.update(heartbeat_at=now, lease_expires_at=lease)
        connection.execute(
            "UPDATE jobs SET status_json=?,heartbeat_at=?,lease_expires_at=? WHERE job_id=?",
            (_json(status), now, lease, job_id),
        )
        connection.execute(
            "UPDATE agents SET status='busy',last_heartbeat_at=? WHERE agent_id=? AND current_job_id=?",
            (now, agent_id, job_id),
        )
    return {"job_id": job_id, "execution_id": execution_id, "started": True}


def report_job(
    store,
    agent_id,
    job_id,
    execution_id,
    decision,
    *,
    action,
    payload,
    lease_seconds=120,
    retention=None,
    recovery=None,
):
    execution_id_value(execution_id)
    if action not in {"heartbeat", "complete", "fail"}:
        fail("INVALID_AGENT_REQUEST", "处理机报告用途无效", 422)
    result = payload.get("result") if action == "complete" else None
    if action == "complete" and not isinstance(result, dict):
        fail("INVALID_AGENT_REQUEST", "result 必须是对象", 422)
    error = (
        str(payload.get("error") or "处理机报告任务失败")[:1000]
        if action == "fail"
        else ""
    )
    receipt_hash = sha256_b64(
        canonical_json(
            {
                "execution_id": execution_id,
                "action": action,
                "result": result,
                "error": error,
            }
        )
    )
    with store._transaction() as connection:
        require_decision(decision, "report")
        row, status = _assigned(connection, agent_id, job_id, decision)
        execution = status.get("agent_execution")
        if (
            execution is None
            and row["status"] == "running"
            and action == "fail"
            and recovery is None
        ):
            # Definitive preparation failure can close an assigned, unstarted
            # job, but a report permit cannot create a successful execution.
            status["agent_execution"] = {
                "execution_id": execution_id,
                "phase": "not_started",
            }
        elif (
            not isinstance(execution, dict)
            or execution.get("execution_id") != execution_id
        ):
            fail("DEVICE_AGENT_EXECUTION_UNCERTAIN", "报告与原执行回执不一致", 409)
        recovery_record = None
        if recovery is not None:
            recovery_record = validate_recovery(recovery)
            if (
                recovery["execution_id"] != execution_id
                or recovery["resolution"]
                != {"complete": "completed", "fail": "failed"}.get(action)
                or recovery["result"] != result
                or recovery["error"] != error
            ):
                fail("INVALID_AGENT_RECOVERY", "核实结论与原结果回报不一致", 422)
            old_recovery = status.get("agent_manual_recovery")
            if (
                isinstance(old_recovery, dict)
                and old_recovery.get("request_id") == recovery_record["request_id"]
            ):
                if old_recovery.get("request_hash") != recovery_record["request_hash"]:
                    fail(
                        "DEVICE_AGENT_RESULT_CONFLICT",
                        "同一核实请求不能改为另一结论",
                        409,
                    )
                return status, False
            current = _recovery_view(row, status, execution_id)
            if current["review_hash"] != recovery["review_hash"]:
                fail(
                    "DEVICE_AGENT_REVIEW_CHANGED", "原任务状态已经改变，请重新核实", 409
                )
            if row["status"] == "running" and not current["can_resolve"]:
                fail(
                    "DEVICE_AGENT_EXECUTION_ACTIVE",
                    "原任务仍有有效执行租约，请确认停止后等待租约结束",
                    409,
                )
        if row["status"] in {"completed", "failed"}:
            if action == "heartbeat" or status.get("agent_report_hash") == receipt_hash:
                return status, False
            fail(
                "DEVICE_AGENT_RESULT_CONFLICT",
                "原任务已经结束，不能覆盖为另一结果",
                409,
            )
        if row["status"] != "running":
            fail("DEVICE_AGENT_RESULT_CONFLICT", "原任务当前不能接收执行结果", 409)
        now = _now()
        if action == "heartbeat":
            lease = _future(lease_seconds)
            status.update(heartbeat_at=now, lease_expires_at=lease)
            status.pop("agent_recovery_required", None)
            status.pop("recovery_reason", None)
            for key in ("progress", "message", "stage"):
                if key in payload:
                    status[key] = payload[key]
            connection.execute(
                "UPDATE jobs SET status_json=?,heartbeat_at=?,lease_expires_at=? WHERE job_id=?",
                (_json(status), now, lease, job_id),
            )
            connection.execute(
                "UPDATE agents SET last_heartbeat_at=?,status='busy' WHERE agent_id=? AND current_job_id=?",
                (now, agent_id, job_id),
            )
            return status, True
        terminal = "completed" if action == "complete" else "failed"
        status.update(
            status=terminal,
            finished_at=now,
            heartbeat_at=now,
            agent_report_hash=receipt_hash,
        )
        status.pop("lease_expires_at", None)
        status.pop("agent_recovery_required", None)
        status.pop("recovery_reason", None)
        if recovery_record is not None:
            status["agent_manual_recovery"] = {**recovery_record, "resolved_at": now}
        if result is not None:
            status["result"] = result
            status.pop("error", None)
        else:
            status["error"] = error
        if retention:
            for key, value in retention.items():
                status.setdefault(key, value)
        connection.execute(
            "UPDATE jobs SET status=?,status_json=?,finished_at=?,heartbeat_at=?,lease_expires_at=NULL,error=?,result_json=? WHERE job_id=?",
            (
                terminal,
                _json(status),
                now,
                now,
                error,
                _json(result) if result is not None else None,
                job_id,
            ),
        )
        connection.execute(
            "UPDATE agents SET status='idle',current_job_id=NULL,last_heartbeat_at=? WHERE agent_id=? AND current_job_id=?",
            (now, agent_id, job_id),
        )
    return status, True


def _recovery_view(row, status, execution_id):
    execution = status.get("agent_execution")
    if not isinstance(execution, dict) or execution.get("execution_id") != execution_id:
        fail("DEVICE_AGENT_EXECUTION_UNCERTAIN", "中央记录与本机原执行编号不一致", 409)
    view = {
        "schema": "publicvideo.agent-recovery.v1",
        "job_id": row["job_id"],
        "execution_id": execution_id,
        "status": row["status"],
        "payload_hash": sha256_b64(canonical_json(_object(row["payload_json"], {}))),
        "lease_expires_at": row["lease_expires_at"],
        "heartbeat_at": row["heartbeat_at"],
        "cancel_requested": bool(row["cancel_requested"]),
        "result": _object(row["result_json"], None),
        "error": row["error"] or "",
        "report_hash": status.get("agent_report_hash"),
    }
    digest = sha256_b64(canonical_json(view))
    view.update(
        review_hash=digest,
        can_resolve=(
            row["status"] == "running"
            and (not row["lease_expires_at"] or row["lease_expires_at"] <= _now())
        ),
    )
    return view


def prepare_recovery(store, agent_id, job_id, execution_id, payload_hash, decision):
    execution_id_value(execution_id)
    with store._transaction() as connection:
        require_decision(decision, "report")
        row, status = _assigned(connection, agent_id, job_id, decision)
        view = _recovery_view(row, status, execution_id)
        if view["payload_hash"] != payload_hash:
            fail("DEVICE_AGENT_RECEIPT_CONFLICT", "本机原任务输入与中央记录不一致", 409)
        return view


def validate_recovery(recovery):
    if not isinstance(recovery, dict) or set(recovery) != {
        "execution_id",
        "review_hash",
        "request_id",
        "resolution",
        "result",
        "error",
        "confirm_stopped",
        "confirm_reviewed",
    }:
        fail("INVALID_AGENT_RECOVERY", "核实参数无效", 422)
    execution_id_value(recovery["request_id"])
    execution_id_value(recovery["execution_id"])
    if (
        recovery["confirm_stopped"] is not True
        or recovery["confirm_reviewed"] is not True
        or not isinstance(recovery["review_hash"], str)
        or not re.fullmatch(r"[A-Za-z0-9_-]{43}", recovery["review_hash"])
        or not isinstance(recovery["resolution"], str)
        or recovery["resolution"] not in {"completed", "failed"}
        or not isinstance(recovery["error"], str)
        or len(recovery["error"]) > 1000
        or (
            recovery["resolution"] == "completed"
            and (not isinstance(recovery["result"], dict) or recovery["error"])
        )
        or (
            recovery["resolution"] == "failed"
            and (recovery["result"] is not None or not recovery["error"])
        )
    ):
        fail("INVALID_AGENT_RECOVERY", "请明确确认原执行已经停止并核实原结果", 422)
    return {
        "schema": "publicvideo.agent-recovery.v1",
        "request_id": recovery["request_id"],
        "request_hash": sha256_b64(canonical_json(recovery)),
        "resolution": recovery["resolution"],
        "review_hash": recovery["review_hash"],
        "confirmed_stopped": True,
        "confirmed_reviewed": True,
    }
