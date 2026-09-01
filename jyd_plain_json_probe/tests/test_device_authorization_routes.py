from __future__ import annotations

from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from jyd_probe.device_auth_protocol import DeviceAuthorizationError
from jyd_probe.device_authorization_routes import (
    DeviceSessionRegistry,
    install_device_authorization_routes,
)


class DeviceRoutesTest(unittest.TestCase):
    def setUp(self):
        self.session = Mock()
        self.session.summary.return_value = {
            "state": "PENDING",
            "user_id": 7,
            "thumbprint": "public-device-id",
        }
        self.session.refresh.return_value = {"state": "ACTIVE", "user_id": 7}
        self.factory = Mock(return_value=self.session)
        self.registry = DeviceSessionRegistry(
            "https://license.example", session_factory=self.factory
        )
        self.app = FastAPI()

        def current_user(request):
            if request.cookies.get("site") != "website-account-token":
                raise HTTPException(status_code=401, detail="website login required")
            return {"user_id": "7", "username": "tester"}

        install_device_authorization_routes(
            self.app,
            base_url="https://license.example",
            cookie_name="site",
            current_user=current_user,
            registry=self.registry,
        )
        self.client = TestClient(self.app)
        self.client.__enter__()
        self.headers = {
            "Origin": "http://testserver",
            "X-Device-Authorization-Action": "1",
        }

    def tearDown(self):
        self.client.__exit__(None, None, None)

    def login(self):
        self.client.cookies.set("site", "website-account-token")

    def test_missing_website_identity_rejects_even_local_admin_cookie(self):
        self.client.cookies.set("admin_session", "local-admin")
        self.assertEqual(
            self.client.get("/api/new/device-authorization").status_code, 401
        )
        self.factory.assert_not_called()

    def test_status_never_creates_key_or_returns_tokens(self):
        self.login()
        response = self.client.get("/api/new/device-authorization")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["state"], "PENDING")
        self.assertEqual(response.headers["cache-control"], "no-store")
        self.assertNotIn("website-account-token", response.text)
        self.session.register.assert_not_called()
        self.factory.assert_called_once_with(
            user_id=7, login_token="website-account-token"
        )

    def test_missing_key_is_registration_state_not_an_automatic_application(self):
        self.login()
        self.session.status.side_effect = DeviceAuthorizationError(
            "DEVICE_UNREGISTERED", "not initialized"
        )
        self.session.summary.return_value = {"state": "UNREGISTERED"}
        response = self.client.get("/api/new/device-authorization")
        self.assertEqual(response.json()["state"], "UNREGISTERED")
        self.session.register.assert_not_called()

    def test_explicit_apply_only_passes_label_and_version_to_local_key_owner(self):
        self.login()
        response = self.client.post(
            "/api/new/device-authorization/apply",
            json={"label": "250", "client_version": "v4", "confirm_initialize": True},
            headers=self.headers,
        )
        self.assertEqual(response.status_code, 200)
        self.session.register.assert_called_once_with(label="250", client_version="v4")

    def test_software_apply_requires_both_literal_confirmations_and_same_origin(self):
        path = "/api/new/device-authorization/apply-software"
        body = {"confirm_initialize": True, "confirm_software": True}
        self.assertEqual(
            self.client.post(path, json=body, headers=self.headers).status_code, 401
        )
        self.login()
        self.assertEqual(self.client.post(path, json=body).status_code, 403)
        for invalid in (
            {},
            {"confirm_initialize": True},
            {"confirm_software": True},
            {"confirm_initialize": 1, "confirm_software": True},
            {**body, "software_approved": True},
            {**body, "operator_sid": "injected"},
            {**body, "initialization_permit": "injected"},
        ):
            self.assertEqual(
                self.client.post(path, json=invalid, headers=self.headers).status_code,
                422,
            )
        self.session.register_software.assert_not_called()
        response = self.client.post(
            path, json={**body, "label": "250"}, headers=self.headers
        )
        self.assertEqual(response.status_code, 200)
        self.session.register_software.assert_called_once_with(
            label="250", client_version=""
        )
        self.assertNotIn("website-account-token", response.text)
        self.assertEqual(response.headers["cache-control"], "no-store")

    def test_software_policy_denial_does_not_clear_login_or_return_permit(self):
        self.login()
        self.session.register_software.side_effect = DeviceAuthorizationError(
            "DEVICE_SOFTWARE_NOT_ALLOWED", "administrator must allow"
        )
        response = self.client.post(
            "/api/new/device-authorization/apply-software",
            json={"confirm_initialize": True, "confirm_software": True},
            headers=self.headers,
        )
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()["code"], "DEVICE_SOFTWARE_NOT_ALLOWED")
        self.assertNotEqual(response.json()["state"], "LOGIN_REQUIRED")
        self.assertNotIn("initialization_permit", response.text)

    def test_apply_rejects_private_key_id_and_approval_injection(self):
        self.login()
        for name in (
            "private_key",
            "device_id",
            "software_approved",
            "operator_sid",
            "public_jwk",
            "trust_root",
        ):
            response = self.client.post(
                "/api/new/device-authorization/apply",
                json={"confirm_initialize": True, name: "injected"},
                headers=self.headers,
            )
            self.assertEqual(response.status_code, 422)
        self.session.register.assert_not_called()

    def test_initialization_requires_literal_confirmation(self):
        self.login()
        for confirm in (None, False, "true", 1):
            response = self.client.post(
                "/api/new/device-authorization/apply",
                json={"confirm_initialize": confirm},
                headers=self.headers,
            )
            self.assertEqual(response.status_code, 422)
        self.session.register.assert_not_called()

    def test_cross_origin_missing_origin_and_malformed_origin_are_rejected(self):
        self.login()
        for headers in (
            {},
            {"Origin": "http://testserver"},
            {"Origin": "https://evil.example", "X-Device-Authorization-Action": "1"},
            {"Origin": "http://[", "X-Device-Authorization-Action": "1"},
            {"Origin": "null", "X-Device-Authorization-Action": "1"},
        ):
            for action in ("apply", "refresh"):
                response = self.client.post(
                    "/api/new/device-authorization/" + action,
                    json={"confirm_initialize": True},
                    headers=headers,
                )
                self.assertEqual(response.status_code, 403)
        self.factory.assert_not_called()

    def test_refresh_does_not_register_and_returns_only_summary(self):
        self.login()
        response = self.client.post(
            "/api/new/device-authorization/refresh", headers=self.headers
        )
        self.assertEqual(response.json(), {"state": "ACTIVE", "user_id": 7})
        self.session.refresh.assert_called_once_with(force=True)
        self.session.register.assert_not_called()

    def test_pending_is_not_mislabeled_as_new_machine(self):
        self.login()
        self.session.refresh.side_effect = DeviceAuthorizationError(
            "DEVICE_PENDING", "waiting"
        )
        response = self.client.post(
            "/api/new/device-authorization/refresh", headers=self.headers
        )
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()["state"], "PENDING")

    def test_repair_requires_website_user_same_origin_and_literal_confirmation(self):
        path = "/api/new/device-authorization/repair-key-access"
        response = self.client.post(
            path, json={"confirm_repair": True}, headers=self.headers
        )
        self.assertEqual(response.status_code, 401)
        self.login()
        for value in (False, "true", 1, None):
            self.assertEqual(
                self.client.post(
                    path, json={"confirm_repair": value}, headers=self.headers
                ).status_code,
                422,
            )
        for headers in (
            {},
            {"Origin": "https://evil.example", "X-Device-Authorization-Action": "1"},
        ):
            self.assertEqual(
                self.client.post(
                    path, json={"confirm_repair": True}, headers=headers
                ).status_code,
                403,
            )
        for name in (
            "operator_sid",
            "process_id",
            "software_approved",
            "key_name",
            "command",
            "device_id",
        ):
            self.assertEqual(
                self.client.post(
                    path,
                    json={"confirm_repair": True, name: "injected"},
                    headers=self.headers,
                ).status_code,
                422,
            )
        self.session.repair_key_access.assert_not_called()

    def test_repair_invokes_only_existing_key_recovery_and_returns_safe_summary(self):
        self.login()
        self.session.repair_key_access.return_value = {
            "state": "ACTIVE",
            "device_id": "original-id",
            "grant_id": "original-grant",
        }
        response = self.client.post(
            "/api/new/device-authorization/repair-key-access",
            json={"confirm_repair": True},
            headers=self.headers,
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["device_id"], "original-id")
        self.assertEqual(response.headers["cache-control"], "no-store")
        self.session.repair_key_access.assert_called_once_with()
        self.session.register.assert_not_called()
        self.assertNotIn("website-account-token", response.text)

    def test_setup_in_progress_and_cancel_are_not_new_device_or_login_failure(self):
        from jyd_probe.device_identity_windows import DeviceIdentityError

        self.login()
        for code, state in (
            ("KEY_SETUP_IN_PROGRESS", "KEY_INITIALIZING"),
            ("KEY_SETUP_CANCELLED", "KEY_UNAVAILABLE"),
            ("KEY_ACCESS_DENIED", "KEY_UNAVAILABLE"),
        ):
            self.session.register.side_effect = DeviceIdentityError(
                code, "native sanitized status"
            )
            response = self.client.post(
                "/api/new/device-authorization/apply",
                json={"confirm_initialize": True},
                headers=self.headers,
            )
            self.assertEqual(response.status_code, 409)
            self.assertEqual(response.json()["state"], state)
            self.assertEqual(response.json()["code"], code)
        self.session.repair_key_access.assert_not_called()

    def test_repair_cannot_turn_a_revoked_device_into_active(self):
        self.login()
        self.session.repair_key_access.side_effect = DeviceAuthorizationError(
            "DEVICE_REVOKED", "revoked"
        )
        response = self.client.post(
            "/api/new/device-authorization/repair-key-access",
            json={"confirm_repair": True},
            headers=self.headers,
        )
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()["state"], "REVOKED")
        self.session.register.assert_not_called()

    def test_expired_upgrade_and_credential_errors_are_not_account_login_errors(self):
        self.login()
        for code, state, status in (
            ("DEVICE_GRANT_EXPIRED", "EXPIRED", 403),
            ("CLIENT_UPGRADE_REQUIRED", "CLIENT_UPGRADE_REQUIRED", 409),
            ("DEVICE_TOKEN_EXPIRED", "AUTH_REFRESH_REQUIRED", 401),
        ):
            with self.subTest(code=code):
                self.session.refresh.side_effect = DeviceAuthorizationError(
                    code, "denied", status_code=status
                )
                response = self.client.post(
                    "/api/new/device-authorization/refresh", headers=self.headers
                )
                self.assertEqual(response.status_code, status)
                self.assertEqual(response.json()["state"], state)
                self.assertEqual(response.json()["code"], code)
        self.session.register.assert_not_called()

    def test_network_error_reports_existing_grace_without_extending_it(self):
        self.login()
        error = DeviceAuthorizationError(
            "DEVICE_AUTH_UNREACHABLE", "offline", status_code=503, transient=True
        )
        self.session.status.side_effect = error
        self.session.refresh.side_effect = error
        for state in ("OFFLINE_GRACE", "AUTH_REFRESH_REQUIRED"):
            self.session.summary.return_value = {
                "state": state,
                "user_id": 7,
                "exp": 1234,
            }
            for method, path in (("GET", ""), ("POST", "/refresh")):
                with self.subTest(state=state, path=path):
                    response = self.client.request(
                        method,
                        "/api/new/device-authorization" + path,
                        headers=self.headers,
                    )
                    self.assertEqual(response.status_code, 503)
                    self.assertEqual(response.json()["state"], state)
                    if state == "OFFLINE_GRACE":
                        self.assertEqual(response.json()["exp"], 1234)
                    else:
                        self.assertNotIn("exp", response.json())
        self.session.register.assert_not_called()

    def test_revocation_never_reuses_grace_summary(self):
        self.login()
        self.session.refresh.side_effect = DeviceAuthorizationError(
            "DEVICE_REVOKED", "revoked"
        )
        self.session.summary.return_value = {
            "state": "OFFLINE_GRACE",
            "exp": 9999999999,
        }
        response = self.client.post(
            "/api/new/device-authorization/refresh", headers=self.headers
        )
        self.assertEqual(response.json()["state"], "REVOKED")
        self.assertNotIn("exp", response.json())

    def test_registry_reuses_session_but_never_shares_other_account_or_login(self):
        registry = DeviceSessionRegistry(
            "https://license.example", session_factory=lambda **_: Mock()
        )
        first = registry.get("7", "token-a")
        self.assertIs(first, registry.get("7", "token-a"))
        self.assertIsNot(first, registry.get("8", "token-a"))
        self.assertIsNot(first, registry.get("7", "token-b"))
        registry.forget("token-a")
        first.close.assert_called_once()
        self.assertIsNot(first, registry.get("7", "token-a"))
        registry.close()

    def test_unconfigured_trust_does_not_attempt_real_key_initialization(self):
        registry = DeviceSessionRegistry("https://untrusted.example")
        with patch(
            "jyd_probe.device_authorization_routes.WindowsDeviceIdentity"
        ) as native:
            with self.assertRaises(DeviceAuthorizationError):
                registry.get("7", "token-a")
        native.assert_not_called()

    def test_existing_workbench_app_installs_routes_without_native_key_side_effect(
        self,
    ):
        from jyd_probe.web_api import WebApiSettings, create_app

        with tempfile.TemporaryDirectory(prefix="device-web-api-") as folder:
            root = Path(folder)
            settings = WebApiSettings(
                storage_root=root / "storage",
                template_library_root=root / "templates",
                default_draft_root=root / "drafts",
                audio_library_root=root / "audio",
                admin_password="test-admin",
                admin_session_secret="test-session",
                auth_authority=False,
                auth_server_url="https://license.example",
                execution_mode="agent",
            )
            for path in (
                settings.storage_root,
                settings.template_library_root,
                settings.default_draft_root,
                settings.audio_library_root,
            ):
                path.mkdir(parents=True, exist_ok=True)
            user = {"user_id": "7", "username": "tester", "enabled": True}
            with patch(
                "jyd_probe.auth_center.AuthCenterClient.verify", return_value=user
            ), patch(
                "jyd_probe.device_authorization_routes.WindowsDeviceIdentity"
            ) as native:
                with TestClient(create_app(settings)) as client:
                    client.cookies.set(
                        settings.site_cookie_name, "website-account-token"
                    )
                    response = client.get("/api/new/device-authorization")
                    self.assertEqual(response.status_code, 503)
                    self.assertEqual(
                        response.json()["code"], "DEVICE_TRUST_NOT_CONFIGURED"
                    )
                    page = client.get("/app/new/device-authorization")
                    self.assertEqual(page.status_code, 200)
                    self.assertIn('id="confirm"', page.text)
                    self.assertIn("正常更新无需重复激活", page.text)
                    from jyd_probe.auth_center import AuthCenterDeviceError

                    with patch(
                        "jyd_probe.auth_center.AuthCenterClient.list_h3_execution_accounts",
                        side_effect=AuthCenterDeviceError(
                            "请检查设备授权",
                            error_code="DEVICE_BOUND_TOKEN_REQUIRED",
                            status_code=401,
                        ),
                    ):
                        denied = client.get("/api/new/h3/accounts")
                    self.assertEqual(denied.status_code, 409)
                    self.assertEqual(
                        denied.json()["code"], "DEVICE_BOUND_TOKEN_REQUIRED"
                    )
                    self.assertTrue(denied.json()["device_authorization_required"])
                    self.assertEqual(
                        denied.headers["x-workbench-device-error"],
                        "DEVICE_BOUND_TOKEN_REQUIRED",
                    )
                    self.assertEqual(client.post("/api/auth/logout").status_code, 200)
                native.assert_not_called()


if __name__ == "__main__":
    unittest.main()
