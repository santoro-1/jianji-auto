from __future__ import annotations

from pathlib import Path
import shutil
import sys
import unittest
import uuid
from unittest.mock import patch

from fastapi.testclient import TestClient


PROJECT_ROOT = Path(__file__).resolve().parents[1]
FRONTEND_ROOT = PROJECT_ROOT / "apps" / "processor" / "frontend" / "new"
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from jyd_probe.web_api import WebApiSettings, create_app  # noqa: E402


class NewFrontendTest(unittest.TestCase):
    def setUp(self) -> None:
        self.root = (
            PROJECT_ROOT / "runtime" / "test_tmp" / f"new_frontend_{uuid.uuid4().hex}"
        )
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

    def test_new_workspace_uses_real_script_and_image_input_apis(self) -> None:
        html = (FRONTEND_ROOT / "index.html").read_text(encoding="utf-8")
        self.assertIn('href="/api/new/script-template"', html)
        self.assertIn("/api/new/script-imports/preview", html)
        self.assertIn("/image-mapping", html)
        self.assertIn("uploadProjectImage", html)
        self.assertIn("initializeProjectInputs", html)
        self.assertNotIn("simulateExcelParsing", html)
        self.assertNotIn("loadSampleData", html)
        self.assertNotIn("const sampleImages", html)
        self.assertTrue((FRONTEND_ROOT / "project-script-template.xlsx").is_file())

    def test_new_workspace_and_voice_center_use_real_voice_apis(self) -> None:
        workspace = (FRONTEND_ROOT / "index.html").read_text(encoding="utf-8")
        voice_center = (FRONTEND_ROOT / "voice-library.html").read_text(
            encoding="utf-8"
        )
        self.assertIn("/api/new/voices", workspace)
        self.assertIn("/audio/generate", workspace)
        self.assertIn("/audio/status", workspace)
        self.assertIn("/items/${rowId}/audio/retry", workspace)
        self.assertIn("/projects/${activeProject.project_id}/voice", workspace)
        self.assertIn("/api/new/voice-creations", voice_center)
        self.assertIn("submitVoiceCreation", voice_center)
        self.assertIn("saveCreatedVoice", voice_center)
        self.assertIn("生成克隆试听", voice_center)
        self.assertIn("保存到音色库", voice_center)
        self.assertIn("activateSavedVoice", voice_center)
        self.assertIn("deleteSavedVoice", voice_center)
        self.assertIn('id="voice-source-preview"', voice_center)
        self.assertIn("使用该音色生成试听语音，是否继续？", voice_center)
        self.assertIn("使用该音色生成试听语音，是否继续？", workspace)
        self.assertNotIn("首次试听将调用 MiniMax", voice_center)
        self.assertNotIn("提取并注入原型库", voice_center)
        self.assertEqual(voice_center.count('id="voice-task-list"'), 1)
        self.assertNotIn("actions.google.com/sounds", workspace)
        self.assertNotIn("actions.google.com/sounds", voice_center)

    def test_new_pages_require_login_but_login_and_logo_are_public(self) -> None:
        with TestClient(create_app(self.settings)) as client:
            for path in ("/app/new", "/app/new/gallery", "/app/new/voices"):
                response = client.get(path, follow_redirects=False)
                self.assertEqual(response.status_code, 303, path)
                self.assertEqual(
                    response.headers["location"],
                    f"/app/new/login?next={path}",
                )

            login = client.get("/app/new/login")
            self.assertEqual(login.status_code, 200)
            self.assertIn("/api/auth/login", login.text)
            self.assertNotIn("demo_vip@shanjian.ai", login.text)
            self.assertNotIn("模拟扫码成功", login.text)

            logo = client.get("/app-static/new/logo.png")
            self.assertEqual(logo.status_code, 200)
            self.assertEqual(logo.headers["content-type"], "image/png")

    def test_digital_account_login_opens_all_new_routes_and_logout_closes_them(self) -> None:
        user = {"user_id": "center-user", "username": "tester", "enabled": True}

        def verify(_client, token):
            return user if token == "center-token" else None

        with patch(
            "jyd_probe.auth_center.AuthCenterClient.login",
            return_value={"access_token": "center-token", "user": user},
        ), patch(
            "jyd_probe.auth_center.AuthCenterClient.verify",
            new=verify,
        ):
            with TestClient(create_app(self.settings)) as client:
                login = client.post(
                    "/api/auth/login",
                    json={
                        "username": "tester",
                        "password": "pass123",
                        "next": "/app/new/gallery",
                    },
                )
                self.assertEqual(login.status_code, 200, login.text)
                self.assertEqual(login.json()["next"], "/app/new/gallery")
                self.assertIn("HttpOnly", login.headers["set-cookie"])

                expected_files = {
                    "/app/new": "index.html",
                    "/app/new/gallery": "gallery.html",
                    "/app/new/voices": "voice-library.html",
                }
                for path, filename in expected_files.items():
                    response = client.get(path)
                    self.assertEqual(response.status_code, 200, path)
                    self.assertEqual(
                        response.text,
                        (FRONTEND_ROOT / filename).read_text(encoding="utf-8"),
                    )
                    self.assertIn("/api/auth/session", response.text)
                    self.assertIn("/api/auth/logout", response.text)
                    self.assertIn("current-user-name", response.text)

                session = client.get("/api/auth/session")
                self.assertTrue(session.json()["authenticated"])
                self.assertEqual(session.json()["username"], "tester")

                logout = client.post("/api/auth/logout")
                self.assertEqual(logout.status_code, 200)
                self.assertIn("Max-Age=0", logout.headers["set-cookie"])
                client.cookies.clear()

                closed = client.get("/app/new", follow_redirects=False)
                self.assertEqual(closed.status_code, 303)
                self.assertEqual(closed.headers["location"], "/app/new/login?next=/app/new")

    def test_logged_in_login_page_only_redirects_inside_new_app(self) -> None:
        user = {"user_id": "center-user", "username": "tester", "enabled": True}

        def verify(_client, token):
            return user if token == "center-token" else None

        with patch(
            "jyd_probe.auth_center.AuthCenterClient.login",
            return_value={"access_token": "center-token", "user": user},
        ), patch(
            "jyd_probe.auth_center.AuthCenterClient.verify",
            new=verify,
        ):
            with TestClient(create_app(self.settings)) as client:
                client.post(
                    "/api/auth/login",
                    json={"username": "tester", "password": "pass123"},
                )
                accepted = client.get(
                    "/app/new/login?next=/app/new/voices", follow_redirects=False
                )
                self.assertEqual(accepted.headers["location"], "/app/new/voices")

                rejected = client.get(
                    "/app/new/login?next=https://example.com", follow_redirects=False
                )
                self.assertEqual(rejected.headers["location"], "/app/new")

    def test_revoked_digital_account_session_cannot_keep_new_page_open(self) -> None:
        user = {"user_id": "center-user", "username": "tester", "enabled": True}
        account_enabled = True

        def verify(_client, token):
            return user if token == "center-token" and account_enabled else None

        with patch(
            "jyd_probe.auth_center.AuthCenterClient.login",
            return_value={"access_token": "center-token", "user": user},
        ), patch(
            "jyd_probe.auth_center.AuthCenterClient.verify",
            new=verify,
        ):
            with TestClient(create_app(self.settings)) as client:
                client.post(
                    "/api/auth/login",
                    json={"username": "tester", "password": "pass123"},
                )
                self.assertEqual(client.get("/app/new").status_code, 200)

                account_enabled = False
                revoked = client.get("/app/new", follow_redirects=False)
                self.assertEqual(revoked.status_code, 303)
                self.assertEqual(
                    revoked.headers["location"], "/app/new/login?next=/app/new"
                )


if __name__ == "__main__":
    unittest.main()
