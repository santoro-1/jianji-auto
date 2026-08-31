"""Folder-only semantic library with an incremental, portable SQLite index.

The legacy catalog is read ONLY by the explicit migration command. Runtime
scans use source folders and the index; immutable generated media keep frozen
recipes usable after source files are renamed, edited or removed.
"""

from __future__ import annotations

import argparse
from collections import defaultdict
from contextlib import contextmanager
from dataclasses import replace
import hashlib
import json
import logging
import os
from pathlib import Path
import re
import shutil
import sqlite3
import subprocess
import threading
import time
import uuid

from .semantic_visuals import (
    CATALOG_SCHEMA_V3,
    SemanticVisualCatalogError,
    _load_semantic_visual_catalog_v3,
    load_semantic_visual_catalog,
)

SOURCE_DIR = "素材"
INDEX_NAME = "semantic_visual_index.db"
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".bmp"}
VIDEO_EXTENSIONS = {".mp4", ".mov", ".mkv", ".webm", ".m4v"}
_LOG = logging.getLogger(__name__)
_GROUPS = {
    "food": "食物",
    "dish": "食物",
    "meal": "餐食",
    "drink": "饮品",
    "nutrition": "营养",
    "activity": "运动",
    "action": "动作",
    "scene": "生活场景",
    "editorial": "生活场景",
    "health": "健康",
    "body": "身体",
    "body_shape": "体型",
    "weight_management": "体重管理",
    "clothing": "服饰",
    "habit": "生活习惯",
    "portion": "份量",
}


def _json(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _digest(path):
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _safe(root, relative):
    path = (root / relative).resolve()
    if not path.is_relative_to(root.resolve()):
        raise SemanticVisualCatalogError("素材路径超出图库目录")
    return path


def _name(value):
    value = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", str(value)).strip(" .")[:65]
    if value.upper().split(".")[0] in {
        "CON",
        "PRN",
        "AUX",
        "NUL",
        *(f"COM{i}" for i in range(10)),
        *(f"LPT{i}" for i in range(10)),
    }:
        value = "_" + value
    return value or "未命名"


def _copy_once(source, target):
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        if _digest(source) != _digest(target):
            raise SemanticVisualCatalogError(
                f"目标已存在且内容不同，未覆盖：{target.name}"
            )
        return
    temporary = target.with_name(target.name + "." + uuid.uuid4().hex + ".tmp")
    try:
        shutil.copyfile(source, temporary)
        os.replace(temporary, target)
    finally:
        temporary.unlink(missing_ok=True)


def _write_json_once(target, payload):
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        return
    temporary = target.with_name(target.name + "." + uuid.uuid4().hex + ".tmp")
    try:
        temporary.write_text(_json(payload), encoding="utf-8")
        os.replace(temporary, target)
    finally:
        temporary.unlink(missing_ok=True)


@contextmanager
def _connect(root):
    root.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(root / INDEX_NAME, timeout=120)
    connection.row_factory = sqlite3.Row
    connection.executescript(
        """
        CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS concepts (id TEXT PRIMARY KEY, payload TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS folders (path TEXT PRIMARY KEY, concept_id TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS assets (
            id TEXT PRIMARY KEY, payload TEXT NOT NULL, digest TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS sources (
            path TEXT PRIMARY KEY, asset_id TEXT NOT NULL, stamp TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS rejected_sources (
            path TEXT PRIMARY KEY, stamp TEXT NOT NULL, payload TEXT, error TEXT NOT NULL);
    """
    )
    try:
        with connection:
            yield connection
    finally:
        connection.close()


def _stamp(path):
    stat = path.stat()
    return f"{stat.st_size}:{stat.st_mtime_ns}"


def _package_image(root, source, digest):
    from PIL import Image, ImageOps

    bundle = Path("generated") / "bundles" / digest
    preview = bundle / "resources" / "sticker" / "singleImage.png"
    target = _safe(root, preview)
    if not target.exists():
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary = target.with_name(uuid.uuid4().hex + ".tmp")
        try:
            with Image.open(source) as validation:
                validation.verify()
            with Image.open(source) as image:
                if image.format == "PNG" and image.getexif().get(274, 1) == 1:
                    shutil.copyfile(source, temporary)
                else:
                    ImageOps.exif_transpose(image).convert("RGBA").save(
                        temporary, format="PNG"
                    )
            os.replace(temporary, target)
        finally:
            temporary.unlink(missing_ok=True)
    _write_json_once(
        root / bundle / "sticker.json",
        {
            "schema": "jyd_probe.fullscreen_sticker.v1",
            "identity": "folder:" + digest,
            "name": source.stem,
            "usage": "fullscreen_overlay",
            "material": {},
            "segment_template": {},
            "resource": {"library_path": "resources/sticker", "status": "copied"},
            "preview_file": "resources/sticker/singleImage.png",
        },
    )
    return {"bundle": bundle.as_posix(), "preview": preview.as_posix()}


def _run_media(command):
    result = subprocess.run(
        command,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=60,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    if result.returncode:
        raise SemanticVisualCatalogError("视频读取失败：" + result.stderr[-350:])
    return result.stdout


def _package_video(root, source, digest, *, imported_resource=None, original_root=None):
    folder = Path("generated") / "videos" / digest
    _safe(root, folder)
    video = folder / ("video" + source.suffix.lower())
    preview = folder / "poster.png"
    _copy_once(source, root / video)
    if imported_resource is not None:
        resource = dict(imported_resource)
        preview = folder / (
            "poster_" + _digest(_safe(original_root, resource["preview"]))[:16] + ".png"
        )
        _copy_once(_safe(original_root, resource["preview"]), root / preview)
        if resource.get("metadata"):
            metadata = folder / (
                "metadata_"
                + _digest(_safe(original_root, resource["metadata"]))[:16]
                + ".json"
            )
            _copy_once(_safe(original_root, resource["metadata"]), root / metadata)
            resource["metadata"] = metadata.as_posix()
    else:
        from .browser_preview import _ffprobe_path
        from .bgm_loudness import _ffmpeg_path

        probe, ffmpeg = _ffprobe_path(), _ffmpeg_path()
        if not probe or not ffmpeg:
            raise SemanticVisualCatalogError("新增视频需要本机 FFmpeg/FFprobe")
        data = json.loads(
            _run_media(
                [
                    probe,
                    "-v",
                    "error",
                    "-show_streams",
                    "-show_format",
                    "-of",
                    "json",
                    str(source),
                ]
            )
        )
        stream = next(x for x in data["streams"] if x.get("codec_type") == "video")
        duration = float(stream.get("duration") or data["format"]["duration"])
        if duration <= 0:
            raise SemanticVisualCatalogError("视频时长无效")
        resource = {
            "duration_us": round(duration * 1_000_000),
            "width": int(stream["width"]),
            "height": int(stream["height"]),
            "has_audio": any(x.get("codec_type") == "audio" for x in data["streams"]),
        }
        if not (root / preview).exists():
            temporary = root / folder / (uuid.uuid4().hex + ".png")
            try:
                _run_media(
                    [
                        ffmpeg,
                        "-v",
                        "error",
                        "-nostdin",
                        "-i",
                        str(source),
                        "-frames:v",
                        "1",
                        "-y",
                        str(temporary),
                    ]
                )
                os.replace(temporary, root / preview)
            finally:
                temporary.unlink(missing_ok=True)
    resource.update(video=video.as_posix(), preview=preview.as_posix())
    return resource


def _new_asset(root, source, digest, concept_id):
    video = source.suffix.lower() in VIDEO_EXTENSIONS
    resource = (
        _package_video(root, source, digest)
        if video
        else _package_image(root, source, digest)
    )
    defaults = {
        "corner": "bottom_center",
        "scale": 0.615 if video else 0.56,
        "opacity": 1,
        "duration_us": min(3_000_000, resource["duration_us"]) if video else 1_800_000,
    }
    if video:
        defaults.update(source_start_us=0, mute=True, loop=False, fit="contain")
    # Dropping a video into a keyword folder does not approve full-screen use,
    # source-window review or rights. Only a short muted foreground is enabled.
    return {
        "asset_id": "folder." + digest[:24],
        "concept_ids": [concept_id],
        "name": source.stem,
        "description": source.stem,
        "tags": [],
        "media_type": "video" if video else "image",
        "renderer": "video_overlay" if video else "jyd_sticker_bundle",
        "resource": resource,
        "defaults": defaults,
        "semantic_roles": {"depicts": [concept_id], "expresses": [], "related": []},
        "auto_trigger_concept_ids": [concept_id],
        "trigger_basis": {concept_id: "exact_subject"},
        "visual_actions": [],
        "usage_modes": (
            ["semantic_overlay"] if video else ["semantic_overlay", "list_quick_cut"]
        ),
        "cleanliness_grade": "B",
        "auto_eligible": True,
        "requires_clip": False,
        "loop_allowed": False,
        "rights_status": "unknown",
        "person_status": "unknown",
        "brand_status": "unknown",
        "health_claim_status": "unknown",
        "platform_ui_status": "unknown",
    }


def migrate_catalog(source_root, target_root):
    """Explicit, repeat-safe copy. Never delete or overwrite the original library."""
    source_root, target_root = Path(source_root).resolve(), Path(target_root).resolve()
    manifest = source_root / "catalog.json"
    payload = json.loads(manifest.read_text(encoding="utf-8"))
    if payload.get("schema") != CATALOG_SCHEMA_V3:
        raise SemanticVisualCatalogError("首次整理需要 v3 素材目录")
    # Validate legacy ranges/permissions and apply its quarantine exactly once.
    legacy = load_semantic_visual_catalog(source_root, source_mode="json")
    with _connect(target_root) as connection:
        connection.execute("BEGIN IMMEDIATE")
        previous = connection.execute(
            "SELECT value FROM settings WHERE key='import_sha256'"
        ).fetchone()
        if previous:
            if previous[0] != _digest(manifest):
                raise SemanticVisualCatalogError(
                    "已经整理过图库；旧 JSON 已变化，需人工核对，未覆盖现有分类"
                )
            return {"already_imported": True, "assets": len(payload["assets"])}
        if connection.execute("SELECT COUNT(*) FROM assets").fetchone()[0]:
            raise SemanticVisualCatalogError(
                "目标已有文件夹素材，请使用空的目标图库整理"
            )
        # Persist the in-progress marker outside the import transaction. After
        # a crash, runtime must not mistake partially copied files for a fresh
        # library and discard their original review metadata.
        connection.execute(
            "INSERT OR REPLACE INTO settings VALUES ('migration_state','in_progress')"
        )
        connection.commit()
        connection.execute("BEGIN IMMEDIATE")
        concepts = {x["concept_id"]: x for x in payload["concepts"]}
        folder_paths = {}
        for concept in concepts.values():
            cid = concept["concept_id"]
            group = _GROUPS.get(cid.split(".")[0], "待分类")
            folder = (Path(SOURCE_DIR) / group / _name(concept["label"])).as_posix()
            if folder.casefold() in {x.casefold() for x in folder_paths.values()}:
                folder += "_" + hashlib.sha256(cid.encode()).hexdigest()[:6]
            folder_paths[cid] = folder
            connection.execute(
                "INSERT INTO concepts VALUES (?,?)", (cid, _json(concept))
            )
            connection.execute("INSERT INTO folders VALUES (?,?)", (folder, cid))
        counts = defaultdict(int)
        for number, raw in enumerate(payload["assets"], 1):
            asset = json.loads(_json(raw))
            aid, video = asset["asset_id"], asset["media_type"] == "video"
            source = _safe(
                source_root, raw["resource"]["video" if video else "preview"]
            )
            digest = _digest(source)
            rejected = None
            try:
                asset["resource"] = (
                    _package_video(
                        target_root,
                        source,
                        digest,
                        imported_resource=raw["resource"],
                        original_root=source_root,
                    )
                    if video
                    else _package_image(target_root, source, digest)
                )
            except (OSError, ValueError, SyntaxError) as exc:
                rejected = str(exc)
                counts["rejected_assets"] += 1
                _LOG.warning(
                    "保留但不启用损坏素材 %s (%s): %s", asset["name"], aid, exc
                )
            asset["auto_eligible"] = legacy.asset(aid)["auto_eligible"]
            if rejected is None:
                connection.execute(
                    "INSERT INTO assets VALUES (?,?,?)", (aid, _json(asset), digest)
                )
            linked = asset["concept_ids"] or [None]
            for cid in linked:
                folder = folder_paths.get(
                    cid, (Path(SOURCE_DIR) / "待分类" / "仅手动素材").as_posix()
                )
                relative = (
                    Path(folder)
                    / ("视频" if video else "图片")
                    / (
                        _name(asset["name"])
                        + "__"
                        + hashlib.sha256(aid.encode()).hexdigest()[:10]
                        + source.suffix.lower()
                    )
                )
                target = _safe(target_root, relative)
                _copy_once(source, target)
                if rejected is None:
                    connection.execute(
                        "INSERT INTO sources VALUES (?,?,?)",
                        (relative.as_posix(), aid, _stamp(target)),
                    )
                else:
                    connection.execute(
                        "INSERT INTO rejected_sources VALUES (?,?,?,?)",
                        (relative.as_posix(), _stamp(target), _json(asset), rejected),
                    )
                counts["source_files"] += 1
            counts["videos" if video else "images"] += 1
            if number % 100 == 0:
                print(f"已整理 {number}/{len(payload['assets'])} 条素材", flush=True)
        # Fixed identity/nameplate graphics are not keyword search candidates.
        fixed = source_root / "fixed"
        if fixed.is_dir() and source_root != target_root:
            for path in fixed.rglob("*"):
                if path.is_file():
                    _copy_once(path, target_root / path.relative_to(source_root))
        connection.execute(
            "INSERT INTO settings VALUES ('import_sha256',?)", (_digest(manifest),)
        )
        connection.execute(
            "INSERT INTO settings VALUES ('library_id',?)",
            (payload["library_id"] + ".folders",),
        )
        connection.execute(
            "INSERT OR REPLACE INTO settings VALUES ('migration_state','complete')"
        )
    return dict(counts)


def _source_files(root):
    source_root = root / SOURCE_DIR
    source_root.mkdir(parents=True, exist_ok=True)
    files = {}

    # os.walk raises via onerror: never retire a whole unreadable directory.
    def failed(error):
        raise error

    for directory, subdirs, names in os.walk(
        source_root, onerror=failed, followlinks=False
    ):
        subdirs[:] = (
            sorted(
                x
                for x in subdirs
                if not (Path(directory) / x).is_symlink()
                and not (Path(directory) / x).is_junction()
            )
            if hasattr(Path(), "is_junction")
            else sorted(x for x in subdirs if not (Path(directory) / x).is_symlink())
        )
        for name in sorted(names):
            path = Path(directory) / name
            if (
                path.suffix.lower() not in IMAGE_EXTENSIONS | VIDEO_EXTENSIONS
                or path.is_symlink()
            ):
                continue
            relative = path.relative_to(root)
            if len(relative.parts) < 4 or relative.parts[1].startswith("."):
                continue
            _safe(root, relative)
            files[relative.as_posix()] = (path, _stamp(path))
    return files


def _load_snapshot(root, connection):
    concepts = [
        json.loads(x[0])
        for x in connection.execute("SELECT payload FROM concepts ORDER BY id")
    ]
    folders = {
        x[0]: x[1] for x in connection.execute("SELECT path, concept_id FROM folders")
    }
    memberships = defaultdict(set)
    for source in connection.execute("SELECT path, asset_id FROM sources"):
        memberships[source[1]].add(
            folders.get(Path(*Path(source[0]).parts[:3]).as_posix())
        )
    present_ids = set(memberships)
    rows = connection.execute("SELECT * FROM assets ORDER BY id").fetchall()
    assets = []
    for row in rows:
        asset = json.loads(row["payload"])
        if row["id"] not in present_ids:
            asset["auto_eligible"] = False
        else:
            active = [
                cid for cid in asset["concept_ids"] if cid in memberships[row["id"]]
            ]
            asset["concept_ids"] = active
            asset["auto_trigger_concept_ids"] = active
            asset["trigger_basis"] = {
                cid: asset["trigger_basis"][cid] for cid in active
            }
            if not active:
                asset["auto_eligible"] = False
                asset.pop("video_taxonomy", None)
            elif "video_taxonomy" in asset:
                asset["video_taxonomy"]["l3_exact_concept_ids"] = active
        assets.append(asset)
    library = connection.execute(
        "SELECT value FROM settings WHERE key='library_id'"
    ).fetchone()
    catalog = _load_semantic_visual_catalog_v3(
        root,
        {
            "schema": CATALOG_SCHEMA_V3,
            "library_id": library[0] if library else "jyd.semantic.folder-library",
            "concepts": concepts,
            "assets": assets,
        },
        content_version=_json([(x["id"], x["digest"]) for x in rows]),
        read_quarantine=False,
    )
    hashes = {x["id"]: x["digest"] for x in rows}
    originally_eligible = {
        x["id"]: json.loads(x["payload"])["auto_eligible"] for x in rows
    }
    return replace(
        catalog,
        source_mode="folders",
        assets=tuple(
            {
                **x,
                "content_sha256": hashes[x["asset_id"]],
                "source_missing": x["asset_id"] not in present_ids,
                "folder_auto_eligible": originally_eligible[x["asset_id"]],
            }
            for x in catalog.assets
        ),
    )


def scan_folders(root, *, source_files=None):
    root = Path(root).resolve()
    files = _source_files(root) if source_files is None else source_files
    with _connect(root) as connection:
        connection.execute("BEGIN IMMEDIATE")
        reclassification = connection.execute(
            "SELECT value FROM settings WHERE key='reclassification_state'"
        ).fetchone()
        if reclassification and reclassification[0] != "complete":
            raise SemanticVisualCatalogError(
                "图库归类尚未完成，请先恢复归类记录；未启用半成品图库"
            )
        state = connection.execute(
            "SELECT value FROM settings WHERE key='migration_state'"
        ).fetchone()
        if state and state[0] == "in_progress":
            raise SemanticVisualCatalogError(
                "图库整理尚未完成，请重新运行 migrate 继续；未启用半成品图库"
            )
        sources = {
            x["path"]: dict(x) for x in connection.execute("SELECT * FROM sources")
        }
        rejected = {
            x["path"]: dict(x)
            for x in connection.execute("SELECT * FROM rejected_sources")
        }
        folders = {
            x["path"]: x["concept_id"]
            for x in connection.execute("SELECT * FROM folders")
        }
        assets = {x["id"]: dict(x) for x in connection.execute("SELECT * FROM assets")}
        by_hash = defaultdict(list)
        for asset in assets.values():
            by_hash[asset["digest"]].append(asset)
        active_folders = {Path(*Path(x).parts[:3]).as_posix() for x in files}
        for relative, (path, stamp) in files.items():
            old = sources.get(relative)
            if old and old["stamp"] == stamp:
                continue
            rejected_source = rejected.get(relative)
            if rejected_source and rejected_source["stamp"] == stamp:
                continue
            try:
                digest = _digest(path)
                folder = Path(*Path(relative).parts[:3]).as_posix()
                cid = folders.get(folder)
                matches = by_hash[digest]
                if cid is None:
                    # Whole-folder rename: reuse the concept if its previous
                    # location disappeared. Copying to another folder is not a rename.
                    previous_folders = {
                        Path(*Path(p).parts[:3]).as_posix()
                        for p, s in sources.items()
                        if any(a["id"] == s["asset_id"] for a in matches)
                    }
                    absent = [
                        p
                        for p in previous_folders
                        if p not in active_folders and p in folders
                    ]
                    same_label = [
                        p for p in absent if Path(p).name == Path(folder).name
                    ]
                    if len(same_label) == 1:
                        absent = same_label
                    if len(absent) == 1:
                        cid = folders[absent[0]]
                        concept = json.loads(
                            connection.execute(
                                "SELECT payload FROM concepts WHERE id=?", (cid,)
                            ).fetchone()[0]
                        )
                        concept["label"] = Path(folder).name
                        concept["aliases"] = list(
                            dict.fromkeys([*concept["aliases"], Path(folder).name])
                        )
                        connection.execute(
                            "UPDATE concepts SET payload=? WHERE id=?",
                            (_json(concept), cid),
                        )
                    else:
                        label = Path(folder).name
                        cid = "folder." + uuid.uuid4().hex
                        concept = {
                            "concept_id": cid,
                            "label": label,
                            "description": f"画面主体明确呈现{label}，仅匹配该具体对象或动作。",
                            "aliases": [label],
                        }
                        connection.execute(
                            "INSERT INTO concepts VALUES (?,?)", (cid, _json(concept))
                        )
                    connection.execute(
                        "INSERT INTO folders VALUES (?,?)", (folder, cid)
                    )
                    folders[folder] = cid
                # A content match reuses the ID and its review metadata. Distinct
                # imported source windows retain their original IDs via sources.
                matching = next(
                    (x for x in matches if old and x["id"] == old["asset_id"]), None
                )
                if matching is None:
                    matching = next(
                        (
                            x
                            for x in matches
                            if cid in json.loads(x["payload"])["concept_ids"]
                        ),
                        None,
                    )
                if matching is not None:
                    aid = matching["id"]
                else:
                    if matches:
                        # Reclassifying known bytes must not bypass quarantine,
                        # rights or approved source-window limits.
                        asset = json.loads(matches[0]["payload"])
                        asset["asset_id"] = "folder." + digest[:24]
                        asset["concept_ids"] = asset["auto_trigger_concept_ids"] = [cid]
                        asset["semantic_roles"] = {
                            "depicts": [cid],
                            "expresses": [],
                            "related": [],
                        }
                        asset["trigger_basis"] = {cid: "exact_subject"}
                        if "video_taxonomy" in asset:
                            asset["video_taxonomy"]["l3_exact_concept_ids"] = [cid]
                    else:
                        asset = _new_asset(root, path, digest, cid)
                        if (
                            rejected_source
                            and rejected_source["payload"]
                            and asset["media_type"] == "image"
                        ):
                            reviewed = json.loads(rejected_source["payload"])
                            if reviewed["media_type"] == "image":
                                reviewed["asset_id"] = asset["asset_id"]
                                reviewed["resource"] = asset["resource"]
                                asset = reviewed
                    # Same bytes in another concept folder: distinct semantic
                    # binding but common digest, so one video never repeats it.
                    asset["asset_id"] += (
                        "." + hashlib.sha256(cid.encode()).hexdigest()[:10]
                    )
                    aid = asset["asset_id"]
                    connection.execute(
                        "INSERT OR IGNORE INTO assets VALUES (?,?,?)",
                        (aid, _json(asset), digest),
                    )
                    row = {"id": aid, "payload": _json(asset), "digest": digest}
                    by_hash[digest].append(row)
                if _stamp(path) != stamp:
                    raise SemanticVisualCatalogError("素材仍在复制，稍后重试")
                connection.execute(
                    "INSERT OR REPLACE INTO sources VALUES (?,?,?)",
                    (relative, aid, stamp),
                )
                connection.execute(
                    "DELETE FROM rejected_sources WHERE path=?", (relative,)
                )
            except (
                OSError,
                ValueError,
                SyntaxError,
                StopIteration,
                KeyError,
                subprocess.SubprocessError,
            ) as exc:
                # Incomplete/broken new files do not invalidate usable entries.
                # An edited old file retains its last validated immutable cache.
                _LOG.warning("跳过尚未可用的素材 %s: %s", relative, exc)
                connection.execute(
                    "INSERT OR REPLACE INTO rejected_sources VALUES (?,?,?,?)",
                    (
                        relative,
                        stamp,
                        rejected_source["payload"] if rejected_source else None,
                        str(exc),
                    ),
                )
        for relative in sources.keys() - files.keys():
            connection.execute("DELETE FROM sources WHERE path=?", (relative,))
        for relative in rejected.keys() - files.keys():
            connection.execute("DELETE FROM rejected_sources WHERE path=?", (relative,))
        snapshot = _load_snapshot(root, connection)
    return snapshot


class FolderCatalog:
    """Shared live view; only changed source bytes are hashed/probed every 5s."""

    source_mode = "folders"

    def __init__(self, root, *, refresh_seconds=5):
        self.root = Path(root).resolve()
        self._lock = threading.RLock()
        self._refresh_seconds = refresh_seconds
        self._next_scan = 0.0
        self._snapshot = None
        self._fingerprint = None
        self.refresh()

    def refresh(self, *, force=False):
        with self._lock:
            if (
                self._snapshot is not None
                and not force
                and time.monotonic() < self._next_scan
            ):
                return self._snapshot
            try:
                files = _source_files(self.root)
                file_stamps = tuple(
                    sorted((name, row[1]) for name, row in files.items())
                )
                index = self.root / INDEX_NAME
                index_stamp = _stamp(index) if index.exists() else None
                fingerprint = (index_stamp, file_stamps)
                if self._snapshot is None or self._fingerprint != fingerprint:
                    self._snapshot = scan_folders(self.root, source_files=files)
                    self._fingerprint = (_stamp(index), file_stamps)
            except (OSError, ValueError, sqlite3.Error):
                if self._snapshot is None:
                    raise
                _LOG.exception(
                    "文件夹素材扫描失败，继续使用上次有效索引；不会读取旧 JSON"
                )
            self._next_scan = time.monotonic() + self._refresh_seconds
            return self._snapshot

    def __getattr__(self, name):
        return getattr(self.refresh(), name)


def main():
    parser = argparse.ArgumentParser(description="本地文件夹语义素材库（不调用云端）")
    sub = parser.add_subparsers(dest="command", required=True)
    migrate = sub.add_parser("migrate")
    migrate.add_argument("--source", required=True)
    migrate.add_argument("--target", required=True)
    scan = sub.add_parser("scan")
    scan.add_argument("--root", required=True)
    args = parser.parse_args()
    if args.command == "migrate":
        print(_json(migrate_catalog(args.source, args.target)))
    else:
        catalog = scan_folders(args.root)
        print(
            _json(
                {
                    "source_mode": catalog.source_mode,
                    "catalog_version": catalog.catalog_version,
                    "concepts": len(catalog.concepts),
                    "assets": len(catalog.assets),
                    "active": sum(x["auto_eligible"] for x in catalog.assets),
                }
            )
        )


if __name__ == "__main__":
    main()
