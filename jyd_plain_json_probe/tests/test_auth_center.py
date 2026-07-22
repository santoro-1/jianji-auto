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


if __name__ == "__main__":
    unittest.main()
