"""Keep local media references within the Windows editor's path budget."""

from __future__ import annotations

import base64
import hashlib
import os
from pathlib import Path
import shutil
from typing import Any, Iterator
import uuid


# Leave room below the legacy MAX_PATH boundary. Python/FFmpeg accepting a
# source path does not imply that Jianying's file/thumbnail APIs can open it.
MAX_EDITOR_MEDIA_PATH_UNITS = 240
LOCAL_MEDIA_DIRECTORY = "jyd_media"
LOCAL_MEDIA_TOKEN_LENGTH = 24


def _path_units(path: str | Path) -> int:
    return len(str(path).encode("utf-16-le")) // 2


def _sha256(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def _media_token(digest: str) -> str:
    raw = bytes.fromhex(digest)
    if len(raw) != 32:
        raise ValueError("草稿素材摘要格式无效")
    return (
        base64.b32encode(raw).decode("ascii").rstrip("=").lower()
        [:LOCAL_MEDIA_TOKEN_LENGTH]
    )


def _media_materials(value: Any) -> Iterator[dict[str, Any]]:
    """Include embedded subdrafts, without rewriting arbitrary path strings."""
    if isinstance(value, dict):
        materials = value.get("materials")
        if isinstance(materials, dict):
            for category in ("videos", "audios"):
                entries = materials.get(category)
                if isinstance(entries, list):
                    yield from (entry for entry in entries if isinstance(entry, dict))
        for child in value.values():
            yield from _media_materials(child)
    elif isinstance(value, list):
        for child in value:
            yield from _media_materials(child)


def localize_long_media_paths(data: dict[str, Any], draft_dir: Path) -> int:
    """Copy overlong local media into a new output draft, then update references.

    Only media paths change: identities, names, clocks, volume and transitions
    remain intact. Short content tokens isolate same-name clips and regenerated
    versions; complete hashes are still verified from file bytes. Originals are
    never moved, linked or overwritten. The caller must save the JSON only after
    this function succeeds.
    """
    media_root = draft_dir.resolve() / LOCAL_MEDIA_DIRECTORY
    replacements: list[tuple[dict[str, Any], str]] = []
    copied: dict[Path, Path] = {}
    for material in _media_materials(data):
        value = material.get("path")
        if not isinstance(value, str) or not value:
            continue
        source = Path(value).expanduser()
        # Remote URLs and draft-relative placeholders are not local absolute
        # media references. Their existing resolution contracts stay unchanged.
        if not source.is_absolute():
            continue
        source = source.resolve()
        if _path_units(source) <= MAX_EDITOR_MEDIA_PATH_UNITS:
            continue
        if source not in copied:
            if not source.is_file():
                raise FileNotFoundError(f"草稿长路径素材不存在：{source}")
            if source.stat().st_size == 0:
                raise ValueError(f"草稿长路径素材为空：{source}")
            digest = _sha256(source)
            target = media_root / f"m-{_media_token(digest)}{source.suffix.lower()}"
            if _path_units(target) > MAX_EDITOR_MEDIA_PATH_UNITS:
                raise ValueError(
                    "剪映草稿保存目录或草稿名称过长，无法生成兼容的素材路径；"
                    f"请缩短保存目录或名称后重试：{draft_dir}"
                )
            if target.exists():
                if not target.is_file() or _sha256(target) != digest:
                    raise RuntimeError(f"草稿内素材副本校验失败，未覆盖现有文件：{target}")
            else:
                media_root.mkdir(parents=True, exist_ok=True)
                temporary = media_root / f"copy-{uuid.uuid4().hex[:8]}.tmp"
                try:
                    shutil.copyfile(source, temporary)
                    if _sha256(temporary) != digest:
                        raise RuntimeError(f"复制期间素材发生变化，请重试生成草稿：{source}")
                    os.replace(temporary, target)
                finally:
                    temporary.unlink(missing_ok=True)
            copied[source] = target
        replacements.append((material, str(copied[source])))

    # Do not leave the in-memory draft half-rewritten if any copy fails.
    for material, target_path in replacements:
        material["path"] = target_path
    return len(replacements)
