"""Ownership checks for a cryptographically admitted Agent, never job input flags."""

from __future__ import annotations

import time

from .device_agent_protocol import AgentDecision, fail


def require_decision(decision, intent):
    if not isinstance(decision, AgentDecision) or decision.intent != intent:
        fail("DEVICE_AGENT_CONTEXT_REQUIRED", "缺少已验证的执行机授权", 409)
    if decision.expires_at <= time.time():
        fail("AGENT_PERMIT_EXPIRED", "处理机许可已过期，请重新验证", 409)
    return decision


def matches_assignment(status, decision):
    if not isinstance(status, dict):
        return False
    source = status.get("device_authorization") or {}
    binding = status.get("agent_device_authorization") or {}
    if not isinstance(source, dict) or not isinstance(binding, dict):
        return False
    return (
        type(source.get("user_id")) is int
        and source["user_id"] == decision.user_id
        and type(binding.get("user_id")) is int
        and binding["user_id"] == decision.user_id
        and binding.get("schema") == "publicvideo.agent-assignment.v1"
        and binding.get("thumbprint") == decision.thumbprint
        and (decision.thumbprint is not None or decision.mode in {"OFF", "OBSERVE"})
    )


def require_assignment(status, decision):
    if not matches_assignment(status, decision):
        fail("DEVICE_AGENT_ASSIGNMENT_MISMATCH", "原任务不属于此账号和执行机", 409)
