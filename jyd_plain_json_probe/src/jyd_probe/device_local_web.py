"""Bind request identity internally, before local side effects; no UI-supplied grant."""

from __future__ import annotations

import re

from fastapi import Request, HTTPException
from fastapi.responses import JSONResponse
from starlette.concurrency import run_in_threadpool

from .device_auth_protocol import DeviceAuthorizationError
from .device_identity_windows import DeviceIdentityError
from .device_local_execution import (
    LocalDeviceAuthorizer,
    local_authorization_context,
    requires_device_authorization,
)


def local_failure(error):
    code = error.code
    status = getattr(error, "status_code", 409)
    if status == 401 and code != "LOGIN_REQUIRED":
        status = 409
    return JSONResponse(
        {"detail": str(error), "code": code, "device_authorization_required": True},
        status_code=status,
        headers={"Cache-Control": "no-store", "X-Workbench-Device-Error": code},
    )


class RequestLocalAuthorizer:
    def __init__(self, request, registry, current_user, cookie_name):
        self.request, self.registry, self.current_user, self.cookie_name = (
            request,
            registry,
            current_user,
            cookie_name,
        )
        self._authorizer = None

    def authorize(self, scopes):
        if self._authorizer is None:
            user = self.current_user(self.request)
            session = self.registry.get(
                str(user["user_id"]), self.request.cookies.get(self.cookie_name, "")
            )
            self._authorizer = LocalDeviceAuthorizer(session)
        return self._authorizer.authorize(scopes)


class LocalExecutionMiddleware:
    def __init__(self, app, *, registry, current_user, cookie_name):
        self.app, self.registry, self.current_user, self.cookie_name = (
            app,
            registry,
            current_user,
            cookie_name,
        )

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or not requires_device_authorization():
            return await self.app(scope, receive, send)
        request = Request(scope, receive)
        authorizer = RequestLocalAuthorizer(
            request, self.registry, self.current_user, self.cookie_name
        )
        path = scope.get("path", "")
        local_start = request.method == "POST" and (
            re.fullmatch(
                r"/api/new/projects/[^/]+/(?:postprocess/generate|variants/generate|items/[^/]+/(?:postprocess/export|variants/(?:supplement|retry)))",
                path,
            )
        )
        if local_start:
            try:
                # Preflight before coordinator mutations/ASR. The queue and the
                # actual renderer repeat checks at their own operation boundary.
                scopes = (
                    {"local:draft"}
                    if path.endswith("/postprocess/generate")
                    else {"local:draft", "local:render"}
                )
                await run_in_threadpool(authorizer.authorize, scopes)
            except (DeviceAuthorizationError, DeviceIdentityError) as exc:
                return await local_failure(exc)(scope, receive, send)
            except HTTPException as exc:
                return await JSONResponse(
                    {"detail": exc.detail}, status_code=exc.status_code
                )(scope, receive, send)
        with local_authorization_context(authorizer):
            await self.app(scope, receive, send)


def install_local_execution(app, *, registry, current_user, cookie_name):
    app.add_middleware(
        LocalExecutionMiddleware,
        registry=registry,
        current_user=current_user,
        cookie_name=cookie_name,
    )

    async def failed(request, error):
        return local_failure(error)

    app.add_exception_handler(DeviceAuthorizationError, failed)
    app.add_exception_handler(DeviceIdentityError, failed)
