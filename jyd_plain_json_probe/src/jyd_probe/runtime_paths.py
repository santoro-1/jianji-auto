from __future__ import annotations

import os
import json
from dataclasses import dataclass
from pathlib import Path
import shutil
import sys
from typing import Iterable


@dataclass(frozen=True)
class JianyingDraftRootDetection:
    """How the active Jianying draft directory was resolved."""

    path: Path
    source: str
    confirmed: bool


def is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def project_root() -> Path:
    if is_frozen():
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent)).resolve()
    return Path(__file__).resolve().parents[2]


def workspace_root() -> Path:
    # Kept for compatibility with older call sites.  The project is now
    # self-contained, so the source workspace is the project directory itself.
    return project_root()


def data_root() -> Path:
    return project_root() / "data"


def libraries_root() -> Path:
    return data_root() / "libraries"


def detect_jianying_draft_root(
    configured: str | Path | None = None,
    *,
    fallback: str | Path | None = None,
) -> Path:
    """Return the configured or best populated JianyingPro Drafts directory.

    Jianying can be installed on C: while its draft storage is moved to another
    drive.  Its local catalogue (``root_meta_info.json``) is the strongest hint;
    bounded common paths on available drive letters are used as fallbacks.  An
    explicit configured path still wins because it represents a user override.
    """

    return detect_jianying_draft_root_details(configured, fallback=fallback).path


def detect_jianying_draft_root_details(
    configured: str | Path | None = None,
    *,
    fallback: str | Path | None = None,
) -> JianyingDraftRootDetection:
    """Resolve the draft root and retain whether it came from Jianying itself.

    A root recorded in ``root_meta_info.json`` is authoritative even when it is
    currently empty.  Older logic only accepted a root containing at least one
    plain ``draft_content.json`` and could therefore silently fall back to the
    deployment's ``data/drafts`` directory on a new or freshly cleaned PC.
    """

    if configured is not None and str(configured).strip():
        path = Path(configured).expanduser().resolve()
        return JianyingDraftRootDetection(
            path=path,
            source="configured",
            confirmed=path.is_dir(),
        )

    indexed = _jianying_catalogue_roots()
    populated = _best_populated_draft_root(indexed)
    if populated is not None:
        return JianyingDraftRootDetection(populated, "jianying_catalogue", True)

    # Jianying's own catalogue remains the strongest source of truth when the
    # selected folder has no drafts yet.  Prefer the first existing root because
    # _jianying_catalogue_roots() orders entries by Jianying's activity time.
    indexed_existing = _first_existing_directory(indexed)
    if indexed_existing is not None:
        return JianyingDraftRootDetection(indexed_existing, "jianying_catalogue", True)

    candidates = jianying_draft_root_candidates()
    populated = _best_populated_draft_root(candidates)
    if populated is not None:
        return JianyingDraftRootDetection(populated, "populated_scan", True)

    if fallback is not None:
        return JianyingDraftRootDetection(
            Path(fallback).expanduser().resolve(),
            "fallback",
            False,
        )
    home = Path.home()
    default = (
        home
        / "AppData"
        / "Local"
        / "JianyingPro"
        / "User Data"
        / "Projects"
        / "com.lveditor.draft"
    ).resolve()
    return JianyingDraftRootDetection(default, "default", default.is_dir())


def jianying_draft_root_candidates() -> list[Path]:
    """Return bounded draft-root candidates, with Jianying's own index first."""

    home = Path.home()
    default_root = (
        home
        / "AppData"
        / "Local"
        / "JianyingPro"
        / "User Data"
        / "Projects"
        / "com.lveditor.draft"
    )
    candidates: list[Path] = _jianying_catalogue_roots()

    candidates.extend(
        [
            default_root,
            home / "Documents" / "JianyingPro Drafts",
            Path(r"D:\剪映草稿\JianyingPro Drafts"),
        ]
    )
    if os.name == "nt":
        for letter in "CDEFGHIJKLMNOPQRSTUVWXYZ":
            drive = Path(f"{letter}:\\")
            try:
                if not drive.is_dir():
                    continue
            except OSError:
                continue
            candidates.extend(
                [
                    drive / "剪映草稿" / "JianyingPro Drafts",
                    drive / "JianyingPro Drafts",
                ]
            )
    return _unique_paths(candidates)


def _jianying_catalogue_roots() -> list[Path]:
    candidates: list[Path] = []
    for catalogue_path in _jianying_catalogue_paths():
        if not catalogue_path.is_file():
            continue
        try:
            # utf-8-sig accepts both ordinary UTF-8 and the BOM emitted by some
            # Windows-side file writers.
            catalogue = json.loads(catalogue_path.read_text(encoding="utf-8-sig"))
            stores = catalogue.get("all_draft_store", []) if isinstance(catalogue, dict) else []
            indexed: dict[str, tuple[Path, int]] = {}
            for item in stores if isinstance(stores, list) else []:
                if not isinstance(item, dict):
                    continue
                raw_root = str(item.get("draft_root_path", "")).strip()
                if not raw_root:
                    fold = str(item.get("draft_fold_path", "")).strip()
                    raw_root = str(Path(fold).parent) if fold else ""
                if not raw_root:
                    continue
                path = Path(raw_root).expanduser()
                try:
                    resolved = path.resolve()
                    modified = int(item.get("tm_draft_modified", 0) or 0)
                except (OSError, TypeError, ValueError):
                    continue
                key = os.path.normcase(str(resolved))
                previous = indexed.get(key)
                if previous is None or modified > previous[1]:
                    indexed[key] = (resolved, modified)
            candidates.extend(
                path for path, _ in sorted(indexed.values(), key=lambda value: value[1], reverse=True)
            )
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            pass
    return _unique_paths(candidates)


def _jianying_catalogue_paths() -> list[Path]:
    relative = (
        Path("JianyingPro")
        / "User Data"
        / "Projects"
        / "com.lveditor.draft"
        / "root_meta_info.json"
    )
    bases: list[Path] = []
    local_app_data = os.environ.get("LOCALAPPDATA", "").strip()
    if local_app_data:
        bases.append(Path(local_app_data))
    bases.append(Path.home() / "AppData" / "Local")
    return _unique_paths(base / relative for base in bases)


def _first_existing_directory(candidates: Iterable[Path]) -> Path | None:
    for candidate in candidates:
        try:
            resolved = candidate.expanduser().resolve()
            if resolved.is_dir():
                return resolved
        except OSError:
            continue
    return None


def _best_populated_draft_root(candidates: Iterable[Path]) -> Path | None:
    scored: list[tuple[int, float, int, Path]] = []
    for order, candidate in enumerate(candidates):
        try:
            resolved = candidate.expanduser().resolve()
            if not resolved.is_dir():
                continue
            count, newest = _draft_root_activity(resolved)
        except OSError:
            continue
        if count:
            # A recently used root is more likely to be Jianying's active root;
            # count breaks ties while candidate order favours its own catalogue.
            scored.append((count, newest, -order, resolved))
    if not scored:
        return None
    return max(scored, key=lambda value: (value[1], value[0], value[2]))[3]


def _draft_root_activity(root: Path) -> tuple[int, float]:
    count = 0
    newest = 0.0
    try:
        children = root.iterdir()
        for child in children:
            if not child.is_dir():
                continue
            content = child / "draft_content.json"
            if not content.is_file():
                continue
            count += 1
            try:
                newest = max(newest, content.stat().st_mtime)
            except OSError:
                continue
    except OSError:
        return 0, 0.0
    return count, newest


def _unique_paths(paths: Iterable[Path]) -> list[Path]:
    result: list[Path] = []
    seen: set[str] = set()
    for path in paths:
        try:
            resolved = path.expanduser().resolve()
        except OSError:
            continue
        key = os.path.normcase(str(resolved))
        if key in seen:
            continue
        seen.add(key)
        result.append(resolved)
    return result


def resource_path(*parts: str) -> Path:
    return project_root().joinpath(*parts)


def jy_draftc_exe_path() -> Path:
    configured = os.environ.get("JYD_DRAFTC_EXE", "").strip()
    if configured:
        return Path(configured).expanduser().resolve()
    if not is_frozen():
        return project_root() / "vendor" / "jy-draftc" / "jy-draftc.exe"
    bundled = project_root() / "jy-draftc" / "jy-draftc.exe"
    target = collector_state_root() / "tools" / "jy-draftc.exe"
    if bundled.is_file():
        target.parent.mkdir(parents=True, exist_ok=True)
        if not target.is_file() or target.stat().st_size != bundled.stat().st_size:
            shutil.copy2(bundled, target)
    return target


def collector_state_root() -> Path:
    configured = os.environ.get("JYD_COLLECTOR_STATE_ROOT", "").strip()
    if configured:
        return Path(configured).expanduser().resolve()
    if not is_frozen():
        return project_root() / "runtime" / "collector_state"
    local_app_data = os.environ.get("LOCALAPPDATA", "").strip()
    base = Path(local_app_data) if local_app_data else Path.home() / "AppData" / "Local"
    return (base / "JianyingDraftCollector").resolve()
