"""Owner-only cloud queue recovery; read/review never submits new work."""

from __future__ import annotations

import re
from fastapi import Body, HTTPException, Request
from fastapi.responses import JSONResponse
from .auth_center import AuthCenterError
from .device_authorization_routes import _same_origin_action


def install_h3_recovery_routes(app, *, current_user, client_access):
    def invoke(request, method, *args, **kwargs):
        current_user(request)
        client, token = client_access(request)
        try:
            result = getattr(client, method)(token, *args, **kwargs)
        except AuthCenterError as exc:
            return JSONResponse(
                {
                    "detail": str(exc),
                    "code": exc.error_code,
                    "device_authorization_required": bool(exc.response_headers),
                },
                status_code=exc.status_code,
                headers={**exc.response_headers, "Cache-Control": "no-store"},
            )
        return JSONResponse(result, headers={"Cache-Control": "no-store"})

    def valid_id(value):
        if not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", value):
            raise HTTPException(status_code=422, detail="批次或分页标识无效")

    @app.get("/api/new/device-authorization/h3-waiting")
    def waiting(request: Request, after_id: str = ""):
        if after_id:
            valid_id(after_id)
        return invoke(request, "list_h3_authorization_waiting", after_id=after_id)

    @app.post("/api/new/device-authorization/h3/{batch_id}/prepare")
    def prepare(batch_id: str, request: Request):
        _same_origin_action(request)
        valid_id(batch_id)
        return invoke(request, "prepare_h3_authorization_recovery", batch_id)

    @app.post("/api/new/device-authorization/h3/{batch_id}/resume")
    def resume(batch_id: str, request: Request, payload: dict = Body(...)):
        _same_origin_action(request)
        valid_id(batch_id)
        if set(payload) != {"resume_confirmed", "request_key", "review_token"}:
            raise HTTPException(status_code=422, detail="恢复参数无效，请重新查看分段")
        if payload["resume_confirmed"] is not True:
            raise HTTPException(
                status_code=409, detail="请明确确认继续原分段及原计划费用"
            )
        if (
            not isinstance(payload["request_key"], str)
            or not re.fullmatch(r"[A-Za-z0-9_-]{8,100}", payload["request_key"])
            or not isinstance(payload["review_token"], str)
            or not re.fullmatch(r"[a-f0-9]{64}", payload["review_token"])
        ):
            raise HTTPException(status_code=422, detail="恢复请求或分段版本无效")
        return invoke(
            request,
            "resume_h3_authorization_recovery",
            batch_id,
            request_key=payload["request_key"],
            review_token=payload["review_token"],
            resume_confirmed=True,
        )
