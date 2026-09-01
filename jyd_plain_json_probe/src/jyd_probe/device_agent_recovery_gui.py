"""Main-thread Tk view; network/file review stays on the authenticated worker."""

from __future__ import annotations

import queue


def format_review(review):
    labels = {
        "running": "执行结果待核实",
        "completed": "中央已确认完成",
        "failed": "中央已确认失败",
    }
    lines = [
        f"原任务：{review['job_id']}",
        f"原执行编号：{review['execution_id']}",
        f"中央状态：{labels.get(review['status'], review['status'])}",
        "",
    ]
    if review.get("candidate"):
        for item in review["candidate"]["evidence"]:
            lines.extend(
                [
                    item["path"],
                    f"大小：{item['bytes']:,} 字节；文件摘要：{item['sha256']}",
                    "",
                ]
            )
    elif review["status"] == "running":
        lines.append(
            "暂不能采用现有输出：原路径不明确、文件不完整/发生变化，或执行租约仍有效。"
        )
        if review.get("output_error"):
            lines.append(f"核对代码：{review['output_error']}")
    lines.extend(["", review["notice"]])
    return "\n".join(lines)


def run_recovery_dialog(root, controller, stop_event, log):
    import tkinter as tk
    from tkinter import messagebox, ttk

    commands = queue.Queue()
    ui = {}
    state = {"review": None, "busy": False, "closed": False}

    def close():
        state["closed"] = True
        if "window" in ui:
            ui["window"].destroy()
        commands.put(("close", None))

    def controls():
        enabled = "disabled" if state["busy"] else "normal"
        for key in ("refresh", "prepare", "retry"):
            ui[key].configure(state=enabled)
        review = state["review"] or {}
        for key, allowed in (
            ("accept-output", review.get("can_resolve") and review.get("candidate")),
            ("close-task", review.get("can_resolve")),
            ("sync", review.get("status") in {"completed", "failed"}),
        ):
            ui[key].configure(
                state="normal" if allowed and not state["busy"] else "disabled"
            )

    def reset_review(event=None):
        state["review"] = None
        ui["stopped"].set(False)
        ui["reviewed"].set(False)
        controls()

    def dispatch(action, argument=None):
        if state["busy"] or state["closed"]:
            return
        state["busy"] = True
        controls()
        ui["status"].set("正在核对原记录，请稍候；不会运行剪映或重新生成。")
        commands.put((action, argument))

    def prepare():
        selected = ui["list"].selection()
        if selected:
            dispatch("prepare", ui["list"].item(selected[0], "values")[0])

    def resolve(choice):
        review = state["review"]
        if not review or not ui["stopped"].get() or not ui["reviewed"].get():
            messagebox.showinfo(
                "请先核实",
                "请确认原剪映执行已停止，并已核实当前任务及完整输出。",
                parent=ui["window"],
            )
            return
        label = {
            "accept-output": "采用原路径现有输出并结束任务",
            "close": "将原任务结束为失败（保留文件，不自动重做）",
            "sync": "同步中央已确认的原结果",
        }[choice]
        if messagebox.askyesno(
            "确认核实结论",
            f"任务：{review['job_id']}\n执行编号：{review['execution_id']}\n\n{label}？\n不会创建或重做任务。",
            parent=ui["window"],
            default="no",
        ):
            dispatch("resolve", (review["review_id"], choice))

    def build():
        window = ui["window"] = tk.Toplevel(root)
        window.title("核实中断任务 · 不重新渲染")
        window.geometry("860x680")
        window.minsize(700, 580)
        window.transient(root)
        window.protocol("WM_DELETE_WINDOW", close)
        shell = ttk.Frame(window, padding=16)
        shell.pack(fill="both", expand=True)
        ttk.Label(
            shell,
            text="只处理当前账号、原处理机的回执。先停止原剪映执行，再核对任务和完整成片。",
            wraplength=780,
        ).pack(anchor="w")
        ui["list"] = ttk.Treeview(
            shell,
            columns=("job", "phase", "execution"),
            show="headings",
            height=5,
            selectmode="browse",
        )
        for column, title, width in (
            ("job", "原任务", 150),
            ("phase", "本机状态", 140),
            ("execution", "原执行编号", 300),
        ):
            ui["list"].heading(column, text=title)
            ui["list"].column(column, width=width)
        ui["list"].pack(fill="x", pady=10)
        ui["list"].bind("<<TreeviewSelect>>", reset_review)
        row = ttk.Frame(shell)
        row.pack(fill="x")
        for key, label, command in (
            ("refresh", "刷新记录", lambda: dispatch("records")),
            ("prepare", "查看选中任务", prepare),
            ("retry", "补报已保存的原结果", lambda: dispatch("retry")),
        ):
            ui[key] = ttk.Button(row, text=label, command=command)
            ui[key].pack(side="left", padx=(0, 8))
        ui["details"] = tk.Text(shell, height=12, wrap="word", state="disabled")
        ui["details"].pack(fill="both", expand=True, pady=10)
        ui["stopped"], ui["reviewed"] = tk.BooleanVar(value=False), tk.BooleanVar(
            value=False
        )
        ttk.Checkbutton(
            shell,
            text="我已确认原剪映导出/处理已停止，没有另一进程继续写入。",
            variable=ui["stopped"],
        ).pack(anchor="w")
        ttk.Checkbutton(
            shell,
            text="我已核对原任务；采用现有输出时，已人工检查完整画面和音频。",
            variable=ui["reviewed"],
        ).pack(anchor="w")
        actions = ttk.Frame(shell)
        actions.pack(fill="x", pady=10)
        for key, label, choice in (
            ("accept-output", "采用原输出", "accept-output"),
            ("close-task", "结束原任务，保留文件", "close"),
            ("sync", "同步中央原结果", "sync"),
        ):
            ui[key] = ttk.Button(
                actions, text=label, command=lambda selected=choice: resolve(selected)
            )
            ui[key].pack(side="left", padx=(0, 8))
        ui["status"] = tk.StringVar(value="")
        ttk.Label(shell, textvariable=ui["status"], wraplength=780).pack(anchor="w")
        controls()
        dispatch("records")

    def finish(action, result, error):
        if state["closed"]:
            return
        state["busy"] = False
        if error:
            reset_review()
            ui["status"].set(
                f"未改变已确认结论（{error}）。原回执保留；刷新核对或补报原结果。"
            )
        elif action == "records":
            reset_review()
            for item in ui["list"].get_children():
                ui["list"].delete(item)
            for row in result:
                ui["list"].insert(
                    "", "end", values=(row["job_id"], row["phase"], row["execution_id"])
                )
            ui["status"].set(f"当前账号共有 {len(result)} 条未确认记录。")
        elif action == "prepare":
            reset_review()
            state["review"] = result
            ui["details"].configure(state="normal")
            ui["details"].delete("1.0", "end")
            ui["details"].insert("end", format_review(result))
            ui["details"].configure(state="disabled")
            ui["status"].set(
                "请核对上方原任务与输出。文件摘要检查不能代替人工试看；有效租约结束前不能结束任务。"
            )
        else:
            reset_review()
            ui["status"].set("原结果已确认；未重新渲染。可刷新记录后关闭此窗口。")
            log("中断任务的原结果已确认，未重新渲染。")
        controls()

    root.after(0, build)
    try:
        while not stop_event.is_set():
            try:
                action, argument = commands.get(timeout=0.25)
            except queue.Empty:
                continue
            if action == "close":
                break
            try:
                if action == "records":
                    result = controller.records()
                elif action == "prepare":
                    result = controller.prepare(argument)
                elif action == "retry":
                    result = controller.retry_reports()
                else:
                    result = controller.resolve(
                        *argument, confirm_stopped=True, confirm_reviewed=True
                    )
                error = None
            except Exception as exc:
                result, error = None, getattr(exc, "code", type(exc).__name__)
            root.after(0, lambda a=action, r=result, e=error: finish(a, r, e))
    finally:
        root.after(0, lambda: close() if not state["closed"] else None)
