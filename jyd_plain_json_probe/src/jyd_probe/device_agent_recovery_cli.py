"""Interactive explicit recovery; no unattended yes flag and no renderer access."""

from __future__ import annotations

import json
import sys

from .device_agent_journal import AgentJournal
from .device_agent_protocol import fail
from .device_agent_recovery import AgentRecoveryController


def run_recovery_command(args, agent, session, root):
    if session is None:
        fail("DEVICE_AGENT_CONTEXT_REQUIRED", "核实需要登录原网站账号并使用原设备", 409)
    controller = AgentRecoveryController(agent, session, AgentJournal(root))
    if args.recover_list:
        print(json.dumps(controller.records(), ensure_ascii=False, indent=2))
        return 0
    if args.recover_reports:
        print(f"已补报 {controller.retry_reports()} 条原结果；未领取或渲染任务。")
        return 0
    review = controller.prepare(args.recover_job)
    print(json.dumps(review, ensure_ascii=False, indent=2))
    if args.recovery_action == "inspect":
        return 0
    if not sys.stdin or not sys.stdin.isatty():
        fail(
            "DEVICE_AGENT_RECOVERY_INTERACTIVE_REQUIRED",
            "核实结论必须在交互终端明确确认，未改变原任务",
            409,
        )
    phrase = f"确认 {review['job_id']} {review['execution_id']}"
    print("请先确认原剪映执行已停止；采用原输出前必须人工检查完整画面/音频。")
    print(f"选择：{args.recovery_action}。不会重新渲染或删除文件。")
    if input(f"核实无误后输入 {phrase}：").strip() != phrase:
        print("已取消核实，原任务和回执未改变。")
        return 1
    print(
        json.dumps(
            controller.resolve(
                review["review_id"],
                args.recovery_action,
                confirm_stopped=True,
                confirm_reviewed=True,
            ),
            ensure_ascii=False,
        )
    )
    return 0
