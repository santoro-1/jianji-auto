"""Attach this processor's proof to audited paid workbench contracts.

This is transport, not a local license gate. Without usable device credentials a
single account-only request can read/recover old results or receive the cloud's
DEVICE_BOUND_TOKEN_REQUIRED denial. It does NOT enable new work in ENFORCE.
Never downgrade/retry a business request after it has been sent.
"""

from __future__ import annotations

import re

from .device_auth_protocol import DeviceAuthorizationError
from .device_identity_windows import DeviceIdentityError

_ID = r"[A-Za-z0-9_-]{1,100}"
_H3_POST = re.compile(
    r"/api/workbench/(?:h3-execution-accounts|h3-authorization-waiting|h3-audio-sources(?:/approve)?|"
    r"h3-batches/prepare|h3-batches/"
    + _ID
    + r"(?:/confirm|/quote/cancel|/authorization/(?:prepare|resume))?|"
    r"h3-segments/"
    + _ID
    + r"/(?:regeneration/(?:prepare|confirm)|retry/(?:prepare|confirm)|cancel))\Z"
)
_H3_GET = re.compile(
    r"/api/workbench/(?:h3-segments/"
    + _ID
    + r"/video|h3-items/"
    + _ID
    + r"/(?:audio|raw-cues))\Z"
)

_WORKBENCH_POST = re.compile(
    r"/api/workbench/(?:"
    r"voices/" + _ID + r"/(?:preview|activate)|"
    r"voice-creations(?:/" + _ID + r"/save)?|"
    r"audio-batches|"
    r"audio-batches/" + _ID + r"/items/" + _ID + r"/(?:retry|composition)|"
    r"tasks/" + _ID + r"/(?:composition/retry|enhancement/backfill)"
    r")\Z"
)


def is_device_business_contract_path(method: str, path: str) -> bool:
    if path.startswith("/api/workbench/h3-"):
        if (method == "POST" and _H3_POST.fullmatch(path)) or (
            method == "GET" and _H3_GET.fullmatch(path)
        ):
            return True
        from .auth_center import AuthCenterDeviceError

        raise AuthCenterDeviceError(
            "H3 设备请求地址不在已接入的接口范围内",
            error_code="INVALID_DEVICE_REQUEST_TARGET",
        )
    return method == "POST" and _WORKBENCH_POST.fullmatch(path) is not None


def is_h3_contract_path(method: str, path: str) -> bool:
    if not path.startswith("/api/workbench/h3-"):
        return False
    return is_device_business_contract_path(method, path)


class DeviceBusinessProofs:
    def __init__(self, registry, *, account_resolver):
        self.registry = registry
        self.origin = registry.base_url
        self.account_resolver = account_resolver

    def __call__(self, login_token: str, *, method: str, path: str):
        if not is_device_business_contract_path(method, path):
            return None
        # Source builds have no production keys. This is not a configurable
        # allow switch: server enforcement still rejects unbound new operations.
        from .device_trust_roots import TRUSTED_ISSUERS

        if not TRUSTED_ISSUERS and self.registry._factory is None:
            return None
        from .auth_center import AuthCenterDeviceError, AuthCenterError

        user = self.account_resolver(login_token)
        if not isinstance(user, dict) or not user.get("user_id"):
            raise AuthCenterError("请重新登录数字人账号", status_code=401)
        try:
            session = self.registry.get(str(user["user_id"]), login_token)
        except DeviceAuthorizationError as exc:
            # A configured release cannot trust a user-edited origin. Do not
            # turn a trust failure into an account-token request to that origin.
            raise AuthCenterDeviceError(
                str(exc), error_code=exc.code, status_code=exc.status_code
            ) from exc
        if session.trust.origin != self.origin:
            raise AuthCenterDeviceError(
                "设备授权服务地址不一致", error_code="DEVICE_TRUST_MISMATCH"
            )
        try:
            # Cloud services classify paid vs. idempotent/download-only work.
            # A client-side scope check must not stop legitimate result recovery.
            return session.request_headers(method=method, path=path, scope=None)
        except DeviceAuthorizationError as exc:
            if exc.code == "LOGIN_REQUIRED":
                raise AuthCenterError("请重新登录数字人账号", status_code=401) from exc
            return None  # before the one business request, never after rejection
        except DeviceIdentityError:
            return None  # no new key, no private-key export, no business replay
