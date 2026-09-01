import copy
import hashlib
from pathlib import Path

import pytest

from jyd_probe import draft_media_paths as media_paths


def long_media(tmp_path, label="source", payload=b"original video", suffix=".mp4"):
    parent = tmp_path / label
    while len(str(parent)) < 290:
        parent /= "nested-cache-0123456789abcdef"
    parent.mkdir(parents=True, exist_ok=True)
    source = parent / f"segment{suffix}"
    source.write_bytes(payload)
    return source


def draft_data(*sources):
    return {
        "duration": 8_000_000,
        "tracks": [{"type": "video", "segments": [{"material_id": "v0"}]}],
        "materials": {
            "videos": [
                {"id": f"v{i}", "path": str(source), "material_name": "segment.mp4"}
                for i, source in enumerate(sources)
            ]
        },
    }


def test_long_sources_are_copied_unchanged_without_touching_timeline(tmp_path):
    sources = [long_media(tmp_path, str(i), bytes([i]) * 100) for i in range(3)]
    data = draft_data(*sources)
    before = copy.deepcopy(data)
    output = tmp_path / "draft"

    assert media_paths.localize_long_media_paths(data, output) == 3
    paths = [Path(m["path"]) for m in data["materials"]["videos"]]
    assert len(set(paths)) == 3  # All original files have the same basename.
    for original, target in zip(sources, paths):
        assert target.parent == output / media_paths.LOCAL_MEDIA_DIRECTORY
        assert len(str(target)) <= media_paths.MAX_EDITOR_MEDIA_PATH_UNITS
        assert target.read_bytes() == original.read_bytes()
        assert target.stem == hashlib.sha256(original.read_bytes()).hexdigest()
    for actual, expected in zip(data["materials"]["videos"], before["materials"]["videos"]):
        actual["path"] = expected["path"]
    assert data == before


def test_same_content_reused_and_new_content_does_not_overwrite_old_copy(tmp_path):
    source = long_media(tmp_path)
    duplicate = long_media(tmp_path, "second")
    output = tmp_path / "draft"
    data = draft_data(source, source, duplicate)
    assert media_paths.localize_long_media_paths(data, output) == 3
    paths = {Path(m["path"]) for m in data["materials"]["videos"]}
    assert len(paths) == 1
    old_copy = paths.pop()
    assert media_paths.localize_long_media_paths(data, output) == 0
    assert media_paths.localize_long_media_paths(draft_data(source), output) == 1

    source.write_bytes(b"regenerated video")
    newer = draft_data(source)
    assert media_paths.localize_long_media_paths(newer, output) == 1
    new_copy = Path(newer["materials"]["videos"][0]["path"])
    assert new_copy != old_copy
    assert old_copy.read_bytes() == b"original video"
    assert new_copy.read_bytes() == source.read_bytes()


def test_short_paths_remote_urls_and_unrelated_fields_stay_unchanged(tmp_path):
    short = tmp_path / "short.mp4"
    short.write_bytes(b"video")
    data = draft_data(short)
    data["materials"]["videos"].extend([
        {"path": "https://media.example/" + "x" * 300},
        {"path": "##_draftpath_placeholder_1_##/video.mp4"},
        {"path": ""},
    ])
    data["materials"]["texts"] = [{"path": "x" * 300}]
    before = copy.deepcopy(data)
    assert media_paths.localize_long_media_paths(data, tmp_path / "draft") == 0
    assert data == before
    assert not (tmp_path / "draft").exists()


def test_long_audio_and_embedded_subdraft_are_localized(tmp_path):
    source = long_media(tmp_path)
    audio = long_media(tmp_path, "audio", b"wave", ".wav")
    nested = draft_data(source)
    data = {"materials": {
        "audios": [{"id": "a", "path": str(audio)}],
        "drafts": [{"draft": nested}],
    }}
    assert media_paths.localize_long_media_paths(data, tmp_path / "draft") == 2
    assert Path(data["materials"]["audios"][0]["path"]).read_bytes() == b"wave"
    assert Path(nested["materials"]["videos"][0]["path"]).read_bytes() == source.read_bytes()


@pytest.mark.parametrize("empty", [False, True])
def test_missing_or_empty_long_source_fails_without_rewriting_json(tmp_path, empty):
    source = long_media(tmp_path, payload=b"" if empty else b"video")
    if not empty:
        source.unlink()
    data = draft_data(source)
    before = copy.deepcopy(data)
    with pytest.raises((FileNotFoundError, ValueError), match="不存在|为空"):
        media_paths.localize_long_media_paths(data, tmp_path / "draft")
    assert data == before


def test_overlong_output_directory_gives_actionable_error(tmp_path):
    source = long_media(tmp_path)
    data = draft_data(source)
    before = copy.deepcopy(data)
    output = source.parent / "draft"
    with pytest.raises(ValueError, match="缩短保存目录或名称"):
        media_paths.localize_long_media_paths(data, output)
    assert data == before
    assert not output.exists()


@pytest.mark.parametrize("bad_hash", [False, True])
def test_failed_copy_never_publishes_partial_file_or_path(tmp_path, monkeypatch, bad_hash):
    source = long_media(tmp_path)
    data = draft_data(source)
    before = copy.deepcopy(data)
    output = tmp_path / "draft"

    def fail_copy(original, target):
        target.write_bytes(b"partial copy")
        if not bad_hash:
            raise OSError("copy failed")

    monkeypatch.setattr(media_paths.shutil, "copyfile", fail_copy)
    with pytest.raises((OSError, RuntimeError), match="copy failed|素材发生变化"):
        media_paths.localize_long_media_paths(data, output)
    assert data == before
    assert list((output / media_paths.LOCAL_MEDIA_DIRECTORY).iterdir()) == []
    assert source.read_bytes() == b"original video"


def test_existing_corrupted_copy_is_not_overwritten(tmp_path):
    source = long_media(tmp_path)
    output = tmp_path / "draft"
    data = draft_data(source)
    media_paths.localize_long_media_paths(data, output)
    target = Path(data["materials"]["videos"][0]["path"])
    target.write_bytes(b"unexpected existing data")
    with pytest.raises(RuntimeError, match="未覆盖现有文件"):
        media_paths.localize_long_media_paths(draft_data(source), output)
    assert target.read_bytes() == b"unexpected existing data"


def test_path_budget_counts_windows_utf16_units():
    assert media_paths._path_units("a😀") == 3
