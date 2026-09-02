from __future__ import annotations

from pathlib import Path
import threading
import time

from jyd_probe.h3_segment_downloads import (
    H3DownloadManagerUnavailable,
    H3SegmentDownloadManager,
    H3SegmentDownloadTask,
)
import pytest
from jyd_probe.web_api import WebApiSettings, _env_bounded_positive_int


def _wait_until(predicate, timeout: float = 3.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(0.01)
    raise AssertionError("等待 H3 下载状态超时")


def test_manager_clamps_machine_concurrency_to_ten(tmp_path: Path) -> None:
    manager = H3SegmentDownloadManager(
        tmp_path,
        max_workers=99,
        min_workers=1,
        adaptive_enabled=False,
        acquire_machine_lock=False,
    )
    gate = threading.Event()
    guard = threading.Lock()
    active = 0
    peak = 0

    def runner(_progress, _current):
        nonlocal active, peak
        with guard:
            active += 1
            peak = max(peak, active)
        gate.wait(2)
        with guard:
            active -= 1
        return tmp_path

    try:
        for index in range(20):
            manager.enqueue(
                H3SegmentDownloadTask(
                    key=f"task-{index}",
                    slot_key=f"slot-{index}",
                    batch_key="batch",
                    total_count=20,
                    target_directory=tmp_path,
                    runner=runner,
                )
            )
        _wait_until(lambda: peak == 10)
        assert peak == 10
        assert manager.max_workers == 10
    finally:
        gate.set()
        manager.shutdown()


def test_adaptive_manager_starts_at_minimum_and_never_exceeds_ten(
    tmp_path: Path,
) -> None:
    manager = H3SegmentDownloadManager(
        tmp_path,
        max_workers=99,
        min_workers=2,
        adaptive_enabled=True,
        acquire_machine_lock=False,
    )
    try:
        assert manager.effective_limit == 2
        assert manager.set_effective_limit(999) == 10
        assert manager.set_effective_limit(0) == 2
    finally:
        manager.shutdown()


def test_h3_configuration_defaults_and_rejects_values_above_hard_limits(
    tmp_path: Path, monkeypatch
) -> None:
    settings = WebApiSettings(
        storage_root=tmp_path / "storage",
        template_library_root=tmp_path / "templates",
        default_draft_root=tmp_path / "drafts",
        audio_library_root=tmp_path / "audio",
    )
    assert settings.auth_timeout_seconds == 30
    assert settings.h3_download_workers == 10
    assert settings.h3_download_validate_workers == 2
    monkeypatch.setenv("JYD_H3_DOWNLOAD_WORKERS", "11")
    with pytest.raises(RuntimeError, match="不能超过 10"):
        _env_bounded_positive_int("JYD_H3_DOWNLOAD_WORKERS", 10, maximum=10)


def test_manager_deduplicates_and_round_robins_batches(tmp_path: Path) -> None:
    manager = H3SegmentDownloadManager(
        tmp_path, max_workers=1, min_workers=1, acquire_machine_lock=False
    )
    first_gate = threading.Event()
    order: list[str] = []

    def task(name: str, batch: str, *, waits: bool = False):
        def runner(_progress, _current):
            order.append(name)
            if waits:
                first_gate.wait(2)
            return tmp_path

        return H3SegmentDownloadTask(
            key=name,
            slot_key=name,
            batch_key=batch,
            total_count=4,
            target_directory=tmp_path,
            runner=runner,
        )

    try:
        first = task("a1", "a", waits=True)
        manager.enqueue(first)
        manager.enqueue(first)
        _wait_until(lambda: order == ["a1"])
        manager.enqueue(task("a2", "a"))
        manager.enqueue(task("a3", "a"))
        manager.enqueue(task("b1", "b"))
        first_gate.set()
        _wait_until(lambda: len(order) == 4)
        assert order.count("a1") == 1
        assert order.index("b1") < order.index("a3")
    finally:
        first_gate.set()
        manager.shutdown()


def test_new_signature_prevents_old_task_from_publishing(tmp_path: Path) -> None:
    manager = H3SegmentDownloadManager(
        tmp_path, max_workers=1, min_workers=1, acquire_machine_lock=False
    )
    gate = threading.Event()
    published: list[str] = []

    def old_runner(_progress, current):
        gate.wait(2)
        if current():
            published.append("old")
        return tmp_path

    def new_runner(_progress, current):
        if current():
            published.append("new")
        return tmp_path

    try:
        manager.enqueue(
            H3SegmentDownloadTask(
                "old", "slot", "batch", 1, tmp_path, old_runner
            )
        )
        _wait_until(lambda: manager.get_state("old")["state"] == "downloading")
        manager.enqueue(
            H3SegmentDownloadTask(
                "new", "slot", "batch", 1, tmp_path, new_runner
            )
        )
        gate.set()
        _wait_until(lambda: manager.get_state("new")["state"] == "ready")
        assert published == ["new"]
        assert manager.get_state("old")["state"] == "stale"
    finally:
        gate.set()
        manager.shutdown()


def test_second_process_lock_refuses_another_machine_downloader(
    tmp_path: Path,
) -> None:
    first = H3SegmentDownloadManager(tmp_path, max_workers=1)
    second = H3SegmentDownloadManager(tmp_path, max_workers=1)
    try:
        assert first.owns_machine is True
        assert second.owns_machine is False
        with pytest.raises(H3DownloadManagerUnavailable):
            second.enqueue(
                H3SegmentDownloadTask(
                    "blocked", "slot", "batch", 1, tmp_path, lambda *_: tmp_path
                )
            )
    finally:
        second.shutdown()
        first.shutdown()


def test_repeated_host_connection_errors_open_circuit(tmp_path: Path) -> None:
    manager = H3SegmentDownloadManager(
        tmp_path,
        max_workers=3,
        min_workers=1,
        adaptive_enabled=False,
        acquire_machine_lock=False,
    )

    def failing_runner(_progress, _current):
        raise OSError("temporary connection failure")

    try:
        for index in range(3):
            manager.enqueue(
                H3SegmentDownloadTask(
                    key=f"failure-{index}",
                    slot_key=f"failure-slot-{index}",
                    batch_key="batch",
                    total_count=4,
                    target_directory=tmp_path,
                    runner=failing_runner,
                    origin_host="files.example",
                )
            )
        _wait_until(
            lambda: all(
                manager.get_state(f"failure-{index}")["state"] == "failed"
                for index in range(3)
            )
        )
        assert manager.get_batch_progress(
            "batch", total_count=4, ready_count=0
        )["circuit_open_hosts"] == ["files.example"]
        manager.enqueue(
            H3SegmentDownloadTask(
                key="probe-later",
                slot_key="probe-slot",
                batch_key="batch",
                total_count=4,
                target_directory=tmp_path,
                runner=lambda *_: tmp_path,
                origin_host="files.example",
            )
        )
        time.sleep(0.2)
        assert manager.get_state("probe-later")["state"] == "queued"
    finally:
        manager.shutdown()


def test_batch_progress_counts_only_current_result_keys(tmp_path: Path) -> None:
    manager = H3SegmentDownloadManager(
        tmp_path,
        max_workers=1,
        min_workers=1,
        adaptive_enabled=False,
        acquire_machine_lock=False,
    )

    def completed(progress, _current):
        progress(100, 100)
        return tmp_path

    try:
        manager.enqueue(
            H3SegmentDownloadTask(
                "old", "same-slot", "batch", 1, tmp_path, completed
            )
        )
        _wait_until(lambda: manager.get_state("old")["state"] == "ready")
        manager.enqueue(
            H3SegmentDownloadTask(
                "new", "same-slot", "batch", 1, tmp_path, completed
            )
        )
        _wait_until(lambda: manager.get_state("new")["state"] == "ready")
        progress = manager.get_batch_progress(
            "batch",
            total_count=1,
            ready_count=0,
            current_keys={"new"},
        )
        assert progress["downloaded_count"] == 1
        assert progress["bytes_per_second"] == 0
    finally:
        manager.shutdown()


def test_batch_cumulative_size_limit_is_a_nonretryable_failure(
    tmp_path: Path,
) -> None:
    manager = H3SegmentDownloadManager(
        tmp_path,
        max_workers=1,
        min_workers=1,
        max_batch_bytes=100,
        adaptive_enabled=False,
        acquire_machine_lock=False,
    )

    def oversized(progress, _current):
        progress(101, 101)
        return tmp_path

    try:
        manager.enqueue(
            H3SegmentDownloadTask(
                "oversized", "slot", "batch", 1, tmp_path, oversized
            )
        )
        _wait_until(lambda: manager.get_state("oversized")["state"] == "failed")
        state = manager.get_state("oversized")
        assert state["attempts"] == 3
        assert "批次累计下载大小" in state["error"]
        assert manager.diagnostics()["max_batch_bytes"] == 100
    finally:
        manager.shutdown()
