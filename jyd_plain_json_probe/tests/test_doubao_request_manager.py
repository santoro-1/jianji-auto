from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import threading
import time

import pytest

from jyd_probe.doubao_request_manager import (
    DoubaoRequestError,
    DoubaoRequestManager,
)


def test_machine_wide_manager_never_exceeds_ten_active_requests() -> None:
    manager = DoubaoRequestManager(max_concurrency=10, queue_max=200)
    lock = threading.Lock()
    active = 0
    peak = 0

    def remote_call(_remaining: float) -> int:
        nonlocal active, peak
        with lock:
            active += 1
            peak = max(peak, active)
        time.sleep(0.015)
        with lock:
            active -= 1
        return 1

    try:
        with ThreadPoolExecutor(max_workers=40) as callers:
            results = list(
                callers.map(
                    lambda index: manager.execute(
                        project_key=f"project-{index % 4}",
                        operation_id=f"operation-{index}",
                        total_timeout_seconds=3,
                        call=remote_call,
                    ),
                    range(100),
                )
            )
        assert sum(results) == 100
        assert peak == 10
    finally:
        manager.shutdown()


def test_same_operation_joins_one_in_flight_request() -> None:
    manager = DoubaoRequestManager(max_concurrency=2, queue_max=10)
    calls = 0
    lock = threading.Lock()

    def remote_call(_remaining: float) -> str:
        nonlocal calls
        with lock:
            calls += 1
        time.sleep(0.05)
        return "ok"

    try:
        with ThreadPoolExecutor(max_workers=8) as callers:
            futures = [
                callers.submit(
                    manager.execute,
                    project_key="project-a",
                    operation_id="same-operation",
                    total_timeout_seconds=2,
                    call=remote_call,
                )
                for _ in range(8)
            ]
            assert [future.result() for future in futures] == ["ok"] * 8
        assert calls == 1
        assert manager.diagnostics()["deduplicated_count"] == 7
    finally:
        manager.shutdown()


def test_project_round_robin_prevents_large_batch_starvation() -> None:
    manager = DoubaoRequestManager(max_concurrency=1, queue_max=20)
    release = threading.Event()
    order: list[str] = []

    def call(label: str):
        def run(_remaining: float) -> str:
            if label == "a0":
                release.wait(1)
            order.append(label)
            return label

        return run

    try:
        with ThreadPoolExecutor(max_workers=8) as callers:
            first = callers.submit(
                manager.execute,
                project_key="a",
                operation_id="a0",
                total_timeout_seconds=2,
                call=call("a0"),
            )
            time.sleep(0.02)
            pending = [
                callers.submit(
                    manager.execute,
                    project_key="a",
                    operation_id=f"a{index}",
                    total_timeout_seconds=2,
                    call=call(f"a{index}"),
                )
                for index in range(1, 4)
            ]
            pending.append(
                callers.submit(
                    manager.execute,
                    project_key="b",
                    operation_id="b0",
                    total_timeout_seconds=2,
                    call=call("b0"),
                )
            )
            release.set()
            first.result()
            for future in pending:
                future.result()
        assert order.index("b0") < order.index("a3")
    finally:
        manager.shutdown()


def test_bounded_queue_rejects_before_unbounded_growth() -> None:
    manager = DoubaoRequestManager(max_concurrency=1, queue_max=1)
    release = threading.Event()

    def blocked(_remaining: float) -> None:
        release.wait(1)

    try:
        with ThreadPoolExecutor(max_workers=2) as callers:
            running = callers.submit(
                manager.execute,
                project_key="a",
                operation_id="running",
                total_timeout_seconds=2,
                call=blocked,
            )
            time.sleep(0.02)
            queued = callers.submit(
                manager.execute,
                project_key="a",
                operation_id="queued",
                total_timeout_seconds=2,
                call=lambda _remaining: None,
            )
            time.sleep(0.02)
            with pytest.raises(DoubaoRequestError) as captured:
                manager.execute(
                    project_key="b",
                    operation_id="rejected",
                    total_timeout_seconds=2,
                    call=lambda _remaining: None,
                )
            assert captured.value.code == "DOUBAO_QUEUE_FULL"
            release.set()
            running.result()
            queued.result()
    finally:
        release.set()
        manager.shutdown()
