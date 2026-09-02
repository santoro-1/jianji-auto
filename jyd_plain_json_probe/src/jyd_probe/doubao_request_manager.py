from __future__ import annotations

from collections import deque
from concurrent.futures import Future
from dataclasses import dataclass
import threading
import time
from typing import Callable, TypeVar


T = TypeVar("T")
DOUBAO_HARD_CONCURRENCY_LIMIT = 10


class DoubaoRequestError(RuntimeError):
    def __init__(self, code: str, message: str, *, retry_after_seconds: int | None = None):
        super().__init__(message)
        self.code = code
        self.retry_after_seconds = retry_after_seconds


@dataclass
class _Job:
    project_key: str
    operation_id: str
    call: Callable[[float], object]
    future: Future[object]
    created_at: float
    deadline: float


class DoubaoRequestManager:
    """One process-wide, project-fair queue for all JYD paid analysis calls."""

    def __init__(self, *, max_concurrency: int = 10, queue_max: int = 200) -> None:
        if type(max_concurrency) is not int or not 1 <= max_concurrency <= 10:
            raise ValueError("豆包整机并发上限必须为 1-10")
        if type(queue_max) is not int or queue_max < 1:
            raise ValueError("豆包等待队列上限必须为正整数")
        self.max_concurrency = max_concurrency
        self.queue_max = queue_max
        self._condition = threading.Condition()
        self._queues: dict[str, deque[_Job]] = {}
        self._project_order: deque[str] = deque()
        self._operations: dict[str, _Job] = {}
        self._active = 0
        self._accepting = True
        self._submitted = 0
        self._completed = 0
        self._failed = 0
        self._deduplicated = 0
        self._wait_samples: deque[float] = deque(maxlen=1000)
        self._threads = [
            threading.Thread(
                target=self._worker,
                name=f"jyd-doubao-{index + 1}",
                daemon=True,
            )
            for index in range(max_concurrency)
        ]
        for thread in self._threads:
            thread.start()

    def execute(
        self,
        *,
        project_key: str,
        operation_id: str,
        total_timeout_seconds: float,
        call: Callable[[float], T],
    ) -> T:
        clean_project = str(project_key or "default").strip() or "default"
        clean_operation = str(operation_id or "").strip()
        if not clean_operation:
            raise ValueError("豆包操作 ID 不能为空")
        timeout = float(total_timeout_seconds)
        if timeout <= 0:
            raise ValueError("豆包请求预算必须大于 0")
        now = time.monotonic()
        with self._condition:
            if not self._accepting:
                raise DoubaoRequestError(
                    "DOUBAO_MANAGER_SHUTTING_DOWN", "豆包请求管理器正在关闭"
                )
            duplicate = self._operations.get(clean_operation)
            if duplicate is not None:
                self._deduplicated += 1
                future = duplicate.future
            else:
                if self._queued_count() >= self.queue_max:
                    raise DoubaoRequestError(
                        "DOUBAO_QUEUE_FULL",
                        "本机豆包请求队列已满，请稍后重试",
                        retry_after_seconds=5,
                    )
                future = Future()
                job = _Job(
                    project_key=clean_project,
                    operation_id=clean_operation,
                    call=call,
                    future=future,
                    created_at=now,
                    deadline=now + timeout,
                )
                queue = self._queues.get(clean_project)
                if queue is None:
                    queue = deque()
                    self._queues[clean_project] = queue
                    self._project_order.append(clean_project)
                queue.append(job)
                self._operations[clean_operation] = job
                self._submitted += 1
                self._condition.notify_all()
        try:
            return future.result(timeout=timeout + 1.0)  # type: ignore[return-value]
        except TimeoutError as exc:
            raise DoubaoRequestError(
                "DOUBAO_TOTAL_DEADLINE_EXCEEDED", "本机豆包请求总预算已耗尽"
            ) from exc

    def diagnostics(self) -> dict[str, object]:
        with self._condition:
            queued = self._queued_count()
            waits = sorted(self._wait_samples)
            p95 = waits[min(len(waits) - 1, int(len(waits) * 0.95))] if waits else 0.0
            return {
                "schema": "jyd.doubao-request-manager-health.v1",
                "active_count": self._active,
                "queued_count": queued,
                "queue_max": self.queue_max,
                "hard_limit": self.max_concurrency,
                "submitted_count": self._submitted,
                "completed_count": self._completed,
                "failed_count": self._failed,
                "deduplicated_count": self._deduplicated,
                "queue_wait_p95_seconds": round(p95, 3),
                "queued_by_project": {
                    key: len(value) for key, value in self._queues.items() if value
                },
            }

    def shutdown(self) -> None:
        with self._condition:
            self._accepting = False
            for queue in self._queues.values():
                while queue:
                    job = queue.popleft()
                    if not job.future.done():
                        job.future.set_exception(
                            DoubaoRequestError(
                                "DOUBAO_MANAGER_SHUTTING_DOWN",
                                "豆包请求管理器正在关闭",
                            )
                        )
            self._queues.clear()
            self._project_order.clear()
            self._condition.notify_all()

    def _queued_count(self) -> int:
        return sum(len(queue) for queue in self._queues.values())

    def _worker(self) -> None:
        while True:
            with self._condition:
                while self._accepting and not self._project_order:
                    self._condition.wait()
                if not self._accepting:
                    return
                project = self._project_order.popleft()
                queue = self._queues[project]
                job = queue.popleft()
                if queue:
                    self._project_order.append(project)
                else:
                    self._queues.pop(project, None)
                now = time.monotonic()
                if now >= job.deadline:
                    self._failed += 1
                    job.future.set_exception(
                        DoubaoRequestError(
                            "DOUBAO_QUEUE_WAIT_TIMEOUT", "本机豆包请求排队预算已耗尽"
                        )
                    )
                    self._operations.pop(job.operation_id, None)
                    continue
                self._active += 1
                self._wait_samples.append(now - job.created_at)
            try:
                result = job.call(max(0.001, job.deadline - time.monotonic()))
                if time.monotonic() > job.deadline:
                    raise DoubaoRequestError(
                        "DOUBAO_TOTAL_DEADLINE_EXCEEDED", "本机豆包请求总预算已耗尽"
                    )
            except BaseException as exc:
                with self._condition:
                    self._active -= 1
                    self._failed += 1
                    self._operations.pop(job.operation_id, None)
                    if not job.future.done():
                        job.future.set_exception(exc)
                    self._condition.notify_all()
            else:
                with self._condition:
                    self._active -= 1
                    self._completed += 1
                    self._operations.pop(job.operation_id, None)
                    if not job.future.done():
                        job.future.set_result(result)
                    self._condition.notify_all()


_GLOBAL_LOCK = threading.Lock()
_GLOBAL_MANAGER: DoubaoRequestManager | None = None


def global_doubao_request_manager() -> DoubaoRequestManager:
    global _GLOBAL_MANAGER
    with _GLOBAL_LOCK:
        if _GLOBAL_MANAGER is None:
            _GLOBAL_MANAGER = DoubaoRequestManager()
        return _GLOBAL_MANAGER


def shutdown_global_doubao_request_manager() -> None:
    global _GLOBAL_MANAGER
    with _GLOBAL_LOCK:
        manager = _GLOBAL_MANAGER
        _GLOBAL_MANAGER = None
    if manager is not None:
        manager.shutdown()
