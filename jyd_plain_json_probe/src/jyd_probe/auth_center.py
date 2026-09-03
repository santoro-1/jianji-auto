from __future__ import annotations

import copy
import hashlib
from collections import OrderedDict, deque
from dataclasses import dataclass, field
from io import BytesIO
from email.utils import parsedate_to_datetime
import ipaddress
import json
import logging
import mimetypes
import random
import secrets
import socket
import threading
import time
import requests
from pathlib import Path
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlsplit, urlunsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener, urlopen

from .logging_config import log_event
from .doubao_request_manager import (
    DoubaoRequestManager,
    DoubaoRequestError,
    global_doubao_request_manager,
)


WORKBENCH_ANALYSIS_TIMEOUT_SECONDS = 600.0
analysis_logger = logging.getLogger(__name__)


def _safe_connection_cause(error: BaseException) -> dict[str, object]:
    cause = error.__cause__
    if cause is None:
        return {}
    nested = cause.reason if isinstance(cause, URLError) else cause
    return {
        "transport_exception": type(cause).__name__,
        "transport_cause": type(nested).__name__,
        "transport_errno": getattr(nested, "errno", None),
        "transport_summary": str(nested).strip()[:300] or None,
    }


class AuthCenterError(RuntimeError):
    def __init__(
        self,
        message: str,
        *,
        status_code: int = 503,
        error_code: str | None = None,
        retryable: bool | None = None,
        retry_after_seconds: float | None = None,
    ):
        super().__init__(message)
        self.status_code = int(status_code)
        self.error_code = error_code or self._default_error_code(self.status_code)
        self.retryable = (
            self.status_code >= 500
            if retryable is None
            else bool(retryable)
        )
        self.retry_after_seconds = retry_after_seconds

    @staticmethod
    def _default_error_code(status_code: int) -> str:
        if status_code == 401:
            return "DIGITAL_HUMAN_AUTH_EXPIRED"
        if status_code == 403:
            return "DIGITAL_HUMAN_FORBIDDEN"
        if status_code == 429:
            return "DIGITAL_HUMAN_RATE_LIMITED"
        if status_code >= 500:
            return "DIGITAL_HUMAN_SERVER_UNAVAILABLE"
        return "DIGITAL_HUMAN_REQUEST_REJECTED"

    @property
    def response_headers(self) -> dict[str, str]:
        if self.retry_after_seconds is None:
            return {}
        return {"Retry-After": str(max(1, int(self.retry_after_seconds)))}


class AuthCenterDeviceError(AuthCenterError):
    """Device permission is not a lost website login; never auto-resubmit."""

    def __init__(self, message: str, *, error_code: str, status_code: int = 403):
        self.upstream_status_code = status_code
        super().__init__(message, error_code=error_code,
                         status_code=409 if status_code == 401 else status_code,
                         retryable=False)

    @property
    def response_headers(self) -> dict[str, str]:
        return {"X-Workbench-Device-Error": self.error_code}


class _NoDeviceCredentialRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        # A proof names exactly one method/URI. Do not forward it, or retry a
        # paid POST at the redirect target, even if the redirect is same-origin.
        return None


def _device_urlopen(request, *, timeout):
    return build_opener(_NoDeviceCredentialRedirect()).open(request, timeout=timeout)


def _no_redirect_urlopen(request, *, timeout):
    return build_opener(_NoDeviceCredentialRedirect()).open(request, timeout=timeout)


class _H3MediaSession:
    """Dedicated persistent pool; ordinary account API calls never use it."""

    def __init__(self, max_connections: int = 10):
        self.session = requests.Session()
        self.session.trust_env = False
        adapter = requests.adapters.HTTPAdapter(
            pool_connections=max(1, int(max_connections)),
            pool_maxsize=max(1, int(max_connections)),
            pool_block=True,
            max_retries=0,
        )
        self.session.mount("https://", adapter)

    def open(
        self,
        request: Request,
        *,
        connect_timeout: float,
        read_timeout: float,
        allowed_peer_ips: tuple[str, ...] = (),
    ):
        try:
            response = self.session.request(
                method=request.get_method(),
                url=request.full_url,
                headers=dict(request.header_items()),
                stream=True,
                allow_redirects=False,
                timeout=(connect_timeout, read_timeout),
            )
        except requests.RequestException as exc:
            raise URLError(exc) from exc
        if allowed_peer_ips:
            connection = getattr(response.raw, "_connection", None)
            sock = getattr(connection, "sock", None)
            try:
                peer_ip = str(sock.getpeername()[0]) if sock is not None else ""
            except OSError:
                peer_ip = ""
            if peer_ip not in allowed_peer_ips:
                response.close()
                raise URLError("H3 媒体连接的实际目标地址未通过安全校验")
        if response.status_code >= 400:
            raw = response.raw.read(64 * 1024, decode_content=True)
            status = int(response.status_code)
            reason = str(response.reason or "")
            headers = response.headers
            response.close()
            raise HTTPError(
                request.full_url, status, reason, headers, BytesIO(raw)
            )
        return response.raw

    def close(self) -> None:
        self.session.close()


class AuthCenterConnectionError(AuthCenterError):
    def __init__(
        self, message: str, *, retry_after_seconds: float | None = None
    ):
        super().__init__(
            message,
            status_code=503,
            error_code="DIGITAL_HUMAN_CONNECTION_FAILED",
            retryable=True,
            retry_after_seconds=retry_after_seconds,
        )


@dataclass
class _AuthVerifyCacheEntry:
    user: dict[str, Any]
    expires_at: float


@dataclass
class _AuthVerifyFlight:
    event: threading.Event = field(default_factory=threading.Event)
    user: dict[str, Any] | None = None
    error: BaseException | None = None
    invalidated: bool = False


def create_local_workbench_handoff(
    base_url: str,
    manager_token: str,
    login_payload: dict[str, Any],
    *,
    path: str,
    timeout_seconds: float = 4.0,
) -> str:
    """Create a one-time ticket on the other bundled local service."""

    normalized = str(base_url or "").strip().rstrip("/")
    parsed = urlsplit(normalized)
    if parsed.scheme not in {"http", "https"} or parsed.hostname not in {
        "127.0.0.1",
        "localhost",
        "::1",
    }:
        raise AuthCenterError("本地工作台地址无效", status_code=500)
    token = str(manager_token or "").strip()
    access_token = str(login_payload.get("access_token") or "").strip()
    user = login_payload.get("user")
    if not token or not access_token or not isinstance(user, dict):
        raise AuthCenterError("本地登录接力数据无效", status_code=401)
    request = Request(
        f"{normalized}{path}",
        data=json.dumps(
            {"access_token": access_token, "user": user}, ensure_ascii=False
        ).encode("utf-8"),
        headers={
            "Accept": "application/json",
            "Content-Type": "application/json; charset=utf-8",
            "X-Workbench-Manager-Token": token,
        },
        method="POST",
    )
    try:
        with urlopen(request, timeout=max(1.0, float(timeout_seconds))) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        raise AuthCenterError(
            f"本地工作台登录接力失败（HTTP {exc.code}）",
            status_code=exc.code,
        ) from exc
    except (URLError, TimeoutError, OSError, ValueError) as exc:
        raise AuthCenterError("本地工作台登录接力失败") from exc
    code = str(payload.get("handoff_code") or "") if isinstance(payload, dict) else ""
    if not code:
        raise AuthCenterError("本地工作台没有返回登录接力码")
    return code


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

    def __init__(
        self,
        base_url: str,
        *,
        timeout_seconds: float = 4.0,
        h3_provider_allowed_hosts: tuple[str, ...] = (),
        h3_download_connect_timeout_seconds: float = 10.0,
        h3_download_read_idle_timeout_seconds: float = 120.0,
        h3_download_total_timeout_seconds: float = 3600.0,
        doubao_request_manager: DoubaoRequestManager | None = None,
        content_analysis_total_timeout_seconds: float = 600.0,
        content_analysis_connect_timeout_seconds: float = 10.0,
        content_analysis_retry_max: int = 2,
        verify_cache_ttl_seconds: float = 5.0,
        verify_cache_max_entries: int = 128,
        verify_timeout_seconds: float = 8.0,
        verify_breaker_failure_threshold: int = 3,
        verify_breaker_window_seconds: float = 10.0,
        verify_breaker_open_seconds: float = 15.0,
        verify_summary_interval_seconds: float = 60.0,
    ):
        normalized = base_url.strip().rstrip("/")
        parsed = urlsplit(normalized)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("数字人网站必须是有效的 http:// 或 https:// 地址")
        if parsed.query or parsed.fragment:
            raise ValueError("数字人网站地址不能包含查询参数或锚点")
        self.base_url = normalized
        self.timeout_seconds = max(1.0, float(timeout_seconds))
        self.h3_download_connect_timeout_seconds = max(
            1.0, float(h3_download_connect_timeout_seconds)
        )
        self.h3_download_read_idle_timeout_seconds = max(
            1.0, float(h3_download_read_idle_timeout_seconds)
        )
        self.h3_download_total_timeout_seconds = max(
            self.h3_download_read_idle_timeout_seconds,
            float(h3_download_total_timeout_seconds),
        )
        self.h3_provider_allowed_hosts = tuple(
            dict.fromkeys(
                str(value or "").strip().lower().lstrip(".")
                for value in h3_provider_allowed_hosts
                if str(value or "").strip()
            )
        )
        self._h3_media_session = _H3MediaSession(10)
        self._doubao_request_manager = doubao_request_manager
        self.content_analysis_total_timeout_seconds = max(
            1.0, float(content_analysis_total_timeout_seconds)
        )
        self.content_analysis_connect_timeout_seconds = max(
            1.0, float(content_analysis_connect_timeout_seconds)
        )
        self.content_analysis_retry_max = max(
            0, min(2, int(content_analysis_retry_max))
        )
        self.verify_cache_ttl_seconds = max(
            0.01, float(verify_cache_ttl_seconds)
        )
        self.verify_cache_max_entries = max(1, int(verify_cache_max_entries))
        self.verify_timeout_seconds = max(1.0, float(verify_timeout_seconds))
        self.verify_breaker_failure_threshold = max(
            1, int(verify_breaker_failure_threshold)
        )
        self.verify_breaker_window_seconds = max(
            0.01, float(verify_breaker_window_seconds)
        )
        self.verify_breaker_open_seconds = max(
            0.01, float(verify_breaker_open_seconds)
        )
        self.verify_summary_interval_seconds = max(
            0.01, float(verify_summary_interval_seconds)
        )
        self._verify_lock = threading.Lock()
        self._verify_cache: OrderedDict[str, _AuthVerifyCacheEntry] = OrderedDict()
        self._verify_flights: dict[str, _AuthVerifyFlight] = {}
        self._verify_network_failures: deque[float] = deque()
        self._verify_breaker_open_until = 0.0
        self._verify_breaker_probe_in_flight = False
        self._verify_next_summary_at = (
            time.monotonic() + self.verify_summary_interval_seconds
        )
        self._verify_totals = self._new_verify_metrics()
        self._verify_window = self._new_verify_metrics()
        self._verify_window_latencies_ms: list[int] = []
        self._verify_closed = False
        self.device_header_provider = None

    def close(self) -> None:
        self.invalidate_verification_cache()
        with self._verify_lock:
            self._verify_closed = True
        self._h3_media_session.close()

    @staticmethod
    def _new_verify_metrics() -> dict[str, int]:
        return {
            "requests": 0,
            "cache_hits": 0,
            "coalesced_waiters": 0,
            "remote_requests": 0,
            "remote_successes": 0,
            "remote_unauthorized": 0,
            "remote_network_failures": 0,
            "breaker_rejections": 0,
            "wait_timeouts": 0,
        }

    def _bump_verify_metric_locked(self, name: str) -> None:
        self._verify_totals[name] += 1
        self._verify_window[name] += 1

    def verification_snapshot(self) -> dict[str, Any]:
        """Return aggregate diagnostics without exposing tokens or cached users."""

        now = time.monotonic()
        with self._verify_lock:
            return {
                **self._verify_totals,
                "cache_entries": len(self._verify_cache),
                "in_flight": len(self._verify_flights),
                "breaker_state": self._verify_breaker_state_locked(now),
            }

    def invalidate_verification(self, token: str) -> None:
        clean_token = str(token or "").strip()
        if not clean_token:
            return
        with self._verify_lock:
            self._verify_cache.pop(clean_token, None)
            flight = self._verify_flights.pop(clean_token, None)
            if flight is not None:
                flight.invalidated = True
                flight.error = AuthCenterError(
                    "当前登录已经切换或退出，请重新登录",
                    status_code=401,
                    retryable=False,
                )
                flight.event.set()

    def invalidate_verification_cache(self) -> None:
        with self._verify_lock:
            self._verify_cache.clear()
            flights = list(self._verify_flights.values())
            self._verify_flights.clear()
            for flight in flights:
                flight.invalidated = True
                flight.error = AuthCenterError(
                    "当前登录已经切换或退出，请重新登录",
                    status_code=401,
                    retryable=False,
                )
                flight.event.set()

    def _purge_verify_cache_locked(self, now: float) -> None:
        expired = [
            token
            for token, entry in self._verify_cache.items()
            if entry.expires_at <= now
        ]
        for token in expired:
            self._verify_cache.pop(token, None)
        while len(self._verify_cache) > self.verify_cache_max_entries:
            self._verify_cache.popitem(last=False)

    def _verify_breaker_state_locked(self, now: float) -> str:
        if self._verify_breaker_open_until <= 0:
            return "CLOSED"
        if now < self._verify_breaker_open_until:
            return "OPEN"
        return "HALF_OPEN"

    def _breaker_rejection_locked(self, now: float) -> AuthCenterConnectionError | None:
        if self._verify_breaker_open_until <= 0:
            return None
        if now < self._verify_breaker_open_until:
            retry_after = max(1.0, self._verify_breaker_open_until - now)
        elif self._verify_breaker_probe_in_flight:
            retry_after = 1.0
        else:
            self._verify_breaker_probe_in_flight = True
            return None
        self._bump_verify_metric_locked("breaker_rejections")
        return AuthCenterConnectionError(
            "暂时无法连接数字人账号中心，请稍后重试",
            retry_after_seconds=retry_after,
        )

    def _record_verify_network_failure_locked(self, now: float) -> bool:
        cutoff = now - self.verify_breaker_window_seconds
        while self._verify_network_failures and self._verify_network_failures[0] < cutoff:
            self._verify_network_failures.popleft()
        self._verify_network_failures.append(now)
        opened_now = False
        if self._verify_breaker_probe_in_flight or (
            len(self._verify_network_failures)
            >= self.verify_breaker_failure_threshold
        ):
            opened_now = now >= self._verify_breaker_open_until
            self._verify_breaker_open_until = now + self.verify_breaker_open_seconds
            self._verify_breaker_probe_in_flight = False
        return opened_now

    def _record_verify_reachable_locked(self) -> bool:
        recovered = (
            self._verify_breaker_open_until > 0
            or self._verify_breaker_probe_in_flight
        )
        self._verify_network_failures.clear()
        self._verify_breaker_open_until = 0.0
        self._verify_breaker_probe_in_flight = False
        return recovered

    @staticmethod
    def _clone_verify_error(error: BaseException) -> BaseException:
        if isinstance(error, AuthCenterConnectionError):
            return AuthCenterConnectionError(
                str(error), retry_after_seconds=error.retry_after_seconds
            )
        if isinstance(error, AuthCenterError):
            return AuthCenterError(
                str(error),
                status_code=error.status_code,
                error_code=error.error_code,
                retryable=error.retryable,
                retry_after_seconds=error.retry_after_seconds,
            )
        return error

    def _maybe_log_verify_summary(self) -> None:
        now = time.monotonic()
        with self._verify_lock:
            if now < self._verify_next_summary_at:
                return
            metrics = dict(self._verify_window)
            latencies = list(self._verify_window_latencies_ms)
            state = self._verify_breaker_state_locked(now)
            self._verify_window = self._new_verify_metrics()
            self._verify_window_latencies_ms.clear()
            self._verify_next_summary_at = now + self.verify_summary_interval_seconds
        ordered = sorted(latencies)
        p95_index = max(
            0, min(len(ordered) - 1, ((len(ordered) * 95 + 99) // 100) - 1)
        )
        log_event(
            analysis_logger,
            "auth_verify.summary",
            "数字人账号校验一分钟汇总",
            component="workbench",
            **metrics,
            remote_average_ms=(round(sum(ordered) / len(ordered)) if ordered else 0),
            remote_p95_ms=(ordered[p95_index] if ordered else 0),
            remote_max_ms=(ordered[-1] if ordered else 0),
            breaker_state=state,
        )

    def _device_business_headers(
        self, token: str, *, method: str, path: str
    ) -> dict[str, str]:
        from .device_business_transport import is_device_business_contract_path

        if (
            not is_device_business_contract_path(method, path)
            or self.device_header_provider is None
        ):
            return {}
        provider = self.device_header_provider
        if getattr(provider, "origin", self.base_url) != self.base_url:
            raise AuthCenterDeviceError("设备授权服务地址与业务服务不一致", error_code="DEVICE_TRUST_MISMATCH")
        headers = provider(token, method=method, path=path)
        if headers is None:
            # No business request has been sent yet. The original account is
            # used once; ONLY the cloud decides OFF/OBSERVE/ENFORCE permission.
            return {}
        if set(headers) != {"Authorization", "DPoP"} or not headers["Authorization"].startswith("DPoP "):
            raise AuthCenterDeviceError("设备请求凭据格式无效", error_code="INVALID_DEVICE_PROOF")
        return headers

    def login(self, username: str, password: str) -> dict[str, Any]:
        data = self._post(
            "/api/auth/center/login",
            {"username": username, "password": password},
        )
        token = str(data.get("access_token", "")).strip()
        user = data.get("user")
        if not token or not isinstance(user, dict):
            raise AuthCenterError("数字人网站返回了无效的登录结果")
        return {"access_token": token, "user": user}

    def verify(self, token: str) -> dict[str, Any] | None:
        clean_token = str(token or "").strip()
        if not clean_token:
            return None

        now = time.monotonic()
        leader = False
        with self._verify_lock:
            if self._verify_closed:
                raise AuthCenterConnectionError("数字人账号中心客户端已经关闭")
            self._bump_verify_metric_locked("requests")
            self._purge_verify_cache_locked(now)
            cached = self._verify_cache.get(clean_token)
            if cached is not None:
                self._verify_cache.move_to_end(clean_token)
                self._bump_verify_metric_locked("cache_hits")
                user = copy.deepcopy(cached.user)
                flight = None
                rejection = None
            else:
                user = None
                flight = self._verify_flights.get(clean_token)
                if flight is not None:
                    self._bump_verify_metric_locked("coalesced_waiters")
                    rejection = None
                else:
                    rejection = self._breaker_rejection_locked(now)
                    if rejection is None:
                        flight = _AuthVerifyFlight()
                        self._verify_flights[clean_token] = flight
                        leader = True

        if cached is not None:
            self._maybe_log_verify_summary()
            return user
        if rejection is not None:
            self._maybe_log_verify_summary()
            raise rejection
        assert flight is not None
        if not leader:
            if not flight.event.wait(timeout=self.verify_timeout_seconds + 2.0):
                with self._verify_lock:
                    self._bump_verify_metric_locked("wait_timeouts")
                self._maybe_log_verify_summary()
                raise AuthCenterConnectionError(
                    "数字人账号校验等待超时，请稍后重试"
                )
            if flight.error is not None:
                raise self._clone_verify_error(flight.error)
            return copy.deepcopy(flight.user)

        started_at = time.monotonic()
        parsed = urlsplit(self.base_url)
        try:
            target_port = parsed.port
        except ValueError:
            target_port = None
        with self._verify_lock:
            self._bump_verify_metric_locked("remote_requests")
        log_event(
            analysis_logger,
            "auth_verify.remote_started",
            "开始校验数字人账号登录状态",
            component="workbench",
            endpoint="/api/auth/center/verify",
            target_scheme=parsed.scheme,
            target_host=parsed.hostname,
            target_port=target_port,
        )

        verified_user: dict[str, Any] | None = None
        remote_error: BaseException | None = None
        opened_breaker = False
        recovered_breaker = False
        unauthorized = False
        try:
            data = self._post(
                "/api/auth/center/verify",
                {"access_token": clean_token},
                timeout_seconds=self.verify_timeout_seconds,
                use_default_timeout_floor=False,
            )
        except AuthCenterError as exc:
            unauthorized = exc.status_code == 401
            if not unauthorized:
                if isinstance(exc, AuthCenterConnectionError):
                    remote_error = AuthCenterConnectionError(
                        "暂时无法连接数字人账号中心，请稍后重试"
                    )
                    remote_error.__cause__ = exc.__cause__ or exc
                else:
                    remote_error = exc
        except BaseException as exc:
            remote_error = AuthCenterError(
                "数字人账号校验发生内部错误",
                status_code=502,
                error_code="DIGITAL_HUMAN_VERIFY_FAILED",
                retryable=True,
            )
            remote_error.__cause__ = exc

        elapsed_ms = round((time.monotonic() - started_at) * 1000)
        if remote_error is None and not unauthorized:
            candidate = data.get("user")
            if data.get("valid") is True and isinstance(candidate, dict):
                verified_user = copy.deepcopy(candidate)
            else:
                unauthorized = True

        with self._verify_lock:
            self._verify_window_latencies_ms.append(elapsed_ms)
            if isinstance(remote_error, AuthCenterConnectionError):
                self._bump_verify_metric_locked("remote_network_failures")
                opened_breaker = self._record_verify_network_failure_locked(
                    time.monotonic()
                )
            else:
                recovered_breaker = self._record_verify_reachable_locked()
                if unauthorized:
                    self._bump_verify_metric_locked("remote_unauthorized")
                    self._verify_cache.pop(clean_token, None)
                elif remote_error is None:
                    self._bump_verify_metric_locked("remote_successes")

            current_flight = self._verify_flights.get(clean_token)
            if current_flight is flight:
                self._verify_flights.pop(clean_token, None)
            if not flight.invalidated:
                flight.user = copy.deepcopy(verified_user)
                flight.error = remote_error
                if verified_user is not None and remote_error is None:
                    self._verify_cache[clean_token] = _AuthVerifyCacheEntry(
                        user=copy.deepcopy(verified_user),
                        expires_at=time.monotonic()
                        + self.verify_cache_ttl_seconds,
                    )
                    self._verify_cache.move_to_end(clean_token)
                    self._purge_verify_cache_locked(time.monotonic())
            flight.event.set()

        if remote_error is not None or unauthorized:
            error = remote_error
            level = logging.WARNING if unauthorized else logging.ERROR
            log_event(
                analysis_logger,
                "auth_verify.remote_failed",
                "数字人账号登录状态校验失败",
                level=level,
                component="workbench",
                endpoint="/api/auth/center/verify",
                target_scheme=parsed.scheme,
                target_host=parsed.hostname,
                target_port=target_port,
                elapsed_ms=elapsed_ms,
                error_code=(
                    "DIGITAL_HUMAN_AUTH_EXPIRED"
                    if unauthorized
                    else getattr(error, "error_code", "DIGITAL_HUMAN_VERIFY_FAILED")
                ),
                http_status=(401 if unauthorized else getattr(error, "status_code", 502)),
                retryable=(False if unauthorized else getattr(error, "retryable", True)),
                error_summary=(
                    "账号已停用、已删除或登录已失效"
                    if unauthorized
                    else str(error).strip()[:500]
                ),
                **(_safe_connection_cause(error) if error is not None else {}),
            )
        else:
            log_event(
                analysis_logger,
                "auth_verify.remote_succeeded",
                "数字人账号登录状态校验成功",
                component="workbench",
                endpoint="/api/auth/center/verify",
                target_scheme=parsed.scheme,
                target_host=parsed.hostname,
                target_port=target_port,
                elapsed_ms=elapsed_ms,
            )
        if opened_breaker:
            log_event(
                analysis_logger,
                "auth_verify.breaker_opened",
                "数字人账号中心连续连接失败，已进入短时保护",
                level=logging.ERROR,
                component="workbench",
                failure_threshold=self.verify_breaker_failure_threshold,
                open_seconds=self.verify_breaker_open_seconds,
            )
        if recovered_breaker:
            log_event(
                analysis_logger,
                "auth_verify.breaker_recovered",
                "数字人账号中心连接已经恢复",
                component="workbench",
            )
        self._maybe_log_verify_summary()
        if flight.invalidated and flight.error is not None:
            raise self._clone_verify_error(flight.error)
        if remote_error is not None:
            raise remote_error
        return copy.deepcopy(verified_user)

    def create_handoff(self, token: str) -> str:
        if not token:
            raise AuthCenterError("当前登录已经失效，请重新登录", status_code=401)
        data = self._post("/api/auth/center/handoff", {"access_token": token})
        code = str(data.get("handoff_code", "")).strip()
        if not code:
            raise AuthCenterError("数字人网站没有返回登录接力码")
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
            raise AuthCenterError("数字人网站返回了无效的登录接力结果")
        return {"access_token": token, "user": user}

    def list_workbench_tasks(self, token: str, *, limit: int = 50) -> list[dict[str, Any]]:
        data = self._post(
            "/api/workbench/tasks",
            {"access_token": token, "limit": max(1, min(int(limit), 100))},
        )
        tasks = data.get("tasks")
        if not isinstance(tasks, list):
            raise AuthCenterError("数字人网站返回了无效的任务列表")
        return [item for item in tasks if isinstance(item, dict)]

    def get_workbench_task(self, token: str, item_id: str) -> dict[str, Any]:
        data = self._post(
            f"/api/workbench/tasks/{item_id}",
            {"access_token": token},
        )
        if data.get("item_id") != item_id:
            raise AuthCenterError("数字人网站返回了错误的任务")
        return data

    def analyze_workbench_content(
        self,
        token: str,
        original_script: str,
        *,
        force_refresh: bool = False,
        visual_context: dict[str, Any] | None = None,
        analysis_operation_id: str | None = None,
        project_key: str = "default",
        request_budget_seconds: float | None = None,
    ) -> dict[str, Any]:
        trace_id = secrets.token_hex(8)
        script_sha256 = hashlib.sha256(original_script.encode("utf-8")).hexdigest()
        parsed = urlsplit(self.base_url)
        try:
            target_port = parsed.port
        except ValueError:
            target_port = None
        started_at = time.monotonic()
        resolved_budget = min(
            WORKBENCH_ANALYSIS_TIMEOUT_SECONDS,
            self.content_analysis_total_timeout_seconds,
            float(request_budget_seconds or self.content_analysis_total_timeout_seconds),
        )
        diagnostic_context = {
            "trace_id": trace_id,
            "target_scheme": parsed.scheme,
            "target_host": parsed.hostname,
            "target_port": target_port,
            "endpoint": "/api/workbench/content-analysis",
            "timeout_seconds": resolved_budget,
            "script_sha256": script_sha256,
            "script_length": len(original_script),
            "force_refresh": bool(force_refresh),
            "has_visual_context": visual_context is not None,
        }
        log_event(
            analysis_logger,
            "content_analysis.remote_request_started",
            "开始请求数字人网站统一内容分析",
            component="workbench",
            **diagnostic_context,
        )
        payload: dict[str, Any] = {
            "access_token": token,
            "original_script": original_script,
            "force_refresh": force_refresh,
            "analysis_operation_id": (
                str(analysis_operation_id or "").strip() or secrets.token_hex(16)
            ),
        }
        if visual_context is not None:
            payload["visual_context"] = visual_context
        try:
            result = self._execute_doubao_request(
                path="/api/workbench/content-analysis",
                payload=payload,
                project_key=project_key,
                operation_id=str(payload["analysis_operation_id"]),
                request_budget_seconds=resolved_budget,
            )
        except AuthCenterError as exc:
            log_event(
                analysis_logger,
                "content_analysis.remote_request_failed",
                "数字人网站统一内容分析请求失败",
                level=logging.ERROR,
                component="workbench",
                elapsed_ms=round((time.monotonic() - started_at) * 1000),
                error_code=exc.error_code,
                http_status=exc.status_code,
                retryable=exc.retryable,
                error_summary=str(exc).strip()[:500],
                **diagnostic_context,
                **_safe_connection_cause(exc),
            )
            raise
        log_event(
            analysis_logger,
            "content_analysis.remote_response_received",
            "已收到数字人网站统一内容分析响应",
            component="workbench",
            elapsed_ms=round((time.monotonic() - started_at) * 1000),
            response_status=result.get("overall_status"),
            provider_request_id=result.get("provider_request_id"),
            provider_attempts=result.get("provider_attempts"),
            cache_hit=result.get("cache_hit") is True,
            **diagnostic_context,
        )
        return result

    def analyze_workbench_visuals(
        self,
        token: str,
        payload: dict[str, Any],
        *,
        force_refresh: bool = False,
        analysis_operation_id: str | None = None,
        project_key: str = "default",
        request_budget_seconds: float | None = None,
    ) -> dict[str, Any]:
        operation_id = str(analysis_operation_id or "").strip() or secrets.token_hex(16)
        return self._execute_doubao_request(
            path="/api/workbench/visual-analysis",
            payload={
                "access_token": token,
                **payload,
                "force_refresh": force_refresh,
                "analysis_operation_id": operation_id,
            },
            project_key=project_key,
            operation_id=operation_id,
            request_budget_seconds=(
                self.content_analysis_total_timeout_seconds
                if request_budget_seconds is None
                else request_budget_seconds
            ),
        )

    def _execute_doubao_request(
        self,
        *,
        path: str,
        payload: dict[str, Any],
        project_key: str,
        operation_id: str,
        request_budget_seconds: float,
    ) -> dict[str, Any]:
        budget = min(
            WORKBENCH_ANALYSIS_TIMEOUT_SECONDS,
            max(1.0, float(request_budget_seconds)),
        )
        try:
            manager = self._doubao_request_manager or global_doubao_request_manager()
            return manager.execute(
                project_key=project_key,
                operation_id=operation_id,
                total_timeout_seconds=budget,
                call=lambda remaining: self._post_doubao_with_retry(
                    path=path,
                    payload=payload,
                    remaining_seconds=min(budget, remaining),
                ),
            )
        except DoubaoRequestError as exc:
            raise AuthCenterError(
                str(exc),
                status_code=429 if exc.code == "DOUBAO_QUEUE_FULL" else 504,
                error_code=exc.code,
                retryable=True,
            ) from exc

    def _post_doubao_with_retry(
        self,
        *,
        path: str,
        payload: dict[str, Any],
        remaining_seconds: float,
    ) -> dict[str, Any]:
        deadline = time.monotonic() + max(0.001, float(remaining_seconds))
        for attempt in range(self.content_analysis_retry_max + 1):
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise AuthCenterError(
                    "本机豆包请求总预算已耗尽",
                    status_code=504,
                    error_code="DOUBAO_TOTAL_DEADLINE_EXCEEDED",
                    retryable=False,
                )
            try:
                return self._post(
                    path,
                    payload,
                    timeout_seconds=remaining,
                    connect_timeout_seconds=min(
                        self.content_analysis_connect_timeout_seconds, remaining
                    ),
                    extra_headers={
                        "X-JYD-Request-Budget-Ms": str(max(1, int(remaining * 1000)))
                    },
                )
            except AuthCenterError as exc:
                may_retry = isinstance(exc, AuthCenterConnectionError) or exc.error_code in {
                    "ARK_QUEUE_FULL",
                    "ARK_CIRCUIT_OPEN",
                }
                if not may_retry or attempt >= self.content_analysis_retry_max:
                    raise
                ceiling = min(0.5 * (2**attempt), 5.0)
                delay = (
                    float(exc.retry_after_seconds)
                    if exc.retry_after_seconds is not None
                    else random.uniform(0.0, ceiling)
                )
                if time.monotonic() + delay >= deadline:
                    raise
                time.sleep(max(0.0, delay))

    def start_workbench_composition(
        self,
        token: str,
        batch_id: str,
        item_id: str,
        *,
        idempotency_key: str,
        image_asset_id: str,
        image_sha256: str,
        resolution: str = "1024",
        correlation_id: str = "",
        runninghub_execution_account_ids: list[int] | None = None,
        seedvr2_execution_account_ids: list[int] | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "access_token": token,
            "cost_confirmed": True,
            "idempotency_key": idempotency_key,
            "image_asset_id": image_asset_id,
            "image_sha256": image_sha256,
            "resolution": str(resolution or "1024"),
            "correlation_id": correlation_id,
        }
        if runninghub_execution_account_ids is not None:
            payload["runninghub_execution_account_ids"] = list(
                runninghub_execution_account_ids
            )
        if seedvr2_execution_account_ids is not None:
            payload["seedvr2_execution_account_ids"] = list(
                seedvr2_execution_account_ids
            )
        return self._post(
            f"/api/workbench/audio-batches/{batch_id}/items/{item_id}/composition",
            payload,
        )

    def backfill_workbench_video_enhancement(
        self,
        token: str,
        item_id: str,
        *,
        idempotency_key: str,
    ) -> dict[str, Any]:
        return self._post(
            f"/api/workbench/tasks/{item_id}/enhancement/backfill",
            {
                "access_token": token,
                "cost_confirmed": True,
                "idempotency_key": str(idempotency_key or "").strip(),
            },
        )

    def list_workbench_execution_accounts(self, token: str) -> dict[str, Any]:
        return self._post(
            "/api/workbench/runninghub-execution-accounts",
            {"access_token": token},
        )

    def list_workbench_dual_pool_accounts(self, token: str) -> dict[str, Any]:
        return self._post(
            "/api/workbench/runninghub-dual-pool-accounts",
            {"access_token": token},
        )

    def retry_workbench_composition(
        self, token: str, item_id: str, *, resolution: str | None = None
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "access_token": token,
            "cost_confirmed": True,
        }
        if str(resolution or "").strip():
            payload["resolution"] = str(resolution).strip()
        return self._post(
            f"/api/workbench/tasks/{item_id}/composition/retry",
            payload,
        )

    def list_workbench_voices(self, token: str) -> dict[str, Any]:
        return self._post("/api/workbench/voices", {"access_token": token})

    def create_official_voice_preview(
        self,
        token: str,
        voice_asset_id: str,
        *,
        preview_text: str,
        cost_confirmed: bool,
    ) -> dict[str, Any]:
        return self._post(
            f"/api/workbench/voices/{voice_asset_id}/preview",
            {
                "access_token": token,
                "preview_text": preview_text,
                "cost_confirmed": cost_confirmed,
            },
        )

    def create_voice_creation(
        self,
        token: str,
        *,
        fields: dict[str, Any],
        source_a_name: str,
        source_a: bytes,
        source_a_content_type: str,
        source_b_name: str | None = None,
        source_b: bytes | None = None,
        source_b_content_type: str | None = None,
    ) -> dict[str, Any]:
        files = [
            (
                "source_a",
                source_a_name,
                source_a,
                source_a_content_type or "application/octet-stream",
            )
        ]
        if source_b is not None and source_b_name:
            files.append(
                (
                    "source_b",
                    source_b_name,
                    source_b,
                    source_b_content_type or "application/octet-stream",
                )
            )
        return self._multipart_post(
            "/api/workbench/voice-creations",
            {"access_token": token, **fields},
            files,
        )

    def save_voice_creation(self, token: str, task_id: str) -> dict[str, Any]:
        return self._post(
            f"/api/workbench/voice-creations/{task_id}/save",
            {"access_token": token},
        )

    def import_workbench_voice(
        self,
        token: str,
        *,
        voice_id: str,
        name: str,
        already_activated: bool,
    ) -> dict[str, Any]:
        return self._post(
            "/api/workbench/voices/import",
            {
                "access_token": token,
                "voice_id": voice_id,
                "name": name,
                "already_activated": already_activated,
            },
        )

    def activate_workbench_voice(
        self, token: str, voice_asset_id: str, *, cost_confirmed: bool
    ) -> dict[str, Any]:
        return self._post(
            f"/api/workbench/voices/{voice_asset_id}/activate",
            {"access_token": token, "cost_confirmed": cost_confirmed},
        )

    def delete_workbench_voice(
        self, token: str, voice_asset_id: str
    ) -> dict[str, Any]:
        return self._post(
            f"/api/workbench/voices/{voice_asset_id}/delete",
            {"access_token": token},
        )

    def upload_workbench_batch_asset(
        self, token: str, path: Path, *, kind: str, filename: str
    ) -> dict[str, Any]:
        return self._multipart_post(
            "/api/workbench/batch-assets",
            {"access_token": token, "kind": kind},
            [
                (
                    "file",
                    filename,
                    path.read_bytes(),
                    mimetypes.guess_type(filename)[0] or "application/octet-stream",
                )
            ],
        )

    def list_h3_execution_accounts(self, token: str) -> dict[str, Any]:
        return self._post(
            "/api/workbench/h3-execution-accounts",
            {"access_token": token},
            timeout_seconds=150.0,
        )

    def approve_h3_audio_source(
        self,
        token: str,
        *,
        audio_batch_id: str,
        audio_item_id: str,
        audio_generation_version: int,
    ) -> dict[str, Any]:
        return self._post(
            "/api/workbench/h3-audio-sources/approve",
            {
                "access_token": token,
                "audio_batch_id": audio_batch_id,
                "audio_item_id": audio_item_id,
                "audio_generation_version": int(audio_generation_version),
            },
        )

    def prepare_h3_batch(self, token: str, payload: dict[str, Any]) -> dict[str, Any]:
        return self._post(
            "/api/workbench/h3-batches/prepare",
            {**payload, "access_token": token},
            timeout_seconds=360.0,
        )

    def confirm_h3_batch(self, token: str, batch_id: str) -> dict[str, Any]:
        return self._post(
            f"/api/workbench/h3-batches/{batch_id}/confirm",
            {"access_token": token, "cost_confirmed": True},
            timeout_seconds=120.0,
        )

    def get_h3_batch(self, token: str, batch_id: str) -> dict[str, Any]:
        return self._post(
            f"/api/workbench/h3-batches/{batch_id}",
            {"access_token": token},
        )

    def refresh_h3_segment_delivery(
        self, token: str, segment_id: str
    ) -> dict[str, Any]:
        response = self._post(
            f"/api/workbench/h3-segments/{segment_id}/delivery/refresh",
            {"access_token": token},
            timeout_seconds=120.0,
        )
        delivery = response.get("video_delivery")
        if not isinstance(delivery, dict):
            raise AuthCenterError("数字人网站未返回刷新的 H3 交付信息")
        return delivery

    def cancel_h3_quote(self, token: str, batch_id: str, *, request_key: str, quote_token: str) -> dict[str, Any]:
        return self._post(f"/api/workbench/h3-batches/{batch_id}/quote/cancel", {
            "access_token": token, "cancel_quote_confirmed": True,
            "request_key": request_key, "quote_token": quote_token,
        })

    def list_h3_authorization_waiting(self, token: str, *, after_id: str = "") -> dict[str, Any]:
        return self._post("/api/workbench/h3-authorization-waiting", {
            "access_token": token, "after_id": after_id,
        })

    def prepare_h3_authorization_recovery(self, token: str, batch_id: str) -> dict[str, Any]:
        return self._post(f"/api/workbench/h3-batches/{batch_id}/authorization/prepare", {"access_token": token})

    def resume_h3_authorization_recovery(self, token: str, batch_id: str, *, request_key: str,
                                         review_token: str, resume_confirmed: bool) -> dict[str, Any]:
        return self._post(f"/api/workbench/h3-batches/{batch_id}/authorization/resume", {
            "access_token": token, "resume_confirmed": resume_confirmed,
            "request_key": request_key, "review_token": review_token,
        })


    def prepare_h3_segment_regeneration(
        self, token: str, segment_id: str
    ) -> dict[str, Any]:
        return self._post(
            f"/api/workbench/h3-segments/{segment_id}/regeneration/prepare",
            {"access_token": token},
        )

    def confirm_h3_segment_regeneration(
        self,
        token: str,
        segment_id: str,
        *,
        request_key: str,
        quote_token: str,
    ) -> dict[str, Any]:
        return self._post(
            f"/api/workbench/h3-segments/{segment_id}/regeneration/confirm",
            {
                "access_token": token,
                "request_key": request_key,
                "quote_token": quote_token,
                "cost_confirmed": True,
            },
        )

    def prepare_h3_segment_retry(
        self, token: str, segment_id: str
    ) -> dict[str, Any]:
        return self._post(
            f"/api/workbench/h3-segments/{segment_id}/retry/prepare",
            {"access_token": token},
        )

    def confirm_h3_segment_retry(
        self,
        token: str,
        segment_id: str,
        *,
        request_key: str,
        quote_token: str,
        cost_confirmed: bool,
    ) -> dict[str, Any]:
        return self._post(
            f"/api/workbench/h3-segments/{segment_id}/retry/confirm",
            {
                "access_token": token,
                "request_key": request_key,
                "quote_token": quote_token,
                "cost_confirmed": bool(cost_confirmed),
            },
        )

    def cancel_h3_segment(
        self, token: str, segment_id: str, *, request_key: str
    ) -> dict[str, Any]:
        return self._post(
            f"/api/workbench/h3-segments/{segment_id}/cancel",
            {"access_token": token, "request_key": request_key},
        )

    def create_workbench_audio_batch(
        self, token: str, payload: dict[str, Any]
    ) -> dict[str, Any]:
        return self._post(
            "/api/workbench/audio-batches",
            {"access_token": token, **payload},
        )

    def get_workbench_audio_batch(self, token: str, batch_id: str) -> dict[str, Any]:
        return self._post(
            f"/api/workbench/audio-batches/{batch_id}",
            {"access_token": token},
        )

    def lookup_workbench_audio_batch(self, token: str, request_key: str) -> dict[str, Any]:
        return self._post(
            "/api/workbench/audio-batches/lookup",
            {"access_token": token, "request_key": request_key},
        )

    def retry_workbench_audio(
        self,
        token: str,
        batch_id: str,
        item_id: str,
        *,
        speed: float,
    ) -> dict[str, Any]:
        return self._post(
            f"/api/workbench/audio-batches/{batch_id}/items/{item_id}/retry",
            {
                "access_token": token,
                "cost_confirmed": True,
                "speed": speed,
            },
        )

    def download_voice_preview(
        self,
        token: str,
        voice_asset_id: str,
        target: Path,
        *,
        max_bytes: int,
    ) -> int:
        return self._download(
            f"/api/workbench/voices/{voice_asset_id}/preview",
            token,
            target,
            max_bytes=max_bytes,
            timeout_seconds=120.0,
            failure_message="下载声音试听失败",
        )

    def download_voice_creation_preview(
        self,
        token: str,
        task_id: str,
        target: Path,
        *,
        max_bytes: int,
    ) -> int:
        return self._download(
            f"/api/workbench/voice-creations/{task_id}/preview",
            token,
            target,
            max_bytes=max_bytes,
            timeout_seconds=120.0,
            failure_message="下载克隆声音试听失败",
        )

    def download_workbench_audio(
        self,
        token: str,
        batch_id: str,
        item_id: str,
        target: Path,
        *,
        max_bytes: int,
    ) -> int:
        return self._download(
            f"/api/workbench/audio-batches/{batch_id}/items/{item_id}/audio",
            token,
            target,
            max_bytes=max_bytes,
            timeout_seconds=300.0,
            failure_message="下载生成音频失败",
        )

    def download_workbench_video(
        self,
        token: str,
        item_id: str,
        video_index: int,
        target: Path,
        *,
        max_bytes: int,
    ) -> int:
        return self._download(
            f"/api/workbench/tasks/{item_id}/videos/{int(video_index)}",
            token,
            target,
            max_bytes=max_bytes,
            timeout_seconds=120.0,
            failure_message="下载数字人视频失败",
        )

    def download_workbench_base_video(
        self,
        token: str,
        item_id: str,
        target: Path,
        *,
        max_bytes: int,
    ) -> int:
        return self._download(
            f"/api/workbench/tasks/{item_id}/base-video",
            token,
            target,
            max_bytes=max_bytes,
            timeout_seconds=300.0,
            failure_message="下载基础视频失败",
        )

    def download_h3_segment_video(
        self,
        token: str,
        segment_id: str,
        target: Path,
        *,
        max_bytes: int,
        delivery: dict[str, Any] | None = None,
        resume: bool = False,
        progress_callback: Callable[[int, int | None], None] | None = None,
    ) -> int:
        clean_segment_id = str(segment_id or "").strip()
        if not clean_segment_id:
            raise ValueError("H3 分段编号不能为空")
        if isinstance(delivery, dict) and str(delivery.get("mode") or "") == (
            "runninghub_direct"
        ):
            original_signature = str(delivery.get("result_signature") or "")

            def download_direct(current_delivery: dict[str, Any]) -> int:
                direct_url = self._validated_direct_video_url(
                    current_delivery.get("download_url")
                )
                allowed_peer_ips = self._validate_direct_video_destination(direct_url)
                return self._download_request(
                    Request(
                        direct_url,
                        method="GET",
                        headers={"Accept": "video/mp4,*/*"},
                    ),
                    target,
                    max_bytes=max_bytes,
                    timeout_seconds=self.h3_download_read_idle_timeout_seconds,
                    connect_timeout_seconds=self.h3_download_connect_timeout_seconds,
                    total_timeout_seconds=self.h3_download_total_timeout_seconds,
                    failure_message="直连下载 RunningHub H3 分段失败",
                    remote_label="RunningHub",
                    resume=resume,
                    progress_callback=progress_callback,
                    allow_redirects=False,
                    use_h3_media_pool=True,
                    allowed_peer_ips=allowed_peer_ips,
                    resume_identity=original_signature,
                )

            try:
                return download_direct(delivery)
            except AuthCenterError as exc:
                if int(getattr(exc, "upstream_status_code", exc.status_code)) not in {
                    401, 403, 404
                }:
                    raise
            refreshed = self.refresh_h3_segment_delivery(token, clean_segment_id)
            if str(refreshed.get("result_signature") or "") != original_signature:
                raise AuthCenterError(
                    "H3 分段已产生新结果，本次旧版本下载已停止",
                    error_code="H3_RESULT_CHANGED",
                    status_code=409,
                    retryable=False,
                )
            return download_direct(refreshed)
        return self._download(
            f"/api/workbench/h3-segments/{clean_segment_id}/video",
            token,
            target,
            max_bytes=max_bytes,
            timeout_seconds=300.0,
            failure_message="下载 H3 标准化分段失败",
            resume=resume,
            progress_callback=progress_callback,
        )

    def _validated_direct_video_url(self, value: object) -> str:
        url = str(value or "").strip()
        parsed = urlsplit(url)
        if (
            parsed.scheme.lower() != "https"
            or not parsed.hostname
            or parsed.username is not None
            or parsed.password is not None
            or parsed.fragment
        ):
            raise ValueError("数字人网站返回了不安全的 H3 直达地址")
        try:
            port = parsed.port
        except ValueError as exc:
            raise ValueError("数字人网站返回了无效的 H3 直达端口") from exc
        if port not in {None, 443}:
            raise ValueError("H3 直达地址只能使用 HTTPS 标准端口")
        hostname = parsed.hostname.rstrip(".").lower()
        try:
            address = ipaddress.ip_address(hostname)
        except ValueError:
            address = None
        if address is not None and not address.is_global:
            raise ValueError("H3 直达地址不能指向本机、内网或保留地址")
        if self.h3_provider_allowed_hosts and not any(
            hostname == allowed or hostname.endswith("." + allowed)
            for allowed in self.h3_provider_allowed_hosts
        ):
            raise ValueError("H3 直达地址不在允许的供应商主机范围内")
        # RunningHub/COS object names may contain Chinese characters. urllib's
        # Request expects an ASCII-safe request target, so preserve existing
        # percent escapes while encoding only the path component.
        encoded_path = quote(parsed.path, safe="/%:@!$&'()*+,;=-._~")
        return urlunsplit(
            (parsed.scheme, parsed.netloc, encoded_path, parsed.query, parsed.fragment)
        )

    def _validate_direct_video_destination(self, url: str) -> tuple[str, ...]:
        if not self.h3_provider_allowed_hosts:
            return ()
        parsed = urlsplit(url)
        try:
            answers = socket.getaddrinfo(
                parsed.hostname, parsed.port or 443, type=socket.SOCK_STREAM
            )
        except OSError as exc:
            raise ValueError("H3 直达地址暂时无法解析") from exc
        approved: list[str] = []
        for answer in answers:
            address = ipaddress.ip_address(answer[4][0])
            if not address.is_global:
                raise ValueError("H3 直达地址解析到了本机、内网或保留地址")
            approved.append(str(address))
        return tuple(dict.fromkeys(approved))

    def _download(
        self,
        path: str,
        token: str,
        target: Path,
        *,
        max_bytes: int,
        timeout_seconds: float,
        failure_message: str,
        resume: bool = False,
        progress_callback: Callable[[int, int | None], None] | None = None,
    ) -> int:
        device_headers = self._device_business_headers(
            token, method="GET", path=path
        )
        request = Request(
            f"{self.base_url}{path}",
            method="GET",
            headers={"Authorization": f"Bearer {token}", "Accept": "*/*", **device_headers},
        )
        return self._download_request(
            request,
            target,
            max_bytes=max_bytes,
            timeout_seconds=timeout_seconds,
            failure_message=failure_message,
            remote_label="数字人网站",
            resume=resume,
            progress_callback=progress_callback,
        )

    def _download_request(
        self,
        request: Request,
        target: Path,
        *,
        max_bytes: int,
        timeout_seconds: float,
        failure_message: str,
        remote_label: str,
        resume: bool = False,
        progress_callback: Callable[[int, int | None], None] | None = None,
        allow_redirects: bool = True,
        connect_timeout_seconds: float | None = None,
        total_timeout_seconds: float | None = None,
        use_h3_media_pool: bool = False,
        allowed_peer_ips: tuple[str, ...] = (),
        resume_identity: str = "",
    ) -> int:
        target.parent.mkdir(parents=True, exist_ok=True)
        resume_metadata = target.with_name(target.name + ".resume.json")
        offset = target.stat().st_size if resume and target.is_file() else 0
        validator = ""
        if offset:
            try:
                stored = json.loads(resume_metadata.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                stored = {}
            if isinstance(stored, dict):
                stored_identity = str(stored.get("result_signature") or "")
                if resume_identity and stored_identity != resume_identity:
                    target.unlink(missing_ok=True)
                    resume_metadata.unlink(missing_ok=True)
                    offset = 0
                validator = str(
                    stored.get("etag") or stored.get("last_modified") or ""
                ).strip()
            if offset:
                request.add_header("Range", f"bytes={offset}-")
                if validator:
                    request.add_header("If-Range", validator)
        size = offset
        started_at = time.monotonic()
        try:
            connect_timeout = (
                max(1.0, float(connect_timeout_seconds))
                if connect_timeout_seconds is not None
                else max(self.timeout_seconds, timeout_seconds)
            )
            if use_h3_media_pool:
                opened_response = self._h3_media_session.open(
                    request,
                    connect_timeout=connect_timeout,
                    read_timeout=max(1.0, float(timeout_seconds)),
                    allowed_peer_ips=allowed_peer_ips,
                )
            else:
                opener = (
                    _device_urlopen
                    if request.has_header("Dpop")
                    else (urlopen if allow_redirects else _no_redirect_urlopen)
                )
                opened_response = opener(request, timeout=connect_timeout)
            with opened_response as response:
                if connect_timeout_seconds is not None and not use_h3_media_pool:
                    sock = getattr(
                        getattr(getattr(response, "fp", None), "raw", None),
                        "_sock",
                        None,
                    )
                    if sock is not None:
                        sock.settimeout(max(1.0, float(timeout_seconds)))
                status = int(getattr(response, "status", 200))
                append = bool(offset and status == 206)
                content_range = str(
                    getattr(response, "headers", {}).get("Content-Range") or ""
                ).strip()
                if append and not content_range.lower().startswith(
                    f"bytes {offset}-"
                ):
                    target.unlink(missing_ok=True)
                    resume_metadata.unlink(missing_ok=True)
                    raise AuthCenterError(
                        "远程文件断点范围与本地残片不一致",
                        status_code=502,
                        retryable=True,
                    )
                if not append:
                    size = 0
                content_type = str(
                    getattr(response, "headers", {}).get("Content-Type") or ""
                ).split(";", 1)[0].strip().lower()
                if use_h3_media_pool and content_type in {
                    "text/html", "text/plain", "application/json"
                }:
                    target.unlink(missing_ok=True)
                    resume_metadata.unlink(missing_ok=True)
                    raise AuthCenterError(
                        "RunningHub 返回的 H3 文件类型不是视频",
                        status_code=502,
                        retryable=False,
                    )
                content_length = str(
                    getattr(response, "headers", {}).get("Content-Length") or ""
                ).strip()
                declared_size = 0
                if content_length:
                    try:
                        declared_size = int(content_length)
                    except ValueError:
                        declared_size = 0
                    if size + declared_size > max_bytes:
                        target.unlink(missing_ok=True)
                        resume_metadata.unlink(missing_ok=True)
                        raise AuthCenterError(
                            "远程文件超过工作台允许的文件大小",
                            status_code=413,
                        )
                etag = str(
                    getattr(response, "headers", {}).get("ETag") or ""
                ).strip()
                last_modified = str(
                    getattr(response, "headers", {}).get("Last-Modified") or ""
                ).strip()
                resume_metadata.write_text(
                    json.dumps(
                        {
                            "etag": etag or None,
                            "last_modified": last_modified or None,
                            "result_signature": resume_identity or None,
                        },
                        ensure_ascii=False,
                    ),
                    encoding="utf-8",
                )
                total = size + declared_size if declared_size else None
                if progress_callback is not None:
                    progress_callback(size, total)
                with target.open("ab" if append else "wb") as output:
                    while True:
                        if (
                            total_timeout_seconds is not None
                            and time.monotonic() - started_at
                            > float(total_timeout_seconds)
                        ):
                            raise TimeoutError("H3 媒体下载超过总时限")
                        chunk = response.read(1024 * 1024)
                        if not chunk:
                            break
                        size += len(chunk)
                        if size > max_bytes:
                            raise AuthCenterError("远程文件超过工作台允许的文件大小", status_code=413)
                        output.write(chunk)
                        if progress_callback is not None:
                            progress_callback(size, total)
        except HTTPError as exc:
            raw = exc.read()
            if int(exc.code) == 416 and resume and target.is_file() and offset > 0:
                if progress_callback is not None:
                    progress_callback(offset, offset)
                resume_metadata.unlink(missing_ok=True)
                return offset
            if not resume or int(exc.code) not in {401, 403, 404, 429, 502, 503, 504}:
                target.unlink(missing_ok=True)
                resume_metadata.unlink(missing_ok=True)
            error = self._response_error(
                raw,
                int(exc.code),
                f"{remote_label}拒绝下载（HTTP {exc.code}）",
            )
            retry_after = str(getattr(exc, "headers", {}).get("Retry-After") or "").strip()
            if retry_after.isdigit():
                error.retry_after_seconds = min(3600, int(retry_after))
            elif retry_after:
                try:
                    retry_at = parsedate_to_datetime(retry_after).timestamp()
                    error.retry_after_seconds = min(
                        3600, max(0, round(retry_at - time.time()))
                    )
                except (TypeError, ValueError, OverflowError):
                    pass
            raise error from exc
        except (URLError, OSError, TimeoutError) as exc:
            if not resume:
                target.unlink(missing_ok=True)
                resume_metadata.unlink(missing_ok=True)
            raise AuthCenterConnectionError(
                f"{failure_message}，请检查{remote_label}是否在线"
            ) from exc
        except AuthCenterError as exc:
            if exc.status_code in {413, 422} or not exc.retryable:
                target.unlink(missing_ok=True)
                resume_metadata.unlink(missing_ok=True)
            raise
        except BaseException:
            if not resume:
                target.unlink(missing_ok=True)
                resume_metadata.unlink(missing_ok=True)
            raise
        if size <= 0:
            target.unlink(missing_ok=True)
            resume_metadata.unlink(missing_ok=True)
            raise AuthCenterError(f"{remote_label}返回了空文件")
        resume_metadata.unlink(missing_ok=True)
        return size

    def _multipart_post(
        self,
        path: str,
        fields: dict[str, Any],
        files: list[tuple[str, str, bytes, str]],
    ) -> dict[str, Any]:
        device_headers = self._device_business_headers(
            str(fields.get("access_token") or ""), method="POST", path=path
        )
        if device_headers:
            fields = {
                key: value
                for key, value in fields.items()
                if key != "access_token"
            }
        boundary = f"----jyd-{secrets.token_hex(16)}"
        chunks: list[bytes] = []
        for name, value in fields.items():
            chunks.extend(
                [
                    f"--{boundary}\r\n".encode("ascii"),
                    (
                        f'Content-Disposition: form-data; name="{name}"\r\n\r\n'
                    ).encode("utf-8"),
                    str(value).lower().encode("utf-8")
                    if isinstance(value, bool)
                    else str(value).encode("utf-8"),
                    b"\r\n",
                ]
            )
        for field_name, filename, content, content_type in files:
            safe_filename = filename.replace('"', "")
            chunks.extend(
                [
                    f"--{boundary}\r\n".encode("ascii"),
                    (
                        f'Content-Disposition: form-data; name="{field_name}"; '
                        f'filename="{safe_filename}"\r\n'
                    ).encode("utf-8"),
                    f"Content-Type: {content_type}\r\n\r\n".encode("ascii"),
                    content,
                    b"\r\n",
                ]
            )
        chunks.append(f"--{boundary}--\r\n".encode("ascii"))
        request = Request(
            f"{self.base_url}{path}",
            data=b"".join(chunks),
            method="POST",
            headers={
                "Content-Type": f"multipart/form-data; boundary={boundary}",
                "Accept": "application/json",
                **device_headers,
            },
        )
        return self._read_json_response(request, timeout_seconds=300.0)

    def _post(
        self,
        path: str,
        payload: dict[str, Any],
        *,
        timeout_seconds: float | None = None,
        extra_headers: dict[str, str] | None = None,
        connect_timeout_seconds: float | None = None,
        use_default_timeout_floor: bool = True,
    ) -> dict[str, Any]:
        device_headers = self._device_business_headers(
            str(payload.get("access_token") or ""), method="POST", path=path
        )
        if device_headers:
            payload = {key: value for key, value in payload.items() if key != "access_token"}
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        request = Request(
            f"{self.base_url}{path}",
            data=body,
            method="POST",
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json",
                **(extra_headers or {}),
                **device_headers,
            },
        )
        return self._read_json_response(
            request,
            timeout_seconds=(
                self.timeout_seconds
                if timeout_seconds is None
                else (
                    max(self.timeout_seconds, float(timeout_seconds))
                    if use_default_timeout_floor
                    else max(1.0, float(timeout_seconds))
                )
            ),
            connect_timeout_seconds=connect_timeout_seconds,
        )

    def _read_json_response(
        self,
        request: Request,
        *,
        timeout_seconds: float,
        connect_timeout_seconds: float | None = None,
    ) -> dict[str, Any]:
        try:
            opener = _device_urlopen if request.has_header("Dpop") else urlopen
            connect_timeout = (
                timeout_seconds
                if connect_timeout_seconds is None
                else min(timeout_seconds, max(1.0, float(connect_timeout_seconds)))
            )
            with opener(request, timeout=connect_timeout) as response:
                # urllib uses one socket timeout for connect and read. Once the
                # connection is established, widen only the read timeout to the
                # remaining end-to-end budget.
                sock = getattr(
                    getattr(getattr(response, "fp", None), "raw", None),
                    "_sock",
                    None,
                )
                if sock is not None:
                    sock.settimeout(timeout_seconds)
                raw = response.read()
                status = int(getattr(response, "status", 200))
        except HTTPError as exc:
            raw = exc.read()
            raise self._response_error(
                raw,
                int(exc.code),
                f"数字人网站拒绝请求（HTTP {exc.code}）",
                retry_after_header=exc.headers.get("Retry-After"),
            ) from exc
        except (URLError, OSError, TimeoutError) as exc:
            raise AuthCenterConnectionError(
                f"无法连接数字人网站 {self.base_url}，请确认数字人网站已经启动"
            ) from exc
        if status < 200 or status >= 300:
            raise self._response_error(raw, status, f"数字人网站返回 HTTP {status}")
        try:
            data = json.loads(raw.decode("utf-8")) if raw else {}
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise AuthCenterError(
                "数字人网站返回了无法识别的数据",
                status_code=502,
                error_code="DIGITAL_HUMAN_INVALID_RESPONSE",
                retryable=True,
            ) from exc
        if not isinstance(data, dict):
            raise AuthCenterError(
                "数字人网站返回格式错误",
                status_code=502,
                error_code="DIGITAL_HUMAN_INVALID_RESPONSE",
                retryable=True,
            )
        return data

    @classmethod
    def _response_error(
        cls,
        raw: bytes,
        status: int,
        fallback: str,
        *,
        retry_after_header: str | None = None,
    ) -> AuthCenterError:
        try:
            data = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            data = {}
        code = data.get("code") if isinstance(data, dict) else None
        if isinstance(code, str) and len(code) <= 64 and code.replace("_", "").isascii() and code.replace("_", "").isalnum() and (
            code.startswith(("DEVICE_", "INVALID_DEVICE_")) or code in {"AUTH_REFRESH_REQUIRED", "CLIENT_UPGRADE_REQUIRED", "AMBIGUOUS_ACCOUNT_TOKEN"}
        ):
            return AuthCenterDeviceError(cls._detail(raw) or "请检查当前处理机的设备授权", error_code=code, status_code=status)
        if (
            isinstance(code, str)
            and 1 <= len(code) <= 64
            and code.replace("_", "").isalnum()
            and code.replace("_", "").isascii()
        ):
            return AuthCenterError(
                cls._detail(raw) or fallback,
                status_code=status,
                error_code=code,
                retryable=status in {429, 502, 503, 504},
                retry_after_seconds=cls._retry_after_seconds(retry_after_header),
            )
        return AuthCenterError(
            cls._detail(raw) or fallback,
            status_code=status,
            retry_after_seconds=cls._retry_after_seconds(retry_after_header),
        )

    @staticmethod
    def _retry_after_seconds(value: str | None) -> float | None:
        clean = str(value or "").strip()
        if not clean:
            return None
        try:
            return min(60.0, max(0.0, float(clean)))
        except ValueError:
            try:
                return min(
                    60.0,
                    max(0.0, parsedate_to_datetime(clean).timestamp() - time.time()),
                )
            except (TypeError, ValueError, OverflowError):
                return None

    @staticmethod
    def _detail(raw: bytes) -> str:
        try:
            data = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            return ""
        if not isinstance(data, dict):
            return ""
        detail = str(data.get("detail", "")).strip()
        errors = data.get("errors")
        if isinstance(errors, list):
            messages = [
                str(item.get("message") or "").strip()
                for item in errors
                if isinstance(item, dict) and str(item.get("message") or "").strip()
            ]
            if messages:
                return f"{detail}：{'；'.join(messages)}" if detail else "；".join(messages)
        return detail
