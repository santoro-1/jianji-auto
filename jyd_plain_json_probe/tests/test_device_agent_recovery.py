from io import StringIO
import os
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from jyd_probe import (
    device_agent_recovery as recovery,
    device_agent_recovery_cli as cli,
    render_agent,
)
from jyd_probe.device_auth_protocol import DeviceAuthorizationError
from jyd_probe.device_agent_recovery_gui import format_review


def output_payload(tmp_path, *, skip_export=False):
    draft = tmp_path / "draft"
    draft.mkdir()
    (draft / "draft_content.json").write_text('{"duration":1000000}', encoding="utf-8")
    video = tmp_path / "out.mp4"
    video.write_bytes(b"\x00\x00\x00\x18ftypisom" + b"x" * 50)
    return {
        "source": {"type": "video"},
        "output": {
            "draft_root": str(tmp_path),
            "draft_name": "draft",
            "mp4_path": str(video),
            "skip_export": skip_export,
        },
    }


def test_inspect_explicit_original_paths_and_draft_only(tmp_path):
    payload = output_payload(tmp_path, skip_export=True)
    result = recovery.inspect_original_output(payload)
    assert result["result"]["exported"] is False and len(result["evidence"]) == 1
    payload["output"]["skip_export"] = False
    full = recovery.inspect_original_output(payload)
    assert full["result"]["exported"] is True and len(full["evidence"]) == 2
    assert "top_level_changes" not in full["result"]  # Unknown counts are not invented.


@pytest.mark.parametrize(
    "change", ["relative", "missing-name", "traversal", "invalid-mp4"]
)
def test_no_guessed_or_invalid_original_output(tmp_path, change):
    payload = output_payload(tmp_path)
    if change == "relative":
        payload["output"]["draft_root"] = "relative-root"
    elif change == "missing-name":
        payload["output"].pop("draft_name")
    elif change == "traversal":
        payload["output"]["draft_name"] = "../elsewhere"
    else:
        (tmp_path / "out.mp4").write_text("not a video", encoding="utf-8")
    with pytest.raises(DeviceAuthorizationError):
        recovery.inspect_original_output(payload)


def test_windows_ctime_api_difference_is_not_a_false_change(tmp_path, monkeypatch):
    payload = output_payload(tmp_path)
    original = os.fstat

    def fstat(fd):
        value = original(fd)
        fields = {
            name: getattr(value, name)
            for name in (
                "st_dev",
                "st_ino",
                "st_size",
                "st_mtime_ns",
                "st_ctime_ns",
                "st_mode",
            )
        }
        fields["st_ctime_ns"] += 100
        return SimpleNamespace(**fields)

    monkeypatch.setattr(recovery.os, "fstat", fstat)
    assert len(recovery.inspect_original_output(payload)["evidence"]) == 2


def test_change_within_open_handle_is_rejected(tmp_path, monkeypatch):
    payload = output_payload(tmp_path)
    original, calls = os.fstat, []

    def fstat(fd):
        value = original(fd)
        fields = {
            name: getattr(value, name)
            for name in (
                "st_dev",
                "st_ino",
                "st_size",
                "st_mtime_ns",
                "st_ctime_ns",
                "st_mode",
            )
        }
        fields["st_ctime_ns"] += len(calls)
        calls.append(1)
        return SimpleNamespace(**fields)

    monkeypatch.setattr(recovery.os, "fstat", fstat)
    with pytest.raises(DeviceAuthorizationError) as error:
        recovery.inspect_original_output(payload)
    assert error.value.code == "DEVICE_AGENT_OUTPUT_CHANGED"


def test_cli_inspection_is_read_only_and_confirmation_is_interactive(
    tmp_path, monkeypatch
):
    calls = []

    class Controller:
        def __init__(self, *args):
            pass

        def prepare(self, job_id):
            return {"job_id": job_id, "execution_id": "a" * 32, "review_id": "review"}

        def resolve(self, *args, **kwargs):
            calls.append((args, kwargs))
            return {"acknowledged": True}

    monkeypatch.setattr(cli, "AgentRecoveryController", Controller)
    args = SimpleNamespace(
        recover_list=False,
        recover_reports=False,
        recover_job="job-1",
        recovery_action="inspect",
    )
    assert cli.run_recovery_command(args, object(), object(), tmp_path) == 0
    assert calls == []
    args.recovery_action = "close"
    monkeypatch.setattr(cli.sys, "stdin", StringIO("not interactive"))
    with pytest.raises(DeviceAuthorizationError) as error:
        cli.run_recovery_command(args, object(), object(), tmp_path)
    assert (
        error.value.code == "DEVICE_AGENT_RECOVERY_INTERACTIVE_REQUIRED" and calls == []
    )
    monkeypatch.setattr(cli.sys, "stdin", SimpleNamespace(isatty=lambda: True))
    monkeypatch.setattr("builtins.input", lambda *args: "not confirmed")
    assert (
        cli.run_recovery_command(args, object(), object(), tmp_path) == 1
        and calls == []
    )
    monkeypatch.setattr("builtins.input", lambda *args: "确认 job-1 " + "a" * 32)
    assert cli.run_recovery_command(args, object(), object(), tmp_path) == 0
    assert calls == [
        (("review", "close"), {"confirm_stopped": True, "confirm_reviewed": True})
    ]


def test_bad_recovery_flags_never_start_business(monkeypatch, tmp_path):
    monkeypatch.setattr(render_agent, "configure_file_logging", lambda *a: None)
    monkeypatch.setattr(render_agent, "_agent_config_root", lambda: tmp_path)
    for args in (["--recovery-action", "close"], ["--gui", "--recover-list"]):
        with pytest.raises(SystemExit) as error:
            render_agent.main(args)
        assert error.value.code == 2


def test_gui_review_is_readable_not_a_token_dump():
    text = format_review(
        {
            "job_id": "job-1",
            "execution_id": "original-id",
            "review_id": "not-for-display",
            "status": "running",
            "candidate": None,
            "output_error": "FILE_MISSING",
            "notice": "请人工试看。",
        }
    )
    assert "job-1" in text and "original-id" in text and "请人工试看" in text
    assert "not-for-display" not in text
