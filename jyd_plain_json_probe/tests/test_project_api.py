from __future__ import annotations

from pathlib import Path
import shutil
import sqlite3
import sys
import unittest
import uuid
from unittest.mock import patch

from fastapi.testclient import TestClient


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from jyd_probe.project_store import ProjectStore  # noqa: E402
from jyd_probe.task_store import SQLiteTaskStore  # noqa: E402
from jyd_probe.web_api import WebApiSettings, create_app  # noqa: E402


class ProjectApiTest(unittest.TestCase):
    def setUp(self) -> None:
        self.root = (
            PROJECT_ROOT / "runtime" / "test_tmp" / f"project_api_{uuid.uuid4().hex}"
        )
        self.root.mkdir(parents=True)
        self.settings = WebApiSettings(
            storage_root=self.root / "storage",
            template_library_root=self.root / "templates",
            default_draft_root=self.root / "drafts",
            audio_library_root=self.root / "audio",
            admin_password="admin-pass",
            admin_session_secret="admin-secret",
            auth_authority=False,
            auth_server_url="http://127.0.0.1:8000",
            execution_mode="agent",
        )
        for directory in (
            self.settings.storage_root,
            self.settings.template_library_root,
            self.settings.default_draft_root,
            self.settings.audio_library_root,
        ):
            directory.mkdir(parents=True, exist_ok=True)

    def tearDown(self) -> None:
        shutil.rmtree(self.root, ignore_errors=True)

    @staticmethod
    def _login(client: TestClient, user: dict[str, object]) -> None:
        with patch(
            "jyd_probe.auth_center.AuthCenterClient.login",
            return_value={"access_token": f"token-{user['user_id']}", "user": user},
        ):
            response = client.post(
                "/api/auth/login",
                json={"username": user["username"], "password": "pass123"},
            )
        if response.status_code != 200:
            raise AssertionError(response.text)

    def test_project_contract_is_owned_and_contains_backend_actions(self) -> None:
        first_user = {"user_id": "user-1", "username": "tester-1", "enabled": True}
        second_user = {"user_id": "user-2", "username": "tester-2", "enabled": True}
        active_user = first_user

        def verify(_client, _token):
            return active_user

        with patch("jyd_probe.auth_center.AuthCenterClient.verify", new=verify):
            app = create_app(self.settings)
            with TestClient(app) as client:
                self._login(client, first_user)
                created = client.post(
                    "/api/new/projects",
                    json={
                        "name": "八月数字人口播",
                        "items": [
                            {"row_key": "001", "script_text": "第一条口播。"},
                            {"row_key": "002", "script_text": "第二条口播。"},
                        ],
                    },
                )
                self.assertEqual(created.status_code, 201, created.text)
                project = created.json()
                self.assertEqual(project["schema"], "jyd.project.v1")
                self.assertRegex(project["project_no"], r"^DH-\d{8}-\d{4}$")
                self.assertEqual(project["status"], "DRAFT")
                self.assertEqual(len(project["items"]), 2)
                self.assertTrue(project["allowed_actions"]["edit_inputs"])
                self.assertTrue(project["allowed_actions"]["generate_audio"])
                self.assertFalse(project["allowed_actions"]["start_composition"])
                self.assertFalse(project["allowed_actions"]["generate_variants"])

                item = project["items"][0]
                self.assertIsNone(item["outputs"]["audio"])
                self.assertIsNone(item["outputs"]["composition_video"])
                self.assertEqual(item["outputs"]["variants"], [])
                self.assertEqual(item["subtitles"]["status"], "NOT_AVAILABLE")
                self.assertEqual(item["subtitles"]["raw_cues"], [])
                self.assertEqual(item["subtitles"]["render_cues"], [])
                self.assertEqual(item["subtitles"]["style"]["max_lines"], 2)

                detail = client.get(f"/api/new/projects/{project['project_id']}")
                self.assertEqual(detail.status_code, 200)
                listing = client.get("/api/new/projects")
                self.assertEqual(listing.status_code, 200)
                self.assertEqual(listing.json()["total"], 1)

                active_user = second_user
                client.cookies.clear()
                self._login(client, second_user)
                hidden = client.get(f"/api/new/projects/{project['project_id']}")
                self.assertEqual(hidden.status_code, 404)
                self.assertEqual(client.get("/api/new/projects").json()["total"], 0)

    def test_draft_project_and_item_can_be_updated(self) -> None:
        user = {"user_id": "user-1", "username": "tester", "enabled": True}
        with patch("jyd_probe.auth_center.AuthCenterClient.verify", return_value=user):
            app = create_app(self.settings)
            with TestClient(app) as client:
                self._login(client, user)
                project = client.post(
                    "/api/new/projects",
                    json={
                        "name": "旧名称",
                        "items": [{"row_key": "001", "script_text": "旧脚本"}],
                    },
                ).json()
                renamed = client.patch(
                    f"/api/new/projects/{project['project_id']}",
                    json={"name": "新名称", "expected_revision": project["revision"]},
                )
                self.assertEqual(renamed.status_code, 200, renamed.text)
                item = renamed.json()["items"][0]
                edited = client.patch(
                    f"/api/new/projects/{project['project_id']}/items/{item['item_id']}",
                    json={"script_text": "修改后的脚本", "row_key": "A-001"},
                )
                self.assertEqual(edited.status_code, 200, edited.text)
                self.assertEqual(edited.json()["items"][0]["script_text"], "修改后的脚本")
                self.assertEqual(edited.json()["items"][0]["row_key"], "A-001")

    def test_asset_versions_preserve_history_and_change_current_pointer(self) -> None:
        store = ProjectStore(self.settings.storage_root / "control.db")
        project = store.create_project(
            owner_user_id="user-1",
            owner_username="tester",
            name="素材版本测试",
            items=[{"row_key": "001", "script_text": "测试口播。"}],
        )
        item_id = project["items"][0]["item_id"]

        first = store.add_asset(
            owner_user_id="user-1",
            project_id=project["project_id"],
            item_id=item_id,
            asset_type="composition_video",
            source_type="auto_composition",
            status="READY",
            filename="auto.mp4",
            make_current=True,
        )
        second = store.add_asset(
            owner_user_id="user-1",
            project_id=project["project_id"],
            item_id=item_id,
            asset_type="composition_video",
            source_type="user_upload",
            status="READY",
            filename="rough-cut.mp4",
            make_current=True,
        )

        self.assertEqual(first["version"], 1)
        self.assertEqual(second["version"], 2)
        detail = store.get_project("user-1", project["project_id"])
        current = detail["items"][0]["outputs"]["composition_video"]
        self.assertEqual(current["asset_id"], second["asset_id"])
        history = detail["items"][0]["asset_history"]["composition_video"]
        self.assertEqual([asset["version"] for asset in history], [1, 2])
        self.assertTrue(detail["allowed_actions"]["generate_variants"])

    def test_project_voice_applies_atomically_and_preserves_old_audio_history(self) -> None:
        store = ProjectStore(self.settings.storage_root / "control.db")
        project = store.create_project(
            owner_user_id="user-1",
            owner_username="tester",
            name="项目默认音色测试",
            items=[
                {"row_key": "001", "script_text": "第一条。"},
                {"row_key": "002", "script_text": "第二条。"},
            ],
        )
        first_item_id = project["items"][0]["item_id"]
        selected = store.configure_project_voice(
            "user-1",
            project["project_id"],
            voice_asset_id="saved-voice-1",
        )
        self.assertEqual(
            [item["settings"]["voice_asset_id"] for item in selected["items"]],
            ["saved-voice-1", "saved-voice-1"],
        )
        self.assertEqual(
            selected["settings"]["default_voice_asset_id"], "saved-voice-1"
        )
        self.assertEqual(
            store.get_voice_preferences("user-1")["default_voice_asset_id"],
            "saved-voice-1",
        )

        old_audio = store.add_asset(
            owner_user_id="user-1",
            project_id=project["project_id"],
            item_id=first_item_id,
            asset_type="audio",
            source_type="minimax",
            status="READY",
            filename="old.mp3",
            make_current=True,
        )
        changed = store.configure_project_voice(
            "user-1",
            project["project_id"],
            voice_asset_id="saved-voice-2",
        )
        first = changed["items"][0]
        self.assertEqual(first["status"], "DRAFT")
        self.assertIsNone(first["outputs"]["audio"])
        self.assertEqual(
            first["asset_history"]["audio"][0]["asset_id"], old_audio["asset_id"]
        )
        self.assertTrue(
            all(
                item["settings"]["voice_asset_id"] == "saved-voice-2"
                for item in changed["items"]
            )
        )

    def test_project_tables_do_not_modify_existing_render_queue_schema_or_rows(self) -> None:
        database = self.settings.storage_root / "control.db"
        task_store = SQLiteTaskStore(database)
        task_store.add_batch(
            {"batch_id": "existing-batch", "created_at": "2026-08-04T00:00:00"}
        )
        task_store.add_job(
            "existing-job",
            {"schema": "jyd.render_job.v1"},
            {
                "job_id": "existing-job",
                "batch_id": "existing-batch",
                "status": "pending",
                "created_at": "2026-08-04T00:00:00",
            },
        )

        ProjectStore(database)

        self.assertEqual(task_store.get_status("existing-job")["status"], "pending")
        with sqlite3.connect(database) as connection:
            render_schema_version = connection.execute(
                "SELECT value FROM schema_meta WHERE key='version'"
            ).fetchone()[0]
            project_schema_version = connection.execute(
                "SELECT value FROM project_schema_meta WHERE key='version'"
            ).fetchone()[0]
        self.assertEqual(render_schema_version, "1")
        self.assertEqual(project_schema_version, "3")

    def test_operations_are_idempotent_and_external_links_are_preserved(self) -> None:
        store = ProjectStore(self.settings.storage_root / "control.db")
        project = store.create_project(
            owner_user_id="user-1",
            owner_username="tester",
            name="编排关系测试",
            items=[{"row_key": "001", "script_text": "测试口播。"}],
        )
        item_id = project["items"][0]["item_id"]

        first_operation = store.create_operation(
            owner_user_id="user-1",
            project_id=project["project_id"],
            item_id=item_id,
            operation_type="AUDIO_GENERATE",
            idempotency_key="audio-request-1",
            payload={"voice_asset_id": "voice-1"},
        )
        repeated_operation = store.create_operation(
            owner_user_id="user-1",
            project_id=project["project_id"],
            item_id=item_id,
            operation_type="AUDIO_GENERATE",
            idempotency_key="audio-request-1",
            payload={"voice_asset_id": "voice-1"},
        )
        self.assertEqual(
            first_operation["operation_id"], repeated_operation["operation_id"]
        )
        self.assertEqual(
            store.get_project("user-1", project["project_id"])["status"],
            "PROCESSING",
        )

        first_link = store.add_link(
            owner_user_id="user-1",
            project_id=project["project_id"],
            item_id=item_id,
            system="digital_human",
            relation="generation_batch_item",
            external_id="digital-item-1",
        )
        repeated_link = store.add_link(
            owner_user_id="user-1",
            project_id=project["project_id"],
            item_id=item_id,
            system="digital_human",
            relation="generation_batch_item",
            external_id="digital-item-1",
        )
        self.assertEqual(first_link["link_id"], repeated_link["link_id"])
        detail = store.get_project("user-1", project["project_id"])
        self.assertEqual(len(detail["operations"]), 1)
        self.assertEqual(len(detail["links"]), 1)

    def test_current_audio_binds_subtitle_placeholder_and_enables_composition(self) -> None:
        store = ProjectStore(self.settings.storage_root / "control.db")
        project = store.create_project(
            owner_user_id="user-1",
            owner_username="tester",
            name="字幕绑定测试",
            items=[{"row_key": "001", "script_text": "测试口播。"}],
        )
        item_id = project["items"][0]["item_id"]
        audio = store.add_asset(
            owner_user_id="user-1",
            project_id=project["project_id"],
            item_id=item_id,
            asset_type="audio",
            source_type="minimax",
            status="READY",
            filename="speech.mp3",
            make_current=True,
        )
        detail = store.get_project("user-1", project["project_id"])
        item = detail["items"][0]
        self.assertEqual(detail["status"], "AUDIO_READY")
        self.assertEqual(
            item["subtitles"]["bound_audio_asset_id"], audio["asset_id"]
        )
        self.assertEqual(item["subtitles"]["status"], "PENDING_TIMESTAMPS")
        self.assertTrue(detail["allowed_actions"]["start_composition"])


if __name__ == "__main__":
    unittest.main()
