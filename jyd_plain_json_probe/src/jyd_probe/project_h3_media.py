from __future__ import annotations

from dataclasses import dataclass
import json
import os
from pathlib import Path
import shutil
import subprocess
import wave
from typing import Iterable

from .bgm_loudness import _ffmpeg_path


class H3MediaError(RuntimeError):
    pass


H3_VISUAL_DISSOLVE_SECONDS = 0.5


@dataclass(frozen=True)
class H3MediaAssets:
    master_av_path: Path
    silent_base_video_path: Path
    authoritative_audio_path: Path
    raw_cues: tuple[dict[str, int | str], ...]
    segment_durations_seconds: tuple[float, ...]
    visual_dissolve_seconds: float = 0.0


def _run(command: list[str], message: str) -> None:
    resolved_command = list(command)
    if resolved_command and resolved_command[0].lower() == "ffmpeg":
        ffmpeg = _ffmpeg_path()
        if not ffmpeg:
            raise H3MediaError("本机未安装 FFmpeg")
        resolved_command[0] = ffmpeg
    try:
        completed = subprocess.run(
            resolved_command,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=1800,
            check=False,
            creationflags=(subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0),
        )
    except FileNotFoundError as exc:
        raise H3MediaError("本机未安装 FFmpeg/FFprobe") from exc
    except subprocess.TimeoutExpired as exc:
        raise H3MediaError(f"{message}：处理超时") from exc
    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout or "").strip()[-500:]
        raise H3MediaError(f"{message}：{detail or '未知错误'}")


def _ffprobe_path() -> str | None:
    configured = str(os.environ.get("JYD_FFPROBE") or "").strip()
    if configured and Path(configured).expanduser().is_file():
        return str(Path(configured).expanduser().resolve())
    discovered = shutil.which("ffprobe")
    if discovered:
        return str(Path(discovered).resolve())
    ffmpeg = _ffmpeg_path()
    if not ffmpeg:
        return None
    candidate = Path(ffmpeg).with_name(
        "ffprobe.exe" if Path(ffmpeg).suffix.lower() == ".exe" else "ffprobe"
    )
    return str(candidate.resolve()) if candidate.is_file() else None


def _atomic_media(command: list[str], target: Path, message: str) -> Path:
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_name(f"{target.stem}.part{target.suffix}")
    try:
        _run([*command, str(temporary)], message)
        os.replace(temporary, target)
        return target
    finally:
        temporary.unlink(missing_ok=True)


def _concat_manifest(segment_paths: Iterable[Path], target: Path) -> Path:
    paths = list(segment_paths)
    if not paths or any(not path.is_file() for path in paths):
        raise H3MediaError("H3 音画分段不完整")
    target.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "file '" + path.resolve().as_posix().replace("'", "'\\''") + "'"
        for path in paths
    ]
    target.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return target


def _probe_av_starts(path: Path) -> tuple[float, float]:
    ffprobe = _ffprobe_path()
    if not ffprobe:
        raise H3MediaError("本机未安装 FFprobe")
    command = [
        ffprobe, "-v", "error", "-show_entries", "stream=codec_type,start_time",
        "-of", "json", str(path),
    ]
    try:
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=60,
            check=False,
            creationflags=(subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0),
        )
        payload = json.loads(completed.stdout)
        starts = {
            str(stream["codec_type"]): float(stream.get("start_time") or 0)
            for stream in payload["streams"]
        }
        video_start, audio_start = starts["video"], starts["audio"]
    except FileNotFoundError as exc:
        raise H3MediaError("本机未安装 FFprobe") from exc
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise H3MediaError("无法读取 H3 音画时间戳") from exc
    if completed.returncode != 0 or video_start < 0 or audio_start < 0:
        raise H3MediaError("H3 音画时间戳不合法")
    return video_start, audio_start


def _duration_preserving_dissolve_filter(
    segment_durations_seconds: list[float],
    requested_seconds: float,
) -> tuple[str, float]:
    if len(segment_durations_seconds) < 2 or requested_seconds <= 0:
        return "", 0.0
    if any(duration <= 0 for duration in segment_durations_seconds):
        raise H3MediaError("H3 分段视频时长不合法")
    transition_seconds = min(
        float(requested_seconds), min(segment_durations_seconds) / 2
    )
    half_seconds = transition_seconds / 2
    filters: list[str] = []
    for index, duration in enumerate(segment_durations_seconds):
        branches = ["body"]
        if index > 0:
            branches.append("head")
        if index < len(segment_durations_seconds) - 1:
            branches.append("tail")
        split_outputs = "".join(
            f"[source_{index}_{branch}]" for branch in branches
        )
        filters.append(
            f"[{index}:v:0]split={len(branches)}{split_outputs}"
        )
        body_start = half_seconds if index > 0 else 0.0
        body_end = (
            duration - half_seconds
            if index < len(segment_durations_seconds) - 1
            else duration
        )
        filters.append(
            f"[source_{index}_body]trim=start={body_start:.9f}:end={body_end:.9f},"
            f"setpts=PTS-STARTPTS,settb=AVTB,setsar=1,format=yuv420p[body_{index}]"
        )
        if index > 0:
            filters.append(
                f"[source_{index}_head]trim=start=0:end={half_seconds:.9f},"
                f"setpts=PTS-STARTPTS,settb=AVTB,setsar=1,format=yuv420p,"
                f"tpad=start_mode=clone:start_duration={half_seconds:.9f}[head_{index}]"
            )
        if index < len(segment_durations_seconds) - 1:
            filters.append(
                f"[source_{index}_tail]trim=start={duration - half_seconds:.9f}:end={duration:.9f},"
                f"setpts=PTS-STARTPTS,settb=AVTB,setsar=1,format=yuv420p,"
                f"tpad=stop_mode=clone:stop_duration={half_seconds:.9f}[tail_{index}]"
            )
    for index in range(len(segment_durations_seconds) - 1):
        filters.append(
            f"[tail_{index}][head_{index + 1}]xfade=transition=fade:"
            f"duration={transition_seconds:.9f}:offset=0[transition_{index}]"
        )
    timeline = "".join(
        label
        for index in range(len(segment_durations_seconds))
        for label in (
            [f"[body_{index}]", f"[transition_{index}]"]
            if index < len(segment_durations_seconds) - 1
            else [f"[body_{index}]"]
        )
    )
    filters.append(
        f"{timeline}concat=n={len(segment_durations_seconds) * 2 - 1}:v=1:a=0,"
        "setpts=PTS-STARTPTS,format=yuv420p[vout]"
    )
    return ";".join(filters), transition_seconds


def _merge_segments(
    segment_paths: list[Path],
    segment_durations_seconds: list[float],
    target: Path,
    *,
    dissolve_seconds: float,
) -> tuple[Path, float]:
    manifest = target.with_suffix(".segments.txt")
    concat_output = target.with_name(f"{target.stem}.concat{target.suffix}")
    zeroed_output = target.with_name(f"{target.stem}.zeroed{target.suffix}")
    dissolve_output = target.with_name(f"{target.stem}.dissolve{target.suffix}")
    _concat_manifest(segment_paths, manifest)
    try:
        _atomic_media(
            [
                "ffmpeg", "-hide_banner", "-nostdin", "-y", "-f", "concat",
                "-safe", "0", "-i", str(manifest), "-map", "0:v:0", "-map",
                "0:a:0", "-c", "copy", "-movflags", "+faststart",
            ],
            concat_output,
            "合并 H3 原生音画失败",
        )
        video_start, audio_start = _probe_av_starts(concat_output)
        _atomic_media(
            [
                "ffmpeg", "-hide_banner", "-nostdin", "-y", "-itsoffset",
                f"{-video_start:.9f}", "-i", str(concat_output), "-itsoffset",
                f"{-audio_start:.9f}", "-i", str(concat_output), "-map", "0:v:0",
                "-map", "1:a:0", "-c", "copy", "-avoid_negative_ts", "disabled",
                "-movflags", "+faststart",
            ],
            zeroed_output,
            "归零 H3 原生音画时间戳失败",
        )
        filter_graph, applied_dissolve_seconds = (
            _duration_preserving_dissolve_filter(
                segment_durations_seconds, dissolve_seconds
            )
        )
        if not filter_graph:
            os.replace(zeroed_output, target)
            return target, 0.0
        inputs = [part for path in segment_paths for part in ("-i", str(path))]
        _atomic_media(
            [
                "ffmpeg", "-hide_banner", "-nostdin", "-y", *inputs,
                "-filter_complex", filter_graph, "-map", "[vout]", "-an",
                "-c:v", "libx264", "-preset", "fast", "-crf", "18",
                "-pix_fmt", "yuv420p", "-movflags", "+faststart",
            ],
            dissolve_output,
            "生成 H3 片段叠化失败",
        )
        return (
            _atomic_media(
                [
                    "ffmpeg", "-hide_banner", "-nostdin", "-y", "-i",
                    str(dissolve_output), "-i", str(zeroed_output), "-map",
                    "0:v:0", "-map", "1:a:0", "-c", "copy", "-movflags",
                    "+faststart",
                ],
                target,
                "合并 H3 叠化画面与原始音频失败",
            ),
            applied_dissolve_seconds,
        )
    finally:
        manifest.unlink(missing_ok=True)
        concat_output.unlink(missing_ok=True)
        zeroed_output.unlink(missing_ok=True)
        dissolve_output.unlink(missing_ok=True)


def _probe_duration(path: Path) -> float:
    ffprobe = _ffprobe_path()
    if not ffprobe:
        raise H3MediaError("本机未安装 FFprobe")
    command = [
        ffprobe, "-v", "error", "-select_streams", "v:0", "-show_entries",
        "stream=duration", "-of", "json", str(path),
    ]
    try:
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=60,
            check=False,
            creationflags=(subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0),
        )
        duration = float(json.loads(completed.stdout)["streams"][0]["duration"])
    except FileNotFoundError as exc:
        raise H3MediaError("本机未安装 FFprobe") from exc
    except (IndexError, KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise H3MediaError("无法读取 H3 分段视频时长") from exc
    if completed.returncode != 0 or duration <= 0:
        raise H3MediaError("H3 分段视频时长不合法")
    return duration


def _compact_text(value: object) -> str:
    return "".join(str(value or "").split())


def build_segment_cues(
    segment_texts: list[str],
    segment_durations_seconds: list[float],
    *,
    script_text: str,
) -> list[dict[str, int | str]]:
    if (
        not segment_texts
        or len(segment_texts) != len(segment_durations_seconds)
        or any(not str(text or "").strip() for text in segment_texts)
        or any(duration <= 0 for duration in segment_durations_seconds)
    ):
        raise H3MediaError("H3 字幕分段输入不完整")
    if _compact_text("".join(segment_texts)) != _compact_text(script_text):
        raise H3MediaError("H3 分段台词无法重建冻结原稿")
    result: list[dict[str, int | str]] = []
    cursor_us = 0
    for index, (text, duration) in enumerate(
        zip(segment_texts, segment_durations_seconds, strict=True)
    ):
        duration_us = max(1, round(duration * 1_000_000))
        end_us = cursor_us + duration_us
        result.append(
            {
                "text": str(text).strip(),
                "start_us": cursor_us,
                "duration_us": duration_us,
                "end_us": end_us,
                "segment_index": index,
            }
        )
        cursor_us = end_us
    return result


def prepare_h3_media(
    *,
    segment_paths: list[Path],
    segment_texts: list[str],
    script_text: str,
    target_dir: Path,
    segment_audio_paths: list[Path] | None = None,
    segment_audio_offsets_seconds: list[float] | None = None,
) -> H3MediaAssets:
    durations = [_probe_duration(path) for path in segment_paths]
    cues = build_segment_cues(segment_texts, durations, script_text=script_text)
    master, visual_dissolve_seconds = _merge_segments(
        segment_paths,
        durations,
        target_dir / "h3-master-av.mp4",
        dissolve_seconds=H3_VISUAL_DISSOLVE_SECONDS,
    )
    if segment_audio_paths is not None:
        audio = _assemble_clean_audio(segment_audio_paths, durations,
            segment_audio_offsets_seconds or [0.0] * len(durations),
            target_dir / "h3-authoritative-full.wav")
        _atomic_media(
            ["ffmpeg", "-hide_banner", "-nostdin", "-y", "-i", str(master),
             "-i", str(audio), "-map", "0:v:0", "-map", "1:a:0", "-c:v", "copy",
             "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart"],
            master, "封装 H3 清理版权威音频失败")
    else:
        audio = _atomic_media(
            ["ffmpeg", "-hide_banner", "-nostdin", "-y", "-i", str(master),
             "-map", "0:a:0", "-vn", "-c:a", "pcm_s16le"],
            target_dir / "h3-authoritative-full.wav", "抽取 H3 权威音频失败")
    base = _atomic_media(
        [
            "ffmpeg", "-hide_banner", "-nostdin", "-y", "-i", str(master),
            "-map", "0:v:0", "-an", "-c:v", "copy", "-movflags", "+faststart",
        ],
        target_dir / "h3-base-video-silent.mp4",
        "拆分 JYD 静音基础视频失败",
    )
    return H3MediaAssets(
        master_av_path=master,
        silent_base_video_path=base,
        authoritative_audio_path=audio,
        raw_cues=tuple(cues),
        segment_durations_seconds=tuple(durations),
        visual_dissolve_seconds=visual_dissolve_seconds,
    )


def _assemble_clean_audio(paths: list[Path], durations: list[float],
                          offsets: list[float], target: Path) -> Path:
    """Concatenate decoded PCM at video boundaries, never AAC priming packets."""
    if not paths or len(paths) != len(durations) or len(offsets) != len(paths):
        raise H3MediaError("H3 清理音频分段数量不一致")
    with wave.open(str(paths[0]), "rb") as source:
        rate, channels = source.getframerate(), source.getnchannels()
    if channels not in (1, 2):
        raise H3MediaError("H3 清理音频仅支持单声道或双声道")
    layout = "mono" if channels == 1 else "stereo"
    inputs = [arg for path in paths for arg in ("-i", str(path))]
    filters = []
    cursor_seconds, cursor_samples = 0.0, 0
    for index, (duration, offset) in enumerate(zip(durations, offsets, strict=True)):
        cursor_seconds += duration
        end_sample = round(cursor_seconds * rate)
        length = end_sample - cursor_samples
        cursor_samples = end_sample
        offset_samples = round(offset * rate)
        timing = (f"adelay={offset_samples}S:all=1," if offset_samples > 0 else
                  f"atrim=start_sample={-offset_samples},asetpts=PTS-STARTPTS," if offset_samples < 0 else "")
        filters.append(f"[{index}:a:0]aresample={rate},aformat=sample_fmts=s16:channel_layouts={layout},"
            f"{timing}apad=whole_len={length},atrim=end_sample={length},asetpts=PTS-STARTPTS[a{index}]")
    filters.append("".join(f"[a{i}]" for i in range(len(paths))) + f"concat=n={len(paths)}:v=0:a=1[out]")
    return _atomic_media(["ffmpeg", "-hide_banner", "-nostdin", "-y", *inputs,
        "-filter_complex", ";".join(filters), "-map", "[out]", "-ar", str(rate),
        "-ac", str(channels), "-c:a", "pcm_s16le"], target, "合并 H3 清理音频失败")
