from __future__ import annotations

from collections import deque
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
import os
import random
import shutil
import threading
import time
from typing import Callable


H3_DOWNLOAD_PROGRESS_SCHEMA = "jyd.h3-download-progress.v1"
H3_DOWNLOAD_HARD_LIMIT = 10


class H3DownloadQueueFull(RuntimeError):
    pass


class H3DownloadManagerUnavailable(RuntimeError):
    pass


class H3DownloadStale(RuntimeError):
    pass


class H3DiskSpaceLow(OSError):
    pass


class H3BatchSizeExceeded(ValueError):
    retryable = False


ProgressCallback = Callable[[int, int | None], None]
CurrentCallback = Callable[[], bool]
DownloadRunner = Callable[[ProgressCallback, CurrentCallback], Path]


@dataclass(frozen=True)
class H3SegmentDownloadTask:
    key: str
    slot_key: str
    batch_key: str
    total_count: int
    target_directory: Path
    runner: DownloadRunner
    origin_host: str = ""


@dataclass
class _DownloadRecord:
    task: H3SegmentDownloadTask
    state: str = "queued"
    bytes_downloaded: int = 0
    total_bytes: int | None = None
    error: str | None = None
    created_at: float = field(default_factory=time.monotonic)
    started_at: float | None = None
    updated_at: float = field(default_factory=time.monotonic)
    completed_at: float | None = None
    attempts: int = 0
    next_retry_at: float = 0.0
    progress_samples: deque[tuple[float, int]] = field(default_factory=deque)


class _MachineInstanceLock:
    """Hold one byte lock so two local services cannot create twenty workers."""

    def __init__(self, path: Path):
        self.path = path
        self.handle = None
        self.acquired = False
        path.parent.mkdir(parents=True, exist_ok=True)
        handle = path.open("a+b")
        handle.seek(0, os.SEEK_END)
        if handle.tell() == 0:
            handle.write(b"0")
            handle.flush()
        handle.seek(0)
        try:
            if os.name == "nt":
                import msvcrt

                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl

                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except (OSError, IOError):
            handle.close()
            return
        self.handle = handle
        self.acquired = True

    def close(self) -> None:
        handle = self.handle
        if handle is None:
            return
        try:
            handle.seek(0)
            if os.name == "nt":
                import msvcrt

                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl

                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        finally:
            handle.close()
            self.handle = None
            self.acquired = False


class H3SegmentDownloadManager:
    """Machine-owned, fair and non-blocking H3 segment download queue."""

    def __init__(
        self,
        storage_root: Path,
        *,
        max_workers: int = H3_DOWNLOAD_HARD_LIMIT,
        min_workers: int = 2,
        queue_max: int = 1000,
        min_free_bytes: int = 0,
        max_batch_bytes: int = 0,
        adaptive_enabled: bool = True,
        validation_workers: int = 2,
        acquire_machine_lock: bool = True,
    ):
        self.storage_root = Path(storage_root).resolve()
        self.max_workers = max(
            1, min(H3_DOWNLOAD_HARD_LIMIT, int(max_workers))
        )
        self.min_workers = max(1, min(self.max_workers, int(min_workers)))
        self.queue_max = max(1, int(queue_max))
        self.min_free_bytes = max(0, int(min_free_bytes))
        self.max_batch_bytes = max(0, int(max_batch_bytes))
        self.adaptive_enabled = bool(adaptive_enabled)
        self.validation_workers = max(1, min(2, int(validation_workers)))
        self._effective_limit = (
            self.min_workers if self.adaptive_enabled else self.max_workers
        )
        self._condition = threading.Condition()
        self._validation_semaphore = threading.BoundedSemaphore(
            self.validation_workers
        )
        self._api_window_started = time.monotonic()
        self._api_window_durations: list[float] = []
        self._api_window_failures = 0
        self._bad_api_windows = 0
        self._good_api_windows = 0
        self._good_api_since: float | None = None
        self._last_limit_increase_at = self._api_window_started
        self._records: dict[str, _DownloadRecord] = {}
        self._current_by_slot: dict[str, str] = {}
        self._batch_queues: dict[str, deque[str]] = {}
        self._batch_order: deque[str] = deque()
        self._active = 0
        self._host_failures: dict[str, deque[float]] = {}
        self._host_circuit_until: dict[str, float] = {}
        self._host_half_open_probe: set[str] = set()
        self._accepting = True
        self._stopping = False
        self._machine_lock = (
            _MachineInstanceLock(
                self.storage_root / ".runtime" / "h3-download-manager.lock"
            )
            if acquire_machine_lock
            else None
        )
        self._owns_machine = (
            self._machine_lock is None or self._machine_lock.acquired
        )
        self._threads: list[threading.Thread] = []
        if self._owns_machine:
            for index in range(self.max_workers):
                thread = threading.Thread(
                    target=self._worker,
                    name=f"h3-segment-download-{index + 1}",
                    daemon=True,
                )
                thread.start()
                self._threads.append(thread)

    @property
    def owns_machine(self) -> bool:
        return self._owns_machine

    @property
    def effective_limit(self) -> int:
        with self._condition:
            return self._effective_limit

    def set_effective_limit(self, value: int) -> int:
        with self._condition:
            self._effective_limit = max(
                self.min_workers, min(self.max_workers, int(value))
            )
            self._condition.notify_all()
            return self._effective_limit

    def observe_api_result(self, duration_seconds: float, *, failed: bool) -> None:
        """Feed ordinary API health into the conservative 2..10 controller."""

        if not self.adaptive_enabled:
            return
        now = time.monotonic()
        with self._condition:
            self._api_window_durations.append(max(0.0, float(duration_seconds)))
            self._api_window_failures += int(bool(failed))
            elapsed = now - self._api_window_started
            if elapsed < 30.0 and len(self._api_window_durations) < 20:
                return
            values = sorted(self._api_window_durations)
            p95 = values[min(len(values) - 1, int(len(values) * 0.95))]
            error_rate = self._api_window_failures / max(1, len(values))
            self._api_window_started = now
            self._api_window_durations = []
            self._api_window_failures = 0
            if p95 > 2.0 or error_rate > 0.02:
                self._bad_api_windows += 1
                self._good_api_windows = 0
                self._good_api_since = None
            elif p95 < 1.0 and error_rate == 0:
                self._good_api_windows += 1
                self._bad_api_windows = 0
                if self._good_api_since is None:
                    self._good_api_since = now
            else:
                self._bad_api_windows = 0
                self._good_api_windows = 0
                self._good_api_since = None
            if self._bad_api_windows >= 3:
                self._effective_limit = max(
                    self.min_workers, self._effective_limit - 1
                )
                self._bad_api_windows = 0
                self._condition.notify_all()
            elif (
                self._good_api_since is not None
                and now - self._good_api_since >= 300.0
                and now - self._last_limit_increase_at >= 60.0
            ):
                self._effective_limit = min(
                    self.max_workers, self._effective_limit + 1
                )
                self._last_limit_increase_at = now
                self._condition.notify_all()

    @contextmanager
    def validation_slot(self):
        """Keep ffprobe/decoder validation at two concurrent processes at most."""

        self._validation_semaphore.acquire()
        try:
            yield
        finally:
            self._validation_semaphore.release()

    def enqueue(self, task: H3SegmentDownloadTask) -> dict[str, object]:
        clean_key = str(task.key or "").strip()
        clean_slot = str(task.slot_key or "").strip()
        clean_batch = str(task.batch_key or "").strip()
        if not clean_key or not clean_slot or not clean_batch:
            raise ValueError("H3 下载任务身份不完整")
        if not self._owns_machine:
            raise H3DownloadManagerUnavailable(
                "另一工作台进程已持有 H3 下载器，本进程不会重复创建下载连接"
            )
        with self._condition:
            if not self._accepting:
                raise H3DownloadManagerUnavailable("H3 下载器正在关闭")
            existing = self._records.get(clean_key)
            if existing is not None:
                if (
                    existing.state == "failed"
                    and existing.attempts < 3
                    and time.monotonic() >= existing.next_retry_at
                ):
                    existing.task = task
                    existing.state = "queued"
                    existing.error = None
                    existing.updated_at = time.monotonic()
                    queue = self._batch_queues.get(clean_batch)
                    if queue is None:
                        queue = deque()
                        self._batch_queues[clean_batch] = queue
                        self._batch_order.append(clean_batch)
                    queue.append(clean_key)
                    self._condition.notify_all()
                return self._snapshot(existing)

            previous_key = self._current_by_slot.get(clean_slot)
            if previous_key and previous_key != clean_key:
                previous = self._records.get(previous_key)
                if previous is not None and previous.state in {
                    "queued",
                    "downloading",
                    "validating",
                }:
                    previous.state = "stale"
                    previous.updated_at = time.monotonic()
            queued = sum(
                record.state == "queued" for record in self._records.values()
            )
            if queued >= self.queue_max:
                raise H3DownloadQueueFull("H3 下载等待队列已满")

            record = _DownloadRecord(task=task)
            self._records[clean_key] = record
            self._current_by_slot[clean_slot] = clean_key
            queue = self._batch_queues.get(clean_batch)
            if queue is None:
                queue = deque()
                self._batch_queues[clean_batch] = queue
                self._batch_order.append(clean_batch)
            queue.append(clean_key)
            self._condition.notify_all()
            return self._snapshot(record)

    def get_state(self, key: str) -> dict[str, object] | None:
        with self._condition:
            record = self._records.get(str(key or ""))
            return self._snapshot(record) if record is not None else None

    def get_batch_progress(
        self,
        batch_key: str,
        *,
        total_count: int,
        ready_count: int,
        current_keys: set[str] | None = None,
    ) -> dict[str, object]:
        with self._condition:
            records = [
                value
                for value in self._records.values()
                if value.task.batch_key == batch_key
                and (current_keys is None or value.task.key in current_keys)
            ]
            downloaded = max(
                int(ready_count),
                sum(record.state == "ready" for record in records),
            )
            speed = sum(self._speed(record) for record in records)
            remaining_bytes = sum(
                max(0, int(record.total_bytes) - int(record.bytes_downloaded))
                for record in records
                if record.total_bytes is not None
                and record.state in {"queued", "downloading", "validating"}
            )
            eta = (
                round(remaining_bytes / speed)
                if remaining_bytes > 0 and speed > 0
                else None
            )
            return {
                "schema": H3_DOWNLOAD_PROGRESS_SCHEMA,
                "downloaded_count": min(max(0, int(total_count)), downloaded),
                "total_count": max(0, int(total_count)),
                "bytes_per_second": round(speed),
                "estimated_remaining_seconds": eta,
                "active_count": sum(
                    record.state in {"downloading", "validating"}
                    for record in records
                ),
                "queued_count": sum(record.state == "queued" for record in records),
                "failed_count": sum(record.state == "failed" for record in records),
                "effective_limit": self._effective_limit,
                "hard_limit": self.max_workers,
                "circuit_open_hosts": sorted(
                    host
                    for host, until in self._host_circuit_until.items()
                    if until > time.monotonic()
                ),
            }

    def diagnostics(self) -> dict[str, object]:
        with self._condition:
            now = time.monotonic()
            queued_records = [
                record for record in self._records.values()
                if record.state == "queued"
            ]
            try:
                free_bytes = shutil.disk_usage(self.storage_root).free
            except OSError:
                free_bytes = None
            return {
                "schema": "jyd.h3-download-manager-health.v1",
                "owns_machine": self._owns_machine,
                "accepting": self._accepting,
                "active_count": self._active,
                "queued_count": len(queued_records),
                "record_count": len(self._records),
                "oldest_queued_seconds": (
                    round(max(now - record.created_at for record in queued_records), 1)
                    if queued_records else 0
                ),
                "effective_limit": self._effective_limit,
                "hard_limit": self.max_workers,
                "validation_limit": self.validation_workers,
                "disk_free_bytes": free_bytes,
                "max_batch_bytes": self.max_batch_bytes,
                "circuit_open_hosts": sorted(
                    host
                    for host, until in self._host_circuit_until.items()
                    if until > now
                ),
            }

    def shutdown(self, *, wait_seconds: float = 10.0) -> None:
        with self._condition:
            self._accepting = False
            self._stopping = True
            for record in self._records.values():
                if record.state == "queued":
                    record.state = "stale"
                    record.updated_at = time.monotonic()
            self._condition.notify_all()
        deadline = time.monotonic() + max(0.0, float(wait_seconds))
        for thread in self._threads:
            remaining = max(0.0, deadline - time.monotonic())
            thread.join(remaining)
        if self._machine_lock is not None:
            self._machine_lock.close()

    def _is_current(self, task: H3SegmentDownloadTask) -> bool:
        with self._condition:
            return (
                not self._stopping
                and self._current_by_slot.get(task.slot_key) == task.key
            )

    def _next_record(self) -> _DownloadRecord | None:
        batch_checks = len(self._batch_order)
        for _ in range(batch_checks):
            batch_key = self._batch_order.popleft()
            queue = self._batch_queues.get(batch_key)
            if not queue:
                self._batch_queues.pop(batch_key, None)
                continue
            key = queue.popleft()
            if queue:
                self._batch_order.append(batch_key)
            else:
                self._batch_queues.pop(batch_key, None)
            record = self._records.get(key)
            if record is not None and record.state == "queued":
                if self._host_available(record.task.origin_host):
                    return record
                blocked_queue = self._batch_queues.get(batch_key)
                if blocked_queue is None:
                    blocked_queue = deque()
                    self._batch_queues[batch_key] = blocked_queue
                    self._batch_order.append(batch_key)
                blocked_queue.append(key)
        return None

    def _host_available(self, host: str) -> bool:
        clean_host = str(host or "").strip().lower()
        if not clean_host:
            return True
        until = self._host_circuit_until.get(clean_host, 0.0)
        if until <= 0:
            return True
        if until > time.monotonic():
            return False
        if clean_host in self._host_half_open_probe:
            return False
        self._host_half_open_probe.add(clean_host)
        return True

    def _record_host_success(self, host: str) -> None:
        clean_host = str(host or "").strip().lower()
        if not clean_host:
            return
        self._host_failures.pop(clean_host, None)
        self._host_circuit_until.pop(clean_host, None)
        self._host_half_open_probe.discard(clean_host)

    def _record_host_failure(self, host: str) -> None:
        clean_host = str(host or "").strip().lower()
        if not clean_host:
            return
        now = time.monotonic()
        failures = self._host_failures.setdefault(clean_host, deque())
        while failures and now - failures[0] > 60.0:
            failures.popleft()
        failures.append(now)
        half_open_failed = clean_host in self._host_half_open_probe
        self._host_half_open_probe.discard(clean_host)
        if half_open_failed or len(failures) >= 3:
            self._host_circuit_until[clean_host] = now + 30.0
            if self.adaptive_enabled:
                self._effective_limit = max(
                    self.min_workers, self._effective_limit - 1
                )

    def _worker(self) -> None:
        while True:
            with self._condition:
                while (
                    not self._stopping
                    and (
                        not self._batch_order
                        or self._active >= self._effective_limit
                    )
                ):
                    self._condition.wait()
                if self._stopping:
                    return
                record = self._next_record()
                if record is None:
                    self._condition.wait(timeout=1.0)
                    continue
                record.state = "downloading"
                record.started_at = record.updated_at = time.monotonic()
                record.attempts += 1
                self._active += 1
            try:
                record.task.target_directory.mkdir(parents=True, exist_ok=True)
                if self.min_free_bytes:
                    free = shutil.disk_usage(record.task.target_directory).free
                    if free < self.min_free_bytes:
                        raise H3DiskSpaceLow(
                            "H3 下载已暂停：本机磁盘剩余空间低于安全阈值"
                        )

                last_disk_check_bytes = 0
                last_disk_check_at = time.monotonic()

                def progress(downloaded: int, total: int | None) -> None:
                    nonlocal last_disk_check_bytes, last_disk_check_at
                    with self._condition:
                        now = time.monotonic()
                        if self.max_batch_bytes:
                            current_batch_bytes = sum(
                                value.bytes_downloaded
                                for key, value in self._records.items()
                                if value is not record
                                and value.task.batch_key == record.task.batch_key
                                and self._current_by_slot.get(value.task.slot_key)
                                == key
                                and value.state
                                in {"queued", "downloading", "validating", "ready"}
                            )
                            if current_batch_bytes + max(0, int(downloaded)) > (
                                self.max_batch_bytes
                            ):
                                raise H3BatchSizeExceeded(
                                    "H3 批次累计下载大小超过本机安全上限"
                                )
                        record.bytes_downloaded = max(0, int(downloaded))
                        record.total_bytes = (
                            max(0, int(total)) if total is not None else None
                        )
                        record.updated_at = now
                        record.progress_samples.append(
                            (now, record.bytes_downloaded)
                        )
                        while (
                            len(record.progress_samples) > 2
                            and now - record.progress_samples[0][0] > 10.0
                        ):
                            record.progress_samples.popleft()
                    if self.min_free_bytes and (
                        downloaded - last_disk_check_bytes >= 64 * 1024 * 1024
                        or now - last_disk_check_at >= 5.0
                    ):
                        last_disk_check_bytes = downloaded
                        last_disk_check_at = now
                        if (
                            shutil.disk_usage(record.task.target_directory).free
                            < self.min_free_bytes
                        ):
                            raise H3DiskSpaceLow(
                                "H3 下载已暂停：本机磁盘剩余空间低于安全阈值"
                            )

                record.task.runner(
                    progress, lambda: self._is_current(record.task)
                )
                with self._condition:
                    record.state = (
                        "ready" if self._is_current(record.task) else "stale"
                    )
                    if record.state == "ready":
                        self._record_host_success(record.task.origin_host)
            except H3DownloadStale:
                with self._condition:
                    record.state = "stale"
                    self._host_half_open_probe.discard(
                        str(record.task.origin_host or "").strip().lower()
                    )
            except H3DiskSpaceLow as exc:
                with self._condition:
                    record.state = "failed"
                    record.error = str(exc)
                    record.attempts = max(0, record.attempts - 1)
                    record.next_retry_at = time.monotonic() + 30.0
            except (OSError, RuntimeError, ValueError) as exc:
                with self._condition:
                    if self._is_current(record.task):
                        record.state = "failed"
                        record.error = str(exc)[:500]
                        explicitly_retryable = getattr(exc, "retryable", None)
                        if explicitly_retryable is False:
                            record.attempts = 3
                        ceiling = min(60.0, float(2 ** record.attempts))
                        retry_after = max(
                            0.0,
                            float(getattr(exc, "retry_after_seconds", 0.0) or 0.0),
                        )
                        record.next_retry_at = (
                            0.0
                            if explicitly_retryable is False
                            else time.monotonic()
                            + max(retry_after, random.uniform(0.0, ceiling))
                        )
                        if bool(getattr(exc, "retryable", False)) or isinstance(
                            exc, (OSError, TimeoutError)
                        ):
                            self._record_host_failure(record.task.origin_host)
                        else:
                            self._host_half_open_probe.discard(
                                str(record.task.origin_host or "").strip().lower()
                            )
                    else:
                        record.state = "stale"
            finally:
                with self._condition:
                    record.completed_at = record.updated_at = time.monotonic()
                    self._active = max(0, self._active - 1)
                    self._condition.notify_all()

    @staticmethod
    def _speed(record: _DownloadRecord) -> float:
        if (
            record.state not in {"downloading", "validating"}
            or record.started_at is None
            or record.bytes_downloaded <= 0
        ):
            return 0.0
        if len(record.progress_samples) >= 2:
            started_at, started_bytes = record.progress_samples[0]
            ended_at, ended_bytes = record.progress_samples[-1]
            elapsed = max(0.001, ended_at - started_at)
            return max(0.0, float(ended_bytes - started_bytes) / elapsed)
        elapsed = max(0.001, record.updated_at - record.started_at)
        return float(record.bytes_downloaded) / elapsed

    def _snapshot(self, record: _DownloadRecord) -> dict[str, object]:
        return {
            "state": record.state,
            "bytes_downloaded": record.bytes_downloaded,
            "total_bytes": record.total_bytes,
            "bytes_per_second": round(self._speed(record)),
            "error": record.error,
            "attempts": record.attempts,
            "retry_after_seconds": (
                max(0, round(record.next_retry_at - time.monotonic()))
                if record.state == "failed" and record.attempts < 3
                else None
            ),
            "effective_limit": self._effective_limit,
            "hard_limit": self.max_workers,
        }
