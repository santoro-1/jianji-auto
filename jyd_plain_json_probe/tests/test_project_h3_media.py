from __future__ import annotations

from pathlib import Path
from subprocess import CompletedProcess
import sys
from unittest.mock import patch
import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from jyd_probe.project_h3_media import (  # noqa: E402
    _duration_preserving_dissolve_filter,
    _ffprobe_path,
    _run,
    prepare_h3_media,
    H3MediaError,
)


def test_h3_script_mismatch_is_rejected_before_encoding(tmp_path: Path) -> None:
    with patch("jyd_probe.project_h3_media._probe_duration", return_value=1.0), patch("jyd_probe.project_h3_media._merge_segments") as merge:
        with pytest.raises(H3MediaError, match="无法重建冻结原稿"):
            prepare_h3_media(segment_paths=[tmp_path / "clip.mp4"], segment_texts=["旧稿"], script_text="新稿", target_dir=tmp_path / "output")
    merge.assert_not_called()


def test_h3_media_uses_bundled_ffmpeg_when_path_has_no_ffmpeg() -> None:
    completed = CompletedProcess(["unused"], 0, stdout="", stderr="")
    with patch(
        "jyd_probe.project_h3_media._ffmpeg_path",
        return_value=r"F:\PublicVideo-x64\digital-human\ffmpeg\bin\ffmpeg.exe",
    ), patch(
        "jyd_probe.project_h3_media.subprocess.run", return_value=completed
    ) as run:
        _run(["ffmpeg", "-version"], "FFmpeg 检查失败")

    assert run.call_args.args[0][0] == (
        r"F:\PublicVideo-x64\digital-human\ffmpeg\bin\ffmpeg.exe"
    )


def test_h3_media_finds_ffprobe_next_to_bundled_ffmpeg(tmp_path: Path) -> None:
    ffmpeg = tmp_path / "ffmpeg.exe"
    ffprobe = tmp_path / "ffprobe.exe"
    ffmpeg.write_bytes(b"ffmpeg")
    ffprobe.write_bytes(b"ffprobe")

    with patch("jyd_probe.project_h3_media.shutil.which", return_value=None), patch(
        "jyd_probe.project_h3_media._ffmpeg_path", return_value=str(ffmpeg)
    ):
        assert _ffprobe_path() == str(ffprobe.resolve())


def test_h3_dissolve_filter_preserves_the_full_timeline() -> None:
    graph, seconds = _duration_preserving_dissolve_filter([3.0, 4.0, 5.0], 0.5)

    assert seconds == 0.5
    assert "trim=start=0.000000000:end=2.750000000" in graph
    assert "trim=start=0.250000000:end=3.750000000" in graph
    assert "trim=start=0.250000000:end=5.000000000" in graph
    assert "tpad=stop_mode=clone:stop_duration=0.250000000" in graph
    assert "tpad=start_mode=clone:start_duration=0.250000000" in graph
    assert graph.count("xfade=transition=fade:duration=0.500000000:offset=0") == 2
    assert "concat=n=5:v=1:a=0" in graph
