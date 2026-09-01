"""Explicit, narrowly scoped TPM initialization/access repair via a UAC helper.

No elevation during status/refresh/startup. No account tokens, SIDs, file paths,
key names or arbitrary commands are accepted from the browser or helper arguments.
The parent retains a live helper handle on timeout; it never deletes/replaces keys.
"""

from __future__ import annotations

import threading

from .device_identity_windows import DeviceIdentityError
from .device_identity_store import MachineDeviceIdentity

HELPER_FLAG = "--device-identity-setup"
MODES = frozenset({"initialize", "repair-access", "initialize-software"})
EXIT_CODES = {
    20: ("KEY_SETUP_CONTEXT_INVALID", "初始化来源无效，请从当前处理机页面重新发起"),
    21: ("KEY_NOT_FOUND", "没有找到原设备密钥，访问权限修复不会创建新身份"),
    22: ("KEY_ACCESS_DENIED", "Windows 未允许访问设备密钥，请联系此电脑管理员"),
    23: ("KEY_UNAVAILABLE", "设备密钥初始化或读取失败，请检查 TPM；未替换原密钥"),
    24: ("KEY_POLICY_INVALID", "现有设备密钥策略异常，已保留原密钥，请联系管理员"),
    25: ("KEY_IDENTITY_CONFLICT", "设备身份存在冲突，请核对原身份；未覆盖密钥"),
    26: ("KEY_IDENTITY_INVALID", "设备身份定位记录损坏；未替换原密钥"),
    27: ("KEY_IDENTITY_MISSING", "原设备密钥无法找到；不会创建第二个身份"),
    28: ("KEY_IDENTITY_UNAVAILABLE", "无法读取设备身份定位记录；请检查权限"),
    29: ("KEY_IDENTITY_WRITE_FAILED", "密钥已保留，但身份定位记录未保存；请明确重试"),
    30: ("KEY_INITIALIZATION_CONFLICT", "另一初始化尚未完成，请稍后明确重试"),
    31: ("KEY_SETUP_CHANNEL_FAILED", "初始化安全通道未完成；请明确重试"),
    32: (
        "SOFTWARE_APPROVAL_REQUIRED",
        "软件初始化许可无效或已过期，请联网重新明确申请",
    ),
}


def _in_progress():
    return DeviceIdentityError(
        "KEY_SETUP_IN_PROGRESS",
        "正在当前处理机上初始化，请处理 Windows 权限提示；不要重复申请",
    )


class DeviceSetupCoordinator:
    """Single in-flight helper for this server, shared by all website accounts."""

    def __init__(self, *, api_factory=None, channel_factory=None):
        self._api_factory = api_factory
        self._channel_factory = channel_factory
        self._channel = None
        self._api = None
        self._handle = None
        self._lock = threading.Lock()

    def _process_api(self):
        if self._api is None:
            if self._api_factory is None:
                from .device_identity_setup_windows import NativeSetupApi

                self._api = NativeSetupApi()
            else:
                self._api = self._api_factory()
        return self._api

    def _finish(self, timeout_ms=0):
        if self._handle is None:
            return
        result = self._api.wait(self._handle, timeout_ms)
        if result is None:
            raise _in_progress()
        handle, self._handle = self._handle, None
        try:
            self._api.close(handle)
        finally:
            if self._channel is not None:
                self._channel.close()
                self._channel = None
        if result != 0:
            code, detail = EXIT_CODES.get(result, EXIT_CODES[23])
            raise DeviceIdentityError(code, detail)

    def check_pending(self):
        if not self._lock.acquire(blocking=False):
            raise _in_progress()
        try:
            self._finish()
        finally:
            self._lock.release()

    def run(self, mode):
        if mode not in {"initialize", "repair-access"}:
            raise DeviceIdentityError("KEY_SETUP_CONTEXT_INVALID", "设备初始化操作无效")
        if not self._lock.acquire(blocking=False):
            raise _in_progress()
        try:
            if self._handle is not None:
                self._finish()
                # A completed old attempt is not authorization to launch a new one.
                return
            api = self._process_api()
            self._handle = api.launch(mode)
            self._finish(45000)
        finally:
            self._lock.release()

    def run_software(self, permit_provider):
        if not callable(permit_provider):
            raise DeviceIdentityError(
                "KEY_SETUP_CONTEXT_INVALID", "软件初始化上下文无效"
            )
        if not self._lock.acquire(blocking=False):
            raise _in_progress()
        try:
            if self._handle is not None:
                self._finish()
                return
            api = self._process_api()
            context = api.software_context()
            permit = permit_provider(context=context)
            from .device_initialization_channel import SoftwareInitializationChannel

            factory = self._channel_factory or SoftwareInitializationChannel
            self._channel = factory(context, permit)
            try:
                self._handle = api.launch("initialize-software", nonce=context.nonce)
                self._channel.bind_helper(api.process_id(self._handle))
            except BaseException:
                self._channel.close()
                if self._handle is None:
                    self._channel = None
                # A successfully launched helper remains observed by its handle.
                raise
            self._finish(45000)
        finally:
            self._lock.release()


_coordinator = DeviceSetupCoordinator()


class InteractiveWindowsDeviceIdentity:
    """Production activation adapter; normal reads use the unchanged CNG key.

    Software creation has a separate signed-permit bootstrap. A browser cannot
    choose a provider or inject an approval boolean into normal activation.
    """

    def __init__(self, *, identity=None, coordinator=None):
        self._identity = identity if identity is not None else MachineDeviceIdentity()
        self._coordinator = coordinator if coordinator is not None else _coordinator

    def open_existing(self):
        self._coordinator.check_pending()
        return self._identity.open_existing()

    def initialize_for_activation(self, *, operator_sid=None, software_approved=False):
        if operator_sid is not None or software_approved is not False:
            raise DeviceIdentityError("KEY_SETUP_CONTEXT_INVALID", "设备初始化参数无效")
        existing = self.open_existing()
        if existing is not None:
            return existing
        self._coordinator.run("initialize")
        return self._reopen_after_setup()

    def repair_operator_access(self):
        self._coordinator.run("repair-access")
        with self._reopen_after_setup():
            pass

    def initialize_software_for_activation(self, permit_provider):
        existing = self.open_existing()
        if existing is not None:
            return existing
        self._coordinator.run_software(permit_provider)
        return self._reopen_after_setup()

    def _reopen_after_setup(self):
        key = self._identity.open_existing()
        if key is None:
            raise DeviceIdentityError(
                "KEY_NOT_FOUND", "初始化后仍未读取到设备密钥，请重新校验"
            )
        try:
            # Check the original (non-elevated) operator can actually use the key.
            key.sign(b"publicvideo.device-setup.local-check.v1")
        except BaseException:
            key.close()
            raise
        return key


def dispatch_setup_helper(argv, *, api_factory=None, identity_factory=None):
    """Early EXE branch: no server, models, config, tasks or browser is started."""
    if HELPER_FLAG not in argv:
        return None
    if (
        len(argv) not in {3, 4}
        or argv[0] != HELPER_FLAG
        or argv[1] not in MODES
        or not isinstance(argv[2], str)
    ):
        return 20
    if (argv[1] == "initialize-software") != (len(argv) == 4):
        return 20
    from .device_identity_setup_windows import parse_operator_process
    from .device_auth_protocol import DeviceAuthorizationError

    try:
        pid, creation_time = parse_operator_process(argv[2])
        if argv[1] == "initialize-software":
            from .device_initialization_channel import pipe_name

            pipe_name(argv[3])
        if api_factory is None:
            from .device_identity_setup_windows import NativeSetupApi

            api = NativeSetupApi()
        else:
            api = api_factory()
        # SID is read from the original process token, NOT the elevated admin's
        # token, a query parameter, editable config, or a command-line SID.
        with api.verified_operator(pid, creation_time) as operator_sid:
            identity = (identity_factory or MachineDeviceIdentity)()
            if argv[1] == "initialize":
                with identity.initialize_for_activation(operator_sid=operator_sid):
                    pass
            elif argv[1] == "initialize-software":
                import time
                from .device_software_initialization import (
                    SoftwareInitializationContext,
                    verify_initializer_handoff,
                )

                context = SoftwareInitializationContext(
                    pid, creation_time, operator_sid, argv[3]
                )
                raw = api.receive_software_permit(context)

                def verify():
                    verify_initializer_handoff(raw, context=context, now=time.time())

                verify()
                with identity.initialize_for_activation(
                    operator_sid=operator_sid,
                    protection="software",
                    software_approved=True,
                    before_create=verify,
                ):
                    pass
            else:
                identity.repair_operator_access(api, operator_sid)
        return 0
    except DeviceAuthorizationError:
        return 32
    except DeviceIdentityError as exc:
        for result, (code, _) in EXIT_CODES.items():
            if code == exc.code:
                return result
        return 23
    except Exception:
        # No raw native exceptions / tokens / user paths in elevated output.
        return 23
