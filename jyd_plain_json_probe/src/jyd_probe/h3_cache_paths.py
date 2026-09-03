"""Short, project-owned H3 paths with full identities kept in metadata."""

from __future__ import annotations

import base64
from pathlib import Path


H3_PATH_TOKEN_LENGTH = 24


def _full_compact_digest(digest: str) -> str:
    """Encode a full SHA-256 for reading the previous 52-character layout."""

    raw = bytes.fromhex(digest)
    if len(raw) != 32:
        raise ValueError("H3 缓存标识必须是完整 SHA-256")
    return base64.b32encode(raw).decode("ascii").rstrip("=").lower()


def compact_digest(digest: str) -> str:
    """Return the bounded token used by every new H3 directory or filename.

    The complete digest remains in cache metadata and is checked before reuse.
    A 24-character lower-case Base32 prefix gives 120 bits of local namespace
    separation while leaving ample headroom for Windows MAX_PATH installations.
    """

    return _full_compact_digest(digest)[:H3_PATH_TOKEN_LENGTH]


def previous_compact_digest(digest: str) -> str:
    """Return the previous full Base32 name for read-only cache compatibility."""

    return _full_compact_digest(digest)


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


def previous_cleanup_directory(source: Path, key: str) -> Path:
    """Locate the pre-shortening cleanup cache without creating new files there."""

    parent = source.parent
    if parent.parent.name == "segment-cache" and parent.parent.parent.name == "h3":
        root = parent.parent.parent
    elif parent.name.startswith("s-") and parent.parent.name == "h3":
        root = parent.parent
    else:
        root = parent
    return root / ("c-" + previous_compact_digest(key))
