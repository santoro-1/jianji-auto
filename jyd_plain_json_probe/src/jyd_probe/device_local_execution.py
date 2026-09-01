"""Actual local execution boundary, independent of the Pu launcher or web UI.

Context is internal to the process, never accepted from a job's JSON. Every new
unit checks the live authorizer; nested steps of an admitted unit can finish.
"""

from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from functools import wraps
import sys

from .device_auth_protocol import DeviceAuthorizationError
from .device_identity_windows import DeviceIdentityError

_SCOPES = frozenset({"local:draft", "local:render"})
_authorizer = ContextVar("workbench_local_authorizer", default=None)
_unit = ContextVar("workbench_local_unit", default=None)


def requires_device_authorization():
    from .device_trust_roots import TRUSTED_ISSUERS

    # No editable JSON/env switch. Empty-trust source trees are development only;
    # every frozen/private binary fails closed without configured release trust.
    return bool(getattr(sys, "frozen", False) or TRUSTED_ISSUERS)


@dataclass(frozen=True)
class LocalDecision:
    user_id: int
    mode: str
    scopes: frozenset[str]
    device_id: str | None = None
    grant_id: str | None = None
    thumbprint: str | None = None
    grant_revision: int | None = None
    policy_revision: int | None = None

    def snapshot(self):
        return {
            "schema": "publicvideo.local-operation.v1",
            "user_id": self.user_id,
            "mode": self.mode,
            "scopes": sorted(self.scopes),
            "device_id": self.device_id,
            "grant_id": self.grant_id,
            "thumbprint": self.thumbprint,
            "grant_revision": self.grant_revision,
            "policy_revision": self.policy_revision,
            "waiting": False,
        }


def current_local_authorizer():
    return _authorizer.get()


def render_operation_scopes(data):
    source = data.get("source") if isinstance(data.get("source"), dict) else {}
    kind = (
        str(
            source.get("type")
            or source.get("kind")
            or data.get("source_kind")
            or "auto"
        )
        .replace("_", "-")
        .lower()
    )
    if kind == "existing-draft":
        # This path always exports; discovery recovery can also create a new draft.
        return _SCOPES
    output = data.get("output") if isinstance(data.get("output"), dict) else {}
    export = data.get("export") if isinstance(data.get("export"), dict) else {}
    skip = output.get(
        "skip_export", data.get("skip_export", export.get("skip_export", False))
    )
    # Match render_job's accepted truthy values; never infer from a client scope.
    skip = (
        skip.strip().lower() not in {"", "0", "false", "no", "off"}
        if isinstance(skip, str)
        else bool(skip)
    )
    return frozenset({"local:draft"} if skip else _SCOPES)


class LocalDeviceAuthorizer:
    def __init__(self, session):
        self.session = session

    def authorize(self, scopes):
        # All requested scopes must belong to one coherent credential revision.
        # Session refreshes in another request cannot change grants mid-decision.
        with self.session._lock:
            return self._authorize_locked(scopes)

    def _authorize_locked(self, scopes):
        scopes = frozenset(scopes)
        if not scopes or not scopes <= _SCOPES:
            raise ValueError("invalid local operation scopes")
        mode = self.session.local_policy_mode()
        binding = None
        if mode in {"OBSERVE", "ENFORCE"}:
            try:
                for scope in sorted(scopes):
                    binding = self.session.require_local(scope)
            except (DeviceAuthorizationError, DeviceIdentityError):
                if mode == "ENFORCE":
                    raise
                binding = None
        elif mode != "OFF":
            raise DeviceAuthorizationError(
                "INVALID_DEVICE_LOCAL_POLICY", "本地授权模式无效"
            )
        binding = binding or {}
        summary = self.session.summary() if binding else {}
        return LocalDecision(
            self.session.user_id,
            mode,
            scopes,
            device_id=binding.get("device_id"),
            grant_id=binding.get("grant_id"),
            thumbprint=summary.get("thumbprint"),
            grant_revision=binding.get("grant_revision"),
            policy_revision=binding.get("policy_revision"),
        )


@contextmanager
def local_authorization_context(authorizer):
    token = _authorizer.set(authorizer)
    old_unit = _unit.set(None)
    try:
        yield
    finally:
        _unit.reset(old_unit)
        _authorizer.reset(token)


def current_local_decision(scopes):
    scopes = frozenset(scopes)
    if not scopes or not scopes <= _SCOPES:
        raise ValueError("invalid local operation scopes")
    if not requires_device_authorization():
        return None
    authorizer = _authorizer.get()
    if authorizer is None:
        raise DeviceAuthorizationError(
            "DEVICE_LOCAL_CONTEXT_REQUIRED",
            "请从已登录并获准的工作台启动本地任务",
            status_code=409,
        )
    decision = authorizer.authorize(scopes)
    if (
        not isinstance(decision, LocalDecision)
        or type(decision.user_id) is not int
        or decision.scopes != scopes
        or decision.user_id < 1
    ):
        raise DeviceAuthorizationError(
            "DEVICE_LOCAL_CONTEXT_INVALID", "本地执行授权上下文无效", status_code=409
        )
    return decision


@contextmanager
def authorized_local_unit(scopes):
    scopes = frozenset(scopes)
    existing = _unit.get()
    if existing is not None:
        if not scopes <= existing.scopes:
            raise DeviceAuthorizationError(
                "DEVICE_SCOPE_DENIED", "此执行单元未获得该本地功能权限"
            )
        yield existing
        return
    decision = current_local_decision(scopes)
    token = _unit.set(decision)
    try:
        yield decision
    finally:
        _unit.reset(token)


def protected_local_work(scopes):
    def decorate(function):
        @wraps(function)
        def execute(*args, **kwargs):
            required = scopes(*args, **kwargs) if callable(scopes) else scopes
            with authorized_local_unit(required):
                return function(*args, **kwargs)

        return execute

    return decorate
