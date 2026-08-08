from __future__ import annotations

from dataclasses import dataclass
from difflib import SequenceMatcher
import hashlib
import json
from pathlib import Path
import re
import unicodedata
from typing import Any, Iterable, Mapping
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
import uuid

from .subtitles import caption_cues_from_payload


ASR_ALIGNMENT_SCHEMA = "jyd.asr-caption-alignment.v1"
_TOKEN_RE = re.compile(
    r"[\u3400-\u4dbf\u4e00-\u9fff]|"
    r"[A-Za-z]+(?:'[A-Za-z]+)?|"
    r"\d+(?:\.\d+)?"
)
_MIN_GLOBAL_EXACT_RATIO = 0.90
_MIN_RAW_CUE_EXACT_RATIO = 0.55


class CaptionAlignmentError(ValueError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class ScriptToken:
    index: int
    start: int
    end: int
    text: str
    key: str
    raw_cue_index: int


@dataclass(frozen=True)
class RecognizedToken:
    text: str
    key: str
    start_us: int
    end_us: int


def _key(value: str) -> str:
    return unicodedata.normalize("NFKC", value).casefold()


def _lexical_matches(text: str) -> list[re.Match[str]]:
    return list(_TOKEN_RE.finditer(text))


def _raw_cue_character_ranges(
    script: str,
    raw_cues: Iterable[object],
) -> tuple[list[Any], dict[int, int]]:
    try:
        cues = caption_cues_from_payload(raw_cues)
    except (TypeError, ValueError) as exc:
        raise CaptionAlignmentError("RAW_CUES_INVALID", "MiniMax raw_cues 结构无效") from exc
    if not cues:
        raise CaptionAlignmentError("RAW_CUES_MISSING", "当前音频没有 MiniMax raw_cues")
    script_positions = [
        (position, character)
        for position, character in enumerate(script)
        if not character.isspace()
    ]
    provider_characters = [
        character
        for cue in cues
        for character in cue.text
        if not character.isspace()
    ]
    if provider_characters != [character for _, character in script_positions]:
        raise CaptionAlignmentError(
            "RAW_CUES_TEXT_MISMATCH",
            "MiniMax raw_cues 去除空白后不能逐字符重建当前脚本",
        )
    raw_cue_by_character: dict[int, int] = {}
    cursor = 0
    for raw_cue_index, cue in enumerate(cues):
        for character in cue.text:
            if character.isspace():
                continue
            script_position, expected = script_positions[cursor]
            if character != expected:
                raise CaptionAlignmentError(
                    "RAW_CUES_TEXT_MISMATCH", "MiniMax raw_cues 字符顺序与脚本不一致"
                )
            raw_cue_by_character[script_position] = raw_cue_index
            cursor += 1
    return cues, raw_cue_by_character


def script_tokens(
    script: str,
    raw_cues: Iterable[object],
) -> tuple[list[Any], list[ScriptToken]]:
    cues, raw_cue_by_character = _raw_cue_character_ranges(script, raw_cues)
    tokens: list[ScriptToken] = []
    for index, match in enumerate(_lexical_matches(script)):
        cue_indexes = {
            raw_cue_by_character[position]
            for position in range(match.start(), match.end())
            if position in raw_cue_by_character
        }
        if len(cue_indexes) != 1:
            raise CaptionAlignmentError(
                "SCRIPT_TOKEN_CROSSES_RAW_CUE",
                f"脚本字词 {match.group(0)!r} 跨越 MiniMax raw cue 边界",
            )
        tokens.append(
            ScriptToken(
                index=index,
                start=match.start(),
                end=match.end(),
                text=match.group(0),
                key=_key(match.group(0)),
                raw_cue_index=next(iter(cue_indexes)),
            )
        )
    if not tokens:
        raise CaptionAlignmentError("SCRIPT_TOKENS_MISSING", "脚本没有可对齐的字词")
    return cues, tokens


def _recognized_tokens(payload: Mapping[str, Any]) -> list[RecognizedToken]:
    raw_tokens = payload.get("tokens")
    if not isinstance(raw_tokens, list) or not raw_tokens:
        raise CaptionAlignmentError("ASR_TIMESTAMPS_MISSING", "FunASR 没有返回字词时间戳")
    result: list[RecognizedToken] = []
    previous_start = -1
    for position, raw_token in enumerate(raw_tokens, start=1):
        if not isinstance(raw_token, Mapping):
            raise CaptionAlignmentError("ASR_RESPONSE_INVALID", "FunASR token 结构无效")
        text = str(raw_token.get("text") or "")
        try:
            start_us = round(float(raw_token.get("startSeconds")) * 1_000_000)
            end_us = round(float(raw_token.get("endSeconds")) * 1_000_000)
        except (TypeError, ValueError) as exc:
            raise CaptionAlignmentError(
                "ASR_RESPONSE_INVALID", f"FunASR 第 {position} 个时间戳无效"
            ) from exc
        if not text or start_us < 0 or end_us <= start_us or start_us < previous_start:
            raise CaptionAlignmentError(
                "ASR_RESPONSE_INVALID", f"FunASR 第 {position} 个 token 无效"
            )
        result.append(RecognizedToken(text, _key(text), start_us, end_us))
        previous_start = start_us
    return result


def _exact_matches(
    expected: list[ScriptToken], recognized: list[RecognizedToken]
) -> dict[int, RecognizedToken]:
    matcher = SequenceMatcher(
        a=[token.key for token in expected],
        b=[token.key for token in recognized],
        autojunk=False,
    )
    mapped: dict[int, RecognizedToken] = {}
    for block in matcher.get_matching_blocks():
        for offset in range(block.size):
            mapped[block.a + offset] = recognized[block.b + offset]
    return mapped


def _interpolated_range(
    token_index: int,
    cue_token_indexes: list[int],
    exact: Mapping[int, RecognizedToken],
    cue_start_us: int,
    cue_end_us: int,
) -> tuple[int, int]:
    previous_exact = next(
        (index for index in reversed(cue_token_indexes) if index < token_index and index in exact),
        None,
    )
    next_exact = next(
        (index for index in cue_token_indexes if index > token_index and index in exact),
        None,
    )
    if previous_exact is None and next_exact is None:
        raise CaptionAlignmentError(
            "ASR_RAW_CUE_UNMATCHED", "FunASR 在一个 MiniMax raw cue 内没有任何可靠命中"
        )
    left_index = previous_exact if previous_exact is not None else cue_token_indexes[0] - 1
    right_index = next_exact if next_exact is not None else cue_token_indexes[-1] + 1
    left_us = exact[previous_exact].end_us if previous_exact is not None else cue_start_us
    right_us = exact[next_exact].start_us if next_exact is not None else cue_end_us
    slots = right_index - left_index
    slot = token_index - left_index
    start_us = left_us + round((right_us - left_us) * (slot - 1) / slots)
    end_us = left_us + round((right_us - left_us) * slot / slots)
    return start_us, end_us


def build_alignment(
    script: str,
    raw_cues: Iterable[object],
    asr_payload: Mapping[str, Any],
    *,
    audio_asset_id: str,
    audio_version: object,
) -> dict[str, Any]:
    cues, expected = script_tokens(script, raw_cues)
    recognized = _recognized_tokens(asr_payload)
    exact = _exact_matches(expected, recognized)
    exact_ratio = len(exact) / len(expected)
    if exact_ratio < _MIN_GLOBAL_EXACT_RATIO:
        raise CaptionAlignmentError(
            "ASR_SCRIPT_MATCH_TOO_LOW",
            f"FunASR 与原脚本精确命中率仅 {exact_ratio:.1%}，拒绝生成精确字幕",
        )

    by_cue: dict[int, list[int]] = {}
    for token in expected:
        by_cue.setdefault(token.raw_cue_index, []).append(token.index)
    for cue_index, indexes in by_cue.items():
        cue_ratio = sum(index in exact for index in indexes) / len(indexes)
        if cue_ratio < _MIN_RAW_CUE_EXACT_RATIO:
            raise CaptionAlignmentError(
                "ASR_RAW_CUE_MATCH_TOO_LOW",
                f"FunASR 在第 {cue_index + 1} 个 MiniMax raw cue 内命中率过低",
            )

    ranges: list[dict[str, Any]] = []
    for token in expected:
        cue = cues[token.raw_cue_index]
        if token.index in exact:
            recognized_token = exact[token.index]
            start_us = recognized_token.start_us
            end_us = recognized_token.end_us
            method = "asr_exact"
        else:
            start_us, end_us = _interpolated_range(
                token.index,
                by_cue[token.raw_cue_index],
                exact,
                cue.start_us,
                cue.end_us,
            )
            method = "asr_interpolated"
        start_us = max(cue.start_us, min(start_us, cue.end_us - 1))
        end_us = max(start_us + 1, min(end_us, cue.end_us))
        ranges.append(
            {
                "token_index": token.index,
                "start": token.start,
                "end": token.end,
                "start_us": start_us,
                "end_us": end_us,
                "raw_cue_index": token.raw_cue_index,
                "method": method,
            }
        )

    return {
        "schema": ASR_ALIGNMENT_SCHEMA,
        "status": "SUCCESS",
        "script_sha256": hashlib.sha256(script.encode("utf-8")).hexdigest(),
        "audio_asset_id": str(audio_asset_id),
        "audio_version": audio_version,
        "provider": "funasr_http",
        "model": str(asr_payload.get("model") or ""),
        "device": str(asr_payload.get("device") or ""),
        "processing_seconds": asr_payload.get("processingSeconds"),
        "script_token_count": len(expected),
        "recognized_token_count": len(recognized),
        "exact_match_count": len(exact),
        "exact_match_ratio": round(exact_ratio, 6),
        "ranges": ranges,
    }


def alignment_matches(
    alignment: object,
    *,
    script: str,
    audio_asset_id: str,
    audio_version: object,
) -> bool:
    return bool(
        isinstance(alignment, Mapping)
        and alignment.get("schema") == ASR_ALIGNMENT_SCHEMA
        and alignment.get("status") == "SUCCESS"
        and alignment.get("script_sha256")
        == hashlib.sha256(script.encode("utf-8")).hexdigest()
        and str(alignment.get("audio_asset_id") or "") == str(audio_asset_id)
        and alignment.get("audio_version") == audio_version
        and isinstance(alignment.get("ranges"), list)
        and alignment.get("ranges")
    )


def retime_render_cues(
    script: str,
    raw_cues: Iterable[object],
    render_cues: Iterable[Mapping[str, Any]],
    alignment: Mapping[str, Any],
) -> list[dict[str, int | str]]:
    _, expected = script_tokens(script, raw_cues)
    raw_ranges = alignment.get("ranges")
    if not isinstance(raw_ranges, list):
        raise CaptionAlignmentError("ASR_ALIGNMENT_INVALID", "ASR 对齐缓存缺少 ranges")
    ranges = {
        int(entry["token_index"]): entry
        for entry in raw_ranges
        if isinstance(entry, Mapping) and "token_index" in entry
    }
    if len(ranges) != len(expected):
        raise CaptionAlignmentError("ASR_ALIGNMENT_INVALID", "ASR 对齐缓存不完整")

    result: list[dict[str, int | str]] = []
    token_cursor = 0
    for cue in render_cues:
        text = str(cue.get("text") or "")
        keys = [_key(match.group(0)) for match in _lexical_matches(text)]
        if not keys:
            raise CaptionAlignmentError("RENDER_CUE_TEXT_EMPTY", "最终字幕没有可对齐字词")
        expected_keys = [token.key for token in expected[token_cursor : token_cursor + len(keys)]]
        if keys != expected_keys:
            raise CaptionAlignmentError(
                "RENDER_CUE_SCRIPT_MISMATCH", "最终字幕不能按顺序重建原脚本字词"
            )
        first = ranges[token_cursor]
        last = ranges[token_cursor + len(keys) - 1]
        if first.get("raw_cue_index") != last.get("raw_cue_index"):
            raise CaptionAlignmentError(
                "RENDER_CUE_CROSSES_RAW_CUE", "最终字幕跨越 MiniMax raw cue 硬边界"
            )
        result.append(
            {
                "text": text,
                "start_us": int(first["start_us"]),
                "duration_us": int(last["end_us"]) - int(first["start_us"]),
                "_raw_cue_index": int(first["raw_cue_index"]),
            }
        )
        token_cursor += len(keys)
    if token_cursor != len(expected):
        raise CaptionAlignmentError(
            "RENDER_CUES_INCOMPLETE", "最终字幕没有完整覆盖原脚本字词"
        )

    for index in range(len(result) - 1):
        left = result[index]
        right = result[index + 1]
        if left["_raw_cue_index"] != right["_raw_cue_index"]:
            continue
        left_end = int(left["start_us"]) + int(left["duration_us"])
        right_start = int(right["start_us"])
        boundary = round((left_end + right_start) / 2)
        boundary = max(int(left["start_us"]) + 1, boundary)
        right_end = int(right["start_us"]) + int(right["duration_us"])
        boundary = min(right_end - 1, boundary)
        left["duration_us"] = boundary - int(left["start_us"])
        right["duration_us"] = right_end - boundary
        right["start_us"] = boundary

    return [
        {
            "text": str(cue["text"]),
            "start_us": int(cue["start_us"]),
            "duration_us": int(cue["duration_us"]),
        }
        for cue in result
    ]


class FunASRCaptionAligner:
    def __init__(
        self,
        base_url: str,
        *,
        timeout_seconds: int = 1800,
        shared_token: str = "",
    ) -> None:
        self.base_url = str(base_url or "").strip().rstrip("/")
        self.timeout_seconds = max(1, int(timeout_seconds))
        self.shared_token = str(shared_token or "").strip()

    def align(
        self,
        audio_path: str | Path,
        *,
        script: str,
        raw_cues: Iterable[object],
        audio_asset_id: str,
        audio_version: object,
    ) -> dict[str, Any]:
        path = Path(audio_path).expanduser().resolve()
        if not path.is_file():
            raise CaptionAlignmentError("ASR_AUDIO_MISSING", f"ASR 音频不存在：{path}")
        if not self.base_url:
            raise CaptionAlignmentError("ASR_NOT_CONFIGURED", "本地精确字幕服务未配置")
        boundary = f"jyd-{uuid.uuid4().hex}"
        filename = path.name.replace('"', "")
        body = (
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="audio"; filename="{filename}"\r\n'
            "Content-Type: application/octet-stream\r\n\r\n"
        ).encode("utf-8") + path.read_bytes() + f"\r\n--{boundary}--\r\n".encode("ascii")
        headers = {"Content-Type": f"multipart/form-data; boundary={boundary}"}
        if self.shared_token:
            headers["Authorization"] = f"Bearer {self.shared_token}"
        request = Request(
            f"{self.base_url}/v1/transcribe",
            data=body,
            headers=headers,
            method="POST",
        )
        try:
            with urlopen(request, timeout=self.timeout_seconds) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")[:500]
            raise CaptionAlignmentError(
                "ASR_HTTP_ERROR", f"本地精确字幕服务返回 HTTP {exc.code}：{detail}"
            ) from exc
        except (URLError, TimeoutError, OSError) as exc:
            raise CaptionAlignmentError(
                "ASR_UNAVAILABLE", f"无法调用本地精确字幕服务：{exc}"
            ) from exc
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise CaptionAlignmentError("ASR_RESPONSE_INVALID", "FunASR 返回内容不是合法 JSON") from exc
        if not isinstance(payload, Mapping):
            raise CaptionAlignmentError("ASR_RESPONSE_INVALID", "FunASR 返回结构无效")
        return build_alignment(
            script,
            raw_cues,
            payload,
            audio_asset_id=audio_asset_id,
            audio_version=audio_version,
        )
