from __future__ import annotations

import json
import secrets
import threading
import time
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen


class AuthCenterError(RuntimeError):
    def __init__(self, message: str, *, status_code: int = 503):
        super().__init__(message)
        self.status_code = status_code


class AuthHandoffStore:
    """Short-lived, one-time tickets for moving a browser session between hosts."""

    def __init__(self, *, lifetime_seconds: int = 60, max_pending: int = 2048):
        self.lifetime_seconds = max(15, int(lifetime_seconds))
        self.max_pending = max(16, int(max_pending))
        self._lock = threading.Lock()
        self._tickets: dict[str, tuple[str, float]] = {}

    def issue(self, access_token: str) -> str:
        token = access_token.strip()
        if not token:
            raise ValueError("登录令牌不能为空")
        now = time.time()
        with self._lock:
            self._purge(now)
            if len(self._tickets) >= self.max_pending:
                oldest = min(self._tickets, key=lambda code: self._tickets[code][1])
                self._tickets.pop(oldest, None)
            code = secrets.token_urlsafe(32)
            self._tickets[code] = (token, now + self.lifetime_seconds)
        return code

    def consume(self, code: str) -> str | None:
        now = time.time()
        with self._lock:
            self._purge(now)
            record = self._tickets.pop(code.strip(), None)
        if record is None or record[1] <= now:
            return None
        return record[0]

    def _purge(self, now: float) -> None:
        expired = [code for code, (_, expires_at) in self._tickets.items() if expires_at <= now]
        for code in expired:
            self._tickets.pop(code, None)


class AuthCenterClient:
    """HTTP client used by standalone processors to share one account center."""

    def __init__(self, base_url: str, *, timeout_seconds: float = 4.0):
        normalized = base_url.strip().rstrip("/")
        parsed = urlsplit(normalized)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("统一账号中心必须是有效的 http:// 或 https:// 地址")
        if parsed.query or parsed.fragment:
            raise ValueError("统一账号中心地址不能包含查询参数或锚点")
        self.base_url = normalized
        self.timeout_seconds = max(1.0, float(timeout_seconds))

    def login(self, username: str, password: str) -> dict[str, Any]:
        data = self._post(
            "/api/auth/center/login",
            {"username": username, "password": password},
        )
        token = str(data.get("access_token", "")).strip()
        user = data.get("user")
        if not token or not isinstance(user, dict):
            raise AuthCenterError("统一账号中心返回了无效的登录结果")
        return {"access_token": token, "user": user}

    def verify(self, token: str) -> dict[str, Any] | None:
        if not token:
            return None
        try:
            data = self._post("/api/auth/center/verify", {"access_token": token})
        except AuthCenterError as exc:
            if exc.status_code == 401:
                return None
            raise
        user = data.get("user")
        return user if data.get("valid") is True and isinstance(user, dict) else None

    def create_handoff(self, token: str) -> str:
        if not token:
            raise AuthCenterError("当前登录已经失效，请重新登录", status_code=401)
        data = self._post("/api/auth/center/handoff", {"access_token": token})
        code = str(data.get("handoff_code", "")).strip()
        if not code:
            raise AuthCenterError("统一账号中心没有返回登录接力码")
        return code

    def consume_handoff(self, code: str) -> dict[str, Any]:
        if not code:
            raise AuthCenterError("登录接力码不能为空", status_code=401)
        data = self._post(
            "/api/auth/center/handoff/consume",
            {"handoff_code": code},
        )
        token = str(data.get("access_token", "")).strip()
        user = data.get("user")
        if not token or not isinstance(user, dict):
            raise AuthCenterError("统一账号中心返回了无效的登录接力结果")
        return {"access_token": token, "user": user}

    def _post(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        request = Request(
            f"{self.base_url}{path}",
            data=body,
            method="POST",
            headers={"Content-Type": "application/json", "Accept": "application/json"},
        )
        try:
            with urlopen(request, timeout=self.timeout_seconds) as response:
                raw = response.read()
                status = int(getattr(response, "status", 200))
        except HTTPError as exc:
            raw = exc.read()
            message = self._detail(raw) or f"统一账号中心拒绝请求（HTTP {exc.code}）"
            raise AuthCenterError(message, status_code=int(exc.code)) from exc
        except (URLError, OSError, TimeoutError) as exc:
            raise AuthCenterError(
                f"无法连接统一账号中心 {self.base_url}，请检查当前电脑的网络连接"
            ) from exc
        if status < 200 or status >= 300:
            raise AuthCenterError(self._detail(raw) or f"统一账号中心返回 HTTP {status}", status_code=status)
        try:
            data = json.loads(raw.decode("utf-8")) if raw else {}
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise AuthCenterError("统一账号中心返回了无法识别的数据") from exc
        if not isinstance(data, dict):
            raise AuthCenterError("统一账号中心返回格式错误")
        return data

    @staticmethod
    def _detail(raw: bytes) -> str:
        try:
            data = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            return ""
        return str(data.get("detail", "")) if isinstance(data, dict) else ""
