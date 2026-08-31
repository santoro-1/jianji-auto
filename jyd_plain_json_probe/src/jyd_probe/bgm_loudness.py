from __future__ import annotations

from functools import lru_cache
import json
import logging
import math
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
from typing import Any


LOGGER = logging.getLogger(__name__)

BGM_TARGET_GAP_DB = 11.0
BGM_STRONG_VOCAL_EXTRA_GAP_DB = 4.0
BGM_MIN_GAIN_DB = -30.0
BGM_MAX_GAIN_DB = 6.0
BGM_TRUE_PEAK_CEILING_DBTP = -6.0
BGM_MIN_SHORT_TERM_GAP_DB = 7.0
BGM_STRONG_VOCAL_MIN_SHORT_TERM_GAP_DB = 10.0
BGM_FALLBACK_GAIN_DB = -10.0
BGM_STRONG_VOCAL_FALLBACK_GAIN_DB = -14.0
BGM_FALLBACK_VOLUME = round(math.pow(10.0, BGM_FALLBACK_GAIN_DB / 20.0), 4)
BGM_STRONG_VOCAL_FALLBACK_VOLUME = round(
    math.pow(10.0, BGM_STRONG_VOCAL_FALLBACK_GAIN_DB / 20.0), 4
)
BGM_MIN_VOLUME = math.pow(10.0, BGM_MIN_GAIN_DB / 20.0)
BGM_MAX_VOLUME = math.pow(10.0, BGM_MAX_GAIN_DB / 20.0)
BGM_STRONG_VOCAL_MIN_VOLUME = BGM_MIN_VOLUME
BGM_STRONG_VOCAL_MAX_VOLUME = BGM_MAX_VOLUME
BGM_VOLUME_ALGORITHM = "speech-relative-program-lufs.v2"
BGM_MAX_FADE_IN_US = 1_500_000
BGM_FADE_IN_RATIO = 0.1
BGM_DEFAULT_CROSSFADE_US = 200_000


def volume_from_loudness(
    voice_lufs: float,
    bgm_lufs: float,
    *,
    target_gap_db: float = BGM_TARGET_GAP_DB,
    minimum_volume: float = BGM_MIN_VOLUME,
    maximum_volume: float = BGM_MAX_VOLUME,
) -> float:
    """Return a broadly bounded linear BGM gain relative to narration loudness."""

    desired_bgm_lufs = float(voice_lufs) - float(target_gap_db)
    gain_db = desired_bgm_lufs - float(bgm_lufs)
    volume = math.pow(10.0, gain_db / 20.0)
    return round(max(float(minimum_volume), min(float(maximum_volume), volume)), 4)


def fallback_bgm_volume(*, strong_vocals: bool = False) -> float:
    return (
        BGM_STRONG_VOCAL_FALLBACK_VOLUME
        if strong_vocals
        else BGM_FALLBACK_VOLUME
    )


def recommended_bgm_fade_in_us(video_duration_us: int) -> int:
    duration_us = max(0, int(video_duration_us or 0))
    return min(BGM_MAX_FADE_IN_US, int(round(duration_us * BGM_FADE_IN_RATIO)))


def _ffmpeg_path() -> str | None:
    configured = str(os.environ.get("JYD_FFMPEG") or "").strip()
    if configured and Path(configured).expanduser().is_file():
        return str(Path(configured).expanduser().resolve())
    discovered = shutil.which("ffmpeg")
    if discovered:
        return str(Path(discovered).resolve())
    executable_root = Path(sys.executable).resolve().parent
    project_root = Path(__file__).resolve().parents[2]
    candidates = (
        executable_root / "ffmpeg" / "bin" / "ffmpeg.exe",
        executable_root.parent / "ffmpeg" / "bin" / "ffmpeg.exe",
        project_root / "ffmpeg" / "bin" / "ffmpeg.exe",
        Path.cwd() / "ffmpeg" / "bin" / "ffmpeg.exe",
    )
    return next((str(path.resolve()) for path in candidates if path.is_file()), None)


def _ffprobe_path() -> str | None:
    configured = str(os.environ.get("JYD_FFPROBE") or "").strip()
    if configured and Path(configured).expanduser().is_file():
        return str(Path(configured).expanduser().resolve())
    discovered = shutil.which("ffprobe")
    if discovered:
        return str(Path(discovered).resolve())
    ffmpeg_path = _ffmpeg_path()
    if not ffmpeg_path:
        return None
    candidate = Path(ffmpeg_path).with_name(
        "ffprobe.exe" if Path(ffmpeg_path).suffix.lower() == ".exe" else "ffprobe"
    )
    return str(candidate.resolve()) if candidate.is_file() else None


def _loudnorm_metrics(stderr: str) -> tuple[float, float, float]:
    matches = re.findall(r"\{\s*\"input_i\".*?\}", stderr or "", re.DOTALL)
    if not matches:
        raise ValueError("FFmpeg 未返回响度分析结果")
    payload = json.loads(matches[-1])
    integrated_lufs = float(payload["input_i"])
    true_peak_dbtp = float(payload["input_tp"])
    loudness_range_lu = float(payload.get("input_lra") or 0.0)
    if not math.isfinite(integrated_lufs) or not math.isfinite(true_peak_dbtp):
        raise ValueError("音频响度或真峰值不是有限数值")
    return integrated_lufs, true_peak_dbtp, loudness_range_lu


@lru_cache(maxsize=512)
def _measure_audio_loudness_cached(
    resolved_path: str,
    size_bytes: int,
    modified_ns: int,
    ffmpeg_path: str,
) -> tuple[float, float, float]:
    _ = (size_bytes, modified_ns)
    completed = subprocess.run(
        [
            ffmpeg_path,
            "-hide_banner",
            "-nostats",
            "-i",
            resolved_path,
            "-vn",
            "-sn",
            "-dn",
            "-af",
            "loudnorm=I=-24:TP=-2:LRA=11:print_format=json",
            "-f",
            "null",
            os.devnull,
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=120,
        check=False,
    )
    return _loudnorm_metrics(completed.stderr or "")


def measure_audio_loudness(path: str | Path) -> dict[str, float]:
    media_path = Path(path).expanduser().resolve()
    if not media_path.is_file():
        raise ValueError(f"音频文件不存在：{media_path}")
    ffmpeg_path = _ffmpeg_path()
    if not ffmpeg_path:
        raise ValueError("未找到 FFmpeg，无法分析音频响度")
    stat = media_path.stat()
    integrated_lufs, true_peak_dbtp, loudness_range_lu = _measure_audio_loudness_cached(
        str(media_path), stat.st_size, stat.st_mtime_ns, ffmpeg_path
    )
    return {
        "integrated_lufs": integrated_lufs,
        "true_peak_dbtp": true_peak_dbtp,
        "loudness_range_lu": loudness_range_lu,
    }


def measure_integrated_lufs(path: str | Path) -> float:
    return float(measure_audio_loudness(path)["integrated_lufs"])


@lru_cache(maxsize=512)
def _probe_audio_duration_us_cached(
    resolved_path: str,
    size_bytes: int,
    modified_ns: int,
    ffprobe_path: str,
) -> int:
    _ = (size_bytes, modified_ns)
    completed = subprocess.run(
        [
            ffprobe_path,
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            resolved_path,
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=30,
        check=False,
    )
    if completed.returncode != 0:
        raise ValueError("FFprobe 无法读取 BGM 时长")
    duration_seconds = float((completed.stdout or "").strip())
    duration_us = int(round(duration_seconds * 1_000_000))
    if duration_us <= 0:
        raise ValueError("BGM 时长无效")
    return duration_us


def probe_audio_duration_us(path: str | Path) -> int:
    media_path = Path(path).expanduser().resolve()
    if not media_path.is_file():
        raise ValueError(f"音频文件不存在：{media_path}")
    ffprobe_path = _ffprobe_path()
    if not ffprobe_path:
        raise ValueError("未找到 FFprobe，无法读取 BGM 时长")
    stat = media_path.stat()
    return _probe_audio_duration_us_cached(
        str(media_path), stat.st_size, stat.st_mtime_ns, ffprobe_path
    )


def build_backtimed_bgm_plan(
    video_duration_us: int,
    bgm_duration_us: int,
    *,
    crossfade_us: int = BGM_DEFAULT_CROSSFADE_US,
    fade_in_us: int = 0,
) -> list[dict[str, int]]:
    target_duration = max(0, int(video_duration_us or 0))
    loop_duration = max(0, int(bgm_duration_us or 0))
    if target_duration <= 0 or loop_duration <= 0:
        raise ValueError("视频和 BGM 时长必须大于 0")
    crossfade = min(max(0, int(crossfade_us or 0)), loop_duration // 4)
    stride = max(1, loop_duration - crossfade)
    relative_start = target_duration - loop_duration
    planned: list[tuple[int, int, int]] = []
    while True:
        trimmed_source = max(0, -relative_start)
        target_start = max(0, relative_start)
        duration = loop_duration - trimmed_source
        if duration > 0:
            planned.append((target_start, trimmed_source, duration))
        if relative_start <= 0:
            break
        if len(planned) >= 10_000:
            raise ValueError("BGM 过短，无法安全规划循环时间线")
        relative_start -= stride
    planned.sort(key=lambda entry: entry[0])
    result: list[dict[str, int]] = []
    for index, (target_start, source_start, duration) in enumerate(planned):
        result.append(
            {
                "target_start_us": target_start,
                "source_start_us": source_start,
                "duration_us": duration,
                "fade_in_us": (
                    min(crossfade, duration // 2)
                    if index > 0
                    else min(max(0, int(fade_in_us or 0)), duration)
                ),
                "fade_out_us": (
                    min(crossfade, duration // 2)
                    if index < len(planned) - 1
                    else 0
                ),
            }
        )
    return result


def _seconds(value_us: int) -> str:
    return f"{max(0, int(value_us)) / 1_000_000:.6f}"


def _program_filter_graph(
    plan: list[dict[str, int]],
    *,
    video_duration_us: int,
) -> str:
    if not plan:
        raise ValueError("BGM 播放计划为空")
    filters: list[str] = []
    input_label = "bgm_input"
    filters.append(
        "[0:a]aresample=48000,"
        "aformat=sample_fmts=fltp:sample_rates=48000:channel_layouts=stereo"
        f"[{input_label}]"
    )
    labels = [f"bgm_{index}" for index in range(len(plan))]
    if len(plan) > 1:
        filters.append(
            f"[{input_label}]asplit={len(plan)}"
            + "".join(f"[{label}]" for label in labels)
        )
    else:
        labels = [input_label]
    mixed_labels: list[str] = []
    for index, entry in enumerate(plan):
        chain = (
            f"[{labels[index]}]atrim=start={_seconds(entry['source_start_us'])}:"
            f"duration={_seconds(entry['duration_us'])},asetpts=PTS-STARTPTS"
        )
        fade_in_us = int(entry.get("fade_in_us") or 0)
        fade_out_us = int(entry.get("fade_out_us") or 0)
        if fade_in_us > 0:
            chain += f",afade=t=in:st=0:d={_seconds(fade_in_us)}"
        if fade_out_us > 0:
            fade_out_start = max(0, int(entry["duration_us"]) - fade_out_us)
            chain += (
                f",afade=t=out:st={_seconds(fade_out_start)}:"
                f"d={_seconds(fade_out_us)}"
            )
        target_start_us = int(entry.get("target_start_us") or 0)
        if target_start_us > 0:
            delay_samples = int(round(target_start_us * 48_000 / 1_000_000))
            chain += f",adelay={delay_samples}S:all=1"
        output_label = f"program_{index}"
        filters.append(f"{chain}[{output_label}]")
        mixed_labels.append(output_label)
    if len(mixed_labels) > 1:
        filters.append(
            "".join(f"[{label}]" for label in mixed_labels)
            + f"amix=inputs={len(mixed_labels)}:normalize=0:dropout_transition=0"
            + f",atrim=duration={_seconds(video_duration_us)},asetpts=PTS-STARTPTS"
            + "[program]"
        )
    else:
        filters.append(
            f"[{mixed_labels[0]}]atrim=duration={_seconds(video_duration_us)},"
            "asetpts=PTS-STARTPTS[program]"
        )
    filters.extend(
        [
            "[program]asplit=2[loudnorm_input][ebur_input]",
            "[loudnorm_input]loudnorm=I=-24:TP=-2:LRA=11:print_format=json[loudnorm_out]",
            "[ebur_input]ebur128=peak=true[ebur_out]",
        ]
    )
    return ";".join(filters)


def _percentile(values: list[float], percentile: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    position = (len(ordered) - 1) * max(0.0, min(1.0, percentile))
    lower = int(math.floor(position))
    upper = int(math.ceil(position))
    if lower == upper:
        return ordered[lower]
    fraction = position - lower
    return ordered[lower] * (1.0 - fraction) + ordered[upper] * fraction


def _program_short_term_stats(
    stderr: str,
    *,
    video_duration_us: int,
) -> tuple[float | None, float]:
    rows = re.findall(
        r"t:\s*([0-9.]+).*?\bM:\s*(-?[0-9.]+)\s+S:\s*(-?[0-9.]+)",
        stderr or "",
    )
    duration_seconds = video_duration_us / 1_000_000
    use_short_term = duration_seconds >= 3.0
    warmup_seconds = 3.0 if use_short_term else min(0.4, duration_seconds / 2)
    samples: list[float] = []
    valid: list[float] = []
    for timestamp, momentary, short_term in rows:
        if float(timestamp) + 1e-6 < warmup_seconds:
            continue
        value = float(short_term if use_short_term else momentary)
        samples.append(value)
        if value > -70.0 and math.isfinite(value):
            valid.append(value)
    silence_ratio = (
        1.0 - (len(valid) / len(samples)) if samples else 1.0
    )
    return _percentile(valid, 0.95), silence_ratio


@lru_cache(maxsize=512)
def _measure_bgm_program_loudness_cached(
    resolved_path: str,
    size_bytes: int,
    modified_ns: int,
    bgm_duration_us: int,
    video_duration_us: int,
    crossfade_us: int,
    fade_in_us: int,
    ffmpeg_path: str,
) -> tuple[float, float, float, float]:
    _ = (size_bytes, modified_ns)
    plan = build_backtimed_bgm_plan(
        video_duration_us,
        bgm_duration_us,
        crossfade_us=crossfade_us,
        fade_in_us=fade_in_us,
    )
    completed = subprocess.run(
        [
            ffmpeg_path,
            "-hide_banner",
            "-nostats",
            "-i",
            resolved_path,
            "-vn",
            "-sn",
            "-dn",
            "-filter_complex",
            _program_filter_graph(plan, video_duration_us=video_duration_us),
            "-map",
            "[loudnorm_out]",
            "-map",
            "[ebur_out]",
            "-f",
            "null",
            os.devnull,
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=180,
        check=False,
    )
    integrated_lufs, true_peak_dbtp, _ = _loudnorm_metrics(completed.stderr or "")
    short_term_p95_lufs, silence_ratio = _program_short_term_stats(
        completed.stderr or "", video_duration_us=video_duration_us
    )
    return (
        integrated_lufs,
        true_peak_dbtp,
        short_term_p95_lufs if short_term_p95_lufs is not None else math.nan,
        silence_ratio,
    )


def measure_bgm_program_loudness(
    path: str | Path,
    *,
    video_duration_us: int,
    crossfade_us: int = BGM_DEFAULT_CROSSFADE_US,
    fade_in_us: int = 0,
) -> dict[str, Any]:
    media_path = Path(path).expanduser().resolve()
    if not media_path.is_file():
        raise ValueError(f"BGM 文件不存在：{media_path}")
    if int(video_duration_us or 0) <= 0:
        raise ValueError("视频时长不可用，无法测量实际 BGM 播放区间")
    ffmpeg_path = _ffmpeg_path()
    if not ffmpeg_path:
        raise ValueError("未找到 FFmpeg，无法分析实际 BGM 时间线")
    bgm_duration_us = probe_audio_duration_us(media_path)
    effective_fade_in_us = min(
        max(0, int(fade_in_us or 0)), int(video_duration_us)
    )
    stat = media_path.stat()
    integrated_lufs, true_peak_dbtp, short_term_p95_lufs, silence_ratio = (
        _measure_bgm_program_loudness_cached(
            str(media_path),
            stat.st_size,
            stat.st_mtime_ns,
            bgm_duration_us,
            int(video_duration_us),
            max(0, int(crossfade_us or 0)),
            effective_fade_in_us,
            ffmpeg_path,
        )
    )
    plan = build_backtimed_bgm_plan(
        int(video_duration_us),
        bgm_duration_us,
        crossfade_us=crossfade_us,
        fade_in_us=effective_fade_in_us,
    )
    return {
        "integrated_lufs": integrated_lufs,
        "true_peak_dbtp": true_peak_dbtp,
        "short_term_p95_lufs": (
            short_term_p95_lufs if math.isfinite(short_term_p95_lufs) else None
        ),
        "silence_ratio": silence_ratio,
        "bgm_duration_us": bgm_duration_us,
        "video_duration_us": int(video_duration_us),
        "crossfade_us": max(0, int(crossfade_us or 0)),
        "fade_in_us": effective_fade_in_us,
        "segments": plan,
    }


def _gain_snapshot(
    *,
    voice_lufs: float,
    program_lufs: float,
    program_true_peak_dbtp: float,
    program_short_term_p95_lufs: float | None,
    silence_ratio: float,
    target_gap_db: float,
    minimum_short_term_gap_db: float,
) -> dict[str, Any]:
    desired_program_lufs = float(voice_lufs) - float(target_gap_db)
    raw_gain_db = desired_program_lufs - float(program_lufs)
    true_peak_limit_gain_db = (
        BGM_TRUE_PEAK_CEILING_DBTP - float(program_true_peak_dbtp)
    )
    limits = [raw_gain_db, BGM_MAX_GAIN_DB, true_peak_limit_gain_db]
    short_term_limit_gain_db: float | None = None
    if (
        program_short_term_p95_lufs is not None
        and math.isfinite(float(program_short_term_p95_lufs))
    ):
        short_term_limit_gain_db = (
            float(voice_lufs)
            - float(minimum_short_term_gap_db)
            - float(program_short_term_p95_lufs)
        )
        limits.append(short_term_limit_gain_db)
    limited_gain_db = min(limits)
    applied_gain_db = max(BGM_MIN_GAIN_DB, limited_gain_db)
    constraints_hit: list[str] = []
    if BGM_MAX_GAIN_DB < raw_gain_db - 1e-6:
        constraints_hit.append("maximum_gain")
    if true_peak_limit_gain_db < raw_gain_db - 1e-6:
        constraints_hit.append("true_peak")
    if (
        short_term_limit_gain_db is not None
        and short_term_limit_gain_db < raw_gain_db - 1e-6
    ):
        constraints_hit.append("short_term_loudness")
    if applied_gain_db > limited_gain_db + 1e-6:
        constraints_hit.append("minimum_gain")
    quiet_reasons: list[str] = []
    if float(program_lufs) < -40.0:
        quiet_reasons.append("program_lufs_below_-40")
    if float(silence_ratio) > 0.5:
        quiet_reasons.append("program_silence_ratio_above_50pct")
    if raw_gain_db > BGM_MAX_GAIN_DB:
        quiet_reasons.append("required_gain_above_+6db")
    return {
        "desired_program_lufs": round(desired_program_lufs, 2),
        "raw_gain_db": round(raw_gain_db, 2),
        "applied_gain_db": round(applied_gain_db, 2),
        "volume": round(math.pow(10.0, applied_gain_db / 20.0), 4),
        "post_gain_program_lufs": round(program_lufs + applied_gain_db, 2),
        "post_gain_true_peak_dbtp": round(
            program_true_peak_dbtp + applied_gain_db, 2
        ),
        "achieved_gap_db": round(voice_lufs - (program_lufs + applied_gain_db), 2),
        "true_peak_limit_gain_db": round(true_peak_limit_gain_db, 2),
        "short_term_limit_gain_db": (
            round(short_term_limit_gain_db, 2)
            if short_term_limit_gain_db is not None
            else None
        ),
        "constraints_hit": constraints_hit,
        "quiet_program": bool(quiet_reasons),
        "quiet_program_reasons": quiet_reasons,
    }


def automatic_bgm_mix(
    voice_path: str | Path,
    bgm_path: str | Path,
    *,
    strong_vocals: bool = False,
    video_duration_us: int = 0,
    crossfade_us: int = BGM_DEFAULT_CROSSFADE_US,
    fade_in_us: int | None = None,
) -> dict[str, Any]:
    """Measure the exact BGM program and return one preview/export snapshot."""

    target_gap_db = BGM_TARGET_GAP_DB + (
        BGM_STRONG_VOCAL_EXTRA_GAP_DB if strong_vocals else 0.0
    )
    minimum_short_term_gap_db = (
        BGM_STRONG_VOCAL_MIN_SHORT_TERM_GAP_DB
        if strong_vocals
        else BGM_MIN_SHORT_TERM_GAP_DB
    )
    effective_fade_in_us = (
        recommended_bgm_fade_in_us(video_duration_us)
        if fade_in_us is None
        else max(0, int(fade_in_us))
    )
    try:
        voice = measure_audio_loudness(voice_path)
        source_bgm = measure_audio_loudness(bgm_path)
        program = measure_bgm_program_loudness(
            bgm_path,
            video_duration_us=int(video_duration_us),
            crossfade_us=crossfade_us,
            fade_in_us=effective_fade_in_us,
        )
        gain = _gain_snapshot(
            voice_lufs=float(voice["integrated_lufs"]),
            program_lufs=float(program["integrated_lufs"]),
            program_true_peak_dbtp=float(program["true_peak_dbtp"]),
            program_short_term_p95_lufs=program.get("short_term_p95_lufs"),
            silence_ratio=float(program.get("silence_ratio") or 0.0),
            target_gap_db=target_gap_db,
            minimum_short_term_gap_db=minimum_short_term_gap_db,
        )
        return {
            "algorithm": BGM_VOLUME_ALGORITHM,
            **gain,
            "voice_lufs": round(float(voice["integrated_lufs"]), 2),
            "voice_true_peak_dbtp": round(float(voice["true_peak_dbtp"]), 2),
            "bgm_source_lufs": round(float(source_bgm["integrated_lufs"]), 2),
            "bgm_source_true_peak_dbtp": round(
                float(source_bgm["true_peak_dbtp"]), 2
            ),
            "bgm_program_lufs": round(float(program["integrated_lufs"]), 2),
            "bgm_program_true_peak_dbtp": round(
                float(program["true_peak_dbtp"]), 2
            ),
            "bgm_program_short_term_p95_lufs": (
                round(float(program["short_term_p95_lufs"]), 2)
                if program.get("short_term_p95_lufs") is not None
                else None
            ),
            "bgm_program_silence_ratio": round(
                float(program.get("silence_ratio") or 0.0), 4
            ),
            "program": {
                key: value
                for key, value in program.items()
                if key
                in {
                    "bgm_duration_us",
                    "video_duration_us",
                    "crossfade_us",
                    "fade_in_us",
                    "segments",
                }
            },
            "crossfade_us": int(program["crossfade_us"]),
            "fade_in_us": int(program["fade_in_us"]),
            "target_gap_db": target_gap_db,
            "minimum_short_term_gap_db": minimum_short_term_gap_db,
            "strong_vocals": strong_vocals,
            "fallback": False,
        }
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        LOGGER.warning("BGM 响度分析失败，使用保守自动音量：%s", exc)
        return {
            "algorithm": BGM_VOLUME_ALGORITHM,
            "volume": fallback_bgm_volume(strong_vocals=strong_vocals),
            "applied_gain_db": (
                BGM_STRONG_VOCAL_FALLBACK_GAIN_DB
                if strong_vocals
                else BGM_FALLBACK_GAIN_DB
            ),
            "target_gap_db": target_gap_db,
            "minimum_short_term_gap_db": minimum_short_term_gap_db,
            "crossfade_us": max(0, int(crossfade_us or 0)),
            "fade_in_us": effective_fade_in_us,
            "strong_vocals": strong_vocals,
            "fallback": True,
            "constraints_hit": ["analysis_fallback"],
            "reason": str(exc)[:300],
        }
