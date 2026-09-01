"""Local activation surface. Accounts come from the existing website session.

Never accepts a device key, device ID, trust root, approval flag, or signing input
from the browser. These routes manage activation, not business enforcement.
"""

from __future__ import annotations

from collections import OrderedDict
import hashlib
import threading
from typing import Any, Callable
from urllib.parse import urlsplit

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, StrictBool

from .device_auth_protocol import DeviceAuthorizationError, bundled_trust
from .device_authorization import DeviceAuthorizationSession, DeviceLeaseCache
from .device_identity_windows import DeviceIdentityError
from .device_identity_setup import (
    InteractiveWindowsDeviceIdentity as WindowsDeviceIdentity,
)


class DeviceSessionRegistry:
    def __init__(self, base_url: str, *, session_factory=None):
        self.base_url = base_url
        self._factory = session_factory
        self._lock = threading.RLock()
        self._sessions = OrderedDict()
        from .device_background_refresh import DeviceBackgroundRefresher

        self._background = DeviceBackgroundRefresher(self.active_sessions)

    def active_sessions(self):
        with self._lock:
            return tuple(self._sessions.values())

    def start_background(self):
        self._background.start()

    def get(self, user_id: str, token: str) -> DeviceAuthorizationSession:
        try:
            numeric_id = int(user_id)
            if str(numeric_id) != user_id or numeric_id < 1 or not token:
                raise ValueError()
        except (TypeError, ValueError) as exc:
            raise DeviceAuthorizationError(
                "LOGIN_REQUIRED", "请使用数字人网站账号登录", status_code=401
            ) from exc
        identity = (numeric_id, hashlib.sha256(token.encode("utf-8")).hexdigest())
        with self._lock:
            if identity in self._sessions:
                self._sessions.move_to_end(identity)
                return self._sessions[identity]
            if self._factory is not None:
                session = self._factory(user_id=numeric_id, login_token=token)
            else:
                trust = bundled_trust(self.base_url)  # no configurable trust-file path
                session = DeviceAuthorizationSession(
                    user_id=numeric_id,
                    login_token=token,
                    trust=trust,
                    identity=WindowsDeviceIdentity(),
                    cache=DeviceLeaseCache.for_machine(),
                )
            self._sessions[identity] = session
            while len(self._sessions) > 128:
                _, oldest = self._sessions.popitem(last=False)
                oldest.close()  # closes only handles, never deletes the machine key
            return session

    def forget(self, token: str) -> None:
        digest = hashlib.sha256(token.encode("utf-8")).hexdigest()
        with self._lock:
            for identity in list(self._sessions):
                if identity[1] == digest:
                    self._sessions.pop(identity).close()

    def close(self) -> None:
        self._background.stop()
        with self._lock:
            for session in self._sessions.values():
                session.close()
            self._sessions.clear()


class DeviceApplication(BaseModel):
    model_config = ConfigDict(extra="forbid")
    label: str = Field(default="", max_length=80)
    client_version: str = Field(default="", max_length=80)
    confirm_initialize: StrictBool = False


class DeviceAccessRepair(BaseModel):
    model_config = ConfigDict(extra="forbid")
    confirm_repair: StrictBool = False


class DeviceSoftwareApplication(DeviceApplication):
    confirm_software: StrictBool = False


def _same_origin_action(request: Request) -> None:
    origin = request.headers.get("origin", "")
    try:
        supplied = urlsplit(origin)
        expected = urlsplit(str(request.base_url))
    except ValueError as exc:
        raise HTTPException(status_code=403, detail="设备授权请求来源无效") from exc
    if (
        not origin
        or supplied.scheme not in {"http", "https"}
        or supplied.scheme != expected.scheme
        or supplied.netloc.lower() != expected.netloc.lower()
        or supplied.path
        or supplied.query
        or supplied.fragment
        or supplied.username is not None
        or request.headers.get("x-device-authorization-action") != "1"
    ):
        raise HTTPException(
            status_code=403, detail="设备授权操作必须从当前工作台页面发起"
        )


def install_device_authorization_routes(
    app: FastAPI,
    *,
    base_url: str,
    cookie_name: str,
    current_user: Callable[[Request], dict[str, Any]],
    registry: DeviceSessionRegistry | None = None,
) -> None:
    registry = registry if registry is not None else DeviceSessionRegistry(base_url)
    app.state.device_sessions = registry

    def session_for(request):
        user = current_user(request)  # local technical admin alone is insufficient
        return registry.get(
            str(user.get("user_id") or ""), request.cookies.get(cookie_name, "")
        )

    def response(payload: dict, status_code: int = 200):
        return JSONResponse(
            payload,
            status_code=status_code,
            headers={"Cache-Control": "no-store", "Pragma": "no-cache"},
        )

    def failure(error, session=None):
        status = (
            error.status_code if isinstance(error, DeviceAuthorizationError) else 409
        )
        states = {
            "DEVICE_UNREGISTERED": "UNREGISTERED",
            "DEVICE_PENDING": "PENDING",
            "DEVICE_REJECTED": "REJECTED",
            "DEVICE_REVOKED": "REVOKED",
            "DEVICE_SUSPENDED": "SUSPENDED",
            "DEVICE_GRANT_EXPIRED": "EXPIRED",
            "CLIENT_UPGRADE_REQUIRED": "CLIENT_UPGRADE_REQUIRED",
            "LOGIN_REQUIRED": "LOGIN_REQUIRED",
        }
        state = (
            (
                "KEY_INITIALIZING"
                if error.code == "KEY_SETUP_IN_PROGRESS"
                else "KEY_UNAVAILABLE"
            )
            if isinstance(error, DeviceIdentityError)
            else states.get(error.code, "AUTH_REFRESH_REQUIRED")
        )
        payload = {"state": state, "code": error.code, "detail": str(error)}
        if (
            session is not None
            and isinstance(error, DeviceAuthorizationError)
            and error.transient
        ):
            summary = session.summary()
            # Only the session's already-valid signed lease can indicate grace.
            # Do not convert an expired lease or an ordinary server error to ACTIVE.
            if summary.get("state") == "OFFLINE_GRACE":
                payload.update(summary)
        return response(payload, status)

    @app.get("/api/new/device-authorization")
    def device_authorization_status(request: Request):
        session = None
        try:
            session = session_for(request)
            try:
                session.status()
            except DeviceAuthorizationError as exc:
                if exc.code != "DEVICE_UNREGISTERED":
                    raise
            return response(session.summary())
        except (DeviceAuthorizationError, DeviceIdentityError) as exc:
            return failure(exc, session)

    @app.post("/api/new/device-authorization/apply")
    def apply_device_authorization(request: Request, payload: DeviceApplication):
        _same_origin_action(request)
        if payload.confirm_initialize is not True:
            raise HTTPException(
                status_code=422, detail="请先确认在当前处理机上申请设备授权"
            )
        try:
            session = session_for(request)
            session.register(label=payload.label, client_version=payload.client_version)
            return response(session.summary())
        except (DeviceAuthorizationError, DeviceIdentityError) as exc:
            return failure(exc)

    @app.post("/api/new/device-authorization/apply-software")
    def apply_software_device_authorization(
        request: Request, payload: DeviceSoftwareApplication
    ):
        _same_origin_action(request)
        if (
            payload.confirm_initialize is not True
            or payload.confirm_software is not True
        ):
            raise HTTPException(
                status_code=422, detail="请确认首次初始化及软件保护兼容模式"
            )
        try:
            session = session_for(request)
            session.register_software(
                label=payload.label, client_version=payload.client_version
            )
            return response(session.summary())
        except (DeviceAuthorizationError, DeviceIdentityError) as exc:
            return failure(exc)

    @app.post("/api/new/device-authorization/refresh")
    def refresh_device_authorization(request: Request):
        _same_origin_action(request)
        session = None
        try:
            session = session_for(request)
            return response(session.refresh(force=True))
        except (DeviceAuthorizationError, DeviceIdentityError) as exc:
            return failure(exc, session)

    @app.post("/api/new/device-authorization/repair-key-access")
    def repair_device_key_access(request: Request, payload: DeviceAccessRepair):
        _same_origin_action(request)
        if payload.confirm_repair is not True:
            raise HTTPException(
                status_code=422, detail="请确认只修复原设备密钥的访问权限"
            )
        session = None
        try:
            session = session_for(request)
            return response(session.repair_key_access())
        except (DeviceAuthorizationError, DeviceIdentityError) as exc:
            return failure(exc, session)

    @app.on_event("shutdown")
    def close_device_sessions():
        registry.close()

    @app.on_event("startup")
    def start_device_refresh():
        registry.start_background()
