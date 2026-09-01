"""Durable local execution receipts without login tokens or device credentials."""

from __future__ import annotations

from contextlib import contextmanager
import os
from pathlib import Path
import sqlite3
import time
import uuid

from .device_agent_protocol import fail
from .device_auth_protocol import canonical_json, sha256_b64, strict_json


class AgentJournal:
    def __init__(self, root):
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.path = self.root / "execution-receipts.sqlite3"
        with self._connect() as connection:
            connection.execute("PRAGMA journal_mode=WAL")
            connection.execute(
                "CREATE TABLE IF NOT EXISTS receipts(receipt_id TEXT PRIMARY KEY,central TEXT NOT NULL,"
                "agent_id TEXT NOT NULL,user_id INTEGER NOT NULL,job_id TEXT NOT NULL,execution_id TEXT NOT NULL,"
                "phase TEXT NOT NULL,claim_json TEXT NOT NULL,payload_json TEXT NOT NULL,result_json TEXT,updated_at INTEGER NOT NULL)"
            )
            connection.execute(
                "CREATE TABLE IF NOT EXISTS recovery_audit(request_id TEXT PRIMARY KEY,receipt_id TEXT NOT NULL,request_json TEXT NOT NULL,created_at INTEGER NOT NULL,acknowledged_at INTEGER)"
            )

    @contextmanager
    def _connect(self):
        connection = sqlite3.connect(self.path, timeout=10)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA synchronous=FULL")
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    @contextmanager
    def single_process(self):
        # Fixed per-Windows-user runtime location, independent of the EXE path or
        # central/account selection; two Agents must not control one UI at once.
        with (self.root / "execution.lock").open("a+b") as lock:
            if lock.seek(0, 2) == 0:
                lock.write(b"0")
                lock.flush()
            lock.seek(0)
            acquired = False
            try:
                if os.name == "nt":
                    import msvcrt

                    msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
                else:
                    import fcntl

                    fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                acquired = True
            except OSError:
                fail(
                    "DEVICE_AGENT_ALREADY_RUNNING",
                    "本机已有处理机执行进程，请勿重复启动",
                    409,
                )
            try:
                yield
            finally:
                if acquired:
                    lock.seek(0)
                    if os.name == "nt":
                        msvcrt.locking(lock.fileno(), msvcrt.LK_UNLCK, 1)
                    else:
                        fcntl.flock(lock.fileno(), fcntl.LOCK_UN)

    @staticmethod
    def _record(row):
        value = dict(row)
        for name in ("claim", "payload", "result"):
            raw = value.pop(name + "_json")
            value[name] = strict_json(raw) if raw is not None else None
        return value

    def cancel_prepared(self, receipt):
        with self._connect() as connection:
            cursor = connection.execute(
                "UPDATE receipts SET phase='acknowledged',updated_at=? WHERE receipt_id=? AND phase='prepared'",
                (int(time.time()), receipt["receipt_id"]),
            )
            if cursor.rowcount != 1:
                fail("DEVICE_AGENT_RECEIPT_CONFLICT", "取消回执不属于未启动的任务", 409)
        receipt["phase"] = "acknowledged"

    def pending(self, central, agent_id, user_id):
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM receipts WHERE central=? AND agent_id=? AND user_id=? AND phase!='acknowledged' ORDER BY updated_at,receipt_id",
                (central, agent_id, user_id),
            ).fetchall()
        return [self._record(row) for row in rows]

    def has_unresolved_execution(self):
        with self._connect() as connection:
            return (
                connection.execute(
                    "SELECT 1 FROM receipts WHERE phase IN ('executing','recovery_pending') LIMIT 1"
                ).fetchone()
                is not None
            )

    def prepare(self, central, agent_id, user_id, claim, payload):
        job_id = claim["job_id"]
        key = sha256_b64(canonical_json([central, agent_id, user_id, job_id]))
        encoded_claim, encoded_payload = canonical_json(claim), canonical_json(payload)
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT * FROM receipts WHERE receipt_id=?", (key,)
            ).fetchone()
            if row is None:
                connection.execute(
                    "INSERT INTO receipts VALUES(?,?,?,?,?,?,'prepared',?,?,NULL,?)",
                    (
                        key,
                        central,
                        agent_id,
                        user_id,
                        job_id,
                        uuid.uuid4().hex,
                        encoded_claim,
                        encoded_payload,
                        int(time.time()),
                    ),
                )
                row = connection.execute(
                    "SELECT * FROM receipts WHERE receipt_id=?", (key,)
                ).fetchone()
            else:
                previous = self._record(row)
                if (
                    canonical_json(previous["claim"]["payload"])
                    != canonical_json(claim["payload"])
                    or row["payload_json"] != encoded_payload
                ):
                    fail(
                        "DEVICE_AGENT_RECEIPT_CONFLICT",
                        "原任务输入与执行回执不一致，未重复渲染",
                        409,
                    )
        return self._record(row)

    def executing(self, receipt):
        with self._connect() as connection:
            cursor = connection.execute(
                "UPDATE receipts SET phase='executing',updated_at=? WHERE receipt_id=? AND phase='prepared'",
                (int(time.time()), receipt["receipt_id"]),
            )
            if cursor.rowcount != 1:
                fail(
                    "DEVICE_AGENT_EXECUTION_UNCERTAIN",
                    "原任务不是可首次执行状态，未重复渲染",
                    409,
                )

    def save_result(self, receipt, *, action, payload):
        if action not in {"complete", "fail"}:
            raise ValueError("invalid report action")
        result = canonical_json({"action": action, "payload": payload})
        with self._connect() as connection:
            cursor = connection.execute(
                "UPDATE receipts SET phase='report_pending',result_json=?,updated_at=? WHERE receipt_id=? AND phase='executing'",
                (result, int(time.time()), receipt["receipt_id"]),
            )
            if cursor.rowcount != 1:
                fail(
                    "DEVICE_AGENT_RECEIPT_CONFLICT",
                    "无法保存原执行结果，请保留文件并核对",
                    409,
                )
        receipt.update(phase="report_pending", result=strict_json(result))

    def acknowledge(self, receipt):
        with self._connect() as connection:
            cursor = connection.execute(
                "UPDATE receipts SET phase='acknowledged',updated_at=? WHERE receipt_id=? AND phase='report_pending'",
                (int(time.time()), receipt["receipt_id"]),
            )
            if cursor.rowcount != 1:
                fail("DEVICE_AGENT_RECEIPT_CONFLICT", "原结果回报状态需要核对", 409)
        receipt["phase"] = "acknowledged"

    def begin_recovery(self, receipt, payload):
        encoded = canonical_json({"action": "recovery/resolve", "payload": payload})
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT * FROM receipts WHERE receipt_id=?", (receipt["receipt_id"],)
            ).fetchone()
            if (
                row is None
                or row["phase"] != "executing"
                or row["execution_id"] != payload["execution_id"]
                or self._record(row) != receipt
            ):
                fail("DEVICE_AGENT_REVIEW_CHANGED", "本机原回执已改变，请重新核实", 409)
            connection.execute(
                "INSERT INTO recovery_audit VALUES(?,?,?,?,NULL)",
                (
                    payload["request_id"],
                    receipt["receipt_id"],
                    canonical_json(payload),
                    int(time.time()),
                ),
            )
            connection.execute(
                "UPDATE receipts SET phase='recovery_pending',result_json=?,updated_at=? WHERE receipt_id=?",
                (encoded, int(time.time()), receipt["receipt_id"]),
            )
        receipt.update(phase="recovery_pending", result=strict_json(encoded))

    def acknowledge_recovery(self, receipt):
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            cursor = connection.execute(
                "UPDATE receipts SET phase='acknowledged',updated_at=? WHERE receipt_id=? AND phase='recovery_pending' AND execution_id=? AND result_json=?",
                (
                    int(time.time()),
                    receipt["receipt_id"],
                    receipt["execution_id"],
                    canonical_json(receipt["result"]),
                ),
            )
            if cursor.rowcount != 1:
                fail(
                    "DEVICE_AGENT_RECEIPT_CONFLICT", "核实回执已改变，未清除原记录", 409
                )
            connection.execute(
                "UPDATE recovery_audit SET acknowledged_at=? WHERE request_id=? AND receipt_id=?",
                (
                    int(time.time()),
                    receipt["result"]["payload"]["request_id"],
                    receipt["receipt_id"],
                ),
            )
        receipt["phase"] = "acknowledged"

    def reject_recovery(self, receipt):
        with self._connect() as connection:
            cursor = connection.execute(
                "UPDATE receipts SET phase='executing',result_json=NULL,updated_at=? WHERE receipt_id=? AND phase='recovery_pending' AND result_json=?",
                (
                    int(time.time()),
                    receipt["receipt_id"],
                    canonical_json(receipt["result"]),
                ),
            )
            if cursor.rowcount != 1:
                fail("DEVICE_AGENT_RECEIPT_CONFLICT", "原核实回执状态已改变", 409)
        receipt.update(phase="executing", result=None)
