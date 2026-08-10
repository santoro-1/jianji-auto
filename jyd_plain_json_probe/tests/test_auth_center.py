from __future__ import annotations

import io
import json
from pathlib import Path
import shutil
import sys
import unittest
import uuid
from unittest.mock import patch

from fastapi.testclient import TestClient


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from jyd_probe.auth_center import AuthCenterClient, AuthCenterError  # noqa: E402
from jyd_probe.web_api import WebApiSettings, create_app  # noqa: E402


class _Response:
    status = 200

    def __init__(self, payload: dict):
        self.stream = io.BytesIO(json.dumps(payload).encode("utf-8"))

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return None

    def read(self) -> bytes:
        return self.stream.read()


class AuthCenterTest(unittest.TestCase):
    def test_client_reads_center_token_and_user(self) -> None:
        payload = {
            "access_token": "center-token",
            "user": {"user_id": "u1", "username": "tester", "enabled": True},
        }
        with patch("jyd_probe.auth_center.urlopen", return_value=_Response(payload)):
            result = AuthCenterClient("http://192.168.11.28:8000").login("tester", "pass123")
        self.assertEqual(result["access_token"], "center-token")
        self.assertEqual(result["user"]["username"], "tester")

    def test_client_requests_one_time_browser_handoff(self) -> None:
        with patch(
            "jyd_probe.auth_center.urlopen",
            return_value=_Response({"handoff_code": "one-time-code", "expires_in": 60}),
        ):
            code = AuthCenterClient("http://192.168.11.28:8000").create_handoff(
                "center-token"
            )
        self.assertEqual(code, "one-time-code")

    def test_client_consumes_one_time_browser_handoff(self) -> None:
        payload = {
            "access_token": "center-token",
            "user": {"user_id": "u1", "username": "tester", "enabled": True},
        }
        with patch("jyd_probe.auth_center.urlopen", return_value=_Response(payload)):
            result = AuthCenterClient("https://auth.lanyingjk01.com").consume_handoff(
                "one-time-code"
            )
        self.assertEqual(result["access_token"], "center-token")
        self.assertEqual(result["user"]["username"], "tester")

    def test_content_analysis_forwards_one_exact_script_with_long_timeout(self) -> None:
        payload = {"overall_status": "SUCCESS"}
        with patch(
            "jyd_probe.auth_center.urlopen", return_value=_Response(payload)
        ) as request_mock:
            result = AuthCenterClient(
                "http://127.0.0.1:8000", timeout_seconds=4
            ).analyze_workbench_content(
                "center-token",
                "  原文\n不能 trim  ",
                force_refresh=True,
            )

        request = request_mock.call_args.args[0]
        submitted = json.loads(request.data.decode("utf-8"))
        self.assertEqual(submitted["original_script"], "  原文\n不能 trim  ")
        self.assertTrue(submitted["force_refresh"])
        self.assertEqual(request_mock.call_args.kwargs["timeout"], 360.0)
        self.assertEqual(result, payload)

    def test_content_analysis_forwards_compact_visual_context_in_same_request(self) -> None:
        visual_context = {
            "catalog_version": "catalog-v1",
            "concepts": [{"concept_id": "food.egg", "description": "鸡蛋"}],
            "anchors": [
                {
                    "anchor_id": "B2",
                    "char_start": 2,
                    "char_end": 4,
                    "text": "鸡蛋",
                    "allowed_concepts": ["food.egg"],
                }
            ],
        }
        with patch(
            "jyd_probe.auth_center.urlopen",
            return_value=_Response({"overall_status": "SUCCESS"}),
        ) as request_mock:
            AuthCenterClient("http://127.0.0.1:8000").analyze_workbench_content(
                "center-token",
                "吃鸡蛋",
                visual_context=visual_context,
            )

        submitted = json.loads(request_mock.call_args.args[0].data.decode("utf-8"))
        self.assertEqual(submitted["visual_context"], visual_context)

    def test_runninghub_pool_summary_and_composition_forward_only_internal_ids(self) -> None:
        summary = {
            "schema": "runninghub.workbench-execution-accounts.v1",
            "accounts": [{"id": 11, "label": "RunningHub 一号"}],
            "default_selected_account_ids": [11],
        }
        with patch(
            "jyd_probe.auth_center.urlopen",
            return_value=_Response(summary),
        ) as request_mock:
            result = AuthCenterClient(
                "http://127.0.0.1:8000"
            ).list_workbench_execution_accounts("center-token")
        request = request_mock.call_args.args[0]
        self.assertTrue(request.full_url.endswith("/api/workbench/runninghub-execution-accounts"))
        self.assertEqual(
            json.loads(request.data.decode("utf-8")),
            {"access_token": "center-token"},
        )
        self.assertEqual(result, summary)

        with patch(
            "jyd_probe.auth_center.urlopen",
            return_value=_Response({"composition": {"status": "COMPOSITION_QUEUED"}}),
        ) as request_mock:
            AuthCenterClient("http://127.0.0.1:8000").start_workbench_composition(
                "center-token",
                "batch-1",
                "item-1",
                idempotency_key="composition-1:item-1",
                image_asset_id="image-1",
                image_sha256="a" * 64,
                runninghub_execution_account_ids=[11, 22],
            )
        request = request_mock.call_args.args[0]
        submitted = json.loads(request.data.decode("utf-8"))
        self.assertEqual(submitted["runninghub_execution_account_ids"], [11, 22])
        self.assertEqual(submitted["image_sha256"], "a" * 64)
        self.assertNotIn("api_key", submitted)
        self.assertNotIn("base_url", submitted)

        with patch(
            "jyd_probe.auth_center.urlopen",
            return_value=_Response(
                {
                    "item_id": "item-1",
                    "composition": {"status": "VIDEO_ENHANCING"},
                }
            ),
        ) as request_mock:
            AuthCenterClient(
                "http://127.0.0.1:8000"
            ).backfill_workbench_video_enhancement(
                "center-token",
                "item-1",
                idempotency_key="backfill-1:item-1",
            )
        request = request_mock.call_args.args[0]
        self.assertTrue(
            request.full_url.endswith(
                "/api/workbench/tasks/item-1/enhancement/backfill"
            )
        )
        submitted = json.loads(request.data.decode("utf-8"))
        self.assertEqual(submitted["access_token"], "center-token")
        self.assertTrue(submitted["cost_confirmed"])
        self.assertEqual(submitted["idempotency_key"], "backfill-1:item-1")

    def test_standalone_processor_uses_remote_center_for_login_and_every_request(self) -> None:
        root = PROJECT_ROOT / "runtime" / "test_tmp" / f"remote_auth_{uuid.uuid4().hex}"
        root.mkdir(parents=True)
        settings = WebApiSettings(
            storage_root=root / "storage",
            template_library_root=root / "templates",
            default_draft_root=root / "drafts",
            audio_library_root=root / "audio",
            admin_password="admin-pass",
            admin_session_secret="admin-secret",
            auth_authority=False,
            auth_server_url="https://auth.lanyingjk01.com",
            shared_processor_url="http://192.168.11.28:8000",
            execution_mode="agent",
        )
        for directory in (
            settings.storage_root,
            settings.template_library_root,
            settings.default_draft_root,
            settings.audio_library_root,
        ):
            directory.mkdir(parents=True, exist_ok=True)
        user = {"user_id": "center-user", "username": "tester", "enabled": True}
        try:
            with patch(
                "jyd_probe.auth_center.AuthCenterClient.login",
                return_value={"access_token": "center-token", "user": user},
            ), patch(
                "jyd_probe.auth_center.AuthCenterClient.verify",
                return_value=user,
            ) as verify:
                with TestClient(create_app(settings)) as client:
                    login = client.post(
                        "/api/auth/login",
                        json={"username": "tester", "password": "pass123", "next": "/app"},
                    )
                    self.assertEqual(login.status_code, 200)
                    health = client.get("/api/health").json()
                    self.assertEqual(health["auth_server_url"], "https://auth.lanyingjk01.com")
                    self.assertEqual(health["shared_processor_url"], "http://192.168.11.28:8000")
                    self.assertEqual(client.get("/api/templates").status_code, 200)
                    self.assertGreaterEqual(verify.call_count, 1)

                    verify.return_value = None
                    self.assertEqual(client.get("/api/templates").status_code, 401)

                    verify.side_effect = AuthCenterError("公用机离线")
                    self.assertEqual(client.get("/api/templates").status_code, 503)
        finally:
            shutil.rmtree(root, ignore_errors=True)

    def test_processors_exchange_cloud_session_with_one_time_handoff(self) -> None:
        root = PROJECT_ROOT / "runtime" / "test_tmp" / f"cloud_handoff_{uuid.uuid4().hex}"
        root.mkdir(parents=True)
        settings = WebApiSettings(
            storage_root=root / "storage",
            template_library_root=root / "templates",
            default_draft_root=root / "drafts",
            audio_library_root=root / "audio",
            admin_password="admin-pass",
            admin_session_secret="admin-secret",
            auth_authority=False,
            auth_server_url="https://auth.lanyingjk01.com",
            shared_processor_url="http://192.168.11.28:8000",
            execution_mode="agent",
        )
        for directory in (
            settings.storage_root,
            settings.template_library_root,
            settings.default_draft_root,
            settings.audio_library_root,
        ):
            directory.mkdir(parents=True, exist_ok=True)
        user = {"user_id": "center-user", "username": "tester", "enabled": True}
        try:
            with patch(
                "jyd_probe.auth_center.AuthCenterClient.login",
                return_value={"access_token": "center-token", "user": user},
            ), patch(
                "jyd_probe.auth_center.AuthCenterClient.verify",
                return_value=user,
            ), patch(
                "jyd_probe.auth_center.AuthCenterClient.create_handoff",
                return_value="one-time-code",
            ), patch(
                "jyd_probe.auth_center.AuthCenterClient.consume_handoff",
                return_value={"access_token": "center-token", "user": user},
            ):
                with TestClient(create_app(settings)) as client:
                    client.post(
                        "/api/auth/login",
                        json={"username": "tester", "password": "pass123", "next": "/app"},
                    )
                    to_shared = client.get(
                        "/api/auth/handoff-to?target=shared&next=/app",
                        follow_redirects=False,
                    )
                    self.assertEqual(to_shared.status_code, 303)
                    self.assertTrue(
                        to_shared.headers["location"].startswith(
                            "http://192.168.11.28:8000/api/auth/handoff?code="
                        )
                    )

                    accepted = client.get(
                        "/api/auth/handoff?code=one-time-code&next=/app",
                        follow_redirects=False,
                    )
                    self.assertEqual(accepted.status_code, 303)
                    self.assertEqual(accepted.headers["location"], "/app")
                    self.assertIn("jyd_site_session=center-token", accepted.headers["set-cookie"])
        finally:
            shutil.rmtree(root, ignore_errors=True)

    def test_digital_human_inbox_and_one_click_import_use_logged_in_account(self) -> None:
        root = PROJECT_ROOT / "runtime" / "test_tmp" / f"digital_inbox_{uuid.uuid4().hex}"
        root.mkdir(parents=True)
        settings = WebApiSettings(
            storage_root=root / "storage",
            template_library_root=root / "templates",
            default_draft_root=root / "drafts",
            audio_library_root=root / "audio",
            admin_password="admin-pass",
            admin_session_secret="admin-secret",
            auth_authority=False,
            auth_server_url="http://127.0.0.1:8000",
            execution_mode="embedded",
            allow_local_file_access=True,
        )
        for directory in (
            settings.storage_root,
            settings.template_library_root,
            settings.default_draft_root,
            settings.audio_library_root,
        ):
            directory.mkdir(parents=True, exist_ok=True)
        user = {"user_id": "2", "username": "tester", "enabled": True}
        task = {
            "item_id": "item-1",
            "row_key": "TEXT-001",
            "batch_name": "数字人口播",
            "input_mode": "text",
            "mode": "AUTO_POSTPROCESS",
            "status": "AUTO_READY",
            "source": {"videos": [{"index": 1, "status": "SUCCESS"}]},
            "captions": {
                "text": "精确字幕",
                "cues": [{"start_us": 0, "end_us": 1_000_000, "text": "精确字幕"}],
            },
        }

        def fake_download(_self, _token, _item_id, _index, target, *, max_bytes):
            del max_bytes
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(b"video")
            return 5

        try:
            with patch(
                "jyd_probe.auth_center.AuthCenterClient.login",
                return_value={"access_token": "digital-token", "user": user},
            ), patch(
                "jyd_probe.auth_center.AuthCenterClient.verify", return_value=user
            ), patch(
                "jyd_probe.auth_center.AuthCenterClient.list_workbench_tasks",
                return_value=[task],
            ), patch(
                "jyd_probe.auth_center.AuthCenterClient.get_workbench_task",
                return_value=task,
            ), patch(
                "jyd_probe.auth_center.AuthCenterClient.download_workbench_video",
                new=fake_download,
            ):
                with TestClient(
                    create_app(settings),
                    base_url="http://127.0.0.1",
                    client=("127.0.0.1", 54321),
                ) as client:
                    login = client.post(
                        "/api/auth/login",
                        json={"username": "tester", "password": "pass123"},
                    )
                    self.assertEqual(login.status_code, 200)
                    inbox = client.get("/api/digital-human/tasks")
                    self.assertEqual(inbox.status_code, 200)
                    self.assertEqual(inbox.json()["tasks"][0]["status"], "AUTO_READY")

                    imported = client.post("/api/digital-human/tasks/item-1/import")
                    self.assertEqual(imported.status_code, 200)
                    payload = imported.json()
                    self.assertEqual(payload["media"]["source_item_id"], "item-1")
                    self.assertEqual(payload["captions"]["cues"][0]["text"], "精确字幕")
                    self.assertTrue(Path(payload["media"]["path"]).is_file())
        finally:
            shutil.rmtree(root, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
