"""Regression for 250/188 paths and failures that cannot be written to disk."""

import base64
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
from pathlib import Path
import sys
from unittest.mock import Mock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from jyd_probe import h3_audio_cleanup as cleanup
from jyd_probe import project_h3 as h3
from jyd_probe.h3_cache_paths import compact_digest, cleanup_directory, item_h3_root
from test_h3_audio_cleanup_coordinator import setup_coordinator


def write_cleanup(directory, raw, script):
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "clean.wav").write_bytes(b"clean audio")
    (directory / "preview.mp4").write_bytes(b"clean preview")
    report = {
        "key": cleanup.cleanup_key(cleanup.file_sha256(raw), script),
        "version": cleanup.H3_AUDIO_CLEANUP_VERSION,
        "raw_sha256": cleanup.file_sha256(raw),
        "audio_offset_seconds": 0.0,
        "muted_until_seconds": 0.2,
        "restored_at_seconds": 0.21,
        "audio_bytes": 11,
        "preview_bytes": 13,
    }
    (directory / "report.json").write_text(json.dumps(report), encoding="utf-8")


@pytest.mark.parametrize("runtime", ["F:/cxd/PV/digital-human", "E:/cxd/PublicVideo-x64"])
def test_deployment_paths_include_temp_files_and_stay_below_240(runtime):
    # No file is created on either production drive. Include full-size IDs and
    # both transient filenames: checking only final MP4 names missed this bug.
    storage = Path(runtime) / "data" / "web_storage"
    args = dict(owner_user_id="6", project_id="b" * 32, item_id="f" * 32,
                remote_batch_id="batch", remote_item_id="item", segment_id="segment")
    new_raw, new_meta = h3._h3_segment_cache_files(storage, **args)
    old_raw, _ = h3._h3_segment_cache_files(storage, **args, legacy=True)
    key = "a" * 64
    root = item_h3_root(storage, "6", "b" * 32, "f" * 32)
    short = cleanup_directory(old_raw, key)
    assert short == cleanup_directory(new_raw, key)
    paths = [
        new_raw, new_meta, new_raw.with_name("current." + "1" * 32 + ".mp4.tmp"),
        short / "failure.json", short / "build-12345678" / "analysis.wav",
        root / ("m-" + compact_digest(key)) / "h3-authoritative-full.part.wav",
        root / "f" / key / ("1" * 32 + ".part.mp4"),
    ]
    for path in paths:
        assert len(str(path).encode("utf-16-le")) // 2 < 240, str(path)
        path.relative_to(root)
    old_work = old_raw.parent / "head-cleanup" / key / "build-12345678" / "analysis.wav"
    assert len(str(old_work)) > 260
    assert len(str(short / "build-12345678" / "analysis.wav")) < len(str(old_work)) - 80


def test_compact_ids_keep_all_hash_bits_and_windows_case_safety():
    for raw in (b"raw", b"other", bytes(range(256))):
        digest = hashlib.sha256(raw).hexdigest()
        compact = compact_digest(digest)
        assert compact == compact.lower()
        assert len(compact) == 52
        assert base64.b32decode(compact.upper() + "====").hex() == digest


def test_new_cache_isolated_by_owner_project_item_batch_and_segment(tmp_path):
    args = dict(owner_user_id="u1", project_id="p1", item_id="i1",
                remote_batch_id="b1", remote_item_id="ri1", segment_id="s1")
    raw, _ = h3._h3_segment_cache_files(tmp_path, **args)
    for field in args:
        other, _ = h3._h3_segment_cache_files(tmp_path, **{**args, field: "other"})
        assert other != raw
    first = cleanup_directory(raw, cleanup.cleanup_key("a" * 64, "first"))
    assert first != cleanup_directory(raw, cleanup.cleanup_key("a" * 64, "second"))
    assert first != cleanup_directory(raw, cleanup.cleanup_key("b" * 64, "first"))


def test_old_download_is_reused_then_new_version_uses_short_cache(tmp_path, monkeypatch):
    store, project, client, coordinator, calls, request = setup_coordinator(tmp_path, monkeypatch)
    remote = {**client.snapshot["items"][0], "batch_id": client.snapshot["batch_id"]}
    segment = remote["segments"][0]
    args = ("u1", project["project_id"], project["items"][0]["item_id"], remote, segment)
    old_raw, old_meta = coordinator._segment_cache_files(*args, legacy=True)
    old_raw.parent.mkdir(parents=True)
    old_raw.write_bytes(b"video:s1")
    old_meta.write_text(json.dumps({
        "result_signature": coordinator._segment_result_signature(segment),
        "local_video_sha256": cleanup.file_sha256(old_raw),
    }), encoding="utf-8")
    monkeypatch.setattr(h3, "read_cleanup", lambda *_: None)
    synced = coordinator.sync("u1", project["project_id"], "token")["project"]
    preview_args = dict(item_id=args[2], segment_number=1, storage_root=coordinator.storage_root, original=True)
    assert h3.current_h3_segment_preview_path(synced, **preview_args) == old_raw
    assert not client.downloads
    assert request.call_args.args[0] == old_raw
    new_raw, _ = coordinator._segment_cache_files(*args)
    assert not new_raw.exists()
    new_raw.parent.mkdir(parents=True)
    new_raw.write_bytes(b"")
    assert h3.current_h3_segment_preview_path(synced, **preview_args) == old_raw
    client.snapshot["items"][0]["segments"][0]["completed_at"] = "v2"
    client.video_payloads["s1"] = b"replacement"
    synced = coordinator.sync("u1", project["project_id"], "token")["project"]
    assert client.downloads == ["s1"]
    assert h3.current_h3_segment_preview_path(synced, **preview_args) == new_raw
    assert new_raw.read_bytes() == b"replacement"
    assert old_raw.read_bytes() == b"video:s1"
    assert old_meta.is_file()
    assert not calls  # Cleanup still pending; no premature assembly.
    # If a later snapshot asks for the old signature, the preview and assembly
    # must not choose different files merely because a legacy copy still exists.
    old_segment = {**segment, "completed_at": "v1"}
    assert coordinator._cached_segment_path(*args[:-1], old_segment, require_current=True) is None


def test_old_valid_cleanup_copied_without_asr_or_changing_original(tmp_path, monkeypatch):
    raw = tmp_path / "h3" / "segment-cache" / ("d" * 64) / "current.mp4"
    raw.parent.mkdir(parents=True)
    raw.write_bytes(b"raw media")
    key = cleanup.cleanup_key(cleanup.file_sha256(raw), "script")
    old = raw.parent / "head-cleanup" / key
    write_cleanup(old, raw, "script")
    original = {path.name: path.read_bytes() for path in old.iterdir()}
    run = Mock(side_effect=AssertionError("no encoding"))
    monkeypatch.setattr(cleanup, "_run", run)
    result = cleanup.clean_segment(raw, "script", None)
    assert result.directory == cleanup_directory(raw, key)
    assert result.directory != old
    assert {path.name: path.read_bytes() for path in old.iterdir()} == original
    assert result.audio_path.read_bytes() == original["clean.wav"]
    assert result.preview_path.read_bytes() == original["preview.mp4"]
    assert raw.read_bytes() == b"raw media"
    assert cleanup.clean_segment(raw, "script", None) == result
    run.assert_not_called()


@pytest.fixture
def isolated_queue(monkeypatch):
    monkeypatch.setattr(cleanup, "_PENDING", set())
    monkeypatch.setattr(cleanup, "_FAILURES", {})
    with ThreadPoolExecutor(max_workers=1) as pool:
        submitted = []

        class Executor:
            def submit(self, job):
                future = pool.submit(job)
                submitted.append(future)
                return future

        monkeypatch.setattr(cleanup, "_EXECUTOR", Executor())
        yield submitted


@pytest.mark.parametrize("failure_stage", ["mkdir", "write", "replace", "none"])
def test_failure_budget_survives_failure_record_io_errors(
    tmp_path, monkeypatch, isolated_queue, failure_stage
):
    raw = tmp_path / "raw.mp4"
    raw.write_bytes(b"original")
    directory, _, _ = cleanup._cache_directory(raw, "script", cleanup.DEFAULT_CONFIG)
    clock = [1000.0]
    monkeypatch.setattr(cleanup.time, "time", lambda: clock[0])
    clean = Mock(side_effect=OSError("cannot process output directory"))
    monkeypatch.setattr(cleanup, "clean_segment", clean)
    if failure_stage == "mkdir":
        real_mkdir = Path.mkdir

        def mkdir(path, *args, **kwargs):
            if path == directory:
                raise OSError("cannot create failure directory")
            return real_mkdir(path, *args, **kwargs)

        monkeypatch.setattr(Path, "mkdir", mkdir)
    elif failure_stage == "write":
        monkeypatch.setattr(cleanup.tempfile, "NamedTemporaryFile", Mock(side_effect=PermissionError("cannot write")))
    elif failure_stage == "replace":
        monkeypatch.setattr(cleanup.os, "replace", Mock(side_effect=PermissionError("cannot publish")))
    for attempt in range(1, 4):
        assert cleanup.request_cleanup(raw, "script", None)["status"] == "PROCESSING"
        # This used to raise from the unobserved Future, lose the budget, and
        # launch an unbounded number of new jobs on every status poll.
        assert isolated_queue[-1].result(timeout=3) is None
        if failure_stage == "none":
            cleanup._FAILURES.clear()  # Simulate a restart: use disk state only.
        status = cleanup.request_cleanup(raw, "script", None)
        assert status["status"] == ("FAILED" if attempt == 3 else "RETRY_WAIT")
        assert "cannot process" in status["error"]
        clock[0] += 61
    assert clean.call_count == 3
    for _ in range(5):
        assert cleanup.request_cleanup(raw, "script", None)["status"] == "FAILED"
    assert len(isolated_queue) == 3
    assert raw.read_bytes() == b"original"
    assert cleanup.request_cleanup(raw, "script", None, force_retry=True)["status"] == "PROCESSING"
    assert isolated_queue[-1].result(timeout=3) is None
    assert cleanup.request_cleanup(raw, "script", None)["status"] == "RETRY_WAIT"


def test_executor_failure_is_visible_and_not_requeued(tmp_path, monkeypatch, isolated_queue):
    raw = tmp_path / "raw.mp4"
    raw.write_bytes(b"original")
    submit = Mock(side_effect=RuntimeError("executor shut down"))
    monkeypatch.setattr(cleanup._EXECUTOR, "submit", submit)
    assert cleanup.request_cleanup(raw, "script", None)["status"] == "FAILED"
    assert cleanup.request_cleanup(raw, "script", None)["status"] == "FAILED"
    submit.assert_called_once()
    assert not cleanup._PENDING


def test_success_wins_even_if_old_failure_record_cannot_be_deleted(
    tmp_path, monkeypatch, isolated_queue
):
    raw = tmp_path / "raw.mp4"
    raw.write_bytes(b"original")
    directory, _, _ = cleanup._cache_directory(raw, "script", cleanup.DEFAULT_CONFIG)
    directory.mkdir()
    failure = directory / "failure.json"
    failure.write_text('{"attempts": 3, "error": "old failure"}', encoding="utf-8")
    real_unlink = Path.unlink

    def unlink(path, *args, **kwargs):
        if path == failure:
            raise PermissionError("failure file is locked")
        return real_unlink(path, *args, **kwargs)

    monkeypatch.setattr(Path, "unlink", unlink)
    monkeypatch.setattr(cleanup, "clean_segment", lambda *_: write_cleanup(directory, raw, "script"))
    assert cleanup.request_cleanup(raw, "script", None, force_retry=True)["status"] == "PROCESSING"
    assert isolated_queue[-1].result(timeout=3) is None
    assert cleanup.request_cleanup(raw, "script", None)["status"] == "READY"
    assert failure.is_file()
    assert not cleanup._FAILURES
    assert raw.read_bytes() == b"original"


@pytest.mark.parametrize("invalid", ["[]", "null", "{", '{"attempts": "bad"}', '{"retry_at": "NaN"}'])
def test_corrupt_failure_record_is_visible_not_a_500(tmp_path, monkeypatch, invalid):
    raw = tmp_path / "raw.mp4"
    raw.write_bytes(b"original")
    directory, _, _ = cleanup._cache_directory(raw, "script", cleanup.DEFAULT_CONFIG)
    directory.mkdir()
    (directory / "failure.json").write_text(invalid, encoding="utf-8")
    submit = Mock()
    monkeypatch.setattr(cleanup._EXECUTOR, "submit", submit)
    assert cleanup.request_cleanup(raw, "script", None)["status"] == "FAILED"
    submit.assert_not_called()
