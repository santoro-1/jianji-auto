from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timedelta
import json
from pathlib import Path
import sqlite3
import threading
from typing import Any, Iterator


SCHEMA_VERSION = 1


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _future(seconds: int) -> str:
    return (datetime.now() + timedelta(seconds=max(30, int(seconds)))).isoformat(
        timespec="seconds"
    )


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def _object(value: str | None, default: Any) -> Any:
    if not value:
        return default
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return default


class SQLiteTaskStore:
    """SQLite-backed task and agent state for one central API process.

    Agents never open this database directly. They claim and update work through
    the HTTP API, which keeps SQLite on a single machine even when render agents
    run on several Windows computers.
    """

    def __init__(self, path: str | Path):
        self.path = Path(path).expanduser().resolve()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._schema_lock = threading.Lock()
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=30, isolation_level=None)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA busy_timeout = 30000")
        return connection

    @contextmanager
    def _transaction(self) -> Iterator[sqlite3.Connection]:
        connection = self._connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            yield connection
            connection.commit()
        except BaseException:
            connection.rollback()
            raise
        finally:
            connection.close()

    def _initialize(self) -> None:
        with self._schema_lock, self._connect() as connection:
            connection.execute("PRAGMA journal_mode = WAL")
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS schema_meta (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS batches (
                    batch_id TEXT PRIMARY KEY,
                    created_at TEXT NOT NULL,
                    payload_json TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS jobs (
                    job_id TEXT PRIMARY KEY,
                    batch_id TEXT,
                    status TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    status_json TEXT NOT NULL,
                    assigned_agent_id TEXT,
                    created_at TEXT NOT NULL,
                    queued_at TEXT NOT NULL,
                    started_at TEXT,
                    finished_at TEXT,
                    heartbeat_at TEXT,
                    lease_expires_at TEXT,
                    retry_count INTEGER NOT NULL DEFAULT 0,
                    cancel_requested INTEGER NOT NULL DEFAULT 0,
                    error TEXT NOT NULL DEFAULT '',
                    result_json TEXT,
                    FOREIGN KEY(batch_id) REFERENCES batches(batch_id)
                );

                CREATE INDEX IF NOT EXISTS idx_jobs_queue
                    ON jobs(status, queued_at, created_at);
                CREATE INDEX IF NOT EXISTS idx_jobs_batch
                    ON jobs(batch_id, created_at);
                CREATE INDEX IF NOT EXISTS idx_jobs_agent
                    ON jobs(assigned_agent_id, status);

                CREATE TABLE IF NOT EXISTS agents (
                    agent_id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    status TEXT NOT NULL,
                    registered_at TEXT NOT NULL,
                    last_heartbeat_at TEXT NOT NULL,
                    current_job_id TEXT,
                    hostname TEXT NOT NULL DEFAULT '',
                    version TEXT NOT NULL DEFAULT '',
                    capabilities_json TEXT NOT NULL DEFAULT '{}',
                    details_json TEXT NOT NULL DEFAULT '{}'
                );
                """
            )
            connection.execute(
                "INSERT OR REPLACE INTO schema_meta(key, value) VALUES('version', ?)",
                (str(SCHEMA_VERSION),),
            )

    def add_batch(self, record: dict[str, Any]) -> None:
        batch_id = str(record["batch_id"])
        with self._connect() as connection:
            connection.execute(
                """
                INSERT OR IGNORE INTO batches(batch_id, created_at, payload_json)
                VALUES(?, ?, ?)
                """,
                (batch_id, str(record.get("created_at") or _now()), _json(record)),
            )

    def add_job(
        self,
        job_id: str,
        payload: dict[str, Any],
        status: dict[str, Any],
    ) -> None:
        batch_id = str(status.get("batch_id") or "") or None
        now = str(status.get("created_at") or _now())
        queued_at = str(status.get("queued_at") or now)
        with self._connect() as connection:
            connection.execute(
                """
                INSERT OR IGNORE INTO jobs(
                    job_id, batch_id, status, payload_json, status_json,
                    created_at, queued_at
                ) VALUES(?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    job_id,
                    batch_id,
                    str(status.get("status") or "pending"),
                    _json(payload),
                    _json(status),
                    now,
                    queued_at,
                ),
            )

    def import_legacy_job(
        self,
        job_id: str,
        payload: dict[str, Any],
        status: dict[str, Any],
        *,
        replace_existing: bool = False,
    ) -> None:
        normalized = dict(status)
        current = str(normalized.get("status") or "failed")
        if normalized.get("agent_device_authorization"):
            # A copied/stale status file must not reset an authoritative DB row.
            # If the DB really was lost, preserve the old execution assignment
            # for reporting; never import possibly running Agent work as pending.
            with self._transaction() as connection:
                if connection.execute("SELECT 1 FROM jobs WHERE job_id=?", (job_id,)).fetchone():
                    return
                if current in {"pending", "running"}:
                    current = "running"
                    normalized.update(agent_recovery_required=True, recovery_reason="imported_authorized_agent_uncertain")
                    normalized.pop("lease_expires_at", None)
                normalized["status"] = current
                now = _now()
                connection.execute(
                    "INSERT INTO jobs(job_id,batch_id,status,payload_json,status_json,assigned_agent_id,created_at,queued_at,"
                    "started_at,finished_at,retry_count,cancel_requested,error,result_json) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (job_id, normalized.get("batch_id") or None, current, _json(payload), _json(normalized),
                     normalized.get("assigned_agent_id"), normalized.get("created_at") or now, normalized.get("queued_at") or now,
                     normalized.get("started_at"), normalized.get("finished_at"), int(normalized.get("retry_count") or 0),
                     int(normalized.get("cancel_requested") is True), str(normalized.get("error") or ""),
                     _json(normalized["result"]) if isinstance(normalized.get("result"), dict) else None),
                )
            return
        if current == "running":
            current = "pending"
            normalized.update(
                {
                    "status": "pending",
                    "recovered_at": _now(),
                    "recovery_reason": "imported_interrupted_job",
                }
            )
        normalized["status"] = current
        self.add_job(job_id, payload, normalized)
        if replace_existing:
            self.set_status(job_id, normalized)

    def register_agent(self, agent_id: str, data: dict[str, Any]) -> dict[str, Any]:
        now = _now()
        name = str(data.get("name") or agent_id)
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO agents(
                    agent_id, name, status, registered_at, last_heartbeat_at,
                    hostname, version, capabilities_json, details_json
                ) VALUES(?, ?, 'idle', ?, ?, ?, ?, ?, ?)
                ON CONFLICT(agent_id) DO UPDATE SET
                    name=excluded.name,
                    status=CASE WHEN agents.current_job_id IS NULL THEN 'idle' ELSE 'busy' END,
                    last_heartbeat_at=excluded.last_heartbeat_at,
                    hostname=excluded.hostname,
                    version=excluded.version,
                    capabilities_json=excluded.capabilities_json,
                    details_json=excluded.details_json
                """,
                (
                    agent_id,
                    name,
                    now,
                    now,
                    str(data.get("hostname") or ""),
                    str(data.get("version") or ""),
                    _json(data.get("capabilities") or {}),
                    _json(data.get("details") or {}),
                ),
            )
        return self.get_agent(agent_id)

    def heartbeat_agent(self, agent_id: str, data: dict[str, Any]) -> dict[str, Any]:
        now = _now()
        with self._connect() as connection:
            cursor = connection.execute(
                """
                UPDATE agents SET
                    status=CASE WHEN current_job_id IS NULL THEN 'idle' ELSE 'busy' END,
                    last_heartbeat_at=?,
                    details_json=?
                WHERE agent_id=?
                """,
                (now, _json(data), agent_id),
            )
            if not cursor.rowcount:
                raise KeyError(f"处理机没有注册: {agent_id}")
        return self.get_agent(agent_id)

    def get_agent(self, agent_id: str) -> dict[str, Any]:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM agents WHERE agent_id=?", (agent_id,)
            ).fetchone()
        if row is None:
            raise KeyError(f"处理机不存在: {agent_id}")
        return self._agent_dict(row)

    def list_agents(self, offline_after_seconds: int = 90) -> list[dict[str, Any]]:
        cutoff = (datetime.now() - timedelta(seconds=max(30, offline_after_seconds))).isoformat(
            timespec="seconds"
        )
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM agents ORDER BY name, agent_id"
            ).fetchall()
        result = []
        for row in rows:
            item = self._agent_dict(row)
            if item["last_heartbeat_at"] < cutoff:
                item["status"] = "offline"
            result.append(item)
        return result

    @staticmethod
    def _agent_dict(row: sqlite3.Row) -> dict[str, Any]:
        return {
            "agent_id": row["agent_id"],
            "name": row["name"],
            "status": row["status"],
            "registered_at": row["registered_at"],
            "last_heartbeat_at": row["last_heartbeat_at"],
            "current_job_id": row["current_job_id"],
            "hostname": row["hostname"],
            "version": row["version"],
            "capabilities": _object(row["capabilities_json"], {}),
            "details": _object(row["details_json"], {}),
        }

    def recover_expired_leases(self) -> list[str]:
        now = _now()
        recovered: list[str] = []
        with self._transaction() as connection:
            rows = connection.execute(
                """
                SELECT job_id, assigned_agent_id, status_json, cancel_requested
                FROM jobs
                WHERE status='running' AND lease_expires_at IS NOT NULL
                  AND lease_expires_at < ?
                """,
                (now,),
            ).fetchall()
            for row in rows:
                status = _object(row["status_json"], {})
                if status.get("agent_device_authorization"):
                    # Losing an Agent lease is not proof its renderer stopped.
                    # Keep the original assignment for result recovery, and never
                    # silently hand potentially running work to a second machine.
                    status["agent_recovery_required"] = True
                    status["recovery_reason"] = "authorized_agent_lease_uncertain"
                    status.pop("lease_expires_at", None)
                    connection.execute(
                        "UPDATE jobs SET status_json=?, lease_expires_at=NULL WHERE job_id=?",
                        (_json(status), row["job_id"]),
                    )
                    connection.execute(
                        "UPDATE agents SET status='offline' WHERE agent_id=? AND current_job_id=?",
                        (row["assigned_agent_id"], row["job_id"]),
                    )
                    continue
                cancelled = bool(row["cancel_requested"])
                status.update(
                    {
                        "status": "cancelled" if cancelled else "pending",
                        "recovered_at": now,
                        "recovery_reason": "agent_lease_expired",
                    }
                )
                status.pop("assigned_agent_id", None)
                status.pop("lease_expires_at", None)
                connection.execute(
                    """
                    UPDATE jobs SET
                        status=?, status_json=?, assigned_agent_id=NULL,
                        started_at=NULL, heartbeat_at=NULL, lease_expires_at=NULL,
                        retry_count=retry_count+1,
                        finished_at=CASE WHEN ? THEN ? ELSE NULL END
                    WHERE job_id=?
                    """,
                    (
                        status["status"],
                        _json(status),
                        int(cancelled),
                        now,
                        row["job_id"],
                    ),
                )
                if row["assigned_agent_id"]:
                    connection.execute(
                        """
                        UPDATE agents SET current_job_id=NULL, status='offline'
                        WHERE agent_id=? AND current_job_id=?
                        """,
                        (row["assigned_agent_id"], row["job_id"]),
                    )
                recovered.append(str(row["job_id"]))
        return recovered

    def claim_job(self, agent_id: str, lease_seconds: int = 120, *, authorization=None) -> dict[str, Any] | None:
        from .device_agent_queue import require_decision, require_assignment
        from .device_agent_protocol import fail
        from .device_local_execution import render_operation_scopes

        if authorization is not None:
            require_decision(authorization, "execute")
        self.recover_expired_leases()
        now = _now()
        lease_expires_at = _future(lease_seconds)
        with self._transaction() as connection:
            if authorization is not None:
                require_decision(authorization, "execute")
                from .device_agent_operations import require_agent_binding
                require_agent_binding(connection, agent_id, authorization)
            agent = connection.execute(
                "SELECT current_job_id FROM agents WHERE agent_id=?", (agent_id,)
            ).fetchone()
            if agent is None:
                raise KeyError(f"处理机没有注册: {agent_id}")
            if agent["current_job_id"]:
                row = connection.execute(
                    "SELECT * FROM jobs WHERE job_id=?", (agent["current_job_id"],)
                ).fetchone()
                if row is not None and authorization is not None:
                    status = _object(row["status_json"], {})
                    require_assignment(status, authorization)
                    if status.get("agent_recovery_required") and status.get("agent_execution"):
                        fail("DEVICE_AGENT_EXECUTION_UNCERTAIN", "原处理任务状态待确认，未重复分配", 409)
                    if not render_operation_scopes(_object(row["payload_json"], {})) <= authorization.scopes:
                        fail("DEVICE_SCOPE_DENIED", "此执行机当前没有原任务所需权限")
                    if status.get("agent_recovery_required"):
                        # No durable start receipt exists: the compliant Agent
                        # has not been authorized to invoke its renderer yet.
                        status.pop("agent_recovery_required", None)
                        status.pop("recovery_reason", None)
                        status.update(heartbeat_at=now, lease_expires_at=lease_expires_at)
                        connection.execute("UPDATE jobs SET status_json=?,heartbeat_at=?,lease_expires_at=? WHERE job_id=?",
                                           (_json(status), now, lease_expires_at, row["job_id"]))
                        row = dict(row)
                        row.update(status_json=_json(status), lease_expires_at=lease_expires_at)
                return self._job_claim_dict(row) if row is not None else None

            if authorization is not None and authorization.thumbprint is not None:
                busy = connection.execute(
                    "SELECT 1 FROM jobs WHERE status='running' AND json_extract(status_json, '$.agent_device_authorization.thumbprint')=? LIMIT 1",
                    (authorization.thumbprint,),
                ).fetchone()
                if busy is not None:
                    # Several labels/accounts must not give one physical key
                    # concurrent render slots in the same central queue.
                    return None

            row = connection.execute(
                """
                SELECT * FROM jobs
                WHERE status='pending' AND cancel_requested=0
                  AND COALESCE(json_extract(status_json, '$.device_authorization.waiting'), 0)=0
                  AND json_type(status_json, '$.agent_device_authorization') IS NULL
                ORDER BY queued_at, created_at, rowid
                LIMIT 1
                """
            ).fetchone()
            if authorization is not None:
                # Only server-recorded owners count. Legacy/unowned jobs and
                # user_id fields inside the job payload are never guessed.
                candidates = connection.execute(
                    "SELECT * FROM jobs WHERE status='pending' AND cancel_requested=0 "
                    "AND COALESCE(json_extract(status_json, '$.device_authorization.waiting'), 0)=0 "
                    "AND json_type(status_json, '$.agent_device_authorization') IS NULL "
                    "AND json_type(status_json, '$.device_authorization.user_id')='integer' "
                    "AND json_extract(status_json, '$.device_authorization.user_id')=? "
                    "ORDER BY queued_at, created_at, rowid",
                    (authorization.user_id,),
                )
                row = next((candidate for candidate in candidates
                            if render_operation_scopes(_object(candidate["payload_json"], {})) <= authorization.scopes), None)
            if row is None:
                connection.execute(
                    "UPDATE agents SET status='idle', last_heartbeat_at=? WHERE agent_id=?",
                    (now, agent_id),
                )
                return None

            status = _object(row["status_json"], {})
            if authorization is not None:
                status["agent_device_authorization"] = authorization.snapshot()
            status.update(
                {
                    "status": "running",
                    "assigned_agent_id": agent_id,
                    "started_at": now,
                    "heartbeat_at": now,
                    "lease_expires_at": lease_expires_at,
                }
            )
            connection.execute(
                """
                UPDATE jobs SET
                    status='running', status_json=?, assigned_agent_id=?,
                    started_at=?, heartbeat_at=?, lease_expires_at=?
                WHERE job_id=? AND status='pending'
                """,
                (_json(status), agent_id, now, now, lease_expires_at, row["job_id"]),
            )
            connection.execute(
                """
                UPDATE agents SET status='busy', current_job_id=?, last_heartbeat_at=?
                WHERE agent_id=?
                """,
                (row["job_id"], now, agent_id),
            )
            claimed = dict(row)
            claimed.update(
                {
                    "status": "running",
                    "status_json": _json(status),
                    "assigned_agent_id": agent_id,
                    "started_at": now,
                    "heartbeat_at": now,
                    "lease_expires_at": lease_expires_at,
                }
            )
        return self._job_claim_dict(claimed)

    @staticmethod
    def _job_claim_dict(row: sqlite3.Row | dict[str, Any]) -> dict[str, Any]:
        return {
            "job_id": row["job_id"],
            "batch_id": row["batch_id"],
            "payload": _object(row["payload_json"], {}),
            "status": _object(row["status_json"], {}),
            "assigned_agent_id": row["assigned_agent_id"],
            "lease_expires_at": row["lease_expires_at"],
        }

    def heartbeat_job(
        self,
        agent_id: str,
        job_id: str,
        data: dict[str, Any],
        lease_seconds: int = 120,
    ) -> dict[str, Any]:
        now = _now()
        lease_expires_at = _future(lease_seconds)
        with self._transaction() as connection:
            row = connection.execute(
                "SELECT status_json FROM jobs WHERE job_id=? AND assigned_agent_id=?",
                (job_id, agent_id),
            ).fetchone()
            if row is None:
                raise KeyError("任务没有分配给当前处理机")
            status = _object(row["status_json"], {})
            status.update(
                {
                    "heartbeat_at": now,
                    "lease_expires_at": lease_expires_at,
                }
            )
            for key in ("progress", "message", "stage"):
                if key in data:
                    status[key] = data[key]
            connection.execute(
                """
                UPDATE jobs SET status_json=?, heartbeat_at=?, lease_expires_at=?
                WHERE job_id=? AND status='running'
                """,
                (_json(status), now, lease_expires_at, job_id),
            )
            connection.execute(
                "UPDATE agents SET last_heartbeat_at=?, status='busy' WHERE agent_id=?",
                (now, agent_id),
            )
        return status

    def finish_job(
        self,
        agent_id: str,
        job_id: str,
        *,
        result: dict[str, Any] | None = None,
        error: str = "",
    ) -> dict[str, Any]:
        now = _now()
        terminal = "completed" if result is not None else "failed"
        with self._transaction() as connection:
            row = connection.execute(
                "SELECT status_json FROM jobs WHERE job_id=? AND assigned_agent_id=?",
                (job_id, agent_id),
            ).fetchone()
            if row is None:
                raise KeyError("任务没有分配给当前处理机")
            status = _object(row["status_json"], {})
            status.update({"status": terminal, "finished_at": now})
            status.pop("lease_expires_at", None)
            if result is not None:
                status["result"] = result
                status.pop("error", None)
            else:
                status["error"] = error or "处理机报告任务失败"
            connection.execute(
                """
                UPDATE jobs SET
                    status=?, status_json=?, finished_at=?, heartbeat_at=?,
                    lease_expires_at=NULL, error=?, result_json=?
                WHERE job_id=?
                """,
                (
                    terminal,
                    _json(status),
                    now,
                    now,
                    status.get("error", ""),
                    _json(result) if result is not None else None,
                    job_id,
                ),
            )
            connection.execute(
                """
                UPDATE agents SET status='idle', current_job_id=NULL,
                    last_heartbeat_at=?
                WHERE agent_id=? AND current_job_id=?
                """,
                (now, agent_id, job_id),
            )
        return status

    def device_waiting_jobs(self, user_id: int) -> list[dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT job_id, created_at, status_json FROM jobs WHERE status='pending' AND cancel_requested=0 "
                "AND json_extract(status_json, '$.device_authorization.waiting')=1 "
                "AND json_extract(status_json, '$.device_authorization.user_id')=? ORDER BY created_at, rowid LIMIT 100", (user_id,)
            ).fetchall()
        return [{"job_id": row["job_id"], "created_at": row["created_at"],
                 "code": (_object(row["status_json"], {}).get("device_authorization") or {}).get("code", "AUTH_REFRESH_REQUIRED")}
                for row in rows]

    def get_job_payload(self, job_id: str) -> dict[str, Any]:
        with self._connect() as connection:
            row = connection.execute("SELECT payload_json FROM jobs WHERE job_id=?", (job_id,)).fetchone()
        if row is None:
            raise KeyError("任务不存在")
        return _object(row["payload_json"], {})

    def pause_for_device_authorization(self, job_id: str, code: str) -> dict[str, Any]:
        with self._transaction() as connection:
            row = connection.execute("SELECT status_json, assigned_agent_id, status, cancel_requested FROM jobs WHERE job_id=?", (job_id,)).fetchone()
            if row is None:
                raise KeyError("任务不存在")
            status = _object(row["status_json"], {})
            if row["status"] not in {"running", "pending"}:
                return status
            binding = dict(status.get("device_authorization") or {})
            binding.update({"waiting": True, "code": code, "checked_at": _now()})
            status.update({"status": "cancelled" if row["cancel_requested"] else "pending", "device_authorization": binding})
            for field in ("assigned_agent_id", "started_at", "heartbeat_at", "lease_expires_at"):
                status.pop(field, None)
            connection.execute("UPDATE jobs SET status=?, status_json=?, assigned_agent_id=NULL, started_at=NULL, heartbeat_at=NULL, lease_expires_at=NULL WHERE job_id=?",
                               (status["status"], _json(status), job_id))
            connection.execute("UPDATE agents SET status='idle', current_job_id=NULL WHERE agent_id=? AND current_job_id=?", (row["assigned_agent_id"], job_id))
        return status

    def resume_device_authorization(self, job_id, user_id, binding):
        with self._transaction() as connection:
            row = connection.execute("SELECT status, cancel_requested, status_json FROM jobs WHERE job_id=?", (job_id,)).fetchone()
            if row is None:
                raise KeyError("任务不存在")
            status = _object(row["status_json"], {})
            original = status.get("device_authorization") or {}
            if original.get("user_id") != user_id or binding.get("user_id") != user_id:
                raise PermissionError("无权恢复该任务的设备授权")
            if row["status"] != "pending" or row["cancel_requested"] or not original.get("waiting"):
                raise ValueError("此任务不在等待授权状态")
            status["device_authorization"] = binding
            connection.execute("UPDATE jobs SET status_json=? WHERE job_id=?", (_json(status), job_id))
        return status

    def get_status(self, job_id: str) -> dict[str, Any] | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT status_json, retry_count, cancel_requested FROM jobs WHERE job_id=?",
                (job_id,),
            ).fetchone()
        if row is None:
            return None
        status = _object(row["status_json"], {})
        status["retry_count"] = int(row["retry_count"])
        status["cancel_requested"] = bool(row["cancel_requested"])
        return status

    def set_status(self, job_id: str, status: dict[str, Any]) -> None:
        current = str(status.get("status") or "failed")
        result = status.get("result") if isinstance(status.get("result"), dict) else None
        error = str(status.get("error") or "")
        with self._connect() as connection:
            cursor = connection.execute(
                """
                UPDATE jobs SET status=?, status_json=?, error=?, result_json=?,
                    assigned_agent_id=?, started_at=?, finished_at=?,
                    heartbeat_at=?, lease_expires_at=?,
                    cancel_requested=?
                WHERE job_id=?
                """,
                (
                    current,
                    _json(status),
                    error,
                    _json(result) if result is not None else None,
                    status.get("assigned_agent_id"),
                    status.get("started_at"),
                    status.get("finished_at"),
                    status.get("heartbeat_at"),
                    status.get("lease_expires_at"),
                    int(bool(status.get("cancel_requested", False))),
                    job_id,
                ),
            )
            if not cursor.rowcount:
                raise KeyError(f"任务不存在: {job_id}")

    def pending_job_ids(self) -> list[str]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT job_id FROM jobs WHERE status='pending' ORDER BY queued_at, created_at, rowid"
            ).fetchall()
        return [str(row["job_id"]) for row in rows]

    def pending_count(self) -> int:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT COUNT(*) AS count FROM jobs WHERE status='pending'"
            ).fetchone()
        return int(row["count"])

    def active_count(self) -> int:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT COUNT(*) AS count FROM jobs WHERE status IN ('pending', 'running')"
            ).fetchone()
        return int(row["count"])

    def queue_position(self, job_id: str) -> int | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT status, queued_at, created_at, rowid AS queue_seq FROM jobs WHERE job_id=?",
                (job_id,),
            ).fetchone()
            if row is None or row["status"] != "pending":
                return None
            before = connection.execute(
                """
                SELECT COUNT(*) AS count FROM jobs
                WHERE status='pending'
                  AND (
                    queued_at < ?
                    OR (queued_at = ? AND created_at < ?)
                    OR (queued_at = ? AND created_at = ? AND rowid <= ?)
                  )
                """,
                (
                    row["queued_at"],
                    row["queued_at"],
                    row["created_at"],
                    row["queued_at"],
                    row["created_at"],
                    row["queue_seq"],
                ),
            ).fetchone()
        return int(before["count"])

    def cancel_batch(self, batch_id: str) -> list[str]:
        now = _now()
        cancelled: list[str] = []
        with self._transaction() as connection:
            rows = connection.execute(
                "SELECT job_id, status, status_json FROM jobs WHERE batch_id=?",
                (batch_id,),
            ).fetchall()
            for row in rows:
                status = _object(row["status_json"], {})
                unstarted_agent = row["status"] == "running" and bool(status.get("agent_device_authorization")) and not status.get("agent_execution")
                if row["status"] == "pending" or unstarted_agent:
                    status.update(
                        {
                            "status": "cancelled",
                            "cancel_requested": True,
                            "finished_at": now,
                            "error": "用户取消了尚未开始的任务",
                        }
                    )
                    connection.execute(
                        """
                        UPDATE jobs SET status='cancelled', status_json=?,
                            cancel_requested=1, finished_at=? WHERE job_id=?
                        """,
                        (_json(status), now, row["job_id"]),
                    )
                    cancelled.append(str(row["job_id"]))
                    if unstarted_agent:
                        connection.execute("UPDATE agents SET current_job_id=NULL,status='idle' WHERE current_job_id=?", (row["job_id"],))
                elif row["status"] == "running":
                    connection.execute(
                        "UPDATE jobs SET cancel_requested=1 WHERE job_id=?",
                        (row["job_id"],),
                    )
        return cancelled

    def delete_job(self, job_id: str) -> None:
        with self._connect() as connection:
            connection.execute("DELETE FROM jobs WHERE job_id=?", (job_id,))

    def delete_batch(self, batch_id: str) -> None:
        with self._transaction() as connection:
            connection.execute("DELETE FROM jobs WHERE batch_id=?", (batch_id,))
            connection.execute("DELETE FROM batches WHERE batch_id=?", (batch_id,))
