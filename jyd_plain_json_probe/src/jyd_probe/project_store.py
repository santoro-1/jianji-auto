from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime
import json
from pathlib import Path
import sqlite3
import threading
from typing import Any, Iterator
import uuid


PROJECT_SCHEMA_VERSION = 1
MAX_PROJECT_ITEMS = 500

PROJECT_ITEM_STATUSES = {
    "DRAFT",
    "AUDIO_QUEUED",
    "AUDIO_RUNNING",
    "AUDIO_READY",
    "AUDIO_FAILED",
    "COMPOSITION_QUEUED",
    "COMPOSITION_RUNNING",
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
    "COMPOSITION_RUNNING",
    "VARIANT_QUEUED",
    "VARIANT_RUNNING",
}

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
        "style": {
            "font_id": None,
            "font_size": 15,
            "max_width_ratio": 0.82,
            "max_lines": 2,
        },
        "status": "NOT_AVAILABLE",
        "overflow_risk": False,
    }


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
                    current_audio_asset_id TEXT,
                    current_video_asset_id TEXT,
                    subtitles_json TEXT NOT NULL DEFAULT '{}',
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

                CREATE TABLE IF NOT EXISTS project_operations (
                    operation_id TEXT PRIMARY KEY,
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
                """
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
                        status, subtitles_json, settings_json, created_at, updated_at
                    ) VALUES(?, ?, ?, ?, ?, 'DRAFT', ?, ?, ?, ?)
                    """,
                    (
                        item["item_id"],
                        project_id,
                        item["row_key"],
                        item["position"],
                        item["script_text"],
                        _json(_default_subtitles()),
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
            if item["status"] != "DRAFT":
                raise ValueError("当前脚本行已进入生成流程，不能直接修改输入")
            updates: list[str] = []
            values: list[Any] = []
            if row_key is not None:
                updates.append("row_key=?")
                values.append(_clean_row_key(row_key, int(item["position"])))
            if script_text is not None:
                updates.append("script_text=?")
                values.append(_clean_script(script_text))
            if settings is not None:
                if not isinstance(settings, dict):
                    raise ValueError("脚本行设置必须是对象")
                updates.append("settings_json=?")
                values.append(_json(settings))
            if updates:
                now = _now()
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

    def create_operation(
        self,
        *,
        owner_user_id: str,
        project_id: str,
        operation_type: str,
        idempotency_key: str,
        item_id: str | None = None,
        payload: dict[str, Any] | None = None,
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
            connection.execute(
                """
                INSERT INTO project_operations(
                    operation_id, project_id, item_id, operation_type,
                    status, idempotency_key, payload_json, result_json,
                    created_at, updated_at
                ) VALUES(?, ?, ?, ?, 'PENDING', ?, ?, '{}', ?, ?)
                """,
                (
                    operation_id,
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
                    "VARIANT_GENERATE": "VARIANT_QUEUED",
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
            return self._operation_payload(row)

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
                SET current_audio_asset_id=?, current_video_asset_id=NULL,
                    subtitles_json=?, status='AUDIO_READY', updated_at=?
                WHERE item_id=?
                """,
                (asset_id, _json(subtitles), now, item["item_id"]),
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
            SELECT status, current_audio_asset_id, current_video_asset_id
            FROM project_items WHERE project_id=? ORDER BY position
            """,
            (project_id,),
        ).fetchall()
        statuses = [str(row["status"]) for row in rows]
        if any(status in ACTIVE_ITEM_STATUSES for status in statuses):
            project_status = "PROCESSING"
        elif statuses and all(status == "VARIANT_READY" for status in statuses):
            project_status = "VARIANT_READY"
        elif rows and all(row["current_video_asset_id"] for row in rows):
            project_status = "COMPOSITION_READY"
        elif rows and all(row["current_audio_asset_id"] for row in rows):
            project_status = "AUDIO_READY"
        elif any(status in FAILED_ITEM_STATUSES for status in statuses):
            successful = any(
                row["current_audio_asset_id"] or row["current_video_asset_id"]
                for row in rows
            )
            project_status = "PARTIAL_FAILED" if successful else "FAILED"
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
            WHERE project_id=? ORDER BY created_at, operation_id
            """,
            (project_id,),
        ).fetchall()
        link_rows = connection.execute(
            """
            SELECT * FROM project_links
            WHERE project_id=? ORDER BY created_at, link_id
            """,
            (project_id,),
        ).fetchall()

        assets_by_item: dict[str, list[dict[str, Any]]] = {}
        for row in asset_rows:
            assets_by_item.setdefault(str(row["item_id"]), []).append(
                self._asset_payload(row)
            )

        items: list[dict[str, Any]] = []
        for row in item_rows:
            assets = assets_by_item.get(str(row["item_id"]), [])
            by_id = {asset["asset_id"]: asset for asset in assets}
            history: dict[str, list[dict[str, Any]]] = {}
            for asset in assets:
                history.setdefault(asset["asset_type"], []).append(asset)
            current_audio = by_id.get(str(row["current_audio_asset_id"] or ""))
            current_video = by_id.get(str(row["current_video_asset_id"] or ""))
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
            item_payload = {
                "item_id": row["item_id"],
                "row_key": row["row_key"],
                "position": int(row["position"]),
                "script_text": row["script_text"],
                "status": row["status"],
                "settings": _object(row["settings_json"], {}),
                "outputs": {
                    "audio": current_audio,
                    "composition_video": current_video,
                    "original_video_segments": original_segments,
                    "variants": variants,
                },
                "asset_history": history,
                "subtitles": _object(row["subtitles_json"], _default_subtitles()),
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
            "items": items,
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
        video_ready = outputs["composition_video"] is not None
        active = status in ACTIVE_ITEM_STATUSES
        return {
            "edit_inputs": status == "DRAFT",
            "generate_audio": status in {"DRAFT", "AUDIO_FAILED"},
            "retry_audio": status == "AUDIO_FAILED",
            "download_audio": audio_ready,
            "start_composition": audio_ready and not active,
            "retry_composition": status == "COMPOSITION_FAILED",
            "download_current_video": video_ready,
            "download_original_materials": bool(
                outputs["original_video_segments"]
            ),
            "upload_current_video": video_ready and not active,
            "generate_variants": video_ready and not active,
            "retry_variants": status == "VARIANT_FAILED",
        }

    @staticmethod
    def _project_actions(project: dict[str, Any]) -> dict[str, bool]:
        items = project["items"]
        return {
            "edit_inputs": bool(items)
            and all(item["allowed_actions"]["edit_inputs"] for item in items),
            "generate_audio": any(
                item["allowed_actions"]["generate_audio"] for item in items
            ),
            "retry_audio": any(
                item["allowed_actions"]["retry_audio"] for item in items
            ),
            "start_composition": bool(items)
            and all(item["allowed_actions"]["start_composition"] for item in items),
            "retry_composition": any(
                item["allowed_actions"]["retry_composition"] for item in items
            ),
            "download_audio": any(
                item["allowed_actions"]["download_audio"] for item in items
            ),
            "download_current_video": any(
                item["allowed_actions"]["download_current_video"] for item in items
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
    def _operation_payload(row: sqlite3.Row) -> dict[str, Any]:
        return {
            "operation_id": row["operation_id"],
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
