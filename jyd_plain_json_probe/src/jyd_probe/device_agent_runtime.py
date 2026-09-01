"""Authorized Agent execution with durable pre-start and result receipts."""

from __future__ import annotations

import threading
from urllib.parse import quote

from .device_agent_protocol import fail
from .device_local_execution import (
    LocalDeviceAuthorizer,
    authorized_local_unit,
    local_authorization_context,
    render_operation_scopes,
)


class AuthorizedAgentRunner:
    def __init__(self, agent, session, journal, render):
        self.agent, self.session, self.journal, self.render = (
            agent,
            session,
            journal,
            render,
        )
        self.prefix = "/api/agents/" + quote(agent.agent_id, safe="-_.")
        self.registered = False
        self.last_error = None

    def _register(self):
        if not self.registered:
            self.agent.register()
            self.registered = True

    def run(self, *, once, stop_event):
        with self.journal.single_process():
            while not stop_event.is_set():
                try:
                    pending = self.journal.pending(
                        self.agent.client.server_url,
                        self.agent.agent_id,
                        self.session.user_id,
                    )
                    handled = False
                    for receipt in pending:
                        if receipt["phase"] == "executing":
                            fail(
                                "DEVICE_AGENT_EXECUTION_UNCERTAIN",
                                "上次渲染是否结束尚未确认；已保留回执，不会重复执行",
                                409,
                            )
                        if receipt["phase"] == "recovery_pending":
                            from .device_agent_recovery import deliver_recovery

                            deliver_recovery(self.agent.client, self.journal, receipt)
                        elif receipt["phase"] == "report_pending":
                            # Before registration/new-work authorization: an old
                            # admitted result may still be reported after revoke.
                            self._report(receipt)
                        elif receipt["phase"] == "prepared":
                            self._register()
                            self._execute(receipt)
                        else:
                            fail(
                                "DEVICE_AGENT_RECEIPT_CONFLICT",
                                "本地执行回执状态异常",
                                409,
                            )
                        handled = True
                    if handled and once:
                        return 0
                    if self.journal.has_unresolved_execution():
                        fail(
                            "DEVICE_AGENT_EXECUTION_UNCERTAIN",
                            "本机还有未确认结束的渲染，请先核对原执行记录",
                            409,
                        )
                    self._register()
                    claimed = self.agent.client.post(self.prefix + "/claim").get("job")
                    if claimed is not None:
                        self._validate_claim(claimed)
                        payload = self.agent._localize_payload(claimed["payload"])
                        receipt = self.journal.prepare(
                            self.agent.client.server_url,
                            self.agent.agent_id,
                            self.session.user_id,
                            claimed,
                            payload,
                        )
                        if receipt["phase"] == "acknowledged":
                            fail(
                                "DEVICE_AGENT_RESULT_CONFLICT",
                                "中央服务再次返回已完成任务，未重新渲染",
                                409,
                            )
                        if receipt["phase"] != "prepared":
                            fail(
                                "DEVICE_AGENT_EXECUTION_UNCERTAIN",
                                "原任务已有执行记录，未重复启动",
                                409,
                            )
                        self._execute(receipt)
                    self.last_error = None
                    if once:
                        return 0
                except Exception as exc:
                    code = getattr(exc, "code", type(exc).__name__)
                    if code == "DEVICE_AGENT_REGISTRATION_REQUIRED":
                        self.registered = False
                    if code != self.last_error:
                        self.agent._log(
                            f"处理机暂未继续（{code}）；原任务和回执已保留，未自动重做"
                        )
                    self.last_error = code
                    if once:
                        return 1
                stop_event.wait(self.agent.poll_seconds)
        return 0

    def _validate_claim(self, claimed):
        if (
            not isinstance(claimed, dict)
            or not isinstance(claimed.get("job_id"), str)
            or not isinstance(claimed.get("payload"), dict)
        ):
            fail("INVALID_AGENT_REQUEST", "中央服务任务格式无效", 422)
        status = claimed.get("status")
        if not isinstance(status, dict):
            fail("INVALID_AGENT_REQUEST", "中央服务缺少原任务身份", 422)
        for field in ("device_authorization", "agent_device_authorization"):
            binding = status.get(field)
            if (
                not isinstance(binding, dict)
                or type(binding.get("user_id")) is not int
                or binding["user_id"] != self.session.user_id
            ):
                fail("DEVICE_ACCOUNT_MISMATCH", "中央任务不属于执行机登录账号")
        if claimed.get("assigned_agent_id") != self.agent.agent_id:
            fail("DEVICE_AGENT_ASSIGNMENT_MISMATCH", "任务未分配给当前处理机")

    def _execute(self, receipt):
        self._validate_claim(receipt["claim"])
        job_id, execution_id = receipt["job_id"], receipt["execution_id"]
        path = self.prefix + "/jobs/" + quote(job_id, safe="-_.")
        with local_authorization_context(LocalDeviceAuthorizer(self.session)):
            with authorized_local_unit(
                render_operation_scopes(receipt["payload"])
            ) as decision:
                if decision is None or decision.user_id != self.session.user_id:
                    fail("DEVICE_AGENT_CONTEXT_REQUIRED", "缺少执行机本地授权")
                assigned = receipt["claim"]["status"]["agent_device_authorization"]
                if (
                    decision.mode == "ENFORCE"
                    and assigned.get("thumbprint") != decision.thumbprint
                ):
                    fail("DEVICE_IDENTITY_MISMATCH", "原任务属于另一执行机")
                acknowledgement = self.agent.client.post(
                    path + "/start", {"execution_id": execution_id}
                )
                if acknowledgement == {
                    "job_id": job_id,
                    "execution_id": execution_id,
                    "started": False,
                    "cancelled": True,
                }:
                    self.journal.cancel_prepared(receipt)
                    self.agent._log(f"原任务已取消，未启动渲染：{job_id}")
                    return
                if acknowledgement != {
                    "job_id": job_id,
                    "execution_id": execution_id,
                    "started": True,
                }:
                    fail(
                        "DEVICE_AGENT_EXECUTION_UNCERTAIN",
                        "未取得一致的启动回执，未启动渲染",
                        409,
                    )
                self.journal.executing(receipt)  # Durable before invoking renderer.
                heartbeat_stop = threading.Event()
                heartbeat = threading.Thread(
                    target=self._heartbeat,
                    args=(path, execution_id, heartbeat_stop),
                    daemon=True,
                )
                heartbeat.start()
                self.agent._log(f"开始已授权任务：{job_id}")
                try:
                    try:
                        rendered = self.render(receipt["payload"])
                    except Exception as exc:
                        report = {
                            "execution_id": execution_id,
                            "error": f"本地渲染失败（{type(exc).__name__}）",
                        }
                        self.journal.save_result(receipt, action="fail", payload=report)
                    else:
                        result = rendered.as_dict()
                        if not isinstance(result, dict):
                            fail(
                                "DEVICE_AGENT_RECEIPT_CONFLICT",
                                "渲染已返回，但结果格式异常，请保留文件核对",
                                409,
                            )
                        self.journal.save_result(
                            receipt,
                            action="complete",
                            payload={"execution_id": execution_id, "result": result},
                        )
                finally:
                    heartbeat_stop.set()
                    heartbeat.join(timeout=2)
        # Reporting failures never enter the renderer's exception block.
        self._report(receipt)

    def _heartbeat(self, path, execution_id, stop_event):
        while not stop_event.wait(self.agent.heartbeat_seconds):
            try:
                self.agent.client.post(
                    path + "/heartbeat",
                    {
                        "execution_id": execution_id,
                        "stage": "rendering",
                        "message": "执行机正在处理原任务",
                    },
                )
            except Exception:
                self.agent._log(
                    "原任务心跳暂未送达；当前执行单元继续安全收尾，不重新领取"
                )

    def _report(self, receipt):
        result = receipt["result"]
        if not isinstance(result, dict) or result.get("action") not in {
            "complete",
            "fail",
        }:
            fail("DEVICE_AGENT_RECEIPT_CONFLICT", "本地结果回执无效，请核对原文件", 409)
        path = (
            self.prefix
            + "/jobs/"
            + quote(receipt["job_id"], safe="-_.")
            + "/"
            + result["action"]
        )
        response = self.agent.client.post(path, result["payload"])
        expected_status = "completed" if result["action"] == "complete" else "failed"
        execution = response.get("agent_execution")
        if (
            response.get("job_id") != receipt["job_id"]
            or response.get("status") != expected_status
            or not isinstance(execution, dict)
            or execution.get("execution_id") != receipt["execution_id"]
        ):
            fail(
                "DEVICE_AGENT_RESULT_CONFLICT",
                "中央回报回执与原结果不一致，已保留本地结果",
                409,
            )
        self.journal.acknowledge(receipt)
        self.agent._log(f"原任务结果已确认：{receipt['job_id']}")
