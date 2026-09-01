"""Short, project-owned H3 paths without truncating content/version identities."""

from __future__ import annotations

import base64
from pathlib import Path


def compact_digest(digest: str) -> str:
    # All 256 bits survive; lower-case base32 is safe on case-insensitive Windows.
    raw = bytes.fromhex(digest)
    if len(raw) != 32:
        raise ValueError("H3 缓存标识必须是完整 SHA-256")
    return base64.b32encode(raw).decode("ascii").rstrip("=").lower()


def item_h3_root(storage_root: Path, owner: str, project: str, item: str) -> Path:
    return Path(storage_root).resolve() / "projects" / str(owner) / project / item / "h3"


def cleanup_directory(source: Path, key: str) -> Path:
    # Old downloads stay in place. Only derivative output moves up, so current
    # raw.mp4/current.mp4 and historical draft references are never renamed.
    parent = source.parent
    if parent.parent.name == "segment-cache" and parent.parent.parent.name == "h3":
        root = parent.parent.parent
    elif parent.name.startswith("s-") and parent.parent.name == "h3":
        root = parent.parent
    else:
        # Standalone media tools also use this module, outside a project cache.
        root = parent
    return root / ("c-" + compact_digest(key))
