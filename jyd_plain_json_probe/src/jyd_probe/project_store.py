from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime
import hashlib
import json
import logging
from pathlib import Path
import sqlite3
import threading
from typing import Any, Iterator
import uuid

from .logging_config import log_event


PROJECT_SCHEMA_VERSION = 10
logger = logging.getLogger("jyd_probe.workbench")
MAX_PROJECT_ITEMS = 500

PROJECT_ITEM_STATUSES = {
    "DRAFT",
    "AUDIO_QUEUED",
    "AUDIO_RUNNING",
    "AUDIO_READY",
    "AUDIO_FAILED",
    "COMPOSITION_QUEUED",
    "DIGITAL_HUMAN_RUNNING",
    "VIDEO_MERGING",
    "BASE_VIDEO_READY",
    "POSTPROCESS_RUNNING",
    "COMPOSITION_READY",
    "COMPOSITION_FAILED",
    "VARIANT_QUEUED",
    "VARIANT_RUNNING",
    "VARIANT_READY",
    "VARIANT_FAILED",
}

ACTIVE_ITEM_STATUSES = {
    "AUDIO_QUEUED",
    "AUDIO_RUNNING",
    "COMPOSITION_QUEUED",
    "DIGITAL_HUMAN_RUNNING",
    "VIDEO_MERGING",
    "POSTPROCESS_RUNNING",
    "VARIANT_QUEUED",
    "VARIANT_RUNNING",
}

EDITABLE_ITEM_STATUSES = PROJECT_ITEM_STATUSES - ACTIVE_ITEM_STATUSES
IMAGE_EDITABLE_ITEM_STATUSES = EDITABLE_ITEM_STATUSES

FAILED_ITEM_STATUSES = {
    "AUDIO_FAILED",
    "COMPOSITION_FAILED",
    "VARIANT_FAILED",
}


class ProjectRevisionConflict(ValueError):
    """The caller edited an older project revision."""


def _now() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def _object(value: str | None, default: Any) -> Any:
    if not value:
        return default
    try:
        return json.loads(value)
    except (TypeError, json.JSONDecodeError):
        return default


def _default_subtitles() -> dict[str, Any]:
    return {
        "source": None,
        "raw_cues": [],
        "render_cues": [],
        "bound_audio_asset_id": None,
        "bound_video_asset_id": None,
        "semantic_mapping": {
            "schema": "jyd.semantic-caption-mapping.v1",
            "status": "NOT_REQUESTED",
            "reason_code": None,
            "reason_summary": None,
        },
        "style": {
            "font_id": None,
            "font_size": 15,
            "max_width_ratio": 0.8,
            "max_lines": 1,
            "bottom_offset_ratio": 0.3,
            "transform_y": -0.4,
        },
        "status": "NOT_AVAILABLE",
        "overflow_risk": False,
    }


def _script_sha256(script: str) -> str:
    return hashlib.sha256(script.encode("utf-8")).hexdigest()


def _default_content_analysis(
    script: str,
    *,
    invalidated_reason: str | None = None,
) -> dict[str, Any]:
    now = _now() if invalidated_reason else None
    return {
        "snapshot_schema": "jyd.project-content-analysis.v1",
        "script_sha256": _script_sha256(script),
        "script_length": len(script),
        "overall_status": "NOT_REQUESTED",
        "music_analysis_status": "NOT_REQUESTED",
        "subtitle_analysis_status": "NOT_REQUESTED",
        "music_intent": None,
        "subtitle_units": None,
        "errors": {"music": None, "subtitle": None, "request": None},
        "schema_version": None,
        "prompt_version": None,
        "model": None,
        "provider_request_id": None,
        "provider_attempts": 0,
        "cache_hit": False,
        "cacheable": False,
        "request_count": 0,
        "requested_at": None,
        "analyzed_at": None,
        "invalidated_reason": invalidated_reason,
        "invalidated_at": now,
    }


def _content_analysis_snapshot(value: Any, script: str) -> dict[str, Any]:
    default = _default_content_analysis(script)
    if not isinstance(value, dict):
        return default
    if not value.get("script_sha256"):
        return default
    if value.get("script_sha256") != default["script_sha256"]:
        return _default_content_analysis(script, invalidated_reason="SCRIPT_CHANGED")
    return {**default, **value}


def _default_visual_analysis(
    script: str,
    *,
    invalidated_reason: str | None = None,
    retained_overlays: list[dict[str, Any]] | None = None,
    bound_audio_asset_id: str | None = None,
    raw_cues_sha256: str | None = None,
) -> dict[str, Any]:
    now = _now() if invalidated_reason else None
    overlays = [dict(item) for item in (retained_overlays or [])]
    return {
        "snapshot_schema": "jyd.project-visual-analysis.v1",
        "script_sha256": _script_sha256(script),
        "script_length": len(script),
        "bound_audio_asset_id": bound_audio_asset_id,
        "raw_cues_sha256": raw_cues_sha256,
        "analysis_status": "NOT_REQUESTED",
        "mapping_status": "NOT_REQUESTED",
        "catalog_version": None,
        "candidate_set_sha256": None,
        "candidate_request": None,
        "mapped_candidates": [],
        "decisions": [],
        "recipe": {
            "schema": "jyd.semantic-visual-recipe.v1",
            "catalog_version": None,
            "overlays": overlays,
        },
        "error": None,
        "provider_request_id": None,
        "provider_attempts": 0,
        "cache_hit": False,
        "cacheable": False,
        "request_count": 0,
        "requested_at": None,
        "analyzed_at": None,
        "invalidated_reason": invalidated_reason,
        "invalidated_at": now,
        "revision": 1,
    }


def _raw_cues_sha256(raw_cues: Any) -> str:
    encoded = json.dumps(
        raw_cues if isinstance(raw_cues, list) else [],
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _visual_candidate_set_sha256(candidate_request: Any) -> str:
    candidates = (
        candidate_request.get("candidates", [])
        if isinstance(candidate_request, dict)
        else []
    )
    encoded = json.dumps(
        candidates,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _visual_analysis_snapshot(
    value: Any,
    script: str,
    *,
    current_audio_asset_id: str | None = None,
    current_raw_cues: Any = None,
    validate_media_binding: bool = False,
) -> dict[str, Any]:
    default = _default_visual_analysis(script)
    if not isinstance(value, dict):
        return default
    if value.get("script_sha256") != default["script_sha256"]:
        recipe = value.get("recipe") if isinstance(value.get("recipe"), dict) else {}
        retained = [
            {**dict(item), "requires_review": True}
            for item in recipe.get("overlays", [])
            if isinstance(item, dict)
            and item.get("manual") is True
            and item.get("locked") is True
        ]
        return _default_visual_analysis(
            script,
            invalidated_reason="SCRIPT_CHANGED",
            retained_overlays=retained,
        )
    snapshot = {**default, **value}
    if not isinstance(snapshot.get("recipe"), dict):
        snapshot["recipe"] = default["recipe"]
    if validate_media_binding and snapshot.get("analysis_status") != "NOT_REQUESTED":
        current_cues_hash = _raw_cues_sha256(current_raw_cues)
        if (
            snapshot.get("bound_audio_asset_id") != current_audio_asset_id
            or snapshot.get("raw_cues_sha256") != current_cues_hash
        ):
            recipe = snapshot.get("recipe") if isinstance(snapshot.get("recipe"), dict) else {}
            retained = [
                {**dict(item), "requires_review": True}
                for item in recipe.get("overlays", [])
                if isinstance(item, dict)
                and item.get("manual") is True
                and item.get("locked") is True
            ]
            return _default_visual_analysis(
                script,
                invalidated_reason="AUDIO_OR_RAW_CUES_CHANGED",
                retained_overlays=retained,
                bound_audio_asset_id=current_audio_asset_id,
                raw_cues_sha256=current_cues_hash,
            )
    return snapshot


def _analysis_overall_status(music_status: str, subtitle_status: str) -> str:
    success_count = sum(
        status == "SUCCESS" for status in (music_status, subtitle_status)
    )
    if success_count == 2:
        return "SUCCESS"
    if success_count == 1:
        return "PARTIAL"
    return "FAILED"


def _invalidate_auto_music_selection(
    settings: dict[str, Any], reason_code: str
) -> dict[str, Any]:
    postprocess = settings.get("postprocess")
    if not isinstance(postprocess, dict) or postprocess.get("bgm_selection_mode") != "auto":
        return settings
    postprocess = dict(postprocess)
    previous_identity = str(postprocess.get("bgm_identity") or "").strip()
    previous_selection = postprocess.get("music_selection")
    if reason_code == "AUDIO_VERSION_CHANGED" and previous_identity:
        postprocess["music_selection"] = {
            **(
                dict(previous_selection)
                if isinstance(previous_selection, dict)
                else {}
            ),
            "schema": "jyd.project-music-selection.v1",
            "status": "STALE",
            "selection_source": "ai",
            "bgm_identity": previous_identity,
            "audio_asset_id": None,
            "video_duration_us": 0,
            "reason_code": reason_code,
            "reason_summary": "声音版本已变化，保留当前推荐并在成片前按真实时长复核",
        }
    else:
        postprocess["bgm_identity"] = ""
        postprocess["music_selection"] = {
            "schema": "jyd.project-music-selection.v1",
            "status": "NOT_REQUESTED",
            "selection_source": "ai",
            "bgm_identity": None,
            "reason_code": reason_code,
        }
    settings["postprocess"] = postprocess
    return settings


def _clean_name(value: Any) -> str:
    result = str(value or "").strip()
    if not result:
        raise ValueError("项目名称不能为空")
    if len(result) > 120:
        raise ValueError("项目名称不能超过 120 个字符")
    return result


def _clean_row_key(value: Any, position: int) -> str:
    result = str(value or "").strip() or f"{position:03d}"
    if len(result) > 80:
        raise ValueError("脚本行编号不能超过 80 个字符")
    return result


def _clean_script(value: Any) -> str:
    result = str(value or "").strip()
    if not result:
        raise ValueError("脚本内容不能为空")
    if len(result) > 50_000:
        raise ValueError("单条脚本不能超过 50000 个字符")
    return result


def _clean_status(value: Any, *, allowed: set[str], label: str) -> str:
    result = str(value or "").strip().upper()
    if result not in allowed:
        raise ValueError(f"{label}无效: {result}")
    return result


class ProjectStore:
    """Unified project data stored beside the existing render queue.

    This store creates only `project_*` tables. It deliberately leaves the
    existing render queue's `schema_meta`, `batches`, `jobs`, and `agents`
    untouched so an existing installation can adopt the new workspace without
    migrating or rewriting old Jianying tasks.
    """

    def __init__(self, path: str | Path):
        self.path = Path(path).expanduser().resolve()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._schema_lock = threading.Lock()
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=30, isolation_level=None)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA busy_timeout = 30000")
        return connection

    @contextmanager
    def _transaction(self) -> Iterator[sqlite3.Connection]:
        connection = self._connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            yield connection
            connection.commit()
        except BaseException:
            connection.rollback()
            raise
        finally:
            connection.close()

    def _initialize(self) -> None:
        with self._schema_lock, self._connect() as connection:
            connection.execute("PRAGMA journal_mode = WAL")
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS project_schema_meta (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS project_counters (
                    day_key TEXT PRIMARY KEY,
                    last_value INTEGER NOT NULL
                );

                CREATE TABLE IF NOT EXISTS projects (
                    project_id TEXT PRIMARY KEY,
                    project_no TEXT NOT NULL UNIQUE,
                    owner_user_id TEXT NOT NULL,
                    owner_username TEXT NOT NULL DEFAULT '',
                    name TEXT NOT NULL,
                    status TEXT NOT NULL,
                    revision INTEGER NOT NULL DEFAULT 1,
                    settings_json TEXT NOT NULL DEFAULT '{}',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_projects_owner_updated
                    ON projects(owner_user_id, updated_at DESC);

                CREATE TABLE IF NOT EXISTS project_items (
                    item_id TEXT PRIMARY KEY,
                    project_id TEXT NOT NULL,
                    row_key TEXT NOT NULL,
                    position INTEGER NOT NULL,
                    script_text TEXT NOT NULL,
                    status TEXT NOT NULL,
                    current_image_asset_id TEXT,
                    current_audio_asset_id TEXT,
                    current_base_video_asset_id TEXT,
                    current_video_asset_id TEXT,
                    subtitles_json TEXT NOT NULL DEFAULT '{}',
                    content_analysis_json TEXT NOT NULL DEFAULT '{}',
                    visual_analysis_json TEXT NOT NULL DEFAULT '{}',
                    settings_json TEXT NOT NULL DEFAULT '{}',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY(project_id) REFERENCES projects(project_id)
                        ON DELETE CASCADE,
                    UNIQUE(project_id, row_key),
                    UNIQUE(project_id, position)
                );

                CREATE INDEX IF NOT EXISTS idx_project_items_project
                    ON project_items(project_id, position);

                CREATE TABLE IF NOT EXISTS project_assets (
                    asset_id TEXT PRIMARY KEY,
                    project_id TEXT NOT NULL,
                    item_id TEXT NOT NULL,
                    asset_type TEXT NOT NULL,
                    version INTEGER NOT NULL,
                    status TEXT NOT NULL,
                    source_type TEXT NOT NULL,
                    filename TEXT NOT NULL DEFAULT '',
                    managed_path TEXT,
                    external_ref_json TEXT NOT NULL DEFAULT '{}',
                    metadata_json TEXT NOT NULL DEFAULT '{}',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY(project_id) REFERENCES projects(project_id)
                        ON DELETE CASCADE,
                    FOREIGN KEY(item_id) REFERENCES project_items(item_id)
                        ON DELETE CASCADE,
                    UNIQUE(item_id, asset_type, version)
                );

                CREATE INDEX IF NOT EXISTS idx_project_assets_item_type
                    ON project_assets(item_id, asset_type, version);

                CREATE TABLE IF NOT EXISTS project_input_images (
                    image_id TEXT PRIMARY KEY,
                    project_id TEXT NOT NULL,
                    position INTEGER NOT NULL,
                    filename TEXT NOT NULL,
                    content_type TEXT NOT NULL,
                    size_bytes INTEGER NOT NULL,
                    sha256 TEXT NOT NULL,
                    managed_path TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(project_id) REFERENCES projects(project_id)
                        ON DELETE CASCADE,
                    UNIQUE(project_id, position)
                );

                CREATE INDEX IF NOT EXISTS idx_project_input_images_project
                    ON project_input_images(project_id, position);

                CREATE TABLE IF NOT EXISTS project_script_sources (
                    source_id TEXT PRIMARY KEY,
                    project_id TEXT NOT NULL,
                    version INTEGER NOT NULL,
                    filename TEXT NOT NULL,
                    content_type TEXT NOT NULL,
                    size_bytes INTEGER NOT NULL,
                    sha256 TEXT NOT NULL,
                    managed_path TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(project_id) REFERENCES projects(project_id)
                        ON DELETE CASCADE,
                    UNIQUE(project_id, version)
                );

                CREATE INDEX IF NOT EXISTS idx_project_script_sources_project
                    ON project_script_sources(project_id, version DESC);

                CREATE TABLE IF NOT EXISTS project_result_batch_counters (
                    day_key TEXT PRIMARY KEY,
                    last_value INTEGER NOT NULL
                );

                CREATE TABLE IF NOT EXISTS project_result_batches (
                    result_batch_id TEXT PRIMARY KEY,
                    project_id TEXT NOT NULL,
                    owner_user_id TEXT NOT NULL,
                    date_key TEXT NOT NULL,
                    date_label TEXT NOT NULL,
                    batch_no INTEGER NOT NULL,
                    export_path TEXT NOT NULL,
                    operation_type TEXT NOT NULL,
                    status TEXT NOT NULL,
                    jianying_batch_id TEXT NOT NULL DEFAULT '',
                    error_message TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY(project_id) REFERENCES projects(project_id)
                        ON DELETE CASCADE,
                    UNIQUE(date_key, batch_no)
                );

                CREATE INDEX IF NOT EXISTS idx_project_result_batches_owner
                    ON project_result_batches(owner_user_id, date_key DESC, batch_no DESC);

                CREATE TABLE IF NOT EXISTS project_operations (
                    operation_id TEXT PRIMARY KEY,
                    correlation_id TEXT NOT NULL,
                    project_id TEXT NOT NULL,
                    item_id TEXT,
                    operation_type TEXT NOT NULL,
                    status TEXT NOT NULL,
                    idempotency_key TEXT NOT NULL,
                    attempt_count INTEGER NOT NULL DEFAULT 0,
                    error_code TEXT,
                    error_message TEXT,
                    payload_json TEXT NOT NULL DEFAULT '{}',
                    result_json TEXT NOT NULL DEFAULT '{}',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    started_at TEXT,
                    finished_at TEXT,
                    FOREIGN KEY(project_id) REFERENCES projects(project_id)
                        ON DELETE CASCADE,
                    FOREIGN KEY(item_id) REFERENCES project_items(item_id)
                        ON DELETE CASCADE
                );

                CREATE UNIQUE INDEX IF NOT EXISTS idx_project_operations_idempotency
                    ON project_operations(
                        project_id,
                        IFNULL(item_id, ''),
                        operation_type,
                        idempotency_key
                    );

                CREATE INDEX IF NOT EXISTS idx_project_operations_status
                    ON project_operations(status, created_at);

                CREATE TABLE IF NOT EXISTS project_links (
                    link_id TEXT PRIMARY KEY,
                    project_id TEXT NOT NULL,
                    item_id TEXT,
                    system TEXT NOT NULL,
                    relation TEXT NOT NULL,
                    external_id TEXT NOT NULL,
                    metadata_json TEXT NOT NULL DEFAULT '{}',
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(project_id) REFERENCES projects(project_id)
                        ON DELETE CASCADE,
                    FOREIGN KEY(item_id) REFERENCES project_items(item_id)
                        ON DELETE CASCADE,
                    UNIQUE(project_id, system, relation, external_id)
                );

                CREATE INDEX IF NOT EXISTS idx_project_links_project
                    ON project_links(project_id, system, relation);

                CREATE TABLE IF NOT EXISTS project_user_preferences (
                    owner_user_id TEXT PRIMARY KEY,
                    default_voice_asset_id TEXT,
                    voice_settings_json TEXT NOT NULL DEFAULT '{}',
                    updated_at TEXT NOT NULL
                );
                """
            )
            item_columns = {
                str(row["name"])
                for row in connection.execute("PRAGMA table_info(project_items)").fetchall()
            }
            if "current_image_asset_id" not in item_columns:
                connection.execute(
                    "ALTER TABLE project_items ADD COLUMN current_image_asset_id TEXT"
                )
            if "current_base_video_asset_id" not in item_columns:
                connection.execute(
                    "ALTER TABLE project_items ADD COLUMN current_base_video_asset_id TEXT"
                )
            if "content_analysis_json" not in item_columns:
                connection.execute(
                    "ALTER TABLE project_items ADD COLUMN content_analysis_json TEXT NOT NULL DEFAULT '{}'"
                )
            if "visual_analysis_json" not in item_columns:
                connection.execute(
                    "ALTER TABLE project_items ADD COLUMN visual_analysis_json TEXT NOT NULL DEFAULT '{}'"
                )
            operation_columns = {
                str(row["name"])
                for row in connection.execute(
                    "PRAGMA table_info(project_operations)"
                ).fetchall()
            }
            if "correlation_id" not in operation_columns:
                connection.execute(
                    "ALTER TABLE project_operations ADD COLUMN correlation_id TEXT"
                )
                connection.execute(
                    "UPDATE project_operations SET correlation_id=operation_id "
                    "WHERE correlation_id IS NULL OR correlation_id=''"
                )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_project_operations_correlation "
                "ON project_operations(correlation_id, created_at)"
            )
            connection.execute(
                "INSERT OR REPLACE INTO project_schema_meta(key, value) VALUES('version', ?)",
                (str(PROJECT_SCHEMA_VERSION),),
            )

    def create_project(
        self,
        *,
        owner_user_id: str,
        owner_username: str,
        name: str,
        items: list[dict[str, Any]],
        settings: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        owner_id = str(owner_user_id or "").strip()
        if not owner_id:
            raise ValueError("项目必须绑定有效账号")
        project_name = _clean_name(name)
        if not isinstance(items, list) or not items:
            raise ValueError("项目至少需要一条脚本")
        if len(items) > MAX_PROJECT_ITEMS:
            raise ValueError(f"单个项目最多包含 {MAX_PROJECT_ITEMS} 条脚本")

        normalized_items: list[dict[str, Any]] = []
        row_keys: set[str] = set()
        for position, raw in enumerate(items, start=1):
            if not isinstance(raw, dict):
                raise ValueError(f"第 {position} 条脚本格式无效")
            row_key = _clean_row_key(raw.get("row_key"), position)
            if row_key in row_keys:
                raise ValueError(f"脚本行编号重复: {row_key}")
            row_keys.add(row_key)
            normalized_items.append(
                {
                    "item_id": uuid.uuid4().hex,
                    "row_key": row_key,
                    "position": position,
                    "script_text": _clean_script(raw.get("script_text")),
                    "settings": raw.get("settings")
                    if isinstance(raw.get("settings"), dict)
                    else {},
                }
            )

        project_id = uuid.uuid4().hex
        now = _now()
        with self._transaction() as connection:
            project_no = self._next_project_no(connection)
            connection.execute(
                """
                INSERT INTO projects(
                    project_id, project_no, owner_user_id, owner_username,
                    name, status, revision, settings_json, created_at, updated_at
                ) VALUES(?, ?, ?, ?, ?, 'DRAFT', 1, ?, ?, ?)
                """,
                (
                    project_id,
                    project_no,
                    owner_id,
                    str(owner_username or "").strip()[:120],
                    project_name,
                    _json(settings or {}),
                    now,
                    now,
                ),
            )
            for item in normalized_items:
                connection.execute(
                    """
                    INSERT INTO project_items(
                        item_id, project_id, row_key, position, script_text,
                        status, subtitles_json, content_analysis_json, settings_json,
                        created_at, updated_at
                    ) VALUES(?, ?, ?, ?, ?, 'DRAFT', ?, ?, ?, ?, ?)
                    """,
                    (
                        item["item_id"],
                        project_id,
                        item["row_key"],
                        item["position"],
                        item["script_text"],
                        _json(_default_subtitles()),
                        _json(_default_content_analysis(item["script_text"])),
                        _json(item["settings"]),
                        now,
                        now,
                    ),
                )
        return self.get_project(owner_id, project_id)

    def list_projects(
        self,
        owner_user_id: str,
        *,
        limit: int = 50,
        offset: int = 0,
    ) -> dict[str, Any]:
        owner_id = str(owner_user_id or "").strip()
        safe_limit = min(max(int(limit), 1), 100)
        safe_offset = max(int(offset), 0)
        with self._connect() as connection:
            total = int(
                connection.execute(
                    "SELECT COUNT(*) FROM projects WHERE owner_user_id=?",
                    (owner_id,),
                ).fetchone()[0]
            )
            rows = connection.execute(
                """
                SELECT project_id FROM projects
                WHERE owner_user_id=?
                ORDER BY updated_at DESC, created_at DESC
                LIMIT ? OFFSET ?
                """,
                (owner_id, safe_limit, safe_offset),
            ).fetchall()
            projects = [
                self._project_payload(connection, row["project_id"])
                for row in rows
            ]
        return {
            "schema": "jyd.project-list.v1",
            "total": total,
            "limit": safe_limit,
            "offset": safe_offset,
            "projects": projects,
        }

    def get_project(self, owner_user_id: str, project_id: str) -> dict[str, Any]:
        with self._connect() as connection:
            row = self._owned_project(connection, owner_user_id, project_id)
            return self._project_payload(connection, row["project_id"])

    def update_project(
        self,
        owner_user_id: str,
        project_id: str,
        *,
        name: str | None = None,
        settings: dict[str, Any] | None = None,
        expected_revision: int | None = None,
    ) -> dict[str, Any]:
        with self._transaction() as connection:
            project = self._owned_project(connection, owner_user_id, project_id)
            if expected_revision is not None and int(expected_revision) != int(
                project["revision"]
            ):
                raise ProjectRevisionConflict("项目已被其他操作更新，请刷新后重试")
            updates: list[str] = []
            values: list[Any] = []
            if name is not None:
                updates.append("name=?")
                values.append(_clean_name(name))
            if settings is not None:
                if not isinstance(settings, dict):
                    raise ValueError("项目设置必须是对象")
                updates.append("settings_json=?")
                values.append(_json(settings))
            if updates:
                updates.extend(["revision=revision+1", "updated_at=?"])
                values.extend([_now(), project_id])
                connection.execute(
                    f"UPDATE projects SET {', '.join(updates)} WHERE project_id=?",
                    values,
                )
        return self.get_project(owner_user_id, project_id)

    def update_item(
        self,
        owner_user_id: str,
        project_id: str,
        item_id: str,
        *,
        row_key: str | None = None,
        script_text: str | None = None,
        settings: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        with self._transaction() as connection:
            project = self._owned_project(connection, owner_user_id, project_id)
            item = self._owned_item(connection, project_id, item_id)
            if item["status"] in ACTIVE_ITEM_STATUSES:
                raise ValueError("当前脚本行正在生成，请等待完成后再修改")
            updates: list[str] = []
            values: list[Any] = []
            if row_key is not None:
                clean_row_key = _clean_row_key(row_key, int(item["position"]))
                if clean_row_key != str(item["row_key"]):
                    updates.append("row_key=?")
                    values.append(clean_row_key)
            content_changed = False
            script_changed = False
            if script_text is not None:
                clean_script = _clean_script(script_text)
                if clean_script != str(item["script_text"]):
                    updates.append("script_text=?")
                    values.append(clean_script)
                    content_changed = True
                    script_changed = True
            if settings is not None:
                if not isinstance(settings, dict):
                    raise ValueError("脚本行设置必须是对象")
                if settings != _object(item["settings_json"], {}):
                    updates.append("settings_json=?")
                    values.append(_json(settings))
                    content_changed = True
            if updates:
                now = _now()
                if content_changed:
                    updates.extend(
                        [
                            "current_audio_asset_id=NULL",
                            "current_base_video_asset_id=NULL",
                            "current_video_asset_id=NULL",
                            "subtitles_json=?",
                            "status='DRAFT'",
                        ]
                    )
                    values.append(_json(_default_subtitles()))
                if script_changed:
                    updates.append("content_analysis_json=?")
                    values.append(
                        _json(
                            _default_content_analysis(
                                clean_script,
                                invalidated_reason="SCRIPT_CHANGED",
                            )
                        )
                    )
                    current_visual = _visual_analysis_snapshot(
                        _object(item["visual_analysis_json"], {}),
                        str(item["script_text"]),
                    )
                    retained_overlays = [
                        {**dict(overlay), "requires_review": True}
                        for overlay in current_visual.get("recipe", {}).get(
                            "overlays", []
                        )
                        if isinstance(overlay, dict)
                        and overlay.get("manual") is True
                        and overlay.get("locked") is True
                    ]
                    updates.append("visual_analysis_json=?")
                    values.append(
                        _json(
                            _default_visual_analysis(
                                clean_script,
                                invalidated_reason="SCRIPT_CHANGED",
                                retained_overlays=retained_overlays,
                            )
                        )
                    )
                    if settings is None:
                        invalidated_settings = _invalidate_auto_music_selection(
                            _object(item["settings_json"], {}), "SCRIPT_CHANGED"
                        )
                        updates.append("settings_json=?")
                        values.append(_json(invalidated_settings))
                updates.append("updated_at=?")
                values.extend([now, item_id])
                try:
                    connection.execute(
                        f"UPDATE project_items SET {', '.join(updates)} WHERE item_id=?",
                        values,
                    )
                except sqlite3.IntegrityError as exc:
                    raise ValueError("脚本行编号不能重复") from exc
                connection.execute(
                    """
                    UPDATE projects
                    SET revision=revision+1, updated_at=?
                    WHERE project_id=?
                    """,
                    (now, project["project_id"]),
                )
                self._refresh_project_status(connection, project_id, now=now)
        return self.get_project(owner_user_id, project_id)

    def delete_item(
        self,
        owner_user_id: str,
        project_id: str,
        item_id: str,
    ) -> tuple[dict[str, Any], list[str]]:
        """Remove one inactive project row and its item-owned local assets."""

        cleanup_candidates: set[str] = set()
        with self._transaction() as connection:
            project = self._owned_project(connection, owner_user_id, project_id)
            item = self._owned_item(connection, project_id, item_id)
            if str(item["status"]) in ACTIVE_ITEM_STATUSES:
                raise ValueError("当前任务正在生成，请等待完成后再删除")
            analysis = _content_analysis_snapshot(
                _object(item["content_analysis_json"], {}),
                str(item["script_text"]),
            )
            if str(analysis.get("overall_status") or "") == "PENDING":
                raise ValueError("当前任务正在进行内容分析，请等待完成后再删除")
            visual_analysis = _visual_analysis_snapshot(
                _object(item["visual_analysis_json"], {}),
                str(item["script_text"]),
            )
            if str(visual_analysis.get("analysis_status") or "") == "PENDING":
                raise ValueError("当前任务正在进行语义视觉分析，请等待完成后再删除")
            active_operation = connection.execute(
                """
                SELECT 1 FROM project_operations
                WHERE item_id=? AND status IN ('PENDING', 'RUNNING')
                LIMIT 1
                """,
                (item_id,),
            ).fetchone()
            if active_operation is not None:
                raise ValueError("当前任务仍有异步操作，请等待完成后再删除")

            cleanup_candidates.update(
                str(row["managed_path"])
                for row in connection.execute(
                    """
                    SELECT managed_path FROM project_assets
                    WHERE item_id=? AND asset_type!='input_image'
                      AND managed_path IS NOT NULL AND managed_path!=''
                    """,
                    (item_id,),
                ).fetchall()
            )
            connection.execute("DELETE FROM project_items WHERE item_id=?", (item_id,))

            remaining = connection.execute(
                "SELECT item_id FROM project_items WHERE project_id=? ORDER BY position",
                (project_id,),
            ).fetchall()
            for offset, row in enumerate(remaining, start=1):
                connection.execute(
                    "UPDATE project_items SET position=? WHERE item_id=?",
                    (-offset, row["item_id"]),
                )
            for position, row in enumerate(remaining, start=1):
                connection.execute(
                    "UPDATE project_items SET position=? WHERE item_id=?",
                    (position, row["item_id"]),
                )

            cleanup_paths = [
                path
                for path in sorted(cleanup_candidates)
                if connection.execute(
                    "SELECT 1 FROM project_assets WHERE managed_path=? LIMIT 1",
                    (path,),
                ).fetchone()
                is None
            ]
            now = _now()
            connection.execute(
                """
                UPDATE projects
                SET revision=revision+1, updated_at=?
                WHERE project_id=?
                """,
                (now, project["project_id"]),
            )
            self._refresh_project_status(connection, project_id, now=now)
        return self.get_project(owner_user_id, project_id), cleanup_paths

    def get_voice_preferences(self, owner_user_id: str) -> dict[str, Any]:
        owner_id = str(owner_user_id or "").strip()
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM project_user_preferences WHERE owner_user_id=?",
                (owner_id,),
            ).fetchone()
        if row is None:
            return {
                "default_voice_asset_id": None,
                "voice_settings": {
                    "model": "speech-2.8-hd",
                    "speed": 1.0,
                    "volume": 1.0,
                    "pitch": 0,
                    "language_boost": "Chinese",
                    "output_format": "mp3",
                },
            }
        return {
            "default_voice_asset_id": row["default_voice_asset_id"],
            "voice_settings": _object(row["voice_settings_json"], {}),
        }

    def set_voice_preferences(
        self,
        owner_user_id: str,
        *,
        default_voice_asset_id: str,
        voice_settings: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        owner_id = str(owner_user_id or "").strip()
        voice_id = str(default_voice_asset_id or "").strip()
        if not owner_id or not voice_id:
            raise ValueError("默认声音编号不能为空")
        if voice_settings is not None and not isinstance(voice_settings, dict):
            raise ValueError("声音参数必须是对象")
        current = self.get_voice_preferences(owner_id)
        resolved_settings = (
            voice_settings
            if voice_settings is not None
            else current["voice_settings"]
        )
        with self._transaction() as connection:
            connection.execute(
                """
                INSERT INTO project_user_preferences(
                    owner_user_id, default_voice_asset_id,
                    voice_settings_json, updated_at
                ) VALUES(?, ?, ?, ?)
                ON CONFLICT(owner_user_id) DO UPDATE SET
                    default_voice_asset_id=excluded.default_voice_asset_id,
                    voice_settings_json=excluded.voice_settings_json,
                    updated_at=excluded.updated_at
                """,
                (owner_id, voice_id, _json(resolved_settings), _now()),
            )
        return self.get_voice_preferences(owner_id)

    def configure_item_voice(
        self,
        owner_user_id: str,
        project_id: str,
        item_id: str,
        *,
        voice_asset_id: str,
    ) -> dict[str, Any]:
        voice_id = str(voice_asset_id or "").strip()
        if not voice_id:
            raise ValueError("声音原型不能为空")
        with self._transaction() as connection:
            project = self._owned_project(connection, owner_user_id, project_id)
            item = self._owned_item(connection, project_id, item_id)
            settings = _object(item["settings_json"], {})
            if settings.get("voice_asset_id") == voice_id:
                changed = False
            else:
                changed = True
            if changed and item["status"] in ACTIVE_ITEM_STATUSES:
                raise ValueError("当前脚本行正在生成，请等待完成后再更换声音")
            now = _now()
            if changed:
                settings["voice_asset_id"] = voice_id
                settings = _invalidate_auto_music_selection(
                    settings, "AUDIO_VERSION_CHANGED"
                )
            if changed:
                connection.execute(
                    """
                    UPDATE project_items
                    SET settings_json=?, current_audio_asset_id=NULL,
                        current_base_video_asset_id=NULL,
                        current_video_asset_id=NULL, subtitles_json=?,
                        status='DRAFT', updated_at=?
                    WHERE item_id=?
                    """,
                    (_json(settings), _json(_default_subtitles()), now, item_id),
                )
            if changed:
                connection.execute(
                    "UPDATE projects SET revision=revision+1, updated_at=? WHERE project_id=?",
                    (now, project["project_id"]),
                )
                self._refresh_project_status(connection, project_id, now=now)
        return self.get_project(owner_user_id, project_id)

    def configure_project_voice(
        self,
        owner_user_id: str,
        project_id: str,
        *,
        voice_asset_id: str,
    ) -> dict[str, Any]:
        """Atomically apply one saved voice to every item and the user default."""

        voice_id = str(voice_asset_id or "").strip()
        if not voice_id:
            raise ValueError("声音原型不能为空")
        owner_id = str(owner_user_id or "").strip()
        with self._transaction() as connection:
            project = self._owned_project(connection, owner_id, project_id)
            items = connection.execute(
                "SELECT * FROM project_items WHERE project_id=? ORDER BY position",
                (project_id,),
            ).fetchall()
            changed_items = []
            for item in items:
                settings = _object(item["settings_json"], {})
                if settings.get("voice_asset_id") != voice_id:
                    changed_items.append((item, settings))
            blocked = [
                item["row_key"]
                for item, _settings in changed_items
                if item["status"] in ACTIVE_ITEM_STATUSES
            ]
            if blocked:
                raise ValueError(
                    "以下脚本行已进入声音生成，不能批量更换声音："
                    + "、".join(str(value) for value in blocked[:10])
                )

            now = _now()
            for item, settings in changed_items:
                settings["voice_asset_id"] = voice_id
                settings = _invalidate_auto_music_selection(
                    settings, "AUDIO_VERSION_CHANGED"
                )
                connection.execute(
                    """
                    UPDATE project_items
                    SET settings_json=?, current_audio_asset_id=NULL,
                        current_base_video_asset_id=NULL,
                        current_video_asset_id=NULL, subtitles_json=?,
                        status='DRAFT', updated_at=?
                    WHERE item_id=?
                    """,
                    (_json(settings), _json(_default_subtitles()), now, item["item_id"]),
                )

            project_settings = _object(project["settings_json"], {})
            project_default_changed = (
                project_settings.get("default_voice_asset_id") != voice_id
            )
            project_settings["default_voice_asset_id"] = voice_id
            connection.execute(
                """
                INSERT INTO project_user_preferences(
                    owner_user_id, default_voice_asset_id,
                    voice_settings_json, updated_at
                ) VALUES(?, ?, ?, ?)
                ON CONFLICT(owner_user_id) DO UPDATE SET
                    default_voice_asset_id=excluded.default_voice_asset_id,
                    updated_at=excluded.updated_at
                """,
                (
                    owner_id,
                    voice_id,
                    _json(
                        {
                            "model": "speech-2.8-hd",
                            "speed": 1.0,
                            "volume": 1.0,
                            "pitch": 0,
                            "language_boost": "Chinese",
                            "output_format": "mp3",
                        }
                    ),
                    now,
                ),
            )
            if changed_items or project_default_changed:
                connection.execute(
                    """
                    UPDATE projects
                    SET settings_json=?, revision=revision+1, updated_at=?
                    WHERE project_id=?
                    """,
                    (_json(project_settings), now, project_id),
                )
                self._refresh_project_status(connection, project_id, now=now)
        return self.get_project(owner_id, project_id)

    def projects_using_voice(
        self, owner_user_id: str, voice_asset_id: str
    ) -> list[dict[str, str]]:
        """Return current projects whose default or item settings select a voice."""

        owner_id = str(owner_user_id or "").strip()
        voice_id = str(voice_asset_id or "").strip()
        if not owner_id or not voice_id:
            return []
        used: dict[str, dict[str, str]] = {}
        with self._connect() as connection:
            projects = connection.execute(
                "SELECT project_id, project_no, name, settings_json "
                "FROM projects WHERE owner_user_id=?",
                (owner_id,),
            ).fetchall()
            for project in projects:
                settings = _object(project["settings_json"], {})
                if settings.get("default_voice_asset_id") == voice_id:
                    used[project["project_id"]] = {
                        "project_id": project["project_id"],
                        "project_no": project["project_no"],
                        "name": project["name"],
                    }
            rows = connection.execute(
                """
                SELECT p.project_id, p.project_no, p.name, i.settings_json
                FROM projects p
                JOIN project_items i ON i.project_id=p.project_id
                WHERE p.owner_user_id=?
                """,
                (owner_id,),
            ).fetchall()
            for row in rows:
                settings = _object(row["settings_json"], {})
                if settings.get("voice_asset_id") == voice_id:
                    used[row["project_id"]] = {
                        "project_id": row["project_id"],
                        "project_no": row["project_no"],
                        "name": row["name"],
                    }
        return list(used.values())

    def prepare_item_audio_generation(
        self, owner_user_id: str, project_id: str, item_id: str
    ) -> dict[str, Any]:
        """Start a new audio version without deleting any historical assets."""

        with self._transaction() as connection:
            project = self._owned_project(connection, owner_user_id, project_id)
            item = self._owned_item(connection, project_id, item_id)
            if item["status"] in ACTIVE_ITEM_STATUSES:
                raise ValueError("当前脚本行正在生成，不能创建新的声音任务")
            settings = _invalidate_auto_music_selection(
                _object(item["settings_json"], {}), "AUDIO_VERSION_CHANGED"
            )
            now = _now()
            connection.execute(
                """
                UPDATE project_items
                SET settings_json=?, current_audio_asset_id=NULL,
                    current_base_video_asset_id=NULL,
                    current_video_asset_id=NULL,
                    subtitles_json=?, status='DRAFT', updated_at=?
                WHERE item_id=?
                """,
                (_json(settings), _json(_default_subtitles()), now, item_id),
            )
            connection.execute(
                """
                UPDATE projects
                SET revision=revision+1, updated_at=?
                WHERE project_id=?
                """,
                (now, project["project_id"]),
            )
            self._refresh_project_status(connection, project_id, now=now)
        return self.get_project(owner_user_id, project_id)

    def configure_item_postprocess(
        self,
        owner_user_id: str,
        project_id: str,
        item_id: str,
        *,
        font_identity: str,
        bgm_identity: str,
        text_color: str,
        bgm_selection_mode: str = "manual",
        music_selection: dict[str, Any] | None = None,
        force_invalidate: bool = False,
    ) -> dict[str, Any]:
        """Save editable subtitle/BGM settings and invalidate only final rendering."""

        clean_font = str(font_identity or "").strip()
        clean_bgm = str(bgm_identity or "").strip()
        clean_bgm_mode = str(bgm_selection_mode or "manual").strip().lower()
        clean_color = str(text_color or "#FFFFFF").strip().upper()
        if not clean_font:
            raise ValueError("字幕字体不能为空")
        if len(clean_color) != 7 or not clean_color.startswith("#"):
            raise ValueError("字幕颜色格式不正确")
        if clean_bgm_mode not in {"auto", "manual"}:
            raise ValueError("BGM 选择模式只能是 auto 或 manual")
        if music_selection is not None and not isinstance(music_selection, dict):
            raise ValueError("音乐选择快照必须是对象")
        with self._transaction() as connection:
            project = self._owned_project(connection, owner_user_id, project_id)
            item = self._owned_item(connection, project_id, item_id)
            if item["status"] in ACTIVE_ITEM_STATUSES:
                raise ValueError("当前脚本行正在生成，请等待完成后再修改字幕或 BGM")
            settings = _object(item["settings_json"], {})
            requested = {
                "font_identity": clean_font,
                "bgm_identity": clean_bgm,
                "bgm_selection_mode": clean_bgm_mode,
                "text_color": clean_color,
            }
            if music_selection is not None:
                requested["music_selection"] = music_selection
            elif clean_bgm_mode == "manual":
                requested["music_selection"] = {
                    "schema": "jyd.project-music-selection.v1",
                    "status": "MANUAL",
                    "selection_source": "manual",
                    "bgm_identity": clean_bgm or None,
                    "reason_code": (
                        "USER_SELECTED" if clean_bgm else "USER_SELECTED_NONE"
                    ),
                }
            else:
                requested["music_selection"] = {
                    "schema": "jyd.project-music-selection.v1",
                    "status": "NOT_REQUESTED",
                    "selection_source": "ai",
                    "bgm_identity": None,
                    "reason_code": "WAITING_FOR_4B",
                }
            if settings.get("postprocess") == requested and not force_invalidate:
                return self.get_project(owner_user_id, project_id)
            settings["postprocess"] = requested
            subtitles = _object(item["subtitles_json"], _default_subtitles())
            subtitles["render_cues"] = []
            subtitles["bound_video_asset_id"] = None
            subtitles["overflow_risk"] = False
            subtitles["review_reason"] = None
            subtitles["status"] = (
                "READY" if subtitles.get("raw_cues") else "NOT_AVAILABLE"
            )
            next_status = "DRAFT"
            if item["current_base_video_asset_id"]:
                next_status = "BASE_VIDEO_READY"
            elif item["current_audio_asset_id"]:
                next_status = "AUDIO_READY"
            now = _now()
            connection.execute(
                """
                UPDATE project_items
                SET settings_json=?, current_video_asset_id=NULL,
                    subtitles_json=?, status=?, updated_at=?
                WHERE item_id=?
                """,
                (_json(settings), _json(subtitles), next_status, now, item_id),
            )
            connection.execute(
                """
                UPDATE projects
                SET revision=revision+1, updated_at=?
                WHERE project_id=?
                """,
                (now, project["project_id"]),
            )
            self._refresh_project_status(connection, project_id, now=now)
        return self.get_project(owner_user_id, project_id)

    def save_item_auto_music_selection(
        self,
        owner_user_id: str,
        project_id: str,
        item_id: str,
        *,
        expected_script_sha256: str,
        bgm_identity: str,
        music_selection: dict[str, Any],
    ) -> bool:
        """Persist an AI Top1 choice without overwriting an explicit manual choice."""

        clean_bgm = str(bgm_identity or "").strip()
        if not isinstance(music_selection, dict):
            raise ValueError("音乐选择快照必须是对象")
        with self._transaction() as connection:
            project = self._owned_project(connection, owner_user_id, project_id)
            item = self._owned_item(connection, project_id, item_id)
            script = str(item["script_text"])
            if _script_sha256(script) != expected_script_sha256:
                return False
            settings = _object(item["settings_json"], {})
            current = settings.get("postprocess")
            postprocess = dict(current) if isinstance(current, dict) else {}
            if postprocess.get("bgm_selection_mode") == "manual":
                return False
            previous_identity = str(postprocess.get("bgm_identity") or "").strip()
            postprocess.update(
                {
                    "bgm_identity": clean_bgm,
                    "bgm_selection_mode": "auto",
                    "music_selection": dict(music_selection),
                }
            )
            if current == postprocess:
                return True
            settings["postprocess"] = postprocess
            now = _now()
            if (
                previous_identity != clean_bgm
                and item["current_video_asset_id"]
                and item["status"] not in ACTIVE_ITEM_STATUSES
            ):
                subtitles = _object(item["subtitles_json"], _default_subtitles())
                subtitles["render_cues"] = []
                subtitles["bound_video_asset_id"] = None
                subtitles["overflow_risk"] = False
                subtitles["review_reason"] = None
                subtitles["status"] = (
                    "READY" if subtitles.get("raw_cues") else "NOT_AVAILABLE"
                )
                next_status = (
                    "BASE_VIDEO_READY"
                    if item["current_base_video_asset_id"]
                    else ("AUDIO_READY" if item["current_audio_asset_id"] else "DRAFT")
                )
                connection.execute(
                    """
                    UPDATE project_items
                    SET settings_json=?, current_video_asset_id=NULL,
                        subtitles_json=?, status=?, updated_at=?
                    WHERE item_id=?
                    """,
                    (_json(settings), _json(subtitles), next_status, now, item_id),
                )
            else:
                connection.execute(
                    "UPDATE project_items SET settings_json=?, updated_at=? WHERE item_id=?",
                    (_json(settings), now, item_id),
                )
            connection.execute(
                "UPDATE projects SET revision=revision+1, updated_at=? WHERE project_id=?",
                (now, project["project_id"]),
            )
            self._refresh_project_status(connection, project_id, now=now)
        return True

    def configure_variant_settings(
        self,
        owner_user_id: str,
        project_id: str,
        *,
        settings: dict[str, Any] | None,
        items: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Persist module-6 counts and manual covers without invalidating media."""

        if settings is not None and not isinstance(settings, dict):
            raise ValueError("变体设置必须是对象")
        if not isinstance(items, list) or not all(isinstance(item, dict) for item in items):
            raise ValueError("逐行变体设置格式不正确")
        with self._transaction() as connection:
            project = self._owned_project(connection, owner_user_id, project_id)
            active = connection.execute(
                "SELECT COUNT(*) FROM project_items WHERE project_id=? AND status IN (?, ?)",
                (project_id, "VARIANT_QUEUED", "VARIANT_RUNNING"),
            ).fetchone()[0]
            if active:
                raise ValueError("当前变体任务正在生成，不能修改设置")
            project_settings = _object(project["settings_json"], {})
            if settings is not None:
                project_settings["variants"] = settings
            for raw in items:
                item_id = str(raw.get("item_id") or "").strip()
                item = self._owned_item(connection, project_id, item_id)
                count = int(raw.get("count") or 0)
                if not 1 <= count <= MAX_PROJECT_ITEMS:
                    raise ValueError("每行变体数量必须在 1 到 500 之间")
                cover = raw.get("cover")
                if cover is not None and not isinstance(cover, dict):
                    raise ValueError("手动封面设置必须是对象")
                item_settings = _object(item["settings_json"], {})
                item_settings["variants"] = {"count": count, "cover": cover}
                connection.execute(
                    "UPDATE project_items SET settings_json=?, updated_at=? WHERE item_id=?",
                    (_json(item_settings), _now(), item_id),
                )
            now = _now()
            connection.execute(
                "UPDATE projects SET settings_json=?, revision=revision+1, updated_at=? WHERE project_id=?",
                (_json(project_settings), now, project_id),
            )
        return self.get_project(owner_user_id, project_id)

    def add_asset(
        self,
        *,
        owner_user_id: str,
        project_id: str,
        item_id: str,
        asset_type: str,
        source_type: str,
        status: str,
        filename: str = "",
        managed_path: str | None = None,
        external_ref: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
        make_current: bool = False,
    ) -> dict[str, Any]:
        clean_type = str(asset_type or "").strip().lower()
        if not clean_type:
            raise ValueError("素材类型不能为空")
        clean_source = str(source_type or "").strip().lower()
        if not clean_source:
            raise ValueError("素材来源不能为空")
        clean_status = str(status or "").strip().upper()
        if not clean_status:
            raise ValueError("素材状态不能为空")

        asset_id = uuid.uuid4().hex
        now = _now()
        with self._transaction() as connection:
            self._owned_project(connection, owner_user_id, project_id)
            item = self._owned_item(connection, project_id, item_id)
            version = int(
                connection.execute(
                    """
                    SELECT COALESCE(MAX(version), 0) + 1
                    FROM project_assets
                    WHERE item_id=? AND asset_type=?
                    """,
                    (item_id, clean_type),
                ).fetchone()[0]
            )
            connection.execute(
                """
                INSERT INTO project_assets(
                    asset_id, project_id, item_id, asset_type, version,
                    status, source_type, filename, managed_path,
                    external_ref_json, metadata_json, created_at, updated_at
                ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    asset_id,
                    project_id,
                    item_id,
                    clean_type,
                    version,
                    clean_status,
                    clean_source,
                    str(filename or "").strip()[:255],
                    str(managed_path).strip() if managed_path else None,
                    _json(external_ref or {}),
                    _json(metadata or {}),
                    now,
                    now,
                ),
            )
            if make_current:
                self._set_current_asset(
                    connection,
                    item,
                    asset_id=asset_id,
                    asset_type=clean_type,
                    source_type=clean_source,
                    asset_status=clean_status,
                    now=now,
                )
            self._refresh_project_status(connection, project_id, now=now)
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM project_assets WHERE asset_id=?", (asset_id,)
            ).fetchone()
            return self._asset_payload(row)

    def replace_inputs(
        self,
        owner_user_id: str,
        project_id: str,
        items: list[dict[str, Any]],
    ) -> dict[str, Any]:
        if not isinstance(items, list) or not items:
            raise ValueError("项目至少需要一条脚本")
        if len(items) > MAX_PROJECT_ITEMS:
            raise ValueError(f"单个项目最多包含 {MAX_PROJECT_ITEMS} 条脚本")
        normalized: list[dict[str, Any]] = []
        row_keys: set[str] = set()
        supplied_ids: set[str] = set()
        for position, raw in enumerate(items, start=1):
            if not isinstance(raw, dict):
                raise ValueError(f"第 {position} 条脚本格式无效")
            item_id = str(raw.get("item_id") or "").strip()
            if item_id and item_id in supplied_ids:
                raise ValueError("同一脚本行不能重复提交")
            if item_id:
                supplied_ids.add(item_id)
            row_key = _clean_row_key(raw.get("row_key"), position)
            if row_key in row_keys:
                raise ValueError(f"脚本行编号重复: {row_key}")
            row_keys.add(row_key)
            normalized.append(
                {
                    "item_id": item_id or uuid.uuid4().hex,
                    "is_new": not bool(item_id),
                    "row_key": row_key,
                    "position": position,
                    "script_text": _clean_script(raw.get("script_text")),
                }
            )

        with self._transaction() as connection:
            project = self._owned_project(connection, owner_user_id, project_id)
            existing_rows = connection.execute(
                "SELECT * FROM project_items WHERE project_id=? ORDER BY position",
                (project_id,),
            ).fetchall()
            if any(str(row["status"]) != "DRAFT" for row in existing_rows):
                raise ValueError("项目已进入生成流程，不能替换脚本输入")
            existing = {str(row["item_id"]): row for row in existing_rows}
            unknown = supplied_ids.difference(existing)
            if unknown:
                raise KeyError("项目脚本行不存在")

            now = _now()
            for offset, row in enumerate(existing_rows, start=1):
                connection.execute(
                    "UPDATE project_items SET row_key=?, position=? WHERE item_id=?",
                    (f"__updating__{row['item_id']}", -offset, row["item_id"]),
                )
            retained = {item["item_id"] for item in normalized if not item["is_new"]}
            for item_id in set(existing).difference(retained):
                connection.execute("DELETE FROM project_items WHERE item_id=?", (item_id,))

            for item in normalized:
                if item["is_new"]:
                    connection.execute(
                        """
                        INSERT INTO project_items(
                            item_id, project_id, row_key, position, script_text,
                            status, subtitles_json, content_analysis_json, settings_json,
                            created_at, updated_at
                        ) VALUES(?, ?, ?, ?, ?, 'DRAFT', ?, ?, '{}', ?, ?)
                        """,
                        (
                            item["item_id"],
                            project_id,
                            item["row_key"],
                            item["position"],
                            item["script_text"],
                            _json(_default_subtitles()),
                            _json(_default_content_analysis(item["script_text"])),
                            now,
                            now,
                        ),
                    )
                else:
                    previous = existing[item["item_id"]]
                    script_changed = str(previous["script_text"]) != item["script_text"]
                    connection.execute(
                        """
                        UPDATE project_items
                        SET row_key=?, position=?, script_text=?,
                            content_analysis_json=?, updated_at=?
                        WHERE item_id=?
                        """,
                        (
                            item["row_key"],
                            item["position"],
                            item["script_text"],
                            (
                                _json(
                                    _default_content_analysis(
                                        item["script_text"],
                                        invalidated_reason="SCRIPT_CHANGED",
                                    )
                                )
                                if script_changed
                                else str(previous["content_analysis_json"] or "{}")
                            ),
                            now,
                            item["item_id"],
                        ),
                    )
            connection.execute(
                "UPDATE projects SET revision=revision+1, updated_at=? WHERE project_id=?",
                (now, project["project_id"]),
            )
        return self.get_project(owner_user_id, project_id)

    def register_input_image(
        self,
        *,
        owner_user_id: str,
        project_id: str,
        filename: str,
        content_type: str,
        size_bytes: int,
        sha256: str,
        managed_path: str,
    ) -> dict[str, Any]:
        image_id = uuid.uuid4().hex
        now = _now()
        with self._transaction() as connection:
            project = self._owned_project(connection, owner_user_id, project_id)
            self._require_editable_images(connection, project_id)
            position = int(
                connection.execute(
                    "SELECT COALESCE(MAX(position), 0) + 1 FROM project_input_images WHERE project_id=?",
                    (project_id,),
                ).fetchone()[0]
            )
            connection.execute(
                """
                INSERT INTO project_input_images(
                    image_id, project_id, position, filename, content_type,
                    size_bytes, sha256, managed_path, created_at
                ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    image_id,
                    project_id,
                    position,
                    str(filename or "").strip()[:255],
                    str(content_type or "").strip(),
                    max(0, int(size_bytes)),
                    str(sha256 or "").strip(),
                    str(managed_path or "").strip(),
                    now,
                ),
            )
            connection.execute(
                "UPDATE projects SET revision=revision+1, updated_at=? WHERE project_id=?",
                (now, project["project_id"]),
            )
            row = connection.execute(
                "SELECT * FROM project_input_images WHERE image_id=?", (image_id,)
            ).fetchone()
            return self._input_image_payload(row)

    def get_input_image(
        self, owner_user_id: str, project_id: str, image_id: str
    ) -> dict[str, Any]:
        with self._connect() as connection:
            self._owned_project(connection, owner_user_id, project_id)
            row = connection.execute(
                "SELECT * FROM project_input_images WHERE image_id=? AND project_id=?",
                (str(image_id or "").strip(), project_id),
            ).fetchone()
            if row is None:
                raise KeyError("项目图片不存在")
            return self._input_image_payload(row)

    def remove_input_image(
        self, owner_user_id: str, project_id: str, image_id: str
    ) -> dict[str, Any]:
        with self._transaction() as connection:
            project = self._owned_project(connection, owner_user_id, project_id)
            self._require_editable_images(connection, project_id)
            row = connection.execute(
                "SELECT * FROM project_input_images WHERE image_id=? AND project_id=?",
                (str(image_id or "").strip(), project_id),
            ).fetchone()
            if row is None:
                raise KeyError("项目图片不存在")
            referenced_assets = connection.execute(
                """
                SELECT asset_id, external_ref_json
                FROM project_assets
                WHERE project_id=? AND asset_type='input_image'
                """,
                (project_id,),
            ).fetchall()
            matching_asset_ids = [
                str(asset["asset_id"])
                for asset in referenced_assets
                if _object(asset["external_ref_json"], {}).get("input_image_id")
                == image_id
            ]
            current_asset_ids = {
                str(item["current_image_asset_id"])
                for item in connection.execute(
                    """
                    SELECT current_image_asset_id
                    FROM project_items
                    WHERE project_id=? AND current_image_asset_id IS NOT NULL
                    """,
                    (project_id,),
                ).fetchall()
            }
            if any(asset_id in current_asset_ids for asset_id in matching_asset_ids):
                raise ValueError("图片当前正在被脚本使用，请先重新分配图片")
            for asset_id in matching_asset_ids:
                connection.execute(
                    "DELETE FROM project_assets WHERE asset_id=?", (asset_id,)
                )
            connection.execute("DELETE FROM project_input_images WHERE image_id=?", (image_id,))
            remaining = connection.execute(
                "SELECT image_id FROM project_input_images WHERE project_id=? ORDER BY position",
                (project_id,),
            ).fetchall()
            for offset, remaining_row in enumerate(remaining, start=1):
                connection.execute(
                    "UPDATE project_input_images SET position=? WHERE image_id=?",
                    (-offset, remaining_row["image_id"]),
                )
            for position, remaining_row in enumerate(remaining, start=1):
                connection.execute(
                    "UPDATE project_input_images SET position=? WHERE image_id=?",
                    (position, remaining_row["image_id"]),
                )
            now = _now()
            connection.execute(
                "UPDATE projects SET revision=revision+1, updated_at=? WHERE project_id=?",
                (now, project["project_id"]),
            )
            return self._input_image_payload(row)

    def apply_image_strategy(
        self,
        owner_user_id: str,
        project_id: str,
        *,
        strategy: str,
        reuse_count: int = 1,
    ) -> dict[str, Any]:
        clean_strategy = str(strategy or "").strip().lower()
        if clean_strategy not in {"count", "loop"}:
            raise ValueError("图片分配策略必须是 count 或 loop")
        safe_count = int(reuse_count)
        if safe_count < 1 or safe_count > 100:
            raise ValueError("每张图片复用次数必须在 1 到 100 之间")
        with self._transaction() as connection:
            project = self._owned_project(connection, owner_user_id, project_id)
            self._require_editable_images(connection, project_id)
            images = connection.execute(
                "SELECT * FROM project_input_images WHERE project_id=? ORDER BY position",
                (project_id,),
            ).fetchall()
            if not images:
                raise ValueError("请先上传至少一张图片")
            items = connection.execute(
                "SELECT * FROM project_items WHERE project_id=? ORDER BY position",
                (project_id,),
            ).fetchall()
            now = _now()
            for index, item in enumerate(items):
                image_index = index % len(images)
                if clean_strategy == "count":
                    image_index = (index // safe_count) % len(images)
                self._assign_input_image(
                    connection,
                    item,
                    images[image_index],
                    mapping_source="strategy",
                    now=now,
                )
            settings = _object(project["settings_json"], {})
            settings["image_mapping"] = {
                "strategy": clean_strategy,
                "reuse_count": safe_count,
            }
            connection.execute(
                """
                UPDATE projects
                SET settings_json=?, revision=revision+1, updated_at=?
                WHERE project_id=?
                """,
                (_json(settings), now, project_id),
            )
            self._refresh_project_status(connection, project_id, now=now)
        return self.get_project(owner_user_id, project_id)

    def replace_item_image(
        self,
        owner_user_id: str,
        project_id: str,
        item_id: str,
        image_id: str,
    ) -> dict[str, Any]:
        with self._transaction() as connection:
            project = self._owned_project(connection, owner_user_id, project_id)
            item = self._owned_item(connection, project_id, item_id)
            if item["status"] in ACTIVE_ITEM_STATUSES:
                raise ValueError("当前脚本行正在生成，请等待完成后再替换图片")
            image = connection.execute(
                "SELECT * FROM project_input_images WHERE image_id=? AND project_id=?",
                (str(image_id or "").strip(), project_id),
            ).fetchone()
            if image is None:
                raise KeyError("项目图片不存在")
            now = _now()
            self._assign_input_image(
                connection, item, image, mapping_source="manual", now=now
            )
            connection.execute(
                "UPDATE projects SET revision=revision+1, updated_at=? WHERE project_id=?",
                (now, project["project_id"]),
            )
            self._refresh_project_status(connection, project_id, now=now)
        return self.get_project(owner_user_id, project_id)

    def delete_project(self, owner_user_id: str, project_id: str) -> list[str]:
        with self._transaction() as connection:
            self._owned_project(connection, owner_user_id, project_id)
            has_items = connection.execute(
                "SELECT 1 FROM project_items WHERE project_id=? LIMIT 1",
                (project_id,),
            ).fetchone()
            if has_items is not None:
                self._require_editable_inputs(connection, project_id)
            paths = [
                str(row["managed_path"])
                for row in connection.execute(
                    "SELECT managed_path FROM project_input_images WHERE project_id=?",
                    (project_id,),
                ).fetchall()
                if row["managed_path"]
            ]
            paths.extend(
                str(row["managed_path"])
                for row in connection.execute(
                    "SELECT managed_path FROM project_script_sources WHERE project_id=?",
                    (project_id,),
                ).fetchall()
                if row["managed_path"]
            )
            connection.execute("DELETE FROM projects WHERE project_id=?", (project_id,))
            return paths

    def add_script_source(
        self,
        owner_user_id: str,
        project_id: str,
        *,
        filename: str,
        content_type: str,
        size_bytes: int,
        sha256: str,
        managed_path: str,
    ) -> dict[str, Any]:
        clean_filename = Path(str(filename or "")).name.strip()
        clean_path = str(managed_path or "").strip()
        if not clean_filename or not clean_path:
            raise ValueError("脚本源文件名称和保存路径不能为空")
        with self._transaction() as connection:
            self._owned_project(connection, owner_user_id, project_id)
            self._require_editable_inputs(connection, project_id)
            version = int(
                connection.execute(
                    "SELECT COALESCE(MAX(version), 0) + 1 FROM project_script_sources WHERE project_id=?",
                    (project_id,),
                ).fetchone()[0]
            )
            source_id = uuid.uuid4().hex
            now = _now()
            connection.execute(
                """
                INSERT INTO project_script_sources(
                    source_id, project_id, version, filename, content_type,
                    size_bytes, sha256, managed_path, created_at
                ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    source_id,
                    project_id,
                    version,
                    clean_filename,
                    str(content_type or "application/octet-stream"),
                    max(0, int(size_bytes)),
                    str(sha256 or ""),
                    clean_path,
                    now,
                ),
            )
            connection.execute(
                "UPDATE projects SET revision=revision+1, updated_at=? WHERE project_id=?",
                (now, project_id),
            )
            row = connection.execute(
                "SELECT * FROM project_script_sources WHERE source_id=?", (source_id,)
            ).fetchone()
        return self._script_source_payload(row)

    def allocate_result_batch(
        self,
        owner_user_id: str,
        project_id: str,
        *,
        export_root: str | Path,
        operation_type: str,
        now: datetime | None = None,
    ) -> dict[str, Any]:
        created = (now or datetime.now().astimezone()).astimezone()
        date_key = created.strftime("%Y%m%d")
        date_label = f"{created.month}.{created.day}"
        root = Path(export_root).expanduser().resolve()
        with self._transaction() as connection:
            self._owned_project(connection, owner_user_id, project_id)
            row = connection.execute(
                "SELECT last_value FROM project_result_batch_counters WHERE day_key=?",
                (date_key,),
            ).fetchone()
            sequence = int(row["last_value"]) + 1 if row is not None else 1
            while (root / date_label / str(sequence)).exists():
                sequence += 1
            connection.execute(
                """
                INSERT INTO project_result_batch_counters(day_key, last_value)
                VALUES(?, ?)
                ON CONFLICT(day_key) DO UPDATE SET last_value=excluded.last_value
                """,
                (date_key, sequence),
            )
            result_batch_id = uuid.uuid4().hex
            timestamp = created.isoformat(timespec="seconds")
            export_path = str((root / date_label / str(sequence)).resolve())
            connection.execute(
                """
                INSERT INTO project_result_batches(
                    result_batch_id, project_id, owner_user_id, date_key,
                    date_label, batch_no, export_path, operation_type,
                    status, created_at, updated_at
                ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, 'ALLOCATED', ?, ?)
                """,
                (
                    result_batch_id,
                    project_id,
                    str(owner_user_id),
                    date_key,
                    date_label,
                    sequence,
                    export_path,
                    str(operation_type or "").strip().upper(),
                    timestamp,
                    timestamp,
                ),
            )
            batch = connection.execute(
                "SELECT * FROM project_result_batches WHERE result_batch_id=?",
                (result_batch_id,),
            ).fetchone()
        return self._result_batch_payload(batch)

    def update_result_batch(
        self,
        owner_user_id: str,
        result_batch_id: str,
        *,
        status: str,
        jianying_batch_id: str | None = None,
        error_message: str | None = None,
    ) -> dict[str, Any]:
        clean_status = str(status or "").strip().upper()
        if clean_status not in {
            "ALLOCATED", "RUNNING", "SUCCEEDED", "PARTIAL_FAILED", "FAILED"
        }:
            raise ValueError(f"成果批次状态无效: {clean_status}")
        with self._transaction() as connection:
            row = connection.execute(
                "SELECT * FROM project_result_batches WHERE result_batch_id=? AND owner_user_id=?",
                (str(result_batch_id), str(owner_user_id)),
            ).fetchone()
            if row is None:
                raise KeyError("成果批次不存在")
            connection.execute(
                """
                UPDATE project_result_batches
                SET status=?, jianying_batch_id=?, error_message=?, updated_at=?
                WHERE result_batch_id=?
                """,
                (
                    clean_status,
                    str(jianying_batch_id if jianying_batch_id is not None else row["jianying_batch_id"]),
                    str(error_message if error_message is not None else row["error_message"]),
                    _now(),
                    str(result_batch_id),
                ),
            )
            updated = connection.execute(
                "SELECT * FROM project_result_batches WHERE result_batch_id=?",
                (str(result_batch_id),),
            ).fetchone()
        return self._result_batch_payload(updated)

    def list_gallery_records(self, owner_user_id: str) -> dict[str, Any]:
        owner_id = str(owner_user_id or "").strip()
        with self._connect() as connection:
            batch_rows = connection.execute(
                """
                SELECT rb.*, p.project_no, p.name AS project_name
                FROM project_result_batches rb
                JOIN projects p ON p.project_id=rb.project_id
                WHERE rb.owner_user_id=?
                ORDER BY rb.date_key DESC, rb.batch_no DESC
                """,
                (owner_id,),
            ).fetchall()
            asset_rows = connection.execute(
                """
                SELECT a.*, i.row_key, i.script_text, p.project_no, p.name AS project_name
                FROM project_assets a
                JOIN project_items i ON i.item_id=a.item_id
                JOIN projects p ON p.project_id=a.project_id
                WHERE p.owner_user_id=? AND a.asset_type='variant_video'
                ORDER BY a.created_at DESC
                """,
                (owner_id,),
            ).fetchall()
        videos = []
        for row in asset_rows:
            asset = self._asset_payload(row)
            videos.append(
                {
                    **asset,
                    "project_id": row["project_id"],
                    "item_id": row["item_id"],
                    "project_no": row["project_no"],
                    "project_name": row["project_name"],
                    "row_key": row["row_key"],
                    "script_text": row["script_text"],
                }
            )
        return {
            "batches": [
                {
                    **self._result_batch_payload(row),
                    "project_no": row["project_no"],
                    "project_name": row["project_name"],
                }
                for row in batch_rows
            ],
            "videos": videos,
        }

    def create_operation(
        self,
        *,
        owner_user_id: str,
        project_id: str,
        operation_type: str,
        idempotency_key: str,
        item_id: str | None = None,
        payload: dict[str, Any] | None = None,
        correlation_id: str | None = None,
    ) -> dict[str, Any]:
        clean_type = str(operation_type or "").strip().upper()
        clean_key = str(idempotency_key or "").strip()
        if not clean_type or not clean_key:
            raise ValueError("操作类型和幂等键不能为空")
        now = _now()
        with self._transaction() as connection:
            self._owned_project(connection, owner_user_id, project_id)
            if item_id:
                self._owned_item(connection, project_id, item_id)
            existing = connection.execute(
                """
                SELECT * FROM project_operations
                WHERE project_id=? AND IFNULL(item_id, '')=?
                  AND operation_type=? AND idempotency_key=?
                """,
                (project_id, item_id or "", clean_type, clean_key),
            ).fetchone()
            if existing is not None:
                return self._operation_payload(existing)
            operation_id = uuid.uuid4().hex
            clean_correlation_id = str(correlation_id or "").strip()
            if clean_correlation_id and (
                len(clean_correlation_id) > 64
                or any(
                    not (character.isalnum() or character in "._:-")
                    for character in clean_correlation_id
                )
            ):
                raise ValueError("日志关联标识不合法")
            if not clean_correlation_id:
                clean_correlation_id = uuid.uuid4().hex
            connection.execute(
                """
                INSERT INTO project_operations(
                    operation_id, correlation_id, project_id, item_id, operation_type,
                    status, idempotency_key, payload_json, result_json,
                    created_at, updated_at
                ) VALUES(?, ?, ?, ?, ?, 'PENDING', ?, ?, '{}', ?, ?)
                """,
                (
                    operation_id,
                    clean_correlation_id,
                    project_id,
                    item_id,
                    clean_type,
                    clean_key,
                    _json(payload or {}),
                    now,
                    now,
                ),
            )
            if item_id:
                queued_status = {
                    "AUDIO_GENERATE": "AUDIO_QUEUED",
                    "COMPOSITION_GENERATE": "COMPOSITION_QUEUED",
                    "POSTPROCESS_GENERATE": "POSTPROCESS_RUNNING",
                    "VARIANT_GENERATE": "VARIANT_QUEUED",
                    "VARIANT_SUPPLEMENT": "VARIANT_QUEUED",
                    "VARIANT_RETRY": "VARIANT_QUEUED",
                }.get(clean_type)
                if queued_status:
                    connection.execute(
                        "UPDATE project_items SET status=?, updated_at=? WHERE item_id=?",
                        (queued_status, now, item_id),
                    )
            self._refresh_project_status(connection, project_id, now=now)
            row = connection.execute(
                "SELECT * FROM project_operations WHERE operation_id=?",
                (operation_id,),
            ).fetchone()
            operation_payload = self._operation_payload(row)
        log_event(
            logger,
            "workbench.operation_created",
            "工作台异步操作已创建",
            component="workbench",
            user_id=owner_user_id,
            project_id=project_id,
            item_id=item_id,
            operation_id=operation_id,
            operation_type=clean_type,
            status="PENDING",
            correlation_id=clean_correlation_id,
        )
        return operation_payload

    def transition_audio_operation(
        self,
        owner_user_id: str,
        project_id: str,
        item_id: str,
        *,
        status: str,
        item_status: str,
        result: dict[str, Any] | None = None,
        error_code: str | None = None,
        error_message: str | None = None,
    ) -> dict[str, Any]:
        return self.transition_operation(
            owner_user_id,
            project_id,
            item_id,
            operation_type="AUDIO_GENERATE",
            status=status,
            item_status=item_status,
            result=result,
            error_code=error_code,
            error_message=error_message,
        )

    def transition_operation(
        self,
        owner_user_id: str,
        project_id: str,
        item_id: str,
        *,
        operation_type: str,
        status: str,
        item_status: str,
        result: dict[str, Any] | None = None,
        error_code: str | None = None,
        error_message: str | None = None,
    ) -> dict[str, Any]:
        operation_status = str(status or "").strip().upper()
        clean_type = str(operation_type or "").strip().upper()
        resolved_item_status = _clean_status(
            item_status, allowed=PROJECT_ITEM_STATUSES, label="项目行状态"
        )
        if operation_status not in {"PENDING", "RUNNING", "SUCCEEDED", "FAILED"}:
            raise ValueError("异步操作状态无效")
        now = _now()
        with self._transaction() as connection:
            self._owned_project(connection, owner_user_id, project_id)
            self._owned_item(connection, project_id, item_id)
            operation = connection.execute(
                """
                SELECT * FROM project_operations
                WHERE project_id=? AND item_id=? AND operation_type=?
                ORDER BY rowid DESC LIMIT 1
                """,
                (project_id, item_id, clean_type),
            ).fetchone()
            if operation is None:
                raise KeyError("异步操作不存在")
            previous_status = str(operation["status"])
            started_at = operation["started_at"] or (
                now if operation_status == "RUNNING" else None
            )
            finished_at = (
                now if operation_status in {"SUCCEEDED", "FAILED"} else None
            )
            connection.execute(
                """
                UPDATE project_operations
                SET status=?, attempt_count=CASE
                        WHEN ?='RUNNING' AND status!='RUNNING'
                        THEN attempt_count+1 ELSE attempt_count END,
                    error_code=?, error_message=?, result_json=?,
                    updated_at=?, started_at=?, finished_at=?
                WHERE operation_id=?
                """,
                (
                    operation_status,
                    operation_status,
                    error_code,
                    error_message,
                    _json(result or {}),
                    now,
                    started_at,
                    finished_at,
                    operation["operation_id"],
                ),
            )
            connection.execute(
                "UPDATE project_items SET status=?, updated_at=? WHERE item_id=?",
                (resolved_item_status, now, item_id),
            )
            self._refresh_project_status(connection, project_id, now=now)
        if previous_status != operation_status:
            log_event(
                logger,
                "workbench.operation_status_changed",
                "工作台异步操作状态已变化",
                component="workbench",
                user_id=owner_user_id,
                project_id=project_id,
                item_id=item_id,
                operation_id=operation["operation_id"],
                operation_type=clean_type,
                previous_status=previous_status,
                status=operation_status,
                item_status=resolved_item_status,
                error_code=error_code,
                correlation_id=operation["correlation_id"],
            )
        return self.get_project(owner_user_id, project_id)

    def delete_variant_asset(
        self,
        owner_user_id: str,
        project_id: str,
        item_id: str,
        asset_id: str,
    ) -> str | None:
        """Delete one generated variant record without affecting sibling variants."""

        with self._transaction() as connection:
            self._owned_project(connection, owner_user_id, project_id)
            self._owned_item(connection, project_id, item_id)
            asset = connection.execute(
                """
                SELECT * FROM project_assets
                WHERE project_id=? AND item_id=? AND asset_id=?
                  AND asset_type='variant_video'
                """,
                (project_id, item_id, asset_id),
            ).fetchone()
            if asset is None:
                raise KeyError("变体不存在")
            managed_path = str(asset["managed_path"] or "").strip() or None
            connection.execute("DELETE FROM project_assets WHERE asset_id=?", (asset_id,))
            remaining = int(
                connection.execute(
                    """
                    SELECT COUNT(*) FROM project_assets
                    WHERE item_id=? AND asset_type='variant_video' AND status='READY'
                    """,
                    (item_id,),
                ).fetchone()[0]
            )
            now = _now()
            latest_variant_operation = connection.execute(
                """
                SELECT status FROM project_operations
                WHERE item_id=? AND operation_type IN (
                    'VARIANT_GENERATE', 'VARIANT_SUPPLEMENT', 'VARIANT_RETRY'
                )
                ORDER BY rowid DESC LIMIT 1
                """,
                (item_id,),
            ).fetchone()
            item_status = (
                "VARIANT_FAILED"
                if latest_variant_operation is not None
                and latest_variant_operation["status"] == "FAILED"
                else ("VARIANT_READY" if remaining else "COMPOSITION_READY")
            )
            connection.execute(
                "UPDATE project_items SET status=?, updated_at=? WHERE item_id=?",
                (item_status, now, item_id),
            )
            self._refresh_project_status(connection, project_id, now=now)
        return managed_path

    def delete_variant_assets(
        self,
        owner_user_id: str,
        asset_ids: list[str],
    ) -> list[dict[str, str | None]]:
        """Atomically delete account-owned generated variants from the gallery."""

        clean_ids = list(
            dict.fromkeys(str(asset_id or "").strip() for asset_id in asset_ids)
        )
        clean_ids = [asset_id for asset_id in clean_ids if asset_id]
        if not clean_ids:
            raise ValueError("请选择需要删除的成果视频")
        placeholders = ", ".join("?" for _ in clean_ids)
        with self._transaction() as connection:
            rows = connection.execute(
                f"""
                SELECT a.asset_id, a.project_id, a.item_id, a.managed_path
                FROM project_assets a
                JOIN projects p ON p.project_id=a.project_id
                WHERE p.owner_user_id=? AND a.asset_type='variant_video'
                  AND a.asset_id IN ({placeholders})
                """,
                (str(owner_user_id or "").strip(), *clean_ids),
            ).fetchall()
            by_id = {str(row["asset_id"]): row for row in rows}
            if any(asset_id not in by_id for asset_id in clean_ids):
                raise KeyError("成果视频不存在或无权访问")

            connection.execute(
                f"DELETE FROM project_assets WHERE asset_id IN ({placeholders})",
                clean_ids,
            )
            now = _now()
            affected_items = {
                (str(row["project_id"]), str(row["item_id"])) for row in rows
            }
            affected_projects: set[str] = set()
            for project_id, item_id in affected_items:
                remaining = int(
                    connection.execute(
                        """
                        SELECT COUNT(*) FROM project_assets
                        WHERE item_id=? AND asset_type='variant_video' AND status='READY'
                        """,
                        (item_id,),
                    ).fetchone()[0]
                )
                latest_variant_operation = connection.execute(
                    """
                    SELECT status FROM project_operations
                    WHERE item_id=? AND operation_type IN (
                        'VARIANT_GENERATE', 'VARIANT_SUPPLEMENT', 'VARIANT_RETRY'
                    )
                    ORDER BY rowid DESC LIMIT 1
                    """,
                    (item_id,),
                ).fetchone()
                item_status = (
                    "VARIANT_FAILED"
                    if latest_variant_operation is not None
                    and latest_variant_operation["status"] == "FAILED"
                    else ("VARIANT_READY" if remaining else "COMPOSITION_READY")
                )
                connection.execute(
                    "UPDATE project_items SET status=?, updated_at=? WHERE item_id=?",
                    (item_status, now, item_id),
                )
                affected_projects.add(project_id)
            for project_id in affected_projects:
                self._refresh_project_status(connection, project_id, now=now)

        return [
            {
                "asset_id": asset_id,
                "managed_path": (
                    str(by_id[asset_id]["managed_path"] or "").strip() or None
                ),
            }
            for asset_id in clean_ids
        ]

    def mark_item_content_analysis_pending(
        self,
        owner_user_id: str,
        project_id: str,
        item_id: str,
        *,
        expected_script_sha256: str,
    ) -> bool:
        with self._transaction() as connection:
            self._owned_project(connection, owner_user_id, project_id)
            item = self._owned_item(connection, project_id, item_id)
            script = str(item["script_text"])
            if _script_sha256(script) != expected_script_sha256:
                return False
            snapshot = _content_analysis_snapshot(
                _object(item["content_analysis_json"], {}), script
            )
            snapshot.update(
                {
                    "overall_status": "PENDING",
                    "request_count": int(snapshot.get("request_count") or 0) + 1,
                    "requested_at": _now(),
                    "invalidated_reason": None,
                    "invalidated_at": None,
                }
            )
            now = _now()
            connection.execute(
                "UPDATE project_items SET content_analysis_json=?, updated_at=? WHERE item_id=?",
                (_json(snapshot), now, item_id),
            )
            connection.execute(
                "UPDATE projects SET updated_at=? WHERE project_id=?", (now, project_id)
            )
        return True

    def complete_item_content_analysis(
        self,
        owner_user_id: str,
        project_id: str,
        item_id: str,
        *,
        expected_script_sha256: str,
        result: dict[str, Any],
        previous: dict[str, Any] | None = None,
    ) -> bool:
        with self._transaction() as connection:
            self._owned_project(connection, owner_user_id, project_id)
            item = self._owned_item(connection, project_id, item_id)
            script = str(item["script_text"])
            if _script_sha256(script) != expected_script_sha256:
                return False
            current = _content_analysis_snapshot(
                _object(item["content_analysis_json"], {}), script
            )
            baseline = (
                _content_analysis_snapshot(previous, script)
                if isinstance(previous, dict)
                else current
            )
            errors = result.get("errors") if isinstance(result.get("errors"), dict) else {}

            music_status = str(result.get("music_analysis_status") or "FAILED")
            if music_status == "SUCCESS":
                music_intent = result.get("music_intent")
                music_error = None
            elif baseline.get("music_analysis_status") == "SUCCESS":
                music_status = "SUCCESS"
                music_intent = baseline.get("music_intent")
                music_error = None
            else:
                music_status = "FAILED"
                music_intent = None
                music_error = errors.get("music")

            subtitle_status = str(result.get("subtitle_analysis_status") or "FAILED")
            if subtitle_status == "SUCCESS":
                subtitle_units = result.get("subtitle_units")
                subtitle_error = None
            elif baseline.get("subtitle_analysis_status") == "SUCCESS":
                subtitle_status = "SUCCESS"
                subtitle_units = baseline.get("subtitle_units")
                subtitle_error = None
            else:
                subtitle_status = "FAILED"
                subtitle_units = None
                subtitle_error = errors.get("subtitle")

            analyzed_at = _now()
            snapshot = {
                **current,
                "script_sha256": expected_script_sha256,
                "script_length": len(script),
                "overall_status": _analysis_overall_status(
                    music_status, subtitle_status
                ),
                "music_analysis_status": music_status,
                "subtitle_analysis_status": subtitle_status,
                "music_intent": music_intent,
                "subtitle_units": subtitle_units,
                "errors": {
                    "music": music_error,
                    "subtitle": subtitle_error,
                    "request": None,
                },
                "schema_version": result.get("schema_version")
                or baseline.get("schema_version"),
                "prompt_version": result.get("prompt_version")
                or baseline.get("prompt_version"),
                "model": result.get("model") or baseline.get("model"),
                "provider_request_id": result.get("provider_request_id")
                or baseline.get("provider_request_id"),
                "provider_attempts": int(result.get("provider_attempts") or 0),
                "cache_hit": result.get("cache_hit") is True,
                "cacheable": result.get("cacheable") is True,
                "analyzed_at": analyzed_at,
                "invalidated_reason": None,
                "invalidated_at": None,
            }
            connection.execute(
                "UPDATE project_items SET content_analysis_json=?, updated_at=? WHERE item_id=?",
                (_json(snapshot), analyzed_at, item_id),
            )
            connection.execute(
                "UPDATE projects SET updated_at=? WHERE project_id=?",
                (analyzed_at, project_id),
            )
        return True

    def fail_item_content_analysis(
        self,
        owner_user_id: str,
        project_id: str,
        item_id: str,
        *,
        expected_script_sha256: str,
        error: dict[str, str],
        previous: dict[str, Any] | None = None,
    ) -> bool:
        failed = {
            "music_analysis_status": "FAILED",
            "subtitle_analysis_status": "FAILED",
            "music_intent": None,
            "subtitle_units": None,
            "errors": {"music": error, "subtitle": error},
            "provider_attempts": 0,
            "cache_hit": False,
            "cacheable": False,
        }
        completed = self.complete_item_content_analysis(
            owner_user_id,
            project_id,
            item_id,
            expected_script_sha256=expected_script_sha256,
            result=failed,
            previous=previous,
        )
        if not completed:
            return False
        with self._transaction() as connection:
            self._owned_project(connection, owner_user_id, project_id)
            item = self._owned_item(connection, project_id, item_id)
            script = str(item["script_text"])
            if _script_sha256(script) != expected_script_sha256:
                return False
            snapshot = _content_analysis_snapshot(
                _object(item["content_analysis_json"], {}), script
            )
            snapshot["errors"] = {
                **dict(snapshot.get("errors") or {}),
                "request": error,
            }
            now = _now()
            connection.execute(
                "UPDATE project_items SET content_analysis_json=?, updated_at=? WHERE item_id=?",
                (_json(snapshot), now, item_id),
            )
            connection.execute(
                "UPDATE projects SET updated_at=? WHERE project_id=?", (now, project_id)
            )
        return True

    def mark_item_visual_analysis_pending(
        self,
        owner_user_id: str,
        project_id: str,
        item_id: str,
        *,
        expected_script_sha256: str,
        candidate_request: dict[str, Any],
    ) -> bool:
        with self._transaction() as connection:
            self._owned_project(connection, owner_user_id, project_id)
            item = self._owned_item(connection, project_id, item_id)
            script = str(item["script_text"])
            if _script_sha256(script) != expected_script_sha256:
                return False
            snapshot = _visual_analysis_snapshot(
                _object(item["visual_analysis_json"], {}), script
            )
            snapshot.update(
                {
                    "analysis_status": "PENDING",
                    "mapping_status": "NOT_REQUESTED",
                    "catalog_version": candidate_request.get("catalog_version"),
                    "candidate_set_sha256": _visual_candidate_set_sha256(
                        candidate_request
                    ),
                    "candidate_request": candidate_request,
                    "decisions": [],
                    "error": None,
                    "request_count": int(snapshot.get("request_count") or 0) + 1,
                    "requested_at": _now(),
                    "invalidated_reason": None,
                    "invalidated_at": None,
                    "bound_audio_asset_id": item["current_audio_asset_id"],
                    "raw_cues_sha256": _raw_cues_sha256(
                        _object(item["subtitles_json"], _default_subtitles()).get(
                            "raw_cues", []
                        )
                    ),
                }
            )
            now = _now()
            connection.execute(
                "UPDATE project_items SET visual_analysis_json=?, updated_at=? WHERE item_id=?",
                (_json(snapshot), now, item_id),
            )
            connection.execute(
                "UPDATE projects SET updated_at=? WHERE project_id=?", (now, project_id)
            )
        return True

    def complete_item_visual_analysis(
        self,
        owner_user_id: str,
        project_id: str,
        item_id: str,
        *,
        expected_script_sha256: str,
        result: dict[str, Any],
        recipe: dict[str, Any],
        mapping_status: str,
        mapping_error: dict[str, str] | None = None,
    ) -> bool:
        with self._transaction() as connection:
            self._owned_project(connection, owner_user_id, project_id)
            item = self._owned_item(connection, project_id, item_id)
            script = str(item["script_text"])
            if _script_sha256(script) != expected_script_sha256:
                return False
            snapshot = _visual_analysis_snapshot(
                _object(item["visual_analysis_json"], {}), script
            )
            response_catalog = result.get("catalog_version") or recipe.get(
                "catalog_version"
            )
            if (
                snapshot.get("analysis_status") != "PENDING"
                or snapshot.get("catalog_version") != response_catalog
                or snapshot.get("candidate_set_sha256")
                != result.get("candidate_set_sha256")
            ):
                return False
            analyzed_at = _now()
            snapshot.update(
                {
                    "analysis_status": str(result.get("analysis_status") or "FAILED"),
                    "mapping_status": mapping_status,
                    "catalog_version": result.get("catalog_version")
                    or snapshot.get("catalog_version"),
                    "decisions": (
                        list(result.get("decisions") or [])
                        if isinstance(result.get("decisions"), list)
                        else []
                    ),
                    "mapped_candidates": (
                        list(result.get("mapped_candidates") or [])
                        if isinstance(result.get("mapped_candidates"), list)
                        else []
                    ),
                    "recipe": recipe,
                    "error": mapping_error or result.get("error"),
                    "provider_request_id": result.get("provider_request_id"),
                    "provider_attempts": int(result.get("provider_attempts") or 0),
                    "cache_hit": result.get("cache_hit") is True,
                    "cacheable": result.get("cacheable") is True,
                    "analyzed_at": analyzed_at,
                    "invalidated_reason": None,
                    "invalidated_at": None,
                    "bound_audio_asset_id": item["current_audio_asset_id"],
                    "raw_cues_sha256": _raw_cues_sha256(
                        _object(item["subtitles_json"], _default_subtitles()).get(
                            "raw_cues", []
                        )
                    ),
                    "revision": int(snapshot.get("revision") or 0) + 1,
                }
            )
            connection.execute(
                "UPDATE project_items SET visual_analysis_json=?, updated_at=? WHERE item_id=?",
                (_json(snapshot), analyzed_at, item_id),
            )
            connection.execute(
                "UPDATE projects SET updated_at=? WHERE project_id=?",
                (analyzed_at, project_id),
            )
        return True

    def fail_item_visual_analysis(
        self,
        owner_user_id: str,
        project_id: str,
        item_id: str,
        *,
        expected_script_sha256: str,
        expected_catalog_version: str,
        expected_candidate_set_sha256: str,
        error: dict[str, str],
    ) -> bool:
        with self._transaction() as connection:
            self._owned_project(connection, owner_user_id, project_id)
            item = self._owned_item(connection, project_id, item_id)
            script = str(item["script_text"])
            if _script_sha256(script) != expected_script_sha256:
                return False
            snapshot = _visual_analysis_snapshot(
                _object(item["visual_analysis_json"], {}), script
            )
            if (
                snapshot.get("analysis_status") != "PENDING"
                or snapshot.get("catalog_version") != expected_catalog_version
                or snapshot.get("candidate_set_sha256")
                != expected_candidate_set_sha256
            ):
                return False
            snapshot.update(
                {
                    "analysis_status": "FAILED",
                    "mapping_status": "FAILED",
                    "error": error,
                    "cache_hit": False,
                    "cacheable": False,
                    "analyzed_at": _now(),
                    "revision": int(snapshot.get("revision") or 0) + 1,
                }
            )
            now = _now()
            connection.execute(
                "UPDATE project_items SET visual_analysis_json=?, updated_at=? WHERE item_id=?",
                (_json(snapshot), now, item_id),
            )
            connection.execute(
                "UPDATE projects SET updated_at=? WHERE project_id=?", (now, project_id)
            )
        return True

    def update_item_visual_overlays(
        self,
        owner_user_id: str,
        project_id: str,
        item_id: str,
        *,
        overlays: list[dict[str, Any]],
        expected_revision: int,
        catalog_version: str,
    ) -> dict[str, Any]:
        if not isinstance(overlays, list):
            raise ValueError("语义贴图配方必须是数组")
        normalized: list[dict[str, Any]] = []
        seen: set[str] = set()
        valid_corners = {"top_left", "top_right"}
        for index, raw in enumerate(overlays, start=1):
            if not isinstance(raw, dict):
                raise ValueError(f"第 {index} 个语义贴图不是对象")
            overlay_id = str(raw.get("overlay_id") or "").strip()
            asset_id = str(raw.get("asset_id") or "").strip()
            concept_id = str(raw.get("concept_id") or "").strip()
            corner = str(raw.get("corner") or "").strip()
            start_us = raw.get("start_us")
            duration_us = raw.get("duration_us")
            scale = raw.get("scale")
            opacity = raw.get("opacity")
            if not overlay_id or overlay_id in seen or not asset_id or not concept_id:
                raise ValueError("语义贴图 ID、素材或概念无效")
            if corner not in valid_corners:
                raise ValueError("语义贴图位置无效")
            if type(start_us) is not int or start_us < 0:
                raise ValueError("语义贴图开始时间无效")
            if type(duration_us) is not int or not 100_000 <= duration_us <= 30_000_000:
                raise ValueError("语义贴图持续时间无效")
            if isinstance(scale, bool) or not isinstance(scale, (int, float)) or not 0.05 <= float(scale) <= 2.0:
                raise ValueError("语义贴图缩放无效")
            if isinstance(opacity, bool) or not isinstance(opacity, (int, float)) or not 0.0 <= float(opacity) <= 1.0:
                raise ValueError("语义贴图透明度无效")
            seen.add(overlay_id)
            normalized.append(
                {
                    **raw,
                    "overlay_id": overlay_id,
                    "asset_id": asset_id,
                    "concept_id": concept_id,
                    "corner": corner,
                    "start_us": start_us,
                    "duration_us": duration_us,
                    "scale": float(scale),
                    "opacity": float(opacity),
                    "enabled": raw.get("enabled") is not False,
                    "selection_mode": "manual",
                    "manual": True,
                    "locked": raw.get("locked") is True,
                    "requires_review": False,
                }
            )
        enabled = sorted(
            (item for item in normalized if item["enabled"]),
            key=lambda item: item["start_us"],
        )
        for previous, current in zip(enabled, enabled[1:]):
            if current["start_us"] < previous["start_us"] + previous["duration_us"]:
                raise ValueError("同一时间只能显示一张语义前景图片")
        with self._transaction() as connection:
            project = self._owned_project(connection, owner_user_id, project_id)
            if int(project["revision"]) != int(expected_revision):
                raise ProjectRevisionConflict("项目已被其他操作更新，请刷新后重试")
            item = self._owned_item(connection, project_id, item_id)
            if str(item["status"]) in ACTIVE_ITEM_STATUSES:
                raise ValueError("当前脚本行正在生成，不能修改语义贴图")
            script = str(item["script_text"])
            snapshot = _visual_analysis_snapshot(
                _object(item["visual_analysis_json"], {}), script
            )
            snapshot["recipe"] = {
                "schema": "jyd.semantic-visual-recipe.v1",
                "catalog_version": catalog_version,
                "overlays": normalized,
            }
            snapshot["bound_audio_asset_id"] = item["current_audio_asset_id"]
            snapshot["raw_cues_sha256"] = _raw_cues_sha256(
                _object(item["subtitles_json"], _default_subtitles()).get("raw_cues", [])
            )
            snapshot["revision"] = int(snapshot.get("revision") or 0) + 1
            now = _now()
            connection.execute(
                "UPDATE project_items SET visual_analysis_json=?, updated_at=? WHERE item_id=?",
                (_json(snapshot), now, item_id),
            )
            connection.execute(
                "UPDATE projects SET revision=revision+1, updated_at=? WHERE project_id=?",
                (now, project_id),
            )
        return self.get_project(owner_user_id, project_id)

    def set_item_subtitles(
        self,
        owner_user_id: str,
        project_id: str,
        item_id: str,
        subtitles: dict[str, Any],
    ) -> dict[str, Any]:
        if not isinstance(subtitles, dict):
            raise ValueError("字幕数据必须是对象")
        with self._transaction() as connection:
            self._owned_project(connection, owner_user_id, project_id)
            self._owned_item(connection, project_id, item_id)
            now = _now()
            connection.execute(
                "UPDATE project_items SET subtitles_json=?, updated_at=? WHERE item_id=?",
                (_json(subtitles), now, item_id),
            )
            connection.execute(
                "UPDATE projects SET updated_at=? WHERE project_id=?",
                (now, project_id),
            )
        return self.get_project(owner_user_id, project_id)

    def add_link(
        self,
        *,
        owner_user_id: str,
        project_id: str,
        system: str,
        relation: str,
        external_id: str,
        item_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        values = [str(value or "").strip() for value in (system, relation, external_id)]
        if not all(values):
            raise ValueError("外部关联的系统、关系和编号不能为空")
        clean_system, clean_relation, clean_external_id = values
        with self._transaction() as connection:
            self._owned_project(connection, owner_user_id, project_id)
            if item_id:
                self._owned_item(connection, project_id, item_id)
            existing = connection.execute(
                """
                SELECT * FROM project_links
                WHERE project_id=? AND system=? AND relation=? AND external_id=?
                """,
                (project_id, clean_system, clean_relation, clean_external_id),
            ).fetchone()
            if existing is not None:
                return self._link_payload(existing)
            link_id = uuid.uuid4().hex
            connection.execute(
                """
                INSERT INTO project_links(
                    link_id, project_id, item_id, system, relation,
                    external_id, metadata_json, created_at
                ) VALUES(?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    link_id,
                    project_id,
                    item_id,
                    clean_system,
                    clean_relation,
                    clean_external_id,
                    _json(metadata or {}),
                    _now(),
                ),
            )
            row = connection.execute(
                "SELECT * FROM project_links WHERE link_id=?", (link_id,)
            ).fetchone()
            return self._link_payload(row)

    @staticmethod
    def _next_project_no(connection: sqlite3.Connection) -> str:
        day_key = datetime.now().astimezone().strftime("%Y%m%d")
        row = connection.execute(
            "SELECT last_value FROM project_counters WHERE day_key=?", (day_key,)
        ).fetchone()
        sequence = int(row["last_value"]) + 1 if row is not None else 1
        connection.execute(
            """
            INSERT INTO project_counters(day_key, last_value) VALUES(?, ?)
            ON CONFLICT(day_key) DO UPDATE SET last_value=excluded.last_value
            """,
            (day_key, sequence),
        )
        return f"DH-{day_key}-{sequence:04d}"

    @staticmethod
    def _owned_project(
        connection: sqlite3.Connection, owner_user_id: str, project_id: str
    ) -> sqlite3.Row:
        row = connection.execute(
            """
            SELECT * FROM projects
            WHERE project_id=? AND owner_user_id=?
            """,
            (str(project_id or "").strip(), str(owner_user_id or "").strip()),
        ).fetchone()
        if row is None:
            raise KeyError("项目不存在")
        return row

    @staticmethod
    def _owned_item(
        connection: sqlite3.Connection, project_id: str, item_id: str
    ) -> sqlite3.Row:
        row = connection.execute(
            "SELECT * FROM project_items WHERE item_id=? AND project_id=?",
            (str(item_id or "").strip(), str(project_id or "").strip()),
        ).fetchone()
        if row is None:
            raise KeyError("项目脚本行不存在")
        return row

    @staticmethod
    def _require_editable_inputs(
        connection: sqlite3.Connection, project_id: str
    ) -> None:
        rows = connection.execute(
            "SELECT status FROM project_items WHERE project_id=?", (project_id,)
        ).fetchall()
        if not rows or any(str(row["status"]) != "DRAFT" for row in rows):
            raise ValueError("项目已进入声音生成，不能修改脚本")

    @staticmethod
    def _require_editable_images(
        connection: sqlite3.Connection, project_id: str
    ) -> None:
        rows = connection.execute(
            "SELECT status FROM project_items WHERE project_id=?", (project_id,)
        ).fetchall()
        if not rows or any(
            str(row["status"]) not in IMAGE_EDITABLE_ITEM_STATUSES for row in rows
        ):
            raise ValueError("画面任务已经启动，当前不能修改图片")

    def _assign_input_image(
        self,
        connection: sqlite3.Connection,
        item: sqlite3.Row,
        image: sqlite3.Row,
        *,
        mapping_source: str,
        now: str,
    ) -> None:
        current_asset_id = str(item["current_image_asset_id"] or "")
        if current_asset_id:
            current = connection.execute(
                "SELECT external_ref_json FROM project_assets WHERE asset_id=?",
                (current_asset_id,),
            ).fetchone()
            if current is not None and _object(
                current["external_ref_json"], {}
            ).get("input_image_id") == image["image_id"]:
                return
        version = int(
            connection.execute(
                """
                SELECT COALESCE(MAX(version), 0) + 1
                FROM project_assets
                WHERE item_id=? AND asset_type='input_image'
                """,
                (item["item_id"],),
            ).fetchone()[0]
        )
        asset_id = uuid.uuid4().hex
        connection.execute(
            """
            INSERT INTO project_assets(
                asset_id, project_id, item_id, asset_type, version,
                status, source_type, filename, managed_path,
                external_ref_json, metadata_json, created_at, updated_at
            ) VALUES(?, ?, ?, 'input_image', ?, 'READY', 'project_upload',
                     ?, ?, ?, ?, ?, ?)
            """,
            (
                asset_id,
                item["project_id"],
                item["item_id"],
                version,
                image["filename"],
                image["managed_path"],
                _json({"input_image_id": image["image_id"]}),
                _json(
                    {
                        "mapping_source": mapping_source,
                        "pool_position": int(image["position"]),
                        "content_type": image["content_type"],
                        "size_bytes": int(image["size_bytes"]),
                        "sha256": image["sha256"],
                    }
                ),
                now,
                now,
            ),
        )
        subtitles = _object(item["subtitles_json"], _default_subtitles())
        subtitles["bound_video_asset_id"] = None
        if subtitles.get("raw_cues"):
            subtitles["status"] = "READY"
        next_status = "AUDIO_READY" if item["current_audio_asset_id"] else "DRAFT"
        connection.execute(
            """
            UPDATE project_items
            SET current_image_asset_id=?, current_base_video_asset_id=NULL,
                current_video_asset_id=NULL, subtitles_json=?, status=?, updated_at=?
            WHERE item_id=?
            """,
            (asset_id, _json(subtitles), next_status, now, item["item_id"]),
        )

    def _set_current_asset(
        self,
        connection: sqlite3.Connection,
        item: sqlite3.Row,
        *,
        asset_id: str,
        asset_type: str,
        source_type: str,
        asset_status: str,
        now: str,
    ) -> None:
        if asset_status != "READY":
            raise ValueError("只有已就绪素材可以设为当前版本")
        if asset_type == "audio":
            subtitles = _default_subtitles()
            subtitles.update(
                {
                    "bound_audio_asset_id": asset_id,
                    "status": "PENDING_TIMESTAMPS",
                }
            )
            connection.execute(
                """
                UPDATE project_items
                SET current_audio_asset_id=?, current_base_video_asset_id=NULL,
                    current_video_asset_id=NULL,
                    subtitles_json=?, status='AUDIO_READY', updated_at=?
                WHERE item_id=?
                """,
                (asset_id, _json(subtitles), now, item["item_id"]),
            )
        elif asset_type == "base_video":
            connection.execute(
                """
                UPDATE project_items
                SET current_base_video_asset_id=?, current_video_asset_id=NULL,
                    status='BASE_VIDEO_READY', updated_at=?
                WHERE item_id=?
                """,
                (asset_id, now, item["item_id"]),
            )
        elif asset_type == "composition_video":
            subtitles = _object(item["subtitles_json"], _default_subtitles())
            if source_type == "user_upload":
                subtitles["bound_video_asset_id"] = None
                subtitles["status"] = (
                    "INVALIDATED"
                    if subtitles.get("source") or subtitles.get("raw_cues")
                    else "NOT_AVAILABLE"
                )
            else:
                subtitles["bound_video_asset_id"] = asset_id
            connection.execute(
                """
                UPDATE project_items
                SET current_video_asset_id=?, subtitles_json=?,
                    status='COMPOSITION_READY', updated_at=?
                WHERE item_id=?
                """,
                (asset_id, _json(subtitles), now, item["item_id"]),
            )
        elif asset_type == "variant_video":
            connection.execute(
                """
                UPDATE project_items
                SET status='VARIANT_READY', updated_at=?
                WHERE item_id=?
                """,
                (now, item["item_id"]),
            )
        else:
            raise ValueError(f"素材类型不能设为当前版本: {asset_type}")

    def _refresh_project_status(
        self, connection: sqlite3.Connection, project_id: str, *, now: str
    ) -> None:
        rows = connection.execute(
            """
            SELECT status, current_audio_asset_id, current_base_video_asset_id,
                   current_video_asset_id
            FROM project_items WHERE project_id=? ORDER BY position
            """,
            (project_id,),
        ).fetchall()
        statuses = [str(row["status"]) for row in rows]
        if any(status in ACTIVE_ITEM_STATUSES for status in statuses):
            project_status = "PROCESSING"
        elif statuses and all(status == "VARIANT_READY" for status in statuses):
            project_status = "VARIANT_READY"
        elif any(status in FAILED_ITEM_STATUSES for status in statuses):
            successful = any(
                row["current_audio_asset_id"]
                or row["current_base_video_asset_id"]
                or row["current_video_asset_id"]
                for row in rows
            )
            project_status = "PARTIAL_FAILED" if successful else "FAILED"
        elif rows and all(
            row["current_video_asset_id"]
            or str(row["status"]) in {"COMPOSITION_READY", "VARIANT_READY"}
            for row in rows
        ):
            project_status = "COMPOSITION_READY"
        elif rows and all(row["current_base_video_asset_id"] for row in rows):
            project_status = "BASE_VIDEO_READY"
        elif rows and all(row["current_audio_asset_id"] for row in rows):
            project_status = "AUDIO_READY"
        else:
            project_status = "DRAFT"
        connection.execute(
            "UPDATE projects SET status=?, updated_at=? WHERE project_id=?",
            (project_status, now, project_id),
        )

    def _project_payload(
        self, connection: sqlite3.Connection, project_id: str
    ) -> dict[str, Any]:
        project = connection.execute(
            "SELECT * FROM projects WHERE project_id=?", (project_id,)
        ).fetchone()
        if project is None:
            raise KeyError("项目不存在")
        item_rows = connection.execute(
            "SELECT * FROM project_items WHERE project_id=? ORDER BY position",
            (project_id,),
        ).fetchall()
        asset_rows = connection.execute(
            """
            SELECT * FROM project_assets
            WHERE project_id=? ORDER BY item_id, asset_type, version
            """,
            (project_id,),
        ).fetchall()
        operation_rows = connection.execute(
            """
            SELECT * FROM project_operations
            WHERE project_id=? ORDER BY rowid
            """,
            (project_id,),
        ).fetchall()
        link_rows = connection.execute(
            """
            SELECT * FROM project_links
            WHERE project_id=? ORDER BY rowid
            """,
            (project_id,),
        ).fetchall()
        input_image_rows = connection.execute(
            """
            SELECT * FROM project_input_images
            WHERE project_id=? ORDER BY position
            """,
            (project_id,),
        ).fetchall()
        script_source_rows = connection.execute(
            """
            SELECT * FROM project_script_sources
            WHERE project_id=? ORDER BY version
            """,
            (project_id,),
        ).fetchall()
        result_batch_rows = connection.execute(
            """
            SELECT * FROM project_result_batches
            WHERE project_id=? ORDER BY date_key, batch_no
            """,
            (project_id,),
        ).fetchall()

        assets_by_item: dict[str, list[dict[str, Any]]] = {}
        for row in asset_rows:
            asset = self._asset_payload(row)
            if asset["asset_type"] == "input_image":
                input_image_id = str(asset["external_ref"].get("input_image_id") or "")
                if input_image_id:
                    asset["url"] = (
                        f"/api/new/projects/{project_id}/images/{input_image_id}"
                    )
            assets_by_item.setdefault(str(row["item_id"]), []).append(asset)

        items: list[dict[str, Any]] = []
        for row in item_rows:
            assets = assets_by_item.get(str(row["item_id"]), [])
            by_id = {asset["asset_id"]: asset for asset in assets}
            history: dict[str, list[dict[str, Any]]] = {}
            for asset in assets:
                history.setdefault(asset["asset_type"], []).append(asset)
            current_audio = by_id.get(str(row["current_audio_asset_id"] or ""))
            current_base_video = by_id.get(
                str(row["current_base_video_asset_id"] or "")
            )
            current_video = by_id.get(str(row["current_video_asset_id"] or ""))
            current_image = by_id.get(str(row["current_image_asset_id"] or ""))
            variants = [
                asset
                for asset in assets
                if asset["asset_type"] == "variant_video"
                and asset["status"] == "READY"
            ]
            original_segments = [
                asset
                for asset in assets
                if asset["asset_type"] == "original_video_segment"
            ]
            subtitles = _object(row["subtitles_json"], _default_subtitles())
            item_payload = {
                "item_id": row["item_id"],
                "row_key": row["row_key"],
                "position": int(row["position"]),
                "script_text": row["script_text"],
                "status": row["status"],
                "settings": _object(row["settings_json"], {}),
                "inputs": {"image": current_image},
                "outputs": {
                    "audio": current_audio,
                    "base_video": current_base_video,
                    "composition_video": current_video,
                    "original_video_segments": original_segments,
                    "variants": variants,
                },
                "asset_history": history,
                "subtitles": subtitles,
                "content_analysis": _content_analysis_snapshot(
                    _object(row["content_analysis_json"], {}),
                    str(row["script_text"]),
                ),
                "visual_analysis": _visual_analysis_snapshot(
                    _object(row["visual_analysis_json"], {}),
                    str(row["script_text"]),
                    current_audio_asset_id=row["current_audio_asset_id"],
                    current_raw_cues=subtitles.get("raw_cues", []),
                    validate_media_binding=True,
                ),
                "created_at": row["created_at"],
                "updated_at": row["updated_at"],
            }
            item_payload["allowed_actions"] = self._item_actions(item_payload)
            items.append(item_payload)

        payload = {
            "schema": "jyd.project.v1",
            "project_id": project["project_id"],
            "project_no": project["project_no"],
            "name": project["name"],
            "status": project["status"],
            "revision": int(project["revision"]),
            "owner": {
                "user_id": project["owner_user_id"],
                "username": project["owner_username"],
            },
            "settings": _object(project["settings_json"], {}),
            "input_images": [
                self._input_image_payload(row) for row in input_image_rows
            ],
            "script_source": (
                self._script_source_payload(script_source_rows[-1])
                if script_source_rows
                else None
            ),
            "script_source_history": [
                self._script_source_payload(row) for row in script_source_rows
            ],
            "result_batches": [
                self._result_batch_payload(row) for row in result_batch_rows
            ],
            "items": items,
            "content_analysis_summary": self._content_analysis_summary(items),
            "visual_analysis_summary": self._visual_analysis_summary(items),
            "operations": [
                self._operation_payload(row) for row in operation_rows
            ],
            "links": [self._link_payload(row) for row in link_rows],
            "created_at": project["created_at"],
            "updated_at": project["updated_at"],
        }
        payload["allowed_actions"] = self._project_actions(payload)
        return payload

    @staticmethod
    def _item_actions(item: dict[str, Any]) -> dict[str, bool]:
        status = str(item["status"])
        outputs = item["outputs"]
        audio_ready = outputs["audio"] is not None
        base_video_ready = outputs["base_video"] is not None
        video_ready = outputs["composition_video"] is not None
        preview_ready = (
            base_video_ready
            and str(item.get("subtitles", {}).get("status") or "")
            == "PREVIEW_READY"
            and status in {"COMPOSITION_READY", "VARIANT_READY"}
        )
        composition_ready = video_ready or preview_ready
        active = status in ACTIVE_ITEM_STATUSES
        analysis_status = str(
            item.get("content_analysis", {}).get("overall_status") or "NOT_REQUESTED"
        )
        visual_status = str(
            item.get("visual_analysis", {}).get("analysis_status")
            or "NOT_REQUESTED"
        )
        return {
            "edit_inputs": status == "DRAFT",
            "delete_item": not active and analysis_status != "PENDING",
            "replace_image": status in IMAGE_EDITABLE_ITEM_STATUSES,
            "edit_postprocess": not active,
            "generate_audio": not active,
            "retry_audio": status == "AUDIO_FAILED",
            "download_audio": audio_ready,
            "start_composition": audio_ready and not base_video_ready and not active,
            "retry_composition": status == "COMPOSITION_FAILED" and not base_video_ready,
            "start_postprocess": base_video_ready and not composition_ready and not active,
            "retry_postprocess": status == "COMPOSITION_FAILED" and base_video_ready,
            "download_current_video": video_ready,
            "download_base_video": base_video_ready,
            "download_original_materials": bool(
                outputs["original_video_segments"]
            ),
            "upload_current_video": composition_ready and not active,
            "generate_variants": composition_ready and not active,
            "retry_variants": status == "VARIANT_FAILED",
            "analyze_content": not active and analysis_status != "PENDING",
            "retry_content_analysis": not active
            and analysis_status in {"FAILED", "PARTIAL"},
            "analyze_visuals": not active and visual_status != "PENDING",
            "retry_visual_analysis": not active and visual_status == "FAILED",
            "edit_visual_overlays": not active,
        }

    @staticmethod
    def _content_analysis_summary(items: list[dict[str, Any]]) -> dict[str, Any]:
        counts = {
            "NOT_REQUESTED": 0,
            "PENDING": 0,
            "SUCCESS": 0,
            "PARTIAL": 0,
            "FAILED": 0,
        }
        for item in items:
            status = str(
                item.get("content_analysis", {}).get("overall_status")
                or "NOT_REQUESTED"
            )
            counts[status if status in counts else "FAILED"] += 1
        if counts["PENDING"]:
            overall = "PENDING"
        elif counts["FAILED"] or counts["PARTIAL"]:
            overall = "PARTIAL" if counts["SUCCESS"] or counts["PARTIAL"] else "FAILED"
        elif counts["SUCCESS"] == len(items) and items:
            overall = "SUCCESS"
        else:
            overall = "NOT_REQUESTED"
        return {
            "status": overall,
            "total": len(items),
            "counts": counts,
            "concurrency_limit": 10,
        }

    @staticmethod
    def _visual_analysis_summary(items: list[dict[str, Any]]) -> dict[str, Any]:
        counts = {"NOT_REQUESTED": 0, "PENDING": 0, "SUCCESS": 0, "FAILED": 0}
        overlay_count = 0
        for item in items:
            analysis = item.get("visual_analysis", {})
            status = str(analysis.get("analysis_status") or "NOT_REQUESTED")
            counts[status if status in counts else "FAILED"] += 1
            overlay_count += sum(
                overlay.get("enabled") is not False
                for overlay in analysis.get("recipe", {}).get("overlays", [])
                if isinstance(overlay, dict)
            )
        if counts["PENDING"]:
            overall = "PENDING"
        elif counts["FAILED"]:
            overall = "PARTIAL" if counts["SUCCESS"] else "FAILED"
        elif counts["SUCCESS"] == len(items) and items:
            overall = "SUCCESS"
        else:
            overall = "NOT_REQUESTED"
        return {
            "status": overall,
            "total": len(items),
            "counts": counts,
            "overlay_count": overlay_count,
            "concurrency_limit": 10,
        }

    @staticmethod
    def _project_actions(project: dict[str, Any]) -> dict[str, bool]:
        items = project["items"]
        return {
            "edit_inputs": bool(items)
            and all(item["allowed_actions"]["edit_inputs"] for item in items),
            "analyze_content": bool(items)
            and any(item["allowed_actions"]["analyze_content"] for item in items),
            "retry_content_analysis": any(
                item["allowed_actions"]["retry_content_analysis"] for item in items
            ),
            "analyze_visuals": bool(items)
            and any(item["allowed_actions"]["analyze_visuals"] for item in items),
            "retry_visual_analysis": any(
                item["allowed_actions"]["retry_visual_analysis"] for item in items
            ),
            "manage_input_images": bool(items)
            and all(item["allowed_actions"]["replace_image"] for item in items),
            "apply_image_mapping": bool(project.get("input_images"))
            and bool(items)
            and all(item["allowed_actions"]["replace_image"] for item in items),
            "generate_audio": bool(items)
            and all(item["allowed_actions"]["generate_audio"] for item in items),
            "retry_audio": any(
                item["allowed_actions"]["retry_audio"] for item in items
            ),
            "start_composition": bool(items)
            and all(item["allowed_actions"]["start_composition"] for item in items),
            "retry_composition": any(
                item["allowed_actions"]["retry_composition"] for item in items
            ),
            "start_postprocess": bool(items)
            and all(item["allowed_actions"]["start_postprocess"] for item in items),
            "retry_postprocess": any(
                item["allowed_actions"]["retry_postprocess"] for item in items
            ),
            "download_audio": any(
                item["allowed_actions"]["download_audio"] for item in items
            ),
            "download_current_video": any(
                item["allowed_actions"]["download_current_video"] for item in items
            ),
            "download_base_video": any(
                item["allowed_actions"]["download_base_video"] for item in items
            ),
            "download_original_materials": any(
                item["allowed_actions"]["download_original_materials"]
                for item in items
            ),
            "generate_variants": bool(items)
            and all(item["allowed_actions"]["generate_variants"] for item in items),
            "retry_variants": any(
                item["allowed_actions"]["retry_variants"] for item in items
            ),
        }

    @staticmethod
    def _asset_payload(row: sqlite3.Row) -> dict[str, Any]:
        return {
            "asset_id": row["asset_id"],
            "asset_type": row["asset_type"],
            "version": int(row["version"]),
            "status": row["status"],
            "source_type": row["source_type"],
            "filename": row["filename"],
            "managed_path": row["managed_path"],
            "external_ref": _object(row["external_ref_json"], {}),
            "metadata": _object(row["metadata_json"], {}),
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }

    @staticmethod
    def _input_image_payload(row: sqlite3.Row) -> dict[str, Any]:
        return {
            "image_id": row["image_id"],
            "position": int(row["position"]),
            "filename": row["filename"],
            "content_type": row["content_type"],
            "size_bytes": int(row["size_bytes"]),
            "sha256": row["sha256"],
            "managed_path": row["managed_path"],
            "url": f"/api/new/projects/{row['project_id']}/images/{row['image_id']}",
            "created_at": row["created_at"],
        }

    @staticmethod
    def _script_source_payload(row: sqlite3.Row) -> dict[str, Any]:
        return {
            "source_id": row["source_id"],
            "version": int(row["version"]),
            "filename": row["filename"],
            "content_type": row["content_type"],
            "size_bytes": int(row["size_bytes"]),
            "sha256": row["sha256"],
            "managed_path": row["managed_path"],
            "created_at": row["created_at"],
        }

    @staticmethod
    def _result_batch_payload(row: sqlite3.Row) -> dict[str, Any]:
        return {
            "result_batch_id": row["result_batch_id"],
            "project_id": row["project_id"],
            "date_key": row["date_key"],
            "date_label": row["date_label"],
            "batch_no": int(row["batch_no"]),
            "export_path": row["export_path"],
            "operation_type": row["operation_type"],
            "status": row["status"],
            "jianying_batch_id": row["jianying_batch_id"],
            "error_message": row["error_message"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }

    @staticmethod
    def _operation_payload(row: sqlite3.Row) -> dict[str, Any]:
        return {
            "operation_id": row["operation_id"],
            "correlation_id": row["correlation_id"],
            "item_id": row["item_id"],
            "operation_type": row["operation_type"],
            "status": row["status"],
            "idempotency_key": row["idempotency_key"],
            "attempt_count": int(row["attempt_count"]),
            "error_code": row["error_code"],
            "error_message": row["error_message"],
            "payload": _object(row["payload_json"], {}),
            "result": _object(row["result_json"], {}),
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
            "started_at": row["started_at"],
            "finished_at": row["finished_at"],
        }

    @staticmethod
    def _link_payload(row: sqlite3.Row) -> dict[str, Any]:
        return {
            "link_id": row["link_id"],
            "item_id": row["item_id"],
            "system": row["system"],
            "relation": row["relation"],
            "external_id": row["external_id"],
            "metadata": _object(row["metadata_json"], {}),
            "created_at": row["created_at"],
        }
