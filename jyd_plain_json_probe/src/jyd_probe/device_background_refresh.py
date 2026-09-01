"""Bounded background refresh of existing sessions; no activation or task start."""

from __future__ import annotations

import logging
import queue
import threading


class DeviceBackgroundRefresher:
    def __init__(self, sessions, *, interval=5.0, workers=4):
        if interval <= 0 or not 1 <= workers <= 8:
            raise ValueError("invalid background refresh limits")
        self._sessions, self._interval, self._workers = sessions, interval, workers
        self._lock = threading.RLock()
        self._stop = threading.Event()
        self._queue = queue.Queue(maxsize=128)
        self._pending = set()
        self._threads = []

    def start(self):
        with self._lock:
            self._threads = [thread for thread in self._threads if thread.is_alive()]
            if self._threads:
                return
            self._stop.clear()
            self._threads = [
                threading.Thread(
                    target=self._worker, name="device-auth-refresh", daemon=True
                )
                for _ in range(self._workers)
            ]
            self._threads.append(
                threading.Thread(
                    target=self._schedule, name="device-auth-scheduler", daemon=True
                )
            )
            for thread in self._threads:
                thread.start()

    def schedule_once(self):
        """Bounded and nonblocking: one slow network call cannot duplicate work."""
        if self._stop.is_set():
            return
        for session in self._sessions():
            with self._lock:
                if self._stop.is_set() or session in self._pending:
                    continue
                try:
                    self._queue.put_nowait(session)
                except queue.Full:
                    return
                self._pending.add(session)

    def _schedule(self):
        while not self._stop.wait(self._interval):
            self.schedule_once()

    def _worker(self):
        while not self._stop.is_set():
            try:
                session = self._queue.get(timeout=0.25)
            except queue.Empty:
                continue
            try:
                if not self._stop.is_set():
                    session.background_refresh()
            except Exception as exc:
                # Never log exception text/tracebacks: transport errors may embed
                # headers or tokens. One account failure cannot kill the service.
                logging.getLogger("jyd_probe.device_auth").warning(
                    "后台设备校验异常（%s），请在授权页重新校验", type(exc).__name__
                )
            finally:
                with self._lock:
                    self._pending.discard(session)
                self._queue.task_done()

    def stop(self):
        self._stop.set()
        with self._lock:
            threads = tuple(self._threads)
        for thread in threads:
            thread.join(timeout=0.5)
        # An already-in-flight auth request uses its existing transport timeout.
        # Do not start a second worker pool while any old worker is still alive.
        with self._lock:
            self._threads = [thread for thread in threads if thread.is_alive()]
        while True:
            try:
                session = self._queue.get_nowait()
            except queue.Empty:
                break
            with self._lock:
                self._pending.discard(session)
            self._queue.task_done()
