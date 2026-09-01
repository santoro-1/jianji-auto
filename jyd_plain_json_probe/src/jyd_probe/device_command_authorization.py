"""Login and device authorization for private command-line entry points.

The website remains the account authority. No password/token is accepted on the
command line or saved in configuration. Existing machine keys are only opened;
activation, UAC and key recovery remain explicit operations in the workbench UI.
"""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass, field
import getpass
import os
import re
import sys
import warnings
from urllib.error import HTTPError, URLError
from urllib.request import Request, build_opener

from .device_auth_protocol import (
    DeviceAuthorizationError,
    bundled_trust,
    canonical_json,
    strict_json,
)
from .device_authorization import (
    DeviceAuthorizationSession,
    DeviceLeaseCache,
    _NoRedirect,
)
from .device_identity_store import MachineDeviceIdentity
from .device_local_execution import (
    LocalDeviceAuthorizer,
    local_authorization_context,
    requires_device_authorization,
)

MAX_ACCOUNT_RESPONSE = 65536
MAX_ACCOUNT_TOKEN = 8192


@dataclass(frozen=True)
class CommandAccount:
    user_id: int
    token: str = field(repr=False)


def _token(value):
    if not isinstance(value, str) or not 1 <= len(value) <= MAX_ACCOUNT_TOKEN:
        raise ValueError("invalid account token")
    if not all(33 <= ord(char) <= 126 for char in value):
        raise ValueError("invalid account token")
    return value


def _account(user, token):
    if not isinstance(user, dict):
        raise ValueError("invalid account")
    value = user.get("user_id")
    if type(value) is int and value > 0:
        user_id = value
    elif isinstance(value, str) and re.fullmatch(r"[1-9][0-9]{0,18}", value):
        user_id = int(value)
    else:
        raise ValueError("invalid account")
    return CommandAccount(user_id, _token(token))


class CommandAccountClient:
    """Only two fixed account endpoints on the code-pinned authority."""

    def __init__(self, trust, *, opener=None, timeout_seconds=15):
        self.trust = trust
        self._opener = opener if opener is not None else build_opener(_NoRedirect())
        self.timeout_seconds = max(1, min(30, float(timeout_seconds)))

    def _post(self, action, payload):
        if action not in {"login", "verify"}:
            raise ValueError("invalid account action")
        uri = self.trust.origin + "/api/auth/center/" + action
        request = Request(
            uri,
            method="POST",
            data=canonical_json(payload).encode("ascii"),
            headers={"Content-Type": "application/json", "Accept": "application/json"},
        )
        try:
            with self._opener.open(request, timeout=self.timeout_seconds) as response:
                if response.geturl() != uri:
                    raise DeviceAuthorizationError(
                        "DEVICE_AUTH_REDIRECT_REJECTED", "账号服务不允许重定向"
                    )
                status = int(response.status)
                raw = response.read(MAX_ACCOUNT_RESPONSE + 1)
        except HTTPError as exc:
            status = int(exc.code)
            exc.close()  # Never echo a response body containing credentials.
            self._failure(status)
        except (URLError, OSError, TimeoutError):
            raise DeviceAuthorizationError(
                "DEVICE_AUTH_UNREACHABLE",
                "暂时无法连接账号服务",
                status_code=503,
                transient=True,
            ) from None
        if status != 200:
            self._failure(status)
        try:
            if len(raw) > MAX_ACCOUNT_RESPONSE:
                raise ValueError()
            value = strict_json(raw)
            if not isinstance(value, dict):
                raise ValueError()
            return value
        except (ValueError, TypeError, UnicodeError, RecursionError):
            raise DeviceAuthorizationError(
                "INVALID_ACCOUNT_RESPONSE", "账号服务返回格式无效", status_code=502
            ) from None

    @staticmethod
    def _failure(status):
        if 300 <= status < 400:
            code, message = "DEVICE_AUTH_REDIRECT_REJECTED", "账号服务不允许重定向"
        elif status in {401, 403}:
            code, message = "LOGIN_REQUIRED", "账号登录无效或账号已停用，请重新登录"
        else:
            code, message = "ACCOUNT_SERVICE_REJECTED", "账号服务暂未接受此请求"
        raise DeviceAuthorizationError(
            code, message, status_code=status, transient=status in {429, 502, 503, 504}
        ) from None

    def login(self, username, password):
        if not isinstance(username, str) or not username.strip() or len(username) > 128:
            raise DeviceAuthorizationError(
                "LOGIN_REQUIRED", "请填写有效的网站用户名", status_code=401
            )
        if not isinstance(password, str) or not 1 <= len(password) <= 1024:
            raise DeviceAuthorizationError(
                "LOGIN_REQUIRED", "请填写网站账号密码", status_code=401
            )
        result = self._post(
            "login", {"username": username.strip(), "password": password}
        )
        try:
            return _account(result.get("user"), result.get("access_token"))
        except ValueError:
            raise DeviceAuthorizationError(
                "INVALID_ACCOUNT_RESPONSE",
                "账号服务返回的登录信息无效",
                status_code=502,
            ) from None

    def verify(self, token):
        try:
            token = _token(token)
        except ValueError:
            raise DeviceAuthorizationError(
                "LOGIN_REQUIRED", "账号令牌格式无效", status_code=401
            ) from None
        result = self._post("verify", {"access_token": token})
        try:
            if result.get("valid") is not True:
                raise ValueError()
            return _account(result.get("user"), token)
        except ValueError:
            raise DeviceAuthorizationError(
                "LOGIN_REQUIRED", "账号登录已失效，请重新登录", status_code=401
            ) from None


def add_command_authorization_arguments(parser):
    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "--device-user", default="", help="网站用户名；密码随后隐藏输入，不写入配置"
    )
    group.add_argument(
        "--device-token-stdin",
        action="store_true",
        help="从标准输入读取一行已有网站令牌；不要把令牌放进命令参数",
    )


def _read_account(args, client):
    if getattr(args, "device_token_stdin", False):
        if getattr(args, "device_user", ""):
            raise DeviceAuthorizationError(
                "LOGIN_REQUIRED", "请选择一种登录方式", status_code=401
            )
        if sys.stdin is None or sys.stdin.isatty():
            raise DeviceAuthorizationError(
                "LOGIN_REQUIRED", "请通过标准输入管道传入已有账号令牌", status_code=401
            )
        try:
            token = sys.stdin.readline(MAX_ACCOUNT_TOKEN + 2).rstrip("\r\n")
        except (OSError, UnicodeError):
            raise DeviceAuthorizationError(
                "LOGIN_REQUIRED", "无法读取账号令牌", status_code=401
            ) from None
        return client.verify(token)
    username = getattr(args, "device_user", "")
    if not username or sys.stdin is None or not sys.stdin.isatty():
        raise DeviceAuthorizationError(
            "DEVICE_COMMAND_LOGIN_REQUIRED",
            "请在此处理机先完成设备申请，再使用 --device-user 用户名并隐藏输入密码；自动化可用 --device-token-stdin",
            status_code=401,
        )
    try:
        with warnings.catch_warnings():
            # getpass must never fall back to echoing a password.
            warnings.simplefilter("error", getpass.GetPassWarning)
            password = getpass.getpass("网站账号密码（不保存）: ")
        return client.login(username, password)
    except (getpass.GetPassWarning, EOFError, KeyboardInterrupt, OSError):
        raise DeviceAuthorizationError(
            "LOGIN_REQUIRED", "登录输入已取消或无法隐藏密码", status_code=401
        ) from None
    finally:
        password = None  # Drop the reference; this is not a secure-memory erase claim.


@contextmanager
def command_authorization(args, *, server_url=None):
    """Install an owned per-command authorizer; the actual core checks scopes."""
    if not requires_device_authorization():
        yield None  # Unconfigured source development only, never a frozen build.
        return
    # Resolve trust before prompting for a password or making any network call.
    trust = bundled_trust(server_url or os.environ.get("JYD_AUTH_SERVER_URL", ""))
    account = _read_account(args, CommandAccountClient(trust))
    with account_authorization(account, trust) as session:
        yield session


@contextmanager
def account_authorization(account, trust):
    """Share verified-account session lifetime with the Agent GUI; no persistence."""
    session = DeviceAuthorizationSession(
        user_id=account.user_id,
        login_token=account.token,
        trust=trust,
        identity=MachineDeviceIdentity(),
        cache=DeviceLeaseCache.for_machine(),
    )
    try:
        with local_authorization_context(LocalDeviceAuthorizer(session)):
            yield session
    finally:
        session.close()  # Only closes handles; never removes the persisted key.
