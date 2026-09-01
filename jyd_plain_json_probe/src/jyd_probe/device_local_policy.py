"""Pinned, nonce-bound local rollout policy. An OFF JSON field is not permission."""

from __future__ import annotations

import hmac
import re
import secrets

import jwt

from .device_auth_protocol import (
    DeviceAuthorizationError,
    PRODUCT,
    sha256_b64,
    strict_jwt_parts,
)

POLICY_TYPE = "workbench-local-policy+jwt"
POLICY_AUDIENCE = PRODUCT + ":local-policy"
POLICY_SCHEMA = "publicvideo.local-policy.v1"
POLICY_SECONDS = 300


def verify_local_policy(trust, token, *, user_id, account_token, nonce, now):
    try:
        header, claims = strict_jwt_parts(token)
        if (
            set(header) != {"alg", "typ", "kid"}
            or header["alg"] != "ES256"
            or header["typ"] != POLICY_TYPE
        ):
            raise ValueError()
        jwt.decode(
            token,
            trust.verification_keys[header["kid"]],
            algorithms=["ES256"],
            issuer=trust.issuer,
            audience=POLICY_AUDIENCE,
            options={
                "verify_iat": False,
                "verify_exp": False,
                "verify_nbf": False,
                "require": ["iss", "aud", "sub", "iat", "nbf", "exp", "jti"],
            },
        )
        expected = {
            "schema",
            "iss",
            "aud",
            "product",
            "environment",
            "sub",
            "user_id",
            "ath",
            "nonce",
            "mode",
            "control_revision",
            "iat",
            "nbf",
            "exp",
            "jti",
        }
        if (
            set(claims) != expected
            or claims["schema"] != POLICY_SCHEMA
            or claims["product"] != PRODUCT
            or claims["environment"] != trust.environment
            or claims["aud"] != POLICY_AUDIENCE
            or claims["mode"] not in {"OFF", "OBSERVE", "ENFORCE"}
        ):
            raise ValueError()
        for name in ("user_id", "control_revision", "iat", "nbf", "exp"):
            if type(claims[name]) is not int or claims[name] < 1:
                raise ValueError()
        if (
            claims["user_id"] != user_id
            or claims["sub"] != str(user_id)
            or claims["nbf"] != claims["iat"]
            or claims["iat"] > now + 5
            or now >= claims["exp"]
            or not 0 < claims["exp"] - claims["iat"] <= POLICY_SECONDS
        ):
            raise ValueError()
        for field, value in (("ath", sha256_b64(account_token)), ("nonce", nonce)):
            if not isinstance(claims[field], str) or not hmac.compare_digest(
                claims[field], value
            ):
                raise ValueError()
        if not isinstance(claims["jti"], str) or not re.fullmatch(
            r"[A-Za-z0-9_-]{16,128}", claims["jti"]
        ):
            raise ValueError()
        return claims
    except (
        ValueError,
        TypeError,
        KeyError,
        UnicodeError,
        RecursionError,
        jwt.PyJWTError,
    ) as exc:
        raise DeviceAuthorizationError(
            "INVALID_DEVICE_LOCAL_POLICY",
            "本地授权策略校验失败，请联网重新校验",
            status_code=409,
        ) from exc


class LocalPolicySession:
    def __init__(
        self, *, trust, transport, user_id, account_token, wall_clock, monotonic_clock
    ):
        self.trust, self.transport, self.user_id = trust, transport, user_id
        self._token, self._wall, self._mono = account_token, wall_clock, monotonic_clock
        self._claims = None
        self._wall_anchor = self._mono_anchor = 0.0
        self._revision = 0

    def _valid(self):
        if self._claims is None:
            return False
        elapsed = self._mono() - self._mono_anchor
        return (
            elapsed >= 0
            and abs((self._wall() - self._wall_anchor) - elapsed) <= 5
            and elapsed < self._claims["exp"] - self._wall_anchor
            and self._wall() < self._claims["exp"]
        )

    def mode(self, *, force=False):
        if not force and self._valid():
            return self._claims["mode"]
        nonce = secrets.token_urlsafe(32)
        try:
            response = self.transport.request(
                method="POST",
                path="/api/workbench/device-auth/local-policy",
                headers={"Authorization": "Bearer " + self._token},
                payload={"nonce": nonce},
            )
            claims = verify_local_policy(
                self.trust,
                response.get("policy_token"),
                user_id=self.user_id,
                account_token=self._token,
                nonce=nonce,
                now=self._wall(),
            )
            if claims["control_revision"] < self._revision:
                raise DeviceAuthorizationError(
                    "INVALID_DEVICE_LOCAL_POLICY",
                    "授权策略版本倒退，请联系管理员",
                    status_code=409,
                )
            self._revision = claims["control_revision"]
            self._claims = claims
            self._wall_anchor, self._mono_anchor = self._wall(), self._mono()
            return claims["mode"]
        except DeviceAuthorizationError as exc:
            self._claims = None
            if exc.transient:
                # Stricter fallback grants nothing. The caller must now validate
                # an actual device lease/key, within its original offline expiry.
                return "ENFORCE"
            raise

    def clear(self):
        self._claims, self._token = None, ""
