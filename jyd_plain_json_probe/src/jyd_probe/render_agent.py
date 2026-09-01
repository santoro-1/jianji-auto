from __future__ import annotations

import argparse
from contextlib import nullcontext
from copy import deepcopy
import json
import logging
import os
from pathlib import Path
import platform
import socket
import sys
import threading
import time
import traceback
from typing import Any, Callable
from urllib.parse import quote

from .device_agent_transport import AgentApiClient
from .device_agent_client import AgentRequestAuthorizer
from .device_local_execution import requires_device_authorization
from .device_command_authorization import add_command_authorization_arguments, command_authorization, account_authorization, CommandAccountClient
from .device_auth_protocol import bundled_trust, DeviceAuthorizationError

from .render_job import run_render_job
from .logging_config import configure_file_logging, log_event
from .ui_automation_thread import initialize_ui_automation_in_current_thread


AGENT_VERSION = "1.2.0"
logger = logging.getLogger("jyd_probe.agent")


class RenderAgent:
    def __init__(
        self,
        client: AgentApiClient,
        *,
        agent_id: str,
        name: str,
        draft_root: str = "",
        poll_seconds: int = 3,
        heartbeat_seconds: int = 20,
        log_callback: Callable[[str], None] | None = None,
        journal_root: Path | None = None,
    ) -> None:
        self.client = client
        self.agent_id = _safe_agent_id(agent_id)
        self.name = name.strip() or self.agent_id
        self.draft_root = (
            Path(draft_root).expanduser().resolve() if draft_root.strip() else None
        )
        self.poll_seconds = max(1, int(poll_seconds))
        self.heartbeat_seconds = max(5, int(heartbeat_seconds))
        self.log_callback = log_callback
        self.journal_root = journal_root

    def _log(self, message: str) -> None:
        logger.info(message)
        if sys.stdout is not None:
            print(message, flush=True)
        if self.log_callback is not None:
            self.log_callback(message)

    def register(self) -> dict[str, Any]:
        return self.client.post(
            "/api/agents/register",
            {
                "agent_id": self.agent_id,
                "name": self.name,
                "hostname": socket.gethostname(),
                "version": AGENT_VERSION,
                "capabilities": {
                    "platform": platform.platform(),
                    "single_job_concurrency": 1,
                    "jianying_ui_automation": True,
                },
            },
        )

    def run_forever(
        self,
        *,
        once: bool = False,
        stop_event: threading.Event | None = None,
    ) -> int:
        stop_event = stop_event or threading.Event()
        if getattr(self.client, "authorizer", None) is not None:
            from .device_agent_journal import AgentJournal
            from .device_agent_runtime import AuthorizedAgentRunner
            with initialize_ui_automation_in_current_thread():
                runner = AuthorizedAgentRunner(self, self.client.authorizer.session,
                                               AgentJournal(self.journal_root or _agent_config_root()), run_render_job)
                return runner.run(once=once, stop_event=stop_event)
        if requires_device_authorization():
            raise DeviceAuthorizationError("DEVICE_AGENT_PROTOCOL_REQUIRED", "执行机缺少本机授权会话", status_code=409)
        with initialize_ui_automation_in_current_thread():
            self.register()
            self._log(f"已连接中央服务：{self.name}（{self.agent_id}）")
            while not stop_event.is_set():
                try:
                    claimed = self.client.post(
                        f"/api/agents/{quote(self.agent_id)}/claim"
                    ).get("job")
                    if isinstance(claimed, dict) and claimed.get("job_id"):
                        self._run_claimed_job(claimed)
                        if once:
                            return 0
                        continue
                    self.client.post(
                        f"/api/agents/{quote(self.agent_id)}/heartbeat",
                        {"state": "idle"},
                    )
                except KeyboardInterrupt:
                    return 0
                except Exception as exc:
                    self._log(f"连接或领取任务失败：{exc}")
                    if once:
                        return 1
                stop_event.wait(self.poll_seconds)
            self._log("处理机 Agent 已停止")
            return 0

    def _run_claimed_job(self, claimed: dict[str, Any]) -> None:
        job_id = str(claimed["job_id"])
        payload = claimed.get("payload")
        if not isinstance(payload, dict):
            self._report_failure(job_id, "中央服务返回的任务 payload 不是对象")
            return
        payload = self._localize_payload(payload)
        observability = payload.get("observability", {})
        if not isinstance(observability, dict):
            observability = {}
        event_context = {
            key: observability.get(key)
            for key in ("project_id", "item_id", "operation_id", "correlation_id")
        }
        stop_heartbeat = threading.Event()
        heartbeat = threading.Thread(
            target=self._heartbeat_loop,
            args=(job_id, stop_heartbeat),
            name=f"agent-heartbeat-{job_id[:8]}",
            daemon=True,
        )
        heartbeat.start()
        self._log(f"开始任务：{job_id}")
        log_event(
            logger,
            "agent.job_started",
            "独立处理机开始渲染任务",
            component="agent",
            agent_id=self.agent_id,
            job_id=job_id,
            **event_context,
        )
        try:
            result = run_render_job(payload)
            self.client.post(
                f"/api/agents/{quote(self.agent_id)}/jobs/{quote(job_id)}/complete",
                {"result": result.as_dict()},
            )
            self._log(f"任务完成：{job_id}")
            log_event(
                logger,
                "agent.job_completed",
                "独立处理机渲染任务完成",
                component="agent",
                agent_id=self.agent_id,
                job_id=job_id,
                **event_context,
            )
        except Exception as exc:
            logger.exception("任务执行失败 job_id=%s", job_id)
            if sys.stderr is not None:
                traceback.print_exc()
            self._log(f"任务执行失败：{type(exc).__name__}: {exc}")
            log_event(
                logger,
                "agent.job_failed",
                "独立处理机渲染任务失败",
                level=logging.ERROR,
                component="agent",
                agent_id=self.agent_id,
                job_id=job_id,
                error_type=type(exc).__name__,
                **event_context,
            )
            self._report_failure(job_id, f"{type(exc).__name__}: {exc}")
        finally:
            stop_heartbeat.set()
            heartbeat.join(timeout=2)

    def _localize_payload(self, payload: dict[str, Any]) -> dict[str, Any]:
        localized = deepcopy(payload)
        if self.draft_root is not None:
            output = localized.setdefault("output", {})
            if isinstance(output, dict):
                output["draft_root"] = str(self.draft_root)
        return localized

    def _heartbeat_loop(self, job_id: str, stop_event: threading.Event) -> None:
        while not stop_event.wait(self.heartbeat_seconds):
            try:
                self.client.post(
                    f"/api/agents/{quote(self.agent_id)}/jobs/{quote(job_id)}/heartbeat",
                    {"stage": "rendering", "message": "剪映处理机正在执行任务"},
                )
            except Exception as exc:
                self._log(f"任务心跳上报失败 {job_id}：{exc}")

    def _report_failure(self, job_id: str, error: str) -> None:
        try:
            self.client.post(
                f"/api/agents/{quote(self.agent_id)}/jobs/{quote(job_id)}/fail",
                {"error": error},
            )
        except Exception as report_exc:
            self._log(f"任务失败且无法上报 {job_id}：{report_exc}")


def _safe_agent_id(value: str) -> str:
    safe = "".join(char for char in value.strip() if char.isalnum() or char in "-_.")
    if not safe:
        raise ValueError("agent_id 不能为空，只能包含字母、数字、-、_、.")
    return safe


def build_parser() -> argparse.ArgumentParser:
    hostname = socket.gethostname().lower()
    parser = argparse.ArgumentParser(description="启动独立剪映 Windows 处理机 Agent")
    parser.add_argument(
        "--server-url",
        default=os.environ.get("JYD_SERVER_URL", "http://127.0.0.1:8010"),
    )
    parser.add_argument("--agent-id", default=os.environ.get("JYD_AGENT_ID", hostname))
    parser.add_argument("--name", default=os.environ.get("JYD_AGENT_NAME", hostname))
    parser.add_argument("--token", default=os.environ.get("JYD_AGENT_TOKEN", ""))
    parser.add_argument("--draft-root", default=os.environ.get("JYD_AGENT_DRAFT_ROOT", ""))
    parser.add_argument("--poll-seconds", type=int, default=3)
    parser.add_argument("--heartbeat-seconds", type=int, default=20)
    parser.add_argument("--once", action="store_true", help="只领取并执行一个任务")
    parser.add_argument("--gui", action="store_true", help="打开处理机启动界面")
    recovery = parser.add_mutually_exclusive_group()
    recovery.add_argument("--recover-list", action="store_true", help="登录后列出本机当前账号的未确认执行回执，不运行任务")
    recovery.add_argument("--recover-job", help="查看并核实指定原任务，不重新渲染")
    recovery.add_argument("--recover-reports", action="store_true", help="只补报已经持久保存的原结果，不领取任务")
    parser.add_argument("--recovery-action", choices=("inspect", "accept-output", "close", "sync"), default="inspect", help="指定任务的核实结论；变更必须在交互终端再次确认")
    parser.add_argument("--device-auth-server-url", default=os.environ.get("JYD_AUTH_SERVER_URL", ""), help="受信任的网站授权服务地址，不是中央队列地址")
    add_command_authorization_arguments(parser)
    return parser


def main(argv: list[str] | None = None) -> int:
    configure_file_logging(
        _agent_config_root() / "logs",
        "agent.log",
    )
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.recovery_action != "inspect" and not args.recover_job:
        parser.error("--recovery-action 只能与 --recover-job 一起使用；未启动任务")
    if args.gui and (args.recover_list or args.recover_job or args.recover_reports):
        parser.error("命令行核实参数不能与 --gui 混用；未启动任务")
    if args.gui or (argv is None and len(sys.argv) == 1):
        return launch_agent_gui()
    try:
        with command_authorization(args, server_url=args.device_auth_server_url) as session:
            agent_id = _account_agent_id(args.agent_id, session)
            client = AgentApiClient(args.server_url, args.token, agent_id=agent_id,
                                    authorizer=AgentRequestAuthorizer(session) if session else None)
            agent = RenderAgent(client, agent_id=agent_id, name=args.name, draft_root=args.draft_root,
                                poll_seconds=args.poll_seconds, heartbeat_seconds=args.heartbeat_seconds)
            if args.recover_list or args.recover_job or args.recover_reports:
                from .device_agent_recovery_cli import run_recovery_command
                return run_recovery_command(args, agent, session, _agent_config_root())
            return agent.run_forever(once=args.once)
    except Exception as exc:
        if sys.stderr is not None:
            print(f"处理机未启动（{getattr(exc, 'code', type(exc).__name__)}），请核对账号、原设备授权和连接设置", file=sys.stderr)
        return 1


def _account_agent_id(agent_id, session):
    value = _safe_agent_id(agent_id)
    return value[:70] + "-u" + str(session.user_id) if session is not None else value


def _agent_config_root() -> Path:
    local_app_data = os.environ.get("LOCALAPPDATA", "").strip()
    base = Path(local_app_data) if local_app_data else Path.home() / "AppData" / "Local"
    root = base / "JianyingRenderAgent"
    root.mkdir(parents=True, exist_ok=True)
    return root


def _load_agent_gui_config() -> dict[str, Any]:
    merged: dict[str, Any] = {}
    executable_root = Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) else Path.cwd()
    for path in (executable_root / "agent_config.json", _agent_config_root() / "config.json"):
        if not path.is_file():
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                merged.update(data)
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            continue
    return merged


def _detect_gui_draft_root() -> str:
    try:
        from .runtime_paths import detect_jianying_draft_root

        return str(detect_jianying_draft_root())
    except Exception:
        return ""


def launch_agent_gui() -> int:
    import tkinter as tk
    from tkinter import filedialog, messagebox, ttk

    config = _load_agent_gui_config()
    root = tk.Tk()
    root.title("剪映处理机启动器")
    root.geometry("700x750")
    root.minsize(640, 680)

    server_var = tk.StringVar(value=str(config.get("server_url") or ""))
    token_var = tk.StringVar(value=str(config.get("token") or os.environ.get("JYD_AGENT_TOKEN", "")))
    draft_var = tk.StringVar(value=str(config.get("draft_root") or _detect_gui_draft_root()))
    machine_var = tk.StringVar(value=str(config.get("machine") or "一号处理机"))
    status_var = tk.StringVar(value="尚未启动")
    authorization_required = requires_device_authorization()
    authority_var = tk.StringVar(value=str(config.get("device_auth_server_url") or os.environ.get("JYD_AUTH_SERVER_URL", "")))
    username_var = tk.StringVar(value=str(config.get("device_user") or ""))
    password_var = tk.StringVar(value="")
    stop_event = threading.Event()
    agent_thread: threading.Thread | None = None

    machine_map = {
        "一号处理机": "processor-01",
        "二号处理机": "processor-02",
        "三号处理机": "processor-03",
        "四号处理机": "processor-04",
    }

    shell = ttk.Frame(root, padding=24)
    shell.pack(fill="both", expand=True)
    ttk.Label(shell, text="剪映处理机启动器", font=("Microsoft YaHei UI", 18, "bold")).pack(anchor="w")
    ttk.Label(shell, text="首次粘贴负责人提供的连接信息，以后直接点击启动。", foreground="#666666").pack(anchor="w", pady=(4, 18))

    machine_frame = ttk.LabelFrame(shell, text="这台电脑是", padding=14)
    machine_frame.pack(fill="x")
    for index, label in enumerate(machine_map):
        ttk.Radiobutton(machine_frame, text=label, value=label, variable=machine_var).grid(
            row=index // 2, column=index % 2, sticky="w", padx=(0, 48), pady=5
        )

    settings_frame = ttk.LabelFrame(shell, text="连接设置（只需首次填写）", padding=14)
    settings_frame.pack(fill="x", pady=(16, 0))
    settings_frame.columnconfigure(1, weight=1)

    ttk.Label(settings_frame, text="工作台地址").grid(row=0, column=0, sticky="w", pady=6)
    ttk.Entry(settings_frame, textvariable=server_var).grid(row=0, column=1, columnspan=2, sticky="ew", padx=(12, 0), pady=6)
    ttk.Label(settings_frame, text="接入密码").grid(row=1, column=0, sticky="w", pady=6)
    ttk.Entry(settings_frame, textvariable=token_var, show="●").grid(row=1, column=1, columnspan=2, sticky="ew", padx=(12, 0), pady=6)
    ttk.Label(settings_frame, text="剪映草稿目录").grid(row=2, column=0, sticky="w", pady=6)
    ttk.Entry(settings_frame, textvariable=draft_var).grid(row=2, column=1, sticky="ew", padx=(12, 8), pady=6)

    def browse_draft_root() -> None:
        selected = filedialog.askdirectory(title="选择剪映草稿目录", initialdir=draft_var.get() or None)
        if selected:
            draft_var.set(selected)

    ttk.Button(settings_frame, text="选择…", command=browse_draft_root).grid(row=2, column=2, pady=6)
    if authorization_required:
        ttk.Label(settings_frame, text="网站授权地址").grid(row=3, column=0, sticky="w", pady=6)
        ttk.Entry(settings_frame, textvariable=authority_var).grid(row=3, column=1, columnspan=2, sticky="ew", padx=(12, 0), pady=6)
        ttk.Label(settings_frame, text="网站账号").grid(row=4, column=0, sticky="w", pady=6)
        ttk.Entry(settings_frame, textvariable=username_var).grid(row=4, column=1, columnspan=2, sticky="ew", padx=(12, 0), pady=6)
        ttk.Label(settings_frame, text="网站密码").grid(row=5, column=0, sticky="w", pady=6)
        ttk.Entry(settings_frame, textvariable=password_var, show="●").grid(row=5, column=1, columnspan=2, sticky="ew", padx=(12, 0), pady=6)
        ttk.Label(settings_frame, text="网站密码不保存。首次设备审批在本机工作台完成；日常登录不是重新激活。", wraplength=570).grid(row=6, column=0, columnspan=3, sticky="w", pady=6)

    log_box = tk.Text(shell, height=9, state="disabled", wrap="word", font=("Microsoft YaHei UI", 9))
    log_box.pack(fill="both", expand=True, pady=(16, 0))

    def append_log(message: str) -> None:
        def update() -> None:
            log_box.configure(state="normal")
            log_box.insert("end", message + "\n")
            log_box.see("end")
            log_box.configure(state="disabled")
            status_var.set(message)

        root.after(0, update)

    button_frame = ttk.Frame(shell)
    button_frame.pack(fill="x", pady=(16, 0))
    ttk.Label(button_frame, textvariable=status_var).pack(side="left")

    def save_config() -> dict[str, str]:
        selected_machine = machine_var.get()
        values = {
            "server_url": server_var.get().strip(),
            "token": token_var.get().strip(),
            "draft_root": draft_var.get().strip(),
            "machine": selected_machine,
            "agent_id": machine_map.get(selected_machine, "processor-01"),
            "name": selected_machine,
            "device_auth_server_url": authority_var.get().strip(),
            "device_user": username_var.get().strip(),
        }
        (_agent_config_root() / "config.json").write_text(
            json.dumps(values, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        return values

    def run_agent_in_background(values: dict[str, str], password_box: list[str]) -> None:
        nonlocal agent_thread
        password = password_box.pop()  # Thread arguments do not retain it for the whole run.
        try:
            context = nullcontext(None)
            if authorization_required:
                trust = bundled_trust(values["device_auth_server_url"])
                account = CommandAccountClient(trust).login(values["device_user"], password)
                context = account_authorization(account, trust)
            password = None
            with context as session:
                agent_id = _account_agent_id(values["agent_id"], session)
                agent = RenderAgent(
                    AgentApiClient(values["server_url"], values["token"], agent_id=agent_id,
                                   authorizer=AgentRequestAuthorizer(session) if session else None),
                    agent_id=agent_id, name=values["name"], draft_root=values["draft_root"], log_callback=append_log,
                )
                if values.get("operation") == "recovery":
                    from .device_agent_journal import AgentJournal
                    from .device_agent_recovery import AgentRecoveryController
                    from .device_agent_recovery_gui import run_recovery_dialog
                    if session is None:
                        raise DeviceAuthorizationError("DEVICE_AGENT_CONTEXT_REQUIRED", "核实需要原账号会话", status_code=409)
                    run_recovery_dialog(root, AgentRecoveryController(agent, session, AgentJournal(_agent_config_root())), stop_event, append_log)
                else:
                    agent.run_forever(stop_event=stop_event)
        except Exception as exc:
            append_log(f"启动未完成（{getattr(exc, 'code', type(exc).__name__)}），请核对网站账号、原设备授权和连接设置")
        finally:
            password = None
            agent_thread = None
            try:
                root.after(0, lambda: start_button.configure(state="normal"))
            except (RuntimeError, tk.TclError):
                pass  # The user may already have closed the idle window.

    def start_agent(operation="run") -> None:
        nonlocal agent_thread
        if agent_thread is not None and agent_thread.is_alive():
            messagebox.showinfo("处理机已启动", "当前处理机 Agent 已经在运行。")
            return
        values = save_config()
        if not values["server_url"] or not values["token"] or (operation == "run" and not values["draft_root"]):
            messagebox.showerror("配置不完整", "请填写工作台地址、接入密码和剪映草稿目录。")
            return
        if authorization_required and (not values["device_user"] or not values["device_auth_server_url"] or not password_var.get()):
            messagebox.showerror("请登录网站账号", "请填写受信任的网站授权地址、账号与本次密码；密码不会保存。")
            return
        password = password_var.get()
        values["operation"] = operation  # Runtime-only; not saved in config.
        password_var.set("")
        stop_event.clear()
        start_button.configure(state="disabled")
        append_log(f"正在启动 {values['name']}……")
        agent_thread = threading.Thread(
            target=run_agent_in_background,
            args=(values, [password]),
            name="render-agent-gui",
            daemon=True,
        )
        agent_thread.start()

    def stop_agent() -> None:
        stop_event.set()
        append_log("已请求停止；如果正在导出，将在当前任务结束后停止。")
        start_button.configure(state="normal")

    stop_button = ttk.Button(button_frame, text="停止", command=stop_agent)
    stop_button.pack(side="right")
    start_button = ttk.Button(button_frame, text="保存并启动", command=start_agent)
    start_button.pack(side="right", padx=(0, 10))
    if authorization_required:
        ttk.Button(shell, text="核实中断任务（不重新渲染）", command=lambda: start_agent("recovery")).pack(anchor="e", pady=(8, 0))

    def close_window() -> None:
        stop_event.set()
        password_var.set("")
        if agent_thread is not None and agent_thread.is_alive():
            status_var.set("正在完成当前执行单元和原结果回报，结束后关闭；不会领取新任务。")
            root.after(250, close_window)
        else:
            root.destroy()

    root.protocol("WM_DELETE_WINDOW", close_window)
    root.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
