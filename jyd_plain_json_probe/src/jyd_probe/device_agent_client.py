"""Acquire narrowly scoped Agent permits using this process's account/key."""

from __future__ import annotations

from .device_agent_protocol import verify_agent_permit, sign_agent_request
from .device_auth_protocol import DeviceAuthorizationError, make_proof
from .device_identity_windows import DeviceIdentityError

PERMIT_PATH = "/api/workbench/device-auth/agent-permit"


class AgentRequestAuthorizer:
    def __init__(self, session):
        self.session = session

    def headers(self, context, nonce):
        session = self.session
        with session._lock:
            if session._closed:
                raise DeviceAuthorizationError(
                    "LOGIN_REQUIRED", "请在执行机重新登录", status_code=401
                )
            key = None
            try:
                if context.intent == "execute":
                    headers = session.request_headers(
                        method="POST", path=PERMIT_PATH, scope=None
                    )
                    key = session._ensure_key()
                else:
                    # Reporting an admitted job must survive grant suspension and
                    # expiry of the old device access token. The original account
                    # plus its actual key is proved afresh; no business credential
                    # is issued and the central queue still verifies assignment.
                    key = session._ensure_key()
                    token = session._login_token
                    challenge = session._transport.request(
                        method="POST",
                        path="/api/workbench/device-auth/challenge",
                        headers={"Authorization": "Bearer " + token},
                        payload={"public_jwk": key.public_jwk, "purpose": "request"},
                    )
                    headers = {
                        "Authorization": "Bearer " + token,
                        "DPoP": make_proof(
                            key,
                            session.trust,
                            method="POST",
                            path=PERMIT_PATH,
                            access_token=token,
                            nonce=challenge["nonce"],
                            now=int(session._wall()),
                        ),
                    }
            except (DeviceAuthorizationError, DeviceIdentityError):
                # No central work request has been sent. Only the authority can
                # allow OFF/OBSERVE; ENFORCE rejects this unbound permit request.
                key = None
                headers = {"Authorization": "Bearer " + session._login_token}

            def request_permit(request_headers):
                return session._transport.request(
                    method="POST",
                    path=PERMIT_PATH,
                    headers=request_headers,
                    payload={
                        "nonce": nonce,
                        "context_hash": context.digest,
                        "intent": context.intent,
                    },
                )

            try:
                result = request_permit(headers)
            except DeviceAuthorizationError as exc:
                if (
                    exc.code != "AUTH_REFRESH_REQUIRED"
                    or context.intent != "execute"
                    or not headers["Authorization"].startswith("DPoP ")
                ):
                    raise
                # Only the permit is retried once. No queue request or paid work
                # has been sent; refresh keeps the original device/grant.
                session.refresh(force=True)
                headers = session.request_headers(
                    method="POST", path=PERMIT_PATH, scope=None
                )
                key = session._ensure_key()
                result = request_permit(headers)
            if not isinstance(result, dict) or set(result) != {"agent_permit"}:
                raise DeviceAuthorizationError(
                    "INVALID_AGENT_AUTHORIZATION", "处理机许可响应无效"
                )
            permit = result["agent_permit"]
            decision = verify_agent_permit(
                session.trust,
                permit,
                context,
                now=session._wall(),
                nonce=nonce,
                user_id=session.user_id,
            )
            proof = ""
            if decision.thumbprint is not None:
                if key is None or key.thumbprint != decision.thumbprint:
                    raise DeviceAuthorizationError(
                        "DEVICE_IDENTITY_MISMATCH", "处理机许可不属于本机原密钥"
                    )
                proof = sign_agent_request(
                    key, permit, context, nonce=nonce, now=int(session._wall())
                )
            return {
                "X-Workbench-Agent-Permit": permit,
                "X-Workbench-Agent-Proof": proof,
            }
