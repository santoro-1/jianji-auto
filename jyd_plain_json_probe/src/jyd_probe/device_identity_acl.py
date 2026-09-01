"""Add read/sign access for ONE verified operator, retaining the existing DACL.

Only used by the explicitly elevated helper on the fixed existing product key.
No filesystem key paths, ownership takeover, key creation or private export.
"""

from __future__ import annotations

import ctypes
from ctypes import wintypes

from .device_identity_windows import DeviceIdentityError, SILENT, validate_operator_sid


class _Trustee(ctypes.Structure):
    _fields_ = [
        ("multiple", ctypes.c_void_p),
        ("operation", ctypes.c_int),
        ("form", ctypes.c_int),
        ("kind", ctypes.c_int),
        ("name", ctypes.c_void_p),
    ]


class _ExplicitAccess(ctypes.Structure):
    _fields_ = [
        ("permissions", wintypes.DWORD),
        ("mode", ctypes.c_int),
        ("inheritance", wintypes.DWORD),
        ("trustee", _Trustee),
    ]


class _Descriptor(ctypes.Structure):
    _fields_ = [
        ("revision", wintypes.BYTE),
        ("reserved", wintypes.BYTE),
        ("control", wintypes.WORD),
        ("owner", ctypes.c_void_p),
        ("group", ctypes.c_void_p),
        ("sacl", ctypes.c_void_p),
        ("dacl", ctypes.c_void_p),
    ]


def grant_operator_read_access(api, key_handle, operator_sid):
    validate_operator_sid(operator_sid)
    advapi, pointer, dword = api._advapi, ctypes.c_void_p, wintypes.DWORD
    definitions = {
        "ConvertStringSidToSidW": (
            [wintypes.LPCWSTR, ctypes.POINTER(pointer)],
            wintypes.BOOL,
        ),
        "GetSecurityDescriptorDacl": (
            [
                pointer,
                ctypes.POINTER(wintypes.BOOL),
                ctypes.POINTER(pointer),
                ctypes.POINTER(wintypes.BOOL),
            ],
            wintypes.BOOL,
        ),
        "GetSecurityDescriptorControl": (
            [pointer, ctypes.POINTER(wintypes.WORD), ctypes.POINTER(dword)],
            wintypes.BOOL,
        ),
        "SetEntriesInAclW": (
            [dword, ctypes.POINTER(_ExplicitAccess), pointer, ctypes.POINTER(pointer)],
            dword,
        ),
        "InitializeSecurityDescriptor": ([pointer, dword], wintypes.BOOL),
        "SetSecurityDescriptorDacl": (
            [pointer, wintypes.BOOL, pointer, wintypes.BOOL],
            wintypes.BOOL,
        ),
        "SetSecurityDescriptorControl": (
            [pointer, wintypes.WORD, wintypes.WORD],
            wintypes.BOOL,
        ),
        "MakeSelfRelativeSD": (
            [pointer, pointer, ctypes.POINTER(dword)],
            wintypes.BOOL,
        ),
    }
    for name, (arguments, result) in definitions.items():
        function = getattr(advapi, name)
        function.argtypes, function.restype = arguments, result

    def checked(result):
        if not result:
            api._check(ctypes.get_last_error() or 5)

    size = dword()
    api._check(
        api._ncrypt.NCryptGetProperty(
            key_handle, "Security Descr", None, 0, ctypes.byref(size), 4 | SILENT
        )
    )
    if not 20 <= size.value <= 65536:
        raise DeviceIdentityError("KEY_POLICY_INVALID", "现有密钥访问权限描述无效")
    original = ctypes.create_string_buffer(size.value)
    api._check(
        api._ncrypt.NCryptGetProperty(
            key_handle,
            "Security Descr",
            original,
            len(original),
            ctypes.byref(size),
            4 | SILENT,
        )
    )
    old_acl, present, defaulted = pointer(), wintypes.BOOL(), wintypes.BOOL()
    checked(
        advapi.GetSecurityDescriptorDacl(
            original,
            ctypes.byref(present),
            ctypes.byref(old_acl),
            ctypes.byref(defaulted),
        )
    )
    if not present.value or not old_acl:
        raise DeviceIdentityError(
            "KEY_POLICY_INVALID", "现有密钥缺少受限访问列表，请联系管理员核对"
        )
    control, revision = wintypes.WORD(), dword()
    checked(
        advapi.GetSecurityDescriptorControl(
            original, ctypes.byref(control), ctypes.byref(revision)
        )
    )
    sid, new_acl = pointer(), pointer()
    try:
        checked(advapi.ConvertStringSidToSidW(operator_sid, ctypes.byref(sid)))
        entry = _ExplicitAccess()
        entry.permissions = 0x80000000  # GENERIC_READ only, not change/delete/export
        entry.mode = 1  # GRANT_ACCESS merges, not SET_ACCESS or a DACL replacement
        entry.trustee.form = 0  # TRUSTEE_IS_SID (binary, no name lookup)
        entry.trustee.kind = 1  # TRUSTEE_IS_USER
        entry.trustee.name = sid.value
        api._check(
            advapi.SetEntriesInAclW(
                1, ctypes.byref(entry), old_acl, ctypes.byref(new_acl)
            )
        )
        descriptor = _Descriptor()
        checked(advapi.InitializeSecurityDescriptor(ctypes.byref(descriptor), 1))
        checked(
            advapi.SetSecurityDescriptorDacl(
                ctypes.byref(descriptor), True, new_acl, False
            )
        )
        checked(
            advapi.SetSecurityDescriptorControl(
                ctypes.byref(descriptor), 0x1000, control.value & 0x1000
            )
        )
        length = dword()
        first = advapi.MakeSelfRelativeSD(
            ctypes.byref(descriptor), None, ctypes.byref(length)
        )
        if not first and ctypes.get_last_error() != 122:
            checked(first)
        if not 20 <= length.value <= 65536:
            raise DeviceIdentityError("KEY_POLICY_INVALID", "设备访问权限描述长度异常")
        relative = ctypes.create_string_buffer(length.value)
        checked(
            advapi.MakeSelfRelativeSD(
                ctypes.byref(descriptor), relative, ctypes.byref(length)
            )
        )
        # Update only DACL and persist it, leaving owner/group and the key unchanged.
        api._check(
            api._ncrypt.NCryptSetProperty(
                key_handle,
                "Security Descr",
                relative,
                length.value,
                0x80000004 | SILENT,
            )
        )
    finally:
        if new_acl:
            api._kernel.LocalFree(new_acl)
        if sid:
            api._kernel.LocalFree(sid)
