from __future__ import annotations

import argparse
import ctypes
from datetime import datetime, timezone
import json
import logging
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import threading
import time
import traceback
from urllib.error import URLError
from urllib.parse import urlparse
from urllib.request import urlopen
import webbrowser


SOURCE_ROOT = Path(__file__).resolve().parents[2]
_ASR_EVENT_LOG_LOCK = threading.Lock()
if not getattr(sys, "frozen", False):
    sys.path.insert(0, str(SOURCE_ROOT / "src"))


def _application_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return SOURCE_ROOT


def _load_processor_config(data_root: Path) -> dict[str, str]:
    path = data_root / "processor_config.json"
    if not path.is_file():
        return {}
    try:
        # PowerShell 5 may write JSON with an UTF-8 BOM when preparing a
        # deployment-specific package. utf-8-sig accepts both BOM and no-BOM.
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return {}
    return {str(key): str(value) for key, value in data.items() if value not in (None, "")}


def _resolved_network_config(config: dict[str, str]) -> tuple[str, str, str]:
    cloud_digital_human_url = "https://video.lanyingjk01.com"
    local_digital_human_url = "http://127.0.0.1:8000"
    legacy_account_url = "http://192.168.11.28:8000"
    legacy_cloud_auth_url = "https://auth.lanyingjk01.com"
    explicit_digital_human_url = config.get("digital_human_server_url", "").strip()
    configured_auth_url = (
        explicit_digital_human_url
        or config.get("auth_server_url", cloud_digital_human_url).strip()
    ).rstrip("/")
    shared_processor_url = config.get("shared_processor_url", "").strip().rstrip("/")
    if configured_auth_url in {
        local_digital_human_url,
        legacy_account_url,
        legacy_cloud_auth_url,
    }:
        configured_auth_url = cloud_digital_human_url
    if shared_processor_url == legacy_account_url:
        shared_processor_url = ""
    return configured_auth_url or cloud_digital_human_url, shared_processor_url, "false"


def _semantic_visual_source_mode(config: dict[str, str]) -> str:
    mode = config.get("semantic_visual_source_mode", "folders").strip().lower()
    if mode not in {"folders", "json"}:
        raise ValueError("semantic_visual_source_mode 只允许 folders 或 json")
    return mode


def _detect_draft_root(config: dict[str, str], data_root: Path) -> Path:
    return _detect_draft_root_details(config, data_root).path


def _detect_draft_root_details(config: dict[str, str], data_root: Path):
    configured = os.environ.get("JYD_WEB_DRAFT_ROOT", "").strip() or config.get("draft_root", "").strip()
    fallback = data_root / "drafts"
    fallback.mkdir(parents=True, exist_ok=True)
    from jyd_probe.runtime_paths import detect_jianying_draft_root_details

    return detect_jianying_draft_root_details(configured, fallback=fallback)


def _draft_root_source_label(source: str) -> str:
    return {
        "configured": "手工配置",
        "jianying_catalogue": "剪映本机索引",
        "populated_scan": "现有草稿自动识别",
        "default": "剪映默认目录",
        "fallback": "安装目录临时兜底（未确认）",
    }.get(source, source or "未知")


def _configure_environment() -> tuple[Path, Path]:
    app_root = _application_root()
    data_root = app_root / "data"
    libraries_root = data_root / "libraries"
    legacy_text_template_root = libraries_root / "text_template_library"
    compact_text_template_root = data_root / "l" / "t"
    text_template_root = (
        legacy_text_template_root
        if legacy_text_template_root.exists() or not getattr(sys, "frozen", False)
        else compact_text_template_root
    )
    storage_root = data_root / "web_storage"
    personal_root = data_root / "personal_libraries"
    config = _load_processor_config(data_root)
    auth_server_url, shared_processor_url, auth_authority = _resolved_network_config(config)

    defaults = {
        "JYD_WEB_STORAGE_ROOT": storage_root,
        "JYD_TEMPLATE_LIBRARY_ROOT": data_root / "template_library",
        "JYD_AUDIO_LIBRARY_ROOT": libraries_root / "audio_library",
        "JYD_EFFECT_LIBRARY_ROOT": libraries_root / "effect_library",
        "JYD_FONT_LIBRARY_ROOT": libraries_root / "font_library",
        "JYD_STICKER_LIBRARY_ROOT": libraries_root / "sticker_library",
        "JYD_CORNER_STICKER_LIBRARY_ROOT": libraries_root / "corner_sticker_library",
        "JYD_SEMANTIC_VISUAL_LIBRARY_ROOT": libraries_root / "semantic_visual_library",
        "JYD_TEXT_EFFECT_LIBRARY_ROOT": libraries_root / "text_effect_library",
        "JYD_TEXT_STYLE_LIBRARY_ROOT": libraries_root / "text_style_library",
        "JYD_TEXT_TEMPLATE_LIBRARY_ROOT": text_template_root,
        "JYD_PERSONAL_LIBRARY_ROOT": personal_root,
        "JYD_DECRYPT_WORK_ROOT": data_root / "decrypted",
        "JYD_DRAFTC_EXE": app_root / "tools" / "jy-draftc.exe",
    }
    for name, value in defaults.items():
        os.environ.setdefault(name, str(Path(value).resolve()))
    os.environ.setdefault(
        "JYD_SEMANTIC_VISUAL_SOURCE_MODE",
        _semantic_visual_source_mode(config),
    )
    if os.environ["JYD_SEMANTIC_VISUAL_SOURCE_MODE"].strip().lower() == "folders":
        semantic_visual_root = Path(os.environ["JYD_SEMANTIC_VISUAL_LIBRARY_ROOT"])
        (semantic_visual_root / "素材").mkdir(parents=True, exist_ok=True)
    draft_root_detection = _detect_draft_root_details(config, data_root)
    os.environ.setdefault("JYD_WEB_DRAFT_ROOT", str(draft_root_detection.path))
    os.environ["JYD_DRAFT_ROOT_SOURCE"] = draft_root_detection.source
    os.environ["JYD_DRAFT_ROOT_CONFIRMED"] = (
        "true" if draft_root_detection.confirmed else "false"
    )
    os.environ.setdefault(
        "JYD_AUTH_SERVER_URL",
        auth_server_url,
    )
    os.environ.setdefault(
        "JYD_SHARED_PROCESSOR_URL",
        shared_processor_url,
    )
    workbench_environment = (
        "local"
        if urlparse(auth_server_url).hostname in {"127.0.0.1", "localhost", "::1"}
        else "production"
    )
    os.environ.setdefault(
        "JYD_ADMIN_COOKIE_NAME",
        f"jyd_admin_session_{workbench_environment}",
    )
    os.environ.setdefault(
        "JYD_SITE_COOKIE_NAME",
        f"jyd_site_session_{workbench_environment}",
    )
    os.environ.setdefault(
        "JYD_LTX_WORKBENCH_URL",
        config.get("ltx_workbench_url", "").strip()
        or (
            "http://127.0.0.1:8792"
            if workbench_environment == "local"
            else "http://127.0.0.1:8791"
        ),
    )
    os.environ.setdefault(
        "JYD_AUTH_AUTHORITY",
        auth_authority,
    )
    os.environ.setdefault(
        "JYD_ASR_BASE_URL",
        config.get("asr_base_url", "").strip() or "http://127.0.0.1:18084",
    )
    os.environ.setdefault(
        "JYD_ASR_REQUIRED",
        config.get("asr_required", "").strip() or "true",
    )
    storage_root.mkdir(parents=True, exist_ok=True)
    for name in (
        "audio_library",
        "effect_library",
        "font_library",
        "sticker_library",
        "corner_sticker_library",
        "text_effect_library",
        "text_style_library",
        "text_template_library",
    ):
        (personal_root / name).mkdir(parents=True, exist_ok=True)
    (data_root / "logs").mkdir(parents=True, exist_ok=True)
    return app_root, data_root


def _workspace_path(deployment_mode: str) -> str:
    return "/app/new" if deployment_mode == "standalone" else "/app"


def _lan_addresses(port: int, workspace_path: str = "/app") -> list[str]:
    addresses: list[str] = []
    try:
        candidates = socket.gethostbyname_ex(socket.gethostname())[2]
    except OSError:
        candidates = []
    for address in candidates:
        if address.startswith(("127.", "169.254.")) or ":" in address:
            continue
        url = f"http://{address}:{port}{workspace_path}"
        if url not in addresses:
            addresses.append(url)
    return addresses


def _append_startup_log(data_root: Path, message: str) -> None:
    logging.getLogger("jyd_probe.server").info(message)


def _port_is_open(host: str, port: int) -> bool:
    try:
        with socket.create_connection((host, port), timeout=0.3):
            return True
    except OSError:
        return False


def _asr_is_healthy(base_url: str) -> bool:
    try:
        with urlopen(base_url.rstrip("/") + "/healthz", timeout=2) as response:
            if response.status != 200:
                return False
            payload = json.loads(response.read().decode("utf-8"))
            return isinstance(payload, dict) and payload.get("status") == "ok"
    except (URLError, TimeoutError, OSError, UnicodeDecodeError, json.JSONDecodeError):
        return False


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _asr_log_tail(data_root: Path, *, limit_bytes: int = 8192) -> str:
    path = data_root / "logs" / "asr.log"
    try:
        with path.open("rb") as handle:
            handle.seek(0, os.SEEK_END)
            size = handle.tell()
            handle.seek(max(0, size - limit_bytes), os.SEEK_SET)
            return handle.read().decode("utf-8", errors="replace")[-4000:]
    except OSError:
        return ""


def _system_resource_snapshot(data_root: Path) -> dict[str, object]:
    snapshot: dict[str, object] = {"cpu_count": os.cpu_count()}
    try:
        disk = shutil.disk_usage(data_root)
        snapshot.update(
            {
                "disk_total_bytes": disk.total,
                "disk_free_bytes": disk.free,
            }
        )
    except OSError:
        pass
    if sys.platform == "win32":
        class MemoryStatus(ctypes.Structure):
            _fields_ = [
                ("length", ctypes.c_ulong),
                ("memory_load_percent", ctypes.c_ulong),
                ("total_physical_bytes", ctypes.c_ulonglong),
                ("available_physical_bytes", ctypes.c_ulonglong),
                ("total_page_file_bytes", ctypes.c_ulonglong),
                ("available_page_file_bytes", ctypes.c_ulonglong),
                ("total_virtual_bytes", ctypes.c_ulonglong),
                ("available_virtual_bytes", ctypes.c_ulonglong),
                ("available_extended_virtual_bytes", ctypes.c_ulonglong),
            ]

        memory = MemoryStatus()
        memory.length = ctypes.sizeof(MemoryStatus)
        try:
            if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(memory)):
                snapshot.update(
                    {
                        "memory_load_percent": int(memory.memory_load_percent),
                        "memory_total_bytes": int(memory.total_physical_bytes),
                        "memory_available_bytes": int(memory.available_physical_bytes),
                    }
                )
        except (AttributeError, OSError):
            pass
    return snapshot


def _record_asr_event(data_root: Path, event: str, **details: object) -> None:
    record = {
        "schema": "jyd.asr-supervisor-event.v1",
        "timestamp": _utc_now(),
        "event": event,
        **details,
        "system_resources": _system_resource_snapshot(data_root),
    }
    path = data_root / "logs" / "asr-supervisor.jsonl"
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with _ASR_EVENT_LOG_LOCK, path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n")
    except OSError as exc:
        logging.getLogger("jyd_probe.server").warning(
            "无法写入 ASR 监督日志: %s", exc
        )


def _process_started_at(process: subprocess.Popen[bytes]) -> str:
    return str(getattr(process, "_jyd_asr_started_at", "") or "")


def _record_asr_process_stop(
    data_root: Path,
    process: subprocess.Popen[bytes],
    *,
    event: str,
    launcher_requested_stop: bool,
    reason: str,
    restart_count: int,
) -> None:
    _record_asr_event(
        data_root,
        event,
        pid=process.pid,
        started_at=_process_started_at(process),
        stopped_at=_utc_now(),
        exit_code=process.poll(),
        launcher_requested_stop=launcher_requested_stop,
        reason=reason,
        restart_count=restart_count,
        last_standard_error=_asr_log_tail(data_root),
        captured_stream="combined_stdout_stderr",
    )


def _asr_runtime_layout(app_root: Path, config: dict[str, str]) -> tuple[Path, Path, Path] | None:
    configured = (
        os.environ.get("JYD_ASR_RUNTIME_ROOT", "").strip()
        or config.get("asr_runtime_root", "").strip()
    )
    candidates: list[Path] = []
    if configured:
        candidate = Path(configured).expanduser()
        if not candidate.is_absolute():
            candidate = app_root / candidate
        candidates.append(candidate.resolve())
    candidates.append((app_root / "asr_runtime").resolve())
    if not getattr(sys, "frozen", False) and len(SOURCE_ROOT.parents) >= 2:
        candidates.append(
            (SOURCE_ROOT.parents[1] / "数字人" / "runninghub_mvp").resolve()
        )

    for root in candidates:
        portable_python = root / "python" / "python.exe"
        if portable_python.is_file() and (root / "media_node" / "asr_service" / "app.py").is_file():
            return portable_python, root, root / "media_node" / ".runtime" / "models"
        development_python = root / "media_node" / ".runtime" / "venv" / "Scripts" / "python.exe"
        if development_python.is_file() and (root / "media_node" / "asr_service" / "app.py").is_file():
            return development_python, root, root / "media_node" / ".runtime" / "models"
    return None


def _start_embedded_asr(
    app_root: Path,
    data_root: Path,
    config: dict[str, str],
    *,
    stop_event: threading.Event | None = None,
) -> subprocess.Popen[bytes] | None:
    base_url = os.environ.get("JYD_ASR_BASE_URL", "http://127.0.0.1:18084").rstrip("/")
    if _asr_is_healthy(base_url):
        print("本地 ASR: 已运行，直接复用")
        return None
    if os.environ.get("JYD_ASR_REQUIRED", "true").strip().lower() in {"0", "false", "no", "off"}:
        return None
    parsed = urlparse(base_url)
    if parsed.scheme != "http" or parsed.hostname not in {"127.0.0.1", "localhost"}:
        print(f"本地 ASR: 使用外部地址 {base_url}，不由工作台启动")
        return None
    layout = _asr_runtime_layout(app_root, config)
    if layout is None:
        print("本地 ASR: 未找到内置运行时；生成精确字幕时会明确报错")
        return None
    python, module_root, models_root = layout
    environment = os.environ.copy()
    environment["PYTHONPATH"] = str(module_root)
    environment["PYTHONNOUSERSITE"] = "1"
    environment.setdefault("MODELSCOPE_CACHE", str(models_root))
    environment.setdefault("ASR_MODEL", "paraformer-zh")
    environment.setdefault("ASR_VAD_MODEL", "fsmn-vad")
    environment.setdefault("ASR_DEVICE", "cpu")
    for proxy_name in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY"):
        environment.pop(proxy_name, None)
    port = parsed.port or 18084
    log_path = data_root / "logs" / "asr.log"
    log_handle = log_path.open("ab")
    creation_flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    try:
        process = subprocess.Popen(
            [
                str(python),
                "-s",
                "-m",
                "uvicorn",
                "media_node.asr_service.app:app",
                "--host",
                "127.0.0.1",
                "--port",
                str(port),
            ],
            cwd=module_root,
            env=environment,
            stdin=subprocess.DEVNULL,
            stdout=log_handle,
            stderr=subprocess.STDOUT,
            creationflags=creation_flags,
        )
        started_at = _utc_now()
        setattr(process, "_jyd_asr_started_at", started_at)
        _record_asr_event(
            data_root,
            "process_started",
            pid=process.pid,
            started_at=started_at,
            command_module="media_node.asr_service.app:app",
            base_url=base_url,
        )
    finally:
        log_handle.close()
    for _ in range(30):
        if process.poll() is not None:
            _record_asr_process_stop(
                data_root,
                process,
                event="process_exited_during_startup",
                launcher_requested_stop=False,
                reason="process_exited_before_health_check",
                restart_count=0,
            )
            raise RuntimeError(f"内置 ASR 启动失败，请查看 {log_path}")
        if _asr_is_healthy(base_url):
            print("本地 ASR: CPU 轻量模型已就绪")
            return process
        if stop_event is not None:
            if stop_event.wait(1):
                process.terminate()
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=5)
                _record_asr_process_stop(
                    data_root,
                    process,
                    event="process_stopped_during_startup",
                    launcher_requested_stop=True,
                    reason="workbench_shutdown_during_asr_startup",
                    restart_count=0,
                )
                raise RuntimeError("工作台关闭，已停止正在启动的内置 ASR")
        else:
            time.sleep(1)
    process.terminate()
    try:
        process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=5)
    _record_asr_process_stop(
        data_root,
        process,
        event="process_stopped_during_startup",
        launcher_requested_stop=False,
        reason="health_check_timeout",
        restart_count=0,
    )
    raise RuntimeError(f"内置 ASR 30 秒内未就绪，请查看 {log_path}")


def _asr_supervisor_number(
    config: dict[str, str], name: str, default: float, *, minimum: float
) -> float:
    try:
        return max(minimum, float(config.get(name, default)))
    except (TypeError, ValueError):
        return default


def _asr_restart_backoffs(config: dict[str, str]) -> tuple[float, ...]:
    raw = str(config.get("asr_restart_backoff_seconds", "2,5,15"))
    values: list[float] = []
    for part in raw.split(","):
        try:
            values.append(max(0.0, float(part.strip())))
        except ValueError:
            continue
    return tuple(values) or (2.0, 5.0, 15.0)


class _EmbeddedASRSupervisor:
    def __init__(
        self,
        app_root: Path,
        data_root: Path,
        config: dict[str, str],
    ) -> None:
        self.app_root = app_root
        self.data_root = data_root
        self.config = config
        self.base_url = os.environ.get(
            "JYD_ASR_BASE_URL", "http://127.0.0.1:18084"
        ).rstrip("/")
        self.required = os.environ.get(
            "JYD_ASR_REQUIRED", "true"
        ).strip().lower() not in {"0", "false", "no", "off"}
        self.health_interval_seconds = _asr_supervisor_number(
            config, "asr_health_interval_seconds", 5.0, minimum=0.1
        )
        self.health_failure_limit = round(
            _asr_supervisor_number(
                config, "asr_health_failure_limit", 3.0, minimum=1.0
            )
        )
        self.restart_limit = round(
            _asr_supervisor_number(config, "asr_restart_limit", 3.0, minimum=1.0)
        )
        self.restart_backoffs = _asr_restart_backoffs(config)
        self.restart_count = 0
        self.health_failures = 0
        self.process: subprocess.Popen[bytes] | None = None
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._restart_exhausted_reported = False
        self._restart_unavailable_reported = False

    def _can_start_embedded(self) -> bool:
        if not self.required:
            return False
        parsed = urlparse(self.base_url)
        return bool(
            parsed.scheme == "http"
            and parsed.hostname in {"127.0.0.1", "localhost"}
            and _asr_runtime_layout(self.app_root, self.config) is not None
        )

    def start(self) -> None:
        if not self.required:
            _record_asr_event(
                self.data_root,
                "supervisor_disabled",
                base_url=self.base_url,
                reason="asr_not_required",
            )
            return
        try:
            self.process = _start_embedded_asr(
                self.app_root,
                self.data_root,
                self.config,
                stop_event=self._stop_event,
            )
            if self.process is None and _asr_is_healthy(self.base_url):
                _record_asr_event(
                    self.data_root,
                    "compatible_service_reused",
                    pid=None,
                    base_url=self.base_url,
                    restart_count=0,
                )
        except Exception as exc:
            _record_asr_event(
                self.data_root,
                "initial_start_failed",
                error_type=type(exc).__name__,
                error_message=str(exc),
                restart_count=0,
                last_standard_error=_asr_log_tail(self.data_root),
            )
            print(f"! 本地 ASR 首次启动失败，后台将在有限次数内恢复：{exc}")
        self._thread = threading.Thread(
            target=self._monitor_loop,
            name="jyd-asr-supervisor",
            daemon=True,
        )
        self._thread.start()

    def _monitor_loop(self) -> None:
        while not self._stop_event.wait(self.health_interval_seconds):
            try:
                self._monitor_once()
            except Exception as exc:
                _record_asr_event(
                    self.data_root,
                    "supervisor_check_failed",
                    error_type=type(exc).__name__,
                    error_message=str(exc),
                    restart_count=self.restart_count,
                )

    def _monitor_once(self) -> None:
        if self._stop_event.is_set():
            return
        process = self.process
        if process is not None and process.poll() is not None:
            _record_asr_process_stop(
                self.data_root,
                process,
                event="process_exited",
                launcher_requested_stop=False,
                reason="unexpected_process_exit",
                restart_count=self.restart_count,
            )
            self.process = None
            self.health_failures = self.health_failure_limit
        elif _asr_is_healthy(self.base_url):
            if self.health_failures:
                _record_asr_event(
                    self.data_root,
                    "health_recovered",
                    pid=process.pid if process is not None else None,
                    restart_count=self.restart_count,
                    previous_failure_count=self.health_failures,
                )
            self.health_failures = 0
            return
        else:
            self.health_failures += 1
            if self.health_failures == 1:
                _record_asr_event(
                    self.data_root,
                    "health_check_failed",
                    pid=process.pid if process is not None else None,
                    restart_count=self.restart_count,
                )
        if self.health_failures < self.health_failure_limit:
            return
        self.health_failures = 0
        if process is not None and process.poll() is None:
            self._stop_owned_process(
                process,
                launcher_requested_stop=False,
                reason="health_check_failure_limit_reached",
            )
        self._restart_after_failure()

    def _restart_after_failure(self) -> None:
        if self._stop_event.is_set():
            return
        if not self._can_start_embedded():
            if not self._restart_unavailable_reported:
                self._restart_unavailable_reported = True
                _record_asr_event(
                    self.data_root,
                    "restart_unavailable",
                    base_url=self.base_url,
                    restart_count=self.restart_count,
                    reason="local_runtime_missing_or_external_service",
                )
                print("! 本地 ASR 不可用，且当前地址/运行时不允许工作台自动拉起。")
            return
        if self.restart_count >= self.restart_limit:
            if not self._restart_exhausted_reported:
                self._restart_exhausted_reported = True
                _record_asr_event(
                    self.data_root,
                    "restart_limit_reached",
                    restart_count=self.restart_count,
                    restart_limit=self.restart_limit,
                    last_standard_error=_asr_log_tail(self.data_root),
                )
                print(
                    "! 本地 ASR 自动恢复次数已用完。请查看 "
                    "data\\logs\\asr-supervisor.jsonl 和 asr.log 后重启工作台。"
                )
            return
        attempt = self.restart_count + 1
        delay = self.restart_backoffs[
            min(attempt - 1, len(self.restart_backoffs) - 1)
        ]
        _record_asr_event(
            self.data_root,
            "restart_scheduled",
            restart_count=attempt,
            restart_limit=self.restart_limit,
            delay_seconds=delay,
        )
        if self._stop_event.wait(delay):
            return
        self.restart_count = attempt
        try:
            restarted_process = _start_embedded_asr(
                self.app_root,
                self.data_root,
                self.config,
                stop_event=self._stop_event,
            )
        except Exception as exc:
            self.process = None
            if self._stop_event.is_set():
                return
            _record_asr_event(
                self.data_root,
                "restart_failed",
                restart_count=self.restart_count,
                restart_limit=self.restart_limit,
                error_type=type(exc).__name__,
                error_message=str(exc),
                last_standard_error=_asr_log_tail(self.data_root),
            )
            return
        if self._stop_event.is_set():
            if restarted_process is not None:
                self._stop_owned_process(
                    restarted_process,
                    launcher_requested_stop=True,
                    reason="workbench_shutdown_after_asr_restart",
                )
            return
        self.process = restarted_process
        _record_asr_event(
            self.data_root,
            "restart_succeeded",
            pid=self.process.pid if self.process is not None else None,
            restart_count=self.restart_count,
            restart_limit=self.restart_limit,
            reused_compatible_service=self.process is None,
        )

    def _stop_owned_process(
        self,
        process: subprocess.Popen[bytes],
        *,
        launcher_requested_stop: bool,
        reason: str,
    ) -> None:
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    pass
        _record_asr_process_stop(
            self.data_root,
            process,
            event="process_stopped",
            launcher_requested_stop=launcher_requested_stop,
            reason=reason,
            restart_count=self.restart_count,
        )
        if self.process is process:
            self.process = None

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=self.health_interval_seconds + 1)
        process = self.process
        if process is not None:
            self._stop_owned_process(
                process,
                launcher_requested_stop=True,
                reason="workbench_shutdown",
            )
        _record_asr_event(
            self.data_root,
            "supervisor_stopped",
            restart_count=self.restart_count,
            launcher_requested_stop=True,
        )


def _start_embedded_collector(port: int = 8765) -> bool:
    if _port_is_open("127.0.0.1", port):
        return False
    from jyd_probe.local_collector_api import create_local_collector_app
    from jyd_probe.logging_config import configure_file_logging
    import uvicorn

    configure_file_logging(
        _application_root() / "data" / "logs",
        "collector.log",
        logger_name="jyd_probe.collector",
        propagate=False,
    )

    collector_server = uvicorn.Server(
        uvicorn.Config(
            create_local_collector_app(),
            host="127.0.0.1",
            port=port,
            log_level="warning",
            access_log=False,
            log_config=None,
        )
    )
    threading.Thread(
        target=collector_server.run,
        name="jyd-embedded-collector",
        daemon=True,
    ).start()
    return True


def _write_shared_connection_files(
    app_root: Path,
    lan_urls: list[str],
    agent_token: str,
) -> None:
    if not lan_urls:
        return
    primary_url = lan_urls[0]
    shortcut = "[InternetShortcut]\n" f"URL={primary_url}\n"
    (app_root / "打开公用工作台.url").write_text(shortcut, encoding="utf-8-sig")

    lines = [
        "公用工作台已经启动。",
        "",
        "给普通使用者：",
        "把同目录下的‘打开公用工作台.url’发给对方，双击即可打开。",
        "如果快捷文件打不开，也可以把下面任意一个地址发给对方：",
        *lan_urls,
        "",
        "增加剪映处理电脑：",
        "打开 JianyingRenderAgent，在‘工作台地址’中填写上面的地址，",
        f"在‘接入密码’中填写：{agent_token}",
        "每台处理电脑需要安装剪映，并保持电脑不锁屏。",
        "",
        "本文件会在每次启动时自动更新。",
    ]
    (app_root / "公用工作台连接说明.txt").write_text("\n".join(lines), encoding="utf-8-sig")


def build_parser() -> argparse.ArgumentParser:
    from jyd_probe.device_command_authorization import add_command_authorization_arguments

    parser = argparse.ArgumentParser(description="启动剪映处理机服务")
    add_command_authorization_arguments(parser)
    parser.add_argument("--host", default="")
    parser.add_argument("--port", type=int, default=8010)
    parser.add_argument("--no-browser", action="store_true")
    parser.add_argument(
        "--render-job",
        default="",
        help="只执行指定的 jyd.render_job.v1 文件，完成后退出",
    )
    parser.add_argument("--execution-mode", choices=("embedded", "agent"), default="embedded")
    parser.add_argument(
        "--deployment-mode",
        choices=("standalone", "shared"),
        default="",
        help="standalone 仅本机使用；shared 允许局域网员工连接",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    arguments = list(sys.argv[1:] if argv is None else argv)
    if arguments == ["--device-release-info"]:
        # Read compiled PUBLIC configuration only: no config/logs, account,
        # network, CNG key, UAC, ASR, collector or local service is started.
        import hashlib
        from jyd_probe.device_trust_roots import TRUSTED_ISSUERS

        canonical = json.dumps(
            TRUSTED_ISSUERS, sort_keys=True, separators=(",", ":"), ensure_ascii=True
        )
        print(json.dumps({
            "schema": "publicvideo.device-release.v1",
            "trust_sha256": hashlib.sha256(canonical.encode("ascii")).hexdigest(),
            "issuer_count": len(TRUSTED_ISSUERS),
        }))
        return 0
    from jyd_probe.device_identity_setup import dispatch_setup_helper

    helper_result = dispatch_setup_helper(arguments)
    if helper_result is not None:
        return helper_result
    args = build_parser().parse_args(argv)
    startup_config = _load_processor_config(_application_root() / "data")
    deployment_mode = args.deployment_mode or startup_config.get("deployment_mode", "standalone")
    if deployment_mode not in {"standalone", "shared"}:
        deployment_mode = "standalone"
    host = args.host or startup_config.get("host", "") or (
        "127.0.0.1" if deployment_mode == "standalone" else "0.0.0.0"
    )
    os.environ["JYD_EXECUTION_MODE"] = args.execution_mode
    # Request-level checks still restrict local file operations to loopback clients.
    os.environ["JYD_ALLOW_LOCAL_FILE_ACCESS"] = "true"
    from jyd_probe.logging_config import configure_file_logging

    app_root = _application_root()
    data_root = app_root / "data"
    configure_file_logging(
        data_root / "logs",
        "server.log",
        logger_name="jyd_probe.server",
        propagate=False,
    )
    asr_supervisor: _EmbeddedASRSupervisor | None = None
    try:
        app_root, data_root = _configure_environment()
        if args.render_job:
            configure_file_logging(
                data_root / "logs",
                "render.log",
                logger_name="jyd_probe.render",
                propagate=False,
            )
            from jyd_probe.render_job import run_render_job_file
            from jyd_probe.device_command_authorization import command_authorization

            with command_authorization(args):
                result = run_render_job_file(args.render_job)
            print(json.dumps(result.as_dict(), ensure_ascii=False, indent=2))
            return 0
        asr_supervisor = _EmbeddedASRSupervisor(app_root, data_root, startup_config)
        asr_supervisor.start()
        configure_file_logging(data_root / "logs", "workbench.log")
        configure_file_logging(
            data_root / "logs",
            "render.log",
            logger_name="jyd_probe.render",
            propagate=False,
        )
        from jyd_probe.template_library import rebase_template_library_paths

        rebase_stats = rebase_template_library_paths(os.environ["JYD_TEMPLATE_LIBRARY_ROOT"])
        from jyd_probe.web_api import create_app

        app = create_app()
        collector_started = _start_embedded_collector()
        workspace_path = _workspace_path(deployment_mode)
        local_url = f"http://127.0.0.1:{args.port}{workspace_path}"
        lan_urls = _lan_addresses(args.port, workspace_path)
        if deployment_mode == "shared":
            _write_shared_connection_files(app_root, lan_urls, str(app.state.agent_token))
        print("=" * 68)
        print("剪映处理机已启动。关闭此窗口会停止服务。")
        print(f"本机地址: {local_url}")
        for url in lan_urls:
            print(f"局域网地址: {url}")
        print(f"内部访问密码文件: {os.environ['JYD_WEB_STORAGE_ROOT']}\\access_password.txt")
        print(f"管理员密码文件: {os.environ['JYD_WEB_STORAGE_ROOT']}\\admin_password.txt")
        print(f"处理机令牌文件: {os.environ['JYD_WEB_STORAGE_ROOT']}\\agent_token.txt")
        print(f"执行模式: {args.execution_mode}")
        print(f"使用模式: {deployment_mode}")
        print(f"数字人网站账号与任务源: {os.environ['JYD_AUTH_SERVER_URL']}")
        if os.environ.get("JYD_SHARED_PROCESSOR_URL"):
            print(f"其他工作台: {os.environ['JYD_SHARED_PROCESSOR_URL']}")
        if deployment_mode == "shared" and lan_urls:
            print("连接文件已生成: 打开公用工作台.url")
            print("添加处理电脑说明: 公用工作台连接说明.txt")
        print(f"本机是否为账号中心: {os.environ['JYD_AUTH_AUTHORITY']}")
        print(f"剪映草稿目录: {os.environ['JYD_WEB_DRAFT_ROOT']}")
        print(
            "剪映草稿目录来源: "
            f"{_draft_root_source_label(os.environ.get('JYD_DRAFT_ROOT_SOURCE', ''))}"
        )
        if os.environ.get("JYD_DRAFT_ROOT_CONFIRMED") != "true":
            print("! 未读取到剪映真实草稿目录，当前路径不能作为正式导出位置。")
            print("! 请先打开剪映并打开任意草稿后重启；仍无效时在 data\\processor_config.json 配置 draft_root。")
        print(f"精确字幕 ASR: {os.environ['JYD_ASR_BASE_URL']}")
        print("草稿采集工具: 已集成启动" if collector_started else "草稿采集工具: 已有程序在运行")
        print("=" * 68)
        _append_startup_log(
            data_root,
            f"host={host} port={args.port} deployment={deployment_mode} lan_urls={lan_urls} "
            f"draft_root={os.environ['JYD_WEB_DRAFT_ROOT']} "
            f"draft_root_source={os.environ.get('JYD_DRAFT_ROOT_SOURCE', '')} "
            f"draft_root_confirmed={os.environ.get('JYD_DRAFT_ROOT_CONFIRMED', '')} "
            f"rebase={rebase_stats}",
        )
        if not args.no_browser:
            threading.Timer(1.0, lambda: webbrowser.open(local_url)).start()

        import uvicorn

        server = uvicorn.Server(
            uvicorn.Config(app, host=host, port=args.port, log_config=None)
        )

        def request_graceful_shutdown() -> None:
            app.state.runtime_control.shutdown_requested.wait()
            server.should_exit = True

        threading.Thread(
            target=request_graceful_shutdown,
            name="jyd-managed-shutdown",
            daemon=True,
        ).start()
        server.run()
        return 0
    except BaseException as exc:
        details = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
        _append_startup_log(data_root, details)
        print(details, file=sys.stderr)
        return 1
    finally:
        if asr_supervisor is not None:
            asr_supervisor.stop()


if __name__ == "__main__":
    raise SystemExit(main())
