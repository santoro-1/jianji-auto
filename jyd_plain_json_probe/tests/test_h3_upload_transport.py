from __future__ import annotations

import ctypes
import os
from pathlib import Path
import tracemalloc

import pytest

from jyd_probe.h3_upload_transport import H3_UPLOAD_CHUNK_SIZE, StreamingMultipartBody


def _windows_rss_bytes() -> int | None:
    if os.name != "nt":
        return None

    class ProcessMemoryCounters(ctypes.Structure):
        _fields_ = [
            ("cb", ctypes.c_ulong),
            ("page_fault_count", ctypes.c_ulong),
            ("peak_working_set_size", ctypes.c_size_t),
            ("working_set_size", ctypes.c_size_t),
            ("quota_peak_paged_pool_usage", ctypes.c_size_t),
            ("quota_paged_pool_usage", ctypes.c_size_t),
            ("quota_peak_non_paged_pool_usage", ctypes.c_size_t),
            ("quota_non_paged_pool_usage", ctypes.c_size_t),
            ("pagefile_usage", ctypes.c_size_t),
            ("peak_pagefile_usage", ctypes.c_size_t),
        ]

    counters = ProcessMemoryCounters()
    counters.cb = ctypes.sizeof(counters)
    get_current_process = ctypes.windll.kernel32.GetCurrentProcess
    get_current_process.restype = ctypes.c_void_p
    process = get_current_process()
    get_process_memory_info = ctypes.windll.psapi.GetProcessMemoryInfo
    get_process_memory_info.argtypes = [
        ctypes.c_void_p,
        ctypes.POINTER(ProcessMemoryCounters),
        ctypes.c_ulong,
    ]
    ok = get_process_memory_info(
        process, ctypes.byref(counters), counters.cb
    )
    if not ok:
        raise ctypes.WinError()
    return int(counters.working_set_size)


def test_streaming_multipart_has_exact_length_and_bounded_chunks(tmp_path: Path) -> None:
    source = tmp_path / "large.mp4"
    source.write_bytes(b"a" * (H3_UPLOAD_CHUNK_SIZE * 2 + 317))
    body = StreamingMultipartBody(
        fields={
            "kind": "video",
            "asset_role": "reference_video",
            "upload_key": "upload-key-001",
            "source_sha256": "a" * 64,
            "transport_profile": "original-v1",
        },
        file_field="file",
        file_path=source,
        filename="人物参考视频.mp4",
        boundary="fixed-h3-boundary",
    )
    chunks = list(body)
    assert sum(map(len, chunks)) == body.content_length == len(body)
    assert max(map(len, chunks)) <= H3_UPLOAD_CHUNK_SIZE
    header = chunks[len(body._field_parts)]
    assert b"filename*=UTF-8''%E4%BA%BA%E7%89%A9" in header
    assert b"Transfer-Encoding" not in b"".join(chunks[: len(body._field_parts) + 1])


def test_streaming_multipart_strips_filename_header_injection(tmp_path: Path) -> None:
    source = tmp_path / "input.png"
    source.write_bytes(b"png")
    body = StreamingMultipartBody(
        fields={"kind": "image"},
        file_field="file",
        file_path=source,
        filename='safe.png\r\nX-Injected: yes"',
        boundary="fixed-h3-boundary",
    )
    header = list(body)[1]
    assert b"\r\nX-Injected:" not in header
    assert header.count(b"Content-Disposition:") == 1


def test_mock_07_500mb_stream_has_exact_length_bounded_chunks_and_low_memory(
    tmp_path: Path,
) -> None:
    source = tmp_path / "reference-500mb.mp4"
    with source.open("wb") as output:
        output.truncate(500 * 1024 * 1024)
    body = StreamingMultipartBody(
        fields={
            "kind": "video",
            "asset_role": "reference_video",
            "upload_key": "large-file-acceptance-key",
            "source_sha256": "0" * 64,
            "transport_profile": "original-v1",
        },
        file_field="file",
        file_path=source,
        filename="reference-500mb.mp4",
    )
    tracemalloc.start()
    baseline = _windows_rss_bytes()
    peak = baseline
    transferred = 0
    for chunk in body:
        transferred += len(chunk)
        current = _windows_rss_bytes()
        if current is not None and peak is not None:
            peak = max(peak, current)
        assert len(chunk) <= H3_UPLOAD_CHUNK_SIZE
    assert transferred == body.content_length
    _, python_peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    growth = python_peak if baseline is None or peak is None else peak - baseline
    assert growth < 64 * 1024 * 1024


@pytest.mark.parametrize("field_name", ["bad name", "bad\r\nname", 'bad"name'])
def test_streaming_multipart_rejects_unsafe_field_names(
    tmp_path: Path, field_name: str
) -> None:
    source = tmp_path / "input.bin"
    source.write_bytes(b"x")
    with pytest.raises(ValueError, match="字段名"):
        StreamingMultipartBody(
            fields={field_name: "value"},
            file_field="file",
            file_path=source,
            filename="input.bin",
        )
