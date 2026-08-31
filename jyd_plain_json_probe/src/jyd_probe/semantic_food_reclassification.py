"""Explicit, reversible entity-folder migration of an existing local index.

Only source memberships and semantic bindings change. Original catalogs,
immutable render resources, review restrictions and video windows stay intact.
"""

from __future__ import annotations

import argparse
from collections import defaultdict
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import shutil
import sqlite3
import uuid

from .semantic_food_categories import classification_plan
from .semantic_visual_folders import (
    INDEX_NAME,
    SOURCE_DIR,
    _connect,
    _digest,
    _json,
    _load_snapshot,
    _name,
    _safe,
    _stamp,
    SemanticVisualCatalogError,
)

VERSION = "food-entities-v1"
BACKUPS = "reclassification_backups"


def _read_index(connection):
    return {
        "concepts": {
            k: json.loads(v)
            for k, v in connection.execute("SELECT id,payload FROM concepts")
        },
        "assets": {
            k: json.loads(v)
            for k, v in connection.execute("SELECT id,payload FROM assets")
        },
        "digests": dict(connection.execute("SELECT id,digest FROM assets")),
        "folders": dict(connection.execute("SELECT path,concept_id FROM folders")),
        "sources": {
            x["path"]: dict(x) for x in connection.execute("SELECT * FROM sources")
        },
        "rejected": {
            x["path"]: dict(x)
            for x in connection.execute("SELECT * FROM rejected_sources")
        },
        "settings": dict(connection.execute("SELECT key,value FROM settings")),
    }


def _prepare(root, data):
    state = data["settings"].get("reclassification_state", "complete")
    if state != "complete":
        raise SemanticVisualCatalogError(
            "上次归类未完成，请先使用 rollback 恢复：" + state
        )
    if data["settings"].get("reclassification_version") == VERSION:
        return {"already_applied": True}
    plan = classification_plan(data["concepts"], data["assets"], data["folders"])
    for cid, relative in plan["folders"].items():
        parts = Path(relative).parts
        plan["folders"][cid] = str(
            Path(SOURCE_DIR) / _name(parts[1]) / _name(parts[2])
        ).replace("\\", "/")
    by_asset = defaultdict(list)
    for path, row in data["sources"].items():
        by_asset[row["asset_id"]].append(path)
    registered = {**data["sources"], **data["rejected"]}
    for relative, row in registered.items():
        path = _safe(root, relative)
        if not path.is_file() or _stamp(path) != row["stamp"]:
            raise SemanticVisualCatalogError(
                "素材与索引不一致，请先完成扫描：" + relative
            )
    # Never absorb new user files into an old classification without review.
    for path in (root / SOURCE_DIR).rglob("*"):
        if path.is_symlink() or (hasattr(path, "is_junction") and path.is_junction()):
            raise SemanticVisualCatalogError("归类目录中存在链接，未移动：" + str(path))
        if path.is_file() and path.relative_to(root).as_posix() not in registered:
            raise SemanticVisualCatalogError(
                "发现尚未登记的文件，请先扫描或移出：" + str(path)
            )
    moves, copies, sources, rejected = [], [], {}, {}
    for aid, old_paths in by_asset.items():
        asset = plan["assets"][aid]
        available = sorted(old_paths)
        source = _safe(root, available[0])
        targets = list(
            dict.fromkeys(plan["folders"][cid] for cid in asset["concept_ids"])
        )
        if not targets:
            targets = [Path(available[0]).parent.parent.as_posix()]
        first_target = None
        for folder in targets:
            target = (
                Path(folder)
                / ("视频" if asset["media_type"] == "video" else "图片")
                / (
                    _name(asset["name"])
                    + "__"
                    + hashlib.sha256(aid.encode()).hexdigest()[:10]
                    + source.suffix.lower()
                )
            ).as_posix()
            _safe(root, target)
            if target in sources or target in data["rejected"]:
                raise SemanticVisualCatalogError("目标文件名冲突，未修改：" + target)
            if available:
                old = available.pop(
                    available.index(target) if target in available else 0
                )
                moves.append(
                    {"old": old, "new": target, "stamp": data["sources"][old]["stamp"]}
                )
            else:
                copies.append(
                    {
                        "source": first_target,
                        "new": target,
                        "digest": data["digests"][aid],
                        "bytes": source.stat().st_size,
                    }
                )
            sources[target] = aid
            first_target = first_target or target
    for relative, row in data["rejected"].items():
        moves.append({"old": relative, "new": relative, "stamp": row["stamp"]})
        rejected[relative] = row
        old_folder = Path(*Path(relative).parts[:3]).as_posix()
        cid = data["folders"].get(old_folder)
        if cid:
            plan["folders"][cid] = old_folder
    target_paths = [row["new"].casefold() for row in moves + copies]
    if len(target_paths) != len(set(target_paths)):
        raise SemanticVisualCatalogError("归类目标存在大小写冲突")
    return {
        "metadata": plan,
        "moves": moves,
        "copies": copies,
        "sources": sources,
        "rejected": rejected,
        "summary": {
            "assets": len(data["assets"]),
            "changed_assets": len(plan["changes"]),
            "source_files_before": len(registered),
            "source_files_after": len(target_paths),
            "extra_copy_bytes": sum(row["bytes"] for row in copies),
            "archived_duplicate_files": len(registered) - len(moves),
        },
    }


def _save_journal(backup, journal):
    temporary = backup / "journal.tmp"
    temporary.write_text(_json(journal), encoding="utf-8")
    os.replace(temporary, backup / "journal.json")


def _move(root, source, target):
    source, target = _safe(root, source), _safe(root, target)
    if target.exists():
        raise SemanticVisualCatalogError("不覆盖已有文件：" + str(target))
    target.parent.mkdir(parents=True, exist_ok=True)
    source.rename(target)


def _restore(root, backup, journal):
    """Recover planned moves even after a process crash, without deleting files."""
    before = _safe(root, backup / "sources_before")
    current = _safe(root, SOURCE_DIR)
    staging = journal["status"] in {"prepared", "staging"}
    if not staging:
        # Validate every original first; don't partially restore edited sources.
        for row in journal["moves"]:
            old = _safe(root, before / Path(row["old"]).relative_to(SOURCE_DIR))
            new = _safe(root, row["new"])
            path = old if old.exists() else new
            if not path.is_file() or _stamp(path) != row["stamp"]:
                raise SemanticVisualCatalogError(
                    "归类后原素材发生变化，需人工恢复：" + str(path)
                )
        for row in journal["moves"]:
            old = _safe(root, before / Path(row["old"]).relative_to(SOURCE_DIR))
            if not old.exists():
                _move(root, row["new"], old)
        # Only copies/later additions remain; archive them without moving the
        # root directory, which Windows Explorer may hold open.
        extras = backup / ("added_copies_" + uuid.uuid4().hex[:8])
        for path in current.rglob("*"):
            if path.is_file():
                _move(root, path, extras / path.relative_to(current))
    for relative, stamp in journal["originals"].items():
        old = _safe(root, before / Path(relative).relative_to(SOURCE_DIR))
        source = old if old.exists() else _safe(root, relative)
        if not source.is_file() or _stamp(source) != stamp:
            raise SemanticVisualCatalogError("原文件已变化，需人工恢复：" + str(source))
    for relative in journal["originals"]:
        old = _safe(root, before / Path(relative).relative_to(SOURCE_DIR))
        if old.exists():
            _move(root, old, relative)
    _prune_empty(root)
    with sqlite3.connect(backup / INDEX_NAME) as original, sqlite3.connect(
        root / INDEX_NAME
    ) as target:
        original.backup(target)
    journal["status"] = "rolled_back"
    _save_journal(backup, journal)


def _prune_empty(root):
    source = _safe(root, SOURCE_DIR)
    for path in sorted(source.rglob("*"), key=lambda p: len(p.parts), reverse=True):
        if path.is_dir() and not path.is_symlink():
            path = _safe(root, path)
            if not path.is_relative_to(source) or path == source:
                raise SemanticVisualCatalogError("拒绝清理素材目录以外的空目录")
            try:
                path.rmdir()  # Empty directories only; never recursive deletion.
            except OSError:
                pass  # In-use/nonempty directories are retained.


def rollback(root, backup):
    root = Path(root).resolve()
    backup = _safe(root, backup)
    if not backup.is_relative_to(root / BACKUPS):
        raise SemanticVisualCatalogError("恢复目录必须位于本图库的归类备份目录")
    journal = json.loads((backup / "journal.json").read_text(encoding="utf-8"))
    if journal["root"] != str(root):
        raise SemanticVisualCatalogError("恢复记录不属于当前图库")
    if journal["status"] == "rolled_back":
        return {"already_restored": True}
    if (
        journal.get("index_after_sha256")
        and _digest(root / INDEX_NAME) != journal["index_after_sha256"]
    ):
        raise SemanticVisualCatalogError("索引在归类后已改变，需人工核对，未覆盖")
    _restore(root, backup, journal)
    return {"restored": True, "backup": str(backup)}


def reclassify(root, *, apply=False):
    root = Path(root).resolve()
    index = root / INDEX_NAME
    if not index.is_file() or not (root / SOURCE_DIR).is_dir():
        raise SemanticVisualCatalogError("需要已经建立索引的文件夹图库")
    if not apply:
        with sqlite3.connect(index.as_uri() + "?mode=ro", uri=True) as connection:
            connection.row_factory = sqlite3.Row
            plan = _prepare(root, _read_index(connection))
        if plan.get("already_applied"):
            return plan
        return {**plan["summary"], "changes": plan["metadata"]["changes"]}
    backup = _safe(
        root,
        Path(BACKUPS)
        / (datetime.now().strftime("%Y%m%d-%H%M%S-") + uuid.uuid4().hex[:8]),
    )
    journal = None
    try:
        with _connect(root) as connection:
            connection.execute("BEGIN IMMEDIATE")
            data = _read_index(connection)
            plan = _prepare(root, data)
            if plan.get("already_applied"):
                return plan
            backup.mkdir(parents=True)
            # A second read connection backs up the committed index while the
            # write lock prevents another scanner from changing its snapshot.
            with sqlite3.connect(
                index.as_uri() + "?mode=ro", uri=True
            ) as original, sqlite3.connect(backup / INDEX_NAME) as target:
                original.backup(target)
            journal = {
                "root": str(root),
                "version": VERSION,
                "status": "prepared",
                "moves": plan["moves"],
                "copies": plan["copies"],
                "originals": {
                    p: row["stamp"]
                    for p, row in {**data["sources"], **data["rejected"]}.items()
                },
                "summary": plan["summary"],
            }
            _save_journal(backup, journal)
            (backup / "classification_changes.json").write_text(
                _json(plan["metadata"]["changes"]), encoding="utf-8"
            )
            connection.execute(
                "INSERT OR REPLACE INTO settings VALUES ('reclassification_state',?)",
                (str(backup),),
            )
            connection.commit()
            connection.execute("BEGIN IMMEDIATE")
            journal["status"] = "staging"
            _save_journal(backup, journal)
            for relative in journal["originals"]:
                _move(
                    root,
                    relative,
                    backup / "sources_before" / Path(relative).relative_to(SOURCE_DIR),
                )
            journal["status"] = "moving"
            _save_journal(backup, journal)
            for row in plan["moves"]:
                old = (
                    backup / "sources_before" / Path(row["old"]).relative_to(SOURCE_DIR)
                )
                _move(root, old, row["new"])
            for row in plan["copies"]:
                source, target = _safe(root, row["source"]), _safe(root, row["new"])
                target.parent.mkdir(parents=True, exist_ok=True)
                if target.exists():
                    raise SemanticVisualCatalogError("新增副本目标已存在")
                shutil.copy2(source, target)
                if _digest(target) != row["digest"]:
                    raise SemanticVisualCatalogError("新增副本校验失败")
            metadata = plan["metadata"]
            connection.executemany(
                "INSERT OR REPLACE INTO concepts VALUES (?,?)",
                [(cid, _json(raw)) for cid, raw in metadata["concepts"].items()],
            )
            connection.executemany(
                "UPDATE assets SET payload=? WHERE id=?",
                [(_json(raw), aid) for aid, raw in metadata["assets"].items()],
            )
            connection.execute("DELETE FROM folders")
            connection.executemany(
                "INSERT INTO folders VALUES (?,?)",
                [(folder, cid) for cid, folder in metadata["folders"].items()],
            )
            connection.execute("DELETE FROM sources")
            connection.executemany(
                "INSERT INTO sources VALUES (?,?,?)",
                [
                    (relative, aid, _stamp(_safe(root, relative)))
                    for relative, aid in plan["sources"].items()
                ],
            )
            # Rejected/corrupt files retain their original binding and quarantine.
            catalog = _load_snapshot(root, connection)
            _prune_empty(root)
            connection.execute(
                "INSERT OR REPLACE INTO settings VALUES ('reclassification_state','complete')"
            )
            connection.execute(
                "INSERT OR REPLACE INTO settings VALUES ('reclassification_version',?)",
                (VERSION,),
            )
        journal["status"] = "complete"
        journal["index_after_sha256"] = _digest(index)
        _save_journal(backup, journal)
        return {
            **plan["summary"],
            "eligible_assets": sum(x["auto_eligible"] for x in catalog.assets),
            "backup": str(backup),
        }
    except Exception:
        if journal is not None:
            _restore(root, backup, journal)
        raise


def main():
    parser = argparse.ArgumentParser(
        description="按核心食物归类本地图库；运行 apply/rollback 前关闭测试工作台"
    )
    parser.add_argument("--root", required=True)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--rollback", metavar="BACKUP")
    args = parser.parse_args()
    if args.rollback and args.apply:
        parser.error("--apply 和 --rollback 不能同时使用")
    result = (
        rollback(args.root, args.rollback)
        if args.rollback
        else reclassify(args.root, apply=args.apply)
    )
    print(_json(result))


if __name__ == "__main__":
    main()
