from __future__ import annotations

from pathlib import Path
import hashlib
import shutil
import sys
import unittest
import uuid
from unittest.mock import patch

from fastapi.testclient import TestClient


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from jyd_probe.project_store import ProjectStore  # noqa: E402
from jyd_probe.project_composition import REMOTE_COMPOSITION_ACTIVE  # noqa: E402
from jyd_probe.project_store import ACTIVE_ITEM_STATUSES, PROJECT_ITEM_STATUSES  # noqa: E402
from jyd_probe.web_api import WebApiSettings, create_app  # noqa: E402


class ProjectCompositionApiTest(unittest.TestCase):
    def setUp(self) -> None:
        self.root = (
            PROJECT_ROOT
            / "runtime"
            / "test_tmp"
            / f"project_composition_{uuid.uuid4().hex}"
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

    def test_generate_downloads_original_segments_and_base_video_only(self) -> None:
        user = {
            "user_id": "composition-user",
            "username": "tester",
            "enabled": True,
            "is_admin": True,
        }
        store = ProjectStore(self.settings.storage_root / "control.db")
        project = store.create_project(
            owner_user_id=user["user_id"],
            owner_username=user["username"],
            name="4A 测试",
            items=[{"row_key": "1", "script_text": "第一条。"}],
        )
        item = project["items"][0]
        image_path = self.settings.storage_root / "seed-person.png"
        image_path.write_bytes(b"\x89PNG\r\n\x1a\npayload")
        store.register_input_image(
            owner_user_id=user["user_id"],
            project_id=project["project_id"],
            filename="seed-person.png",
            content_type="image/png",
            size_bytes=image_path.stat().st_size,
            sha256=hashlib.sha256(image_path.read_bytes()).hexdigest(),
            managed_path=str(image_path),
        )
        store.apply_image_strategy(
            user["user_id"],
            project["project_id"],
            strategy="loop",
            reuse_count=1,
        )
        audio_path = self.settings.storage_root / "seed-audio.mp3"
        audio_path.write_bytes(b"audio")
        store.add_asset(
            owner_user_id=user["user_id"],
            project_id=project["project_id"],
            item_id=item["item_id"],
            asset_type="audio",
            source_type="minimax",
            status="READY",
            filename="1.mp3",
            managed_path=str(audio_path),
            make_current=True,
        )
        replacement_path = self.settings.storage_root / "latest-person.png"
        replacement_path.write_bytes(b"\x89PNG\r\n\x1a\nlatest")
        replacement = store.register_input_image(
            owner_user_id=user["user_id"],
            project_id=project["project_id"],
            filename="latest-person.png",
            content_type="image/png",
            size_bytes=replacement_path.stat().st_size,
            sha256=hashlib.sha256(replacement_path.read_bytes()).hexdigest(),
            managed_path=str(replacement_path),
        )
        store.replace_item_image(
            user["user_id"],
            project["project_id"],
            item["item_id"],
            replacement["image_id"],
        )
        store.add_link(
            owner_user_id=user["user_id"],
            project_id=project["project_id"],
            item_id=item["item_id"],
            system="runninghub",
            relation="digital_human_audio_item",
            external_id="remote-item-1",
            metadata={
                "batch_id": "remote-batch-1",
                "correlation_id": "composition-correlation-1",
            },
        )

        remote_ready = {
            "item_id": "remote-item-1",
            "updated_at": "2026-08-04T12:00:00+08:00",
            "source": {
                "type": "single_video",
                "videos": [
                    {
                        "index": 1,
                        "task_id": "runninghub-task-1",
                        "status": "SUCCESS",
                        "script_text": "第一条。",
                        "start_seconds": 0.0,
                        "end_seconds": 3.0,
                        "quality_variant": "seedvr2_upscaled",
                        "source_download_url": (
                            "/api/workbench/tasks/remote-item-1/videos/1/source"
                        ),
                    }
                ],
            },
            "composition": {
                "status": "BASE_VIDEO_READY",
                "segment_count": 1,
                "base_video_ready": True,
                "image_sha256": hashlib.sha256(
                    replacement_path.read_bytes()
                ).hexdigest(),
            },
        }

        def write_segment(_self, _token, _item_id, _index, target, *, max_bytes):
            Path(target).parent.mkdir(parents=True, exist_ok=True)
            Path(target).write_bytes(b"original-segment")
            return len(b"original-segment")

        def write_base(_self, _token, _item_id, target, *, max_bytes):
            Path(target).parent.mkdir(parents=True, exist_ok=True)
            Path(target).write_bytes(b"normalized-base")
            return len(b"normalized-base")

        with patch(
            "jyd_probe.auth_center.AuthCenterClient.login",
            return_value={"access_token": "token", "user": user},
        ), patch(
            "jyd_probe.auth_center.AuthCenterClient.verify", return_value=user
        ), patch(
            "jyd_probe.auth_center.AuthCenterClient.list_workbench_execution_accounts",
            return_value={
                "accounts": [
                    {"id": 11, "name": "pool-11"},
                    {"id": 22, "name": "pool-22"},
                ],
                "default_selected_account_ids": [11, 22],
            },
        ), patch(
            "jyd_probe.auth_center.AuthCenterClient.upload_workbench_batch_asset",
            return_value={
                "asset_id": "staged-image-1",
                "original_name": "seed-person.png",
            },
        ) as upload_remote, patch(
            "jyd_probe.auth_center.AuthCenterClient.start_workbench_composition",
            return_value={
                "item_id": "remote-item-1",
                "composition": {"status": "COMPOSITION_QUEUED"},
            },
        ) as start_remote, patch(
            "jyd_probe.auth_center.AuthCenterClient.backfill_workbench_video_enhancement",
            return_value={
                "item_id": "remote-item-1",
                "composition": {"status": "VIDEO_ENHANCING"},
            },
        ) as backfill_remote, patch(
            "jyd_probe.auth_center.AuthCenterClient.get_workbench_task",
            return_value=remote_ready,
        ) as get_remote, patch(
            "jyd_probe.auth_center.AuthCenterClient.download_workbench_video",
            new=write_segment,
        ), patch(
            "jyd_probe.auth_center.AuthCenterClient.download_workbench_base_video",
            new=write_base,
        ):
            with TestClient(create_app(self.settings)) as client:
                login = client.post(
                    "/api/auth/login",
                    json={"username": "tester", "password": "pass123"},
                )
                self.assertEqual(login.status_code, 200, login.text)
                pool_summary = client.get(
                    "/api/new/runninghub-execution-accounts"
                )
                self.assertEqual(pool_summary.status_code, 200, pool_summary.text)
                self.assertEqual(
                    pool_summary.json()["default_selected_account_ids"], [11, 22]
                )
                missing_selection = client.post(
                    f"/api/new/projects/{project['project_id']}/composition/generate",
                    json={
                        "cost_confirmed": True,
                        "idempotency_key": "composition-missing-selection",
                    },
                )
                self.assertEqual(missing_selection.status_code, 422)
                invalid_selection = client.post(
                    f"/api/new/projects/{project['project_id']}/composition/generate",
                    json={
                        "cost_confirmed": True,
                        "idempotency_key": "composition-invalid-selection",
                        "runninghub_execution_account_ids": ["11"],
                    },
                )
                self.assertEqual(invalid_selection.status_code, 422)
                generated = client.post(
                    f"/api/new/projects/{project['project_id']}/composition/generate",
                    json={
                        "cost_confirmed": True,
                        "idempotency_key": "composition-1",
                        "resolution": "2048",
                        "runninghub_execution_account_ids": [22, 11],
                    },
                )
                self.assertEqual(generated.status_code, 200, generated.text)
                payload = generated.json()
                current = payload["items"][0]
                self.assertEqual(payload["status"], "BASE_VIDEO_READY")
                self.assertEqual(current["status"], "BASE_VIDEO_READY")
                self.assertIsNotNone(current["outputs"]["base_video"])
                self.assertEqual(len(current["outputs"]["original_video_segments"]), 1)
                segment_asset = current["outputs"]["original_video_segments"][0]
                self.assertEqual(
                    segment_asset["metadata"]["quality_variant"],
                    "seedvr2_upscaled",
                )
                self.assertEqual(
                    segment_asset["metadata"]["enhanced_by"],
                    "runninghub_seedvr2",
                )
                self.assertTrue(
                    segment_asset["metadata"]["source_is_available_on_cloud"]
                )
                self.assertIsNone(current["outputs"]["composition_video"])
                self.assertEqual(current["outputs"]["variants"], [])
                self.assertFalse(payload["allowed_actions"]["generate_variants"])
                start_remote.assert_called_once()
                self.assertEqual(
                    Path(upload_remote.call_args.args[1]), replacement_path.resolve()
                )
                self.assertEqual(
                    start_remote.call_args.kwargs["image_asset_id"],
                    "staged-image-1",
                )
                self.assertEqual(
                    start_remote.call_args.kwargs["image_sha256"],
                    hashlib.sha256(replacement_path.read_bytes()).hexdigest(),
                )
                self.assertEqual(
                    start_remote.call_args.kwargs["correlation_id"],
                    "composition-correlation-1",
                )
                self.assertEqual(
                    start_remote.call_args.kwargs["resolution"],
                    "2048",
                )
                self.assertEqual(
                    start_remote.call_args.kwargs[
                        "runninghub_execution_account_ids"
                    ],
                    [11, 22],
                )
                operation = next(
                    value
                    for value in payload["operations"]
                    if value["operation_type"] == "COMPOSITION_GENERATE"
                )
                self.assertEqual(
                    operation["payload"]["runninghub_execution_account_ids"],
                    [11, 22],
                )
                self.assertEqual(operation["payload"]["resolution"], "2048")

                synced = client.get(
                    f"/api/new/projects/{project['project_id']}/composition/status"
                )
                self.assertEqual(synced.status_code, 200, synced.text)
                synced_item = synced.json()["items"][0]
                self.assertEqual(
                    len(synced_item["asset_history"]["original_video_segment"]), 1
                )
                self.assertEqual(len(synced_item["asset_history"]["base_video"]), 1)
                self.assertEqual(
                    get_remote.call_count,
                    1,
                    "已完成的画面操作不应在后续状态轮询中再次请求云端",
                )

                reused = client.post(
                    f"/api/new/projects/{project['project_id']}/composition/generate",
                    json={
                        "cost_confirmed": True,
                        "idempotency_key": "composition-single-reuse",
                        "runninghub_execution_account_ids": [11, 22],
                        "item_ids": [item["item_id"]],
                    },
                )
                self.assertEqual(reused.status_code, 200, reused.text)
                self.assertEqual(
                    reused.json()["items"][0]["outputs"]["base_video"]["asset_id"],
                    synced_item["outputs"]["base_video"]["asset_id"],
                )
                start_remote.assert_called_once()

                downloaded = client.get(
                    f"/api/new/projects/{project['project_id']}/items/{item['item_id']}/base-video"
                )
                self.assertEqual(downloaded.status_code, 200, downloaded.text)
                self.assertEqual(downloaded.content, b"normalized-base")

                invalidated = store.set_digital_human_resolution(
                    user["user_id"],
                    project["project_id"],
                    resolution="1920",
                )
                invalidated_item = invalidated["items"][0]
                self.assertEqual(invalidated_item["status"], "AUDIO_READY")
                self.assertIsNone(invalidated_item["outputs"]["base_video"])
                self.assertIsNone(invalidated_item["outputs"]["composition_video"])
                self.assertEqual(
                    invalidated_item["settings"]["composition_invalidated_reason"],
                    "DIGITAL_HUMAN_RESOLUTION_CHANGED",
                )
                self.assertEqual(
                    len(invalidated_item["asset_history"]["base_video"]), 1
                )

                active_remote = {
                    **remote_ready,
                    "composition": {
                        **remote_ready["composition"],
                        "status": "VIDEO_ENHANCING",
                        "base_video_ready": False,
                    },
                }
                get_remote.return_value = active_remote
                regenerated = client.post(
                    f"/api/new/projects/{project['project_id']}/composition/generate",
                    json={
                        "cost_confirmed": True,
                        "idempotency_key": "composition-resolution-1920",
                        "resolution": "1920",
                        "runninghub_execution_account_ids": [11, 22],
                        "item_ids": [item["item_id"]],
                    },
                )
                self.assertEqual(regenerated.status_code, 200, regenerated.text)
                start_remote.assert_called_once()
                upload_remote.assert_called_once()
                backfill_remote.assert_called_once_with(
                    "token",
                    "remote-item-1",
                    idempotency_key=(
                        f"composition-resolution-1920:{item['item_id']}"
                    ),
                )
                backfill_operation = next(
                    value
                    for value in regenerated.json()["operations"]
                    if value["operation_type"] == "COMPOSITION_GENERATE"
                    and value["idempotency_key"] == "composition-resolution-1920"
                )
                self.assertEqual(
                    backfill_operation["payload"]["scope"],
                    "seedvr2_backfill_only",
                )
                self.assertNotIn(
                    "input_image_sha256", backfill_operation["payload"]
                )

                store.transition_operation(
                    user["user_id"],
                    project["project_id"],
                    item["item_id"],
                    operation_type="COMPOSITION_GENERATE",
                    status="FAILED",
                    item_status="COMPOSITION_FAILED",
                    error_code="TEST_FAILURE",
                    error_message="模拟失败",
                )
                retried = client.post(
                    f"/api/new/projects/{project['project_id']}/items/{item['item_id']}/composition/retry",
                    json={
                        "cost_confirmed": True,
                        "idempotency_key": "composition-resolution-1920-retry",
                    },
                )
                self.assertEqual(retried.status_code, 200, retried.text)
                start_remote.assert_called_once()
                self.assertEqual(backfill_remote.call_count, 2)
                backfill_remote.assert_called_with(
                    "token",
                    "remote-item-1",
                    idempotency_key=(
                        f"composition-resolution-1920-retry:{item['item_id']}"
                    ),
                )

                resolution_ready = {
                    **remote_ready,
                    "updated_at": "2026-08-04T12:30:00+08:00",
                    "source": {
                        **remote_ready["source"],
                        "videos": [
                            {
                                **remote_ready["source"]["videos"][0],
                                "task_id": "runninghub-task-2",
                            }
                        ],
                    },
                    "composition": {
                        **remote_ready["composition"],
                        "status": "BASE_VIDEO_READY",
                        "base_video_ready": True,
                    },
                }
                get_remote.return_value = resolution_ready
                completed_resolution = client.get(
                    f"/api/new/projects/{project['project_id']}/composition/status"
                )
                self.assertEqual(
                    completed_resolution.status_code, 200, completed_resolution.text
                )
                completed_item = completed_resolution.json()["items"][0]
                self.assertIsNotNone(completed_item["outputs"]["base_video"])
                self.assertNotIn(
                    "composition_invalidated_reason", completed_item["settings"]
                )

    def test_video_enhancing_is_a_supported_active_remote_status(self) -> None:
        self.assertIn("VIDEO_ENHANCING", REMOTE_COMPOSITION_ACTIVE)
        self.assertIn("VIDEO_ENHANCING", PROJECT_ITEM_STATUSES)
        self.assertIn("VIDEO_ENHANCING", ACTIVE_ITEM_STATUSES)


if __name__ == "__main__":
    unittest.main()
