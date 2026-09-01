"""Bounded, no-redirect Agent transport; never replay central mutations silently."""

from __future__ import annotations

import re
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, Request, build_opener

from .device_agent_protocol import AgentRequestContext, agent_origin, fail
from .device_auth_protocol import canonical_json, strict_json
from .device_local_execution import requires_device_authorization

MAX_RESPONSE = 8 * 1024 * 1024
CHALLENGE_PATH = "/api/agents/device-authorization/challenge"


class AgentRequestError(RuntimeError):
    def __init__(self, code, status=0):
        self.code, self.status_code = code, status
        super().__init__(f"中央服务请求未完成（{code}），不会自动重复执行任务")


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class AgentApiClient:
    def __init__(
        self, server_url, token, timeout=30, *, authorizer=None, agent_id=None
    ):
        self.server_url = agent_origin(server_url.strip())
        self.token = token.strip()
        self.timeout = max(5, min(120, int(timeout)))
        self.authorizer, self.agent_id = authorizer, agent_id
        self._opener = build_opener(_NoRedirect())
        if (
            not self.token
            or len(self.token) > 8192
            or any(ord(c) <= 32 or ord(c) >= 127 for c in self.token)
        ):
            raise ValueError("缺少有效的处理机接入密码")
        if requires_device_authorization() and authorizer is None:
            fail("DEVICE_AGENT_PROTOCOL_REQUIRED", "请先登录执行机的网站账号", 409)

    def _send(self, path, payload, extra_headers=None):
        if (
            not isinstance(path, str)
            or not path.startswith("/api/agents/")
            or any(c in path for c in "?#\\\r\n")
        ):
            fail("INVALID_AGENT_REQUEST", "中央请求地址无效", 422)
        request = Request(
            self.server_url + path,
            data=canonical_json(payload).encode("ascii"),
            method="POST",
            headers={
                "Authorization": "Bearer " + self.token,
                "Content-Type": "application/json",
                **(extra_headers or {}),
            },
        )
        try:
            with self._opener.open(request, timeout=self.timeout) as response:
                raw = response.read(MAX_RESPONSE + 1)
            if len(raw) > MAX_RESPONSE:
                raise AgentRequestError("RESPONSE_TOO_LARGE")
            result = strict_json(raw)
            if not isinstance(result, dict):
                raise ValueError()
            return result
        except HTTPError as exc:
            code = "HTTP_" + str(exc.code)
            try:
                raw = exc.read(8193)
                if len(raw) <= 8192:
                    parsed = strict_json(raw)
                    candidate = parsed.get("code") if isinstance(parsed, dict) else None
                    if isinstance(candidate, str) and re.fullmatch(
                        r"[A-Z][A-Z0-9_]{1,79}", candidate
                    ):
                        code = candidate
            except (ValueError, TypeError, UnicodeError, OSError):
                pass
            finally:
                exc.close()
            raise AgentRequestError(code, exc.code) from None
        except (URLError, OSError, TimeoutError):
            raise AgentRequestError("CONNECTION_UNCERTAIN") from None
        except (ValueError, TypeError, UnicodeError, RecursionError):
            raise AgentRequestError("INVALID_RESPONSE") from None

    def post(self, path, payload=None):
        payload = {} if payload is None else payload
        if not isinstance(payload, dict):
            fail("INVALID_AGENT_REQUEST", "处理机请求必须为对象", 422)
        if self.authorizer is None:
            if requires_device_authorization():
                fail("DEVICE_AGENT_PROTOCOL_REQUIRED", "执行机缺少设备授权会话", 409)
            return self._send(path, payload)
        context = AgentRequestContext.for_request(
            self.server_url, self.agent_id, path, payload
        )
        challenge = self._send(
            CHALLENGE_PATH,
            {"agent_id": self.agent_id, "path": path, "payload": payload},
        )
        if (
            set(challenge) != {"schema", "nonce", "expires_in"}
            or challenge["schema"] != "publicvideo.agent-challenge.v1"
            or type(challenge["expires_in"]) is not int
            or not 0 < challenge["expires_in"] <= 120
            or not isinstance(challenge["nonce"], str)
            or not re.fullmatch(r"[A-Za-z0-9_-]{32,128}", challenge["nonce"])
        ):
            raise AgentRequestError("INVALID_CHALLENGE")
        headers = self.authorizer.headers(context, challenge["nonce"])
        return self._send(path, payload, headers)  # Exactly one business request.
