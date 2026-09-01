"""Durable central-queue challenge consumption; credentials never enter jobs."""

from __future__ import annotations

import secrets
import time

from .device_agent_protocol import fail, verify_agent_permit, verify_agent_request_proof
from .device_auth_protocol import bundled_trust, sha256_b64


class AgentAuthorizationGate:
    def __init__(
        self,
        store,
        authority_url,
        *,
        trust_resolver=bundled_trust,
        clock=time.time,
        monotonic_clock=time.monotonic,
    ):
        self.store, self.authority_url = store, authority_url
        self.trust_resolver, self.clock = trust_resolver, clock
        self.monotonic_clock = monotonic_clock
        self._anchor_wall, self._anchor_mono = clock(), monotonic_clock()
        with store._transaction() as db:
            db.execute(
                """CREATE TABLE IF NOT EXISTS device_agent_challenges (
                nonce_hash TEXT PRIMARY KEY, agent_id TEXT NOT NULL, context_hash TEXT NOT NULL,
                expires_at INTEGER NOT NULL, consumed INTEGER NOT NULL DEFAULT 0)"""
            )
            db.execute(
                "CREATE INDEX IF NOT EXISTS idx_device_agent_challenge_expiry ON device_agent_challenges(expires_at)"
            )
            # Challenges belong to one central process lifetime. After restart,
            # require a new nonce/online permit instead of trusting old wall time.
            db.execute("UPDATE device_agent_challenges SET consumed=1 WHERE consumed=0")

    def _now(self):
        wall, elapsed = self.clock(), self.monotonic_clock() - self._anchor_mono
        if elapsed < 0 or abs(wall - self._anchor_wall - elapsed) > 5:
            fail(
                "DEVICE_AGENT_CLOCK_ERROR",
                "中央服务时间发生异常，请校准后重启服务",
                409,
            )
        return int(wall)

    def challenge(self, context):
        self.trust_resolver(
            self.authority_url
        )  # Missing roots fail before issuing a challenge.
        now = self._now()
        nonce = secrets.token_urlsafe(32)
        with self.store._transaction() as db:
            db.execute(
                "DELETE FROM device_agent_challenges WHERE expires_at <= ?", (now,)
            )
            if (
                db.execute("SELECT COUNT(*) FROM device_agent_challenges").fetchone()[0]
                >= 4096
            ):
                fail("AGENT_CHALLENGE_BUSY", "处理机验证请求过多，请稍后重试", 429)
            count = db.execute(
                "SELECT COUNT(*) FROM device_agent_challenges WHERE agent_id=? AND consumed=0",
                (context.agent_id,),
            ).fetchone()[0]
            if count >= 16:
                fail("AGENT_CHALLENGE_BUSY", "此处理机验证请求过多，请稍后重试", 429)
            db.execute(
                "INSERT INTO device_agent_challenges(nonce_hash,agent_id,context_hash,expires_at) VALUES(?,?,?,?)",
                (sha256_b64(nonce), context.agent_id, context.digest, now + 120),
            )
        return {
            "schema": "publicvideo.agent-challenge.v1",
            "nonce": nonce,
            "expires_in": 120,
        }

    def verify(self, context, *, permit, proof):
        now = self._now()
        decision = verify_agent_permit(
            self.trust_resolver(self.authority_url), permit, context, now=now
        )
        verify_agent_request_proof(permit, proof, context, decision, now=now)
        with self.store._transaction() as db:
            now = self._now()
            if decision.expires_at <= now:
                fail("AGENT_PERMIT_EXPIRED", "处理机许可已过期，请重新验证", 409)
            updated = db.execute(
                "UPDATE device_agent_challenges SET consumed=1 WHERE nonce_hash=? AND agent_id=? "
                "AND context_hash=? AND expires_at>? AND consumed=0",
                (sha256_b64(decision.nonce), context.agent_id, context.digest, now),
            )
            if updated.rowcount != 1:
                fail(
                    "AGENT_PROOF_REPLAYED", "处理机挑战已失效或已使用，请重新验证", 409
                )
        return decision
