"""Central Agent HTTP surface: verify the executing machine, not the launcher."""

from __future__ import annotations

from typing import Any

from fastapi import Body, HTTPException, Request
from fastapi.responses import JSONResponse

from . import device_agent_operations as operations
from .device_agent_gate import AgentAuthorizationGate
from .device_agent_protocol import AgentRequestContext, fail
from .device_local_execution import requires_device_authorization
from .device_local_queue import sync_authorization_status


def install_device_agent_routes(app, *, queue, settings, require_agent_token):
    gate = AgentAuthorizationGate(queue.store, settings.auth_server_url)
    app.state.agent_authorization_gate = gate

    def response(value):
        return JSONResponse(value, headers={"Cache-Control": "no-store"})

    def origin(request):
        if request.url.query:
            fail("INVALID_AGENT_REQUEST", "处理机接口不接受查询参数", 422)
        return f"{request.url.scheme}://{request.url.netloc}"

    def decision(request, agent_id, payload):
        require_agent_token(request)
        if not requires_device_authorization() and not any(
            key in request.headers
            for key in ("x-workbench-agent-permit", "x-workbench-agent-proof")
        ):
            return None  # Unconfigured source development only, never frozen.
        permit = request.headers.get("x-workbench-agent-permit", "")
        if not permit:
            fail(
                "DEVICE_AGENT_PROTOCOL_REQUIRED",
                "请使用支持设备授权的处理机并登录获准账号",
                409,
            )
        try:
            path = request.scope.get("raw_path", b"").decode("ascii")
        except UnicodeError:
            fail("INVALID_AGENT_REQUEST", "处理机请求地址编码无效", 422)
        context = AgentRequestContext.for_request(
            origin(request), agent_id, path, payload
        )
        return gate.verify(
            context,
            permit=permit,
            proof=request.headers.get("x-workbench-agent-proof", ""),
        )

    @app.post("/api/agents/device-authorization/challenge")
    def challenge(request: Request, payload: dict[str, Any] = Body(...)):
        require_agent_token(request)
        if set(payload) != {"agent_id", "path", "payload"} or not isinstance(
            payload["path"], str
        ):
            fail("INVALID_AGENT_REQUEST", "处理机挑战参数无效", 422)
        context = AgentRequestContext.for_request(
            origin(request), payload["agent_id"], payload["path"], payload["payload"]
        )
        return response(gate.challenge(context))

    @app.post("/api/agents/register")
    def register(request: Request, payload: dict[str, Any] = Body(...)):
        agent_id = payload.get("agent_id")
        if not isinstance(agent_id, str) or not agent_id:
            fail("INVALID_AGENT_REQUEST", "缺少处理机编号", 422)
        authorized = decision(request, agent_id, payload)
        if authorized is None:
            return response(queue.register_agent(agent_id, payload))
        return response(
            operations.register_agent(queue.store, agent_id, payload, authorized)
        )

    @app.post("/api/agents/{agent_id}/heartbeat")
    def heartbeat(
        agent_id: str, request: Request, payload: dict[str, Any] = Body(default={})
    ):
        authorized = decision(request, agent_id, payload)
        if authorized is not None:
            return response(
                operations.heartbeat_agent(queue.store, agent_id, authorized)
            )
        try:
            return response(queue.heartbeat_agent(agent_id, payload))
        except KeyError:
            raise HTTPException(status_code=404, detail="处理机尚未注册") from None

    @app.post("/api/agents/{agent_id}/claim")
    def claim(
        agent_id: str, request: Request, payload: dict[str, Any] = Body(default={})
    ):
        authorized = decision(request, agent_id, payload)
        if payload:
            fail("INVALID_AGENT_REQUEST", "领取任务不接受自报账号、权限或任务编号", 422)
        try:
            return response(
                {"job": queue.claim_agent_job(agent_id, authorization=authorized)}
            )
        except KeyError:
            raise HTTPException(status_code=404, detail="处理机尚未注册") from None

    @app.post("/api/agents/{agent_id}/jobs/{job_id}/start")
    def start(
        agent_id: str,
        job_id: str,
        request: Request,
        payload: dict[str, Any] = Body(...),
    ):
        authorized = decision(request, agent_id, payload)
        if authorized is None or set(payload) != {"execution_id"}:
            fail("DEVICE_AGENT_PROTOCOL_REQUIRED", "启动回执需要完整执行机授权", 409)
        if queue.execution_mode != "agent":
            fail("DEVICE_AGENT_START_DENIED", "中央服务当前不是独立处理机模式", 409)
        receipt = operations.start_job(
            queue.store,
            agent_id,
            job_id,
            payload["execution_id"],
            authorized,
            lease_seconds=settings.agent_lease_seconds,
        )
        sync_authorization_status(
            settings.storage_root / "jobs" / job_id / "status.json",
            queue.store.get_status(job_id),
        )
        return response(receipt)

    @app.post("/api/agents/{agent_id}/jobs/{job_id}/recovery/prepare")
    def recovery_prepare(
        agent_id: str,
        job_id: str,
        request: Request,
        payload: dict[str, Any] = Body(...),
    ):
        authorized = decision(request, agent_id, payload)
        if authorized is None or set(payload) != {"execution_id", "payload_hash"}:
            fail("INVALID_AGENT_RECOVERY", "核实需要原账号与原执行机的完整证明", 409)
        return response(
            operations.prepare_recovery(
                queue.store,
                agent_id,
                job_id,
                payload["execution_id"],
                payload["payload_hash"],
                authorized,
            )
        )

    @app.post("/api/agents/{agent_id}/jobs/{job_id}/recovery/resolve")
    def recovery_resolve(
        agent_id: str,
        job_id: str,
        request: Request,
        payload: dict[str, Any] = Body(...),
    ):
        authorized = decision(request, agent_id, payload)
        if authorized is None:
            fail("DEVICE_AGENT_PROTOCOL_REQUIRED", "核实需要原执行机授权", 409)
        # Validate before any report mutation, including before interpreting result/error.
        operations.validate_recovery(payload)
        result = queue.finish_agent_job(
            agent_id,
            job_id,
            result=payload["result"],
            error=payload["error"],
            authorization=authorized,
            execution_id=payload["execution_id"],
            recovery=payload,
        )
        return response(result)

    @app.post("/api/agents/{agent_id}/jobs/{job_id}/heartbeat")
    def job_heartbeat(
        agent_id: str,
        job_id: str,
        request: Request,
        payload: dict[str, Any] = Body(default={}),
    ):
        authorized = decision(request, agent_id, payload)
        try:
            return response(
                queue.heartbeat_agent_job(
                    agent_id, job_id, payload, authorization=authorized
                )
            )
        except KeyError:
            raise HTTPException(
                status_code=409, detail="任务未分配给当前处理机"
            ) from None

    @app.post("/api/agents/{agent_id}/jobs/{job_id}/complete")
    def complete(
        agent_id: str,
        job_id: str,
        request: Request,
        payload: dict[str, Any] = Body(...),
    ):
        authorized = decision(request, agent_id, payload)
        result = payload.get("result")
        if not isinstance(result, dict):
            fail("INVALID_AGENT_REQUEST", "result 必须是对象", 422)
        try:
            return response(
                queue.finish_agent_job(
                    agent_id,
                    job_id,
                    result=result,
                    authorization=authorized,
                    execution_id=payload.get("execution_id"),
                )
            )
        except KeyError:
            raise HTTPException(
                status_code=409, detail="任务未分配给当前处理机"
            ) from None

    @app.post("/api/agents/{agent_id}/jobs/{job_id}/fail")
    def failed(
        agent_id: str,
        job_id: str,
        request: Request,
        payload: dict[str, Any] = Body(default={}),
    ):
        authorized = decision(request, agent_id, payload)
        try:
            return response(
                queue.finish_agent_job(
                    agent_id,
                    job_id,
                    error=str(payload.get("error") or "处理机报告任务失败"),
                    authorization=authorized,
                    execution_id=payload.get("execution_id"),
                )
            )
        except KeyError:
            raise HTTPException(
                status_code=409, detail="任务未分配给当前处理机"
            ) from None
