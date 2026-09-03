from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import os
import shutil
import sys
import tempfile
import threading
import time
import unittest
import uuid
from unittest.mock import patch

from fastapi.testclient import TestClient


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from jyd_probe.auth_center import (  # noqa: E402
    AuthCenterClient,
    AuthCenterConnectionError,
)
from jyd_probe.web_api import WebApiSettings, create_app  # noqa: E402


class AuthVerifyStormTest(unittest.TestCase):
    def _client(self, **kwargs) -> AuthCenterClient:
        client = AuthCenterClient("https://video.example", **kwargs)
        self.addCleanup(client.close)
        return client

    def test_fifty_same_token_calls_share_one_remote_verification(self) -> None:
        client = self._client()
        started = threading.Event()
        release = threading.Event()
        counter_lock = threading.Lock()
        remote_count = 0

        def remote(*_args, **_kwargs):
            nonlocal remote_count
            with counter_lock:
                remote_count += 1
            started.set()
            self.assertTrue(release.wait(timeout=3))
            return {
                "valid": True,
                "user": {"user_id": "user-1", "username": "tester"},
            }

        with patch.object(client, "_post", side_effect=remote), patch(
            "jyd_probe.auth_center.log_event"
        ):
            with ThreadPoolExecutor(max_workers=50) as pool:
                futures = [pool.submit(client.verify, "same-token") for _ in range(50)]
                self.assertTrue(started.wait(timeout=3))
                time.sleep(0.05)
                release.set()
                results = [future.result(timeout=3) for future in futures]

        self.assertEqual(remote_count, 1)
        self.assertEqual({result["user_id"] for result in results}, {"user-1"})
        snapshot = client.verification_snapshot()
        self.assertEqual(snapshot["requests"], 50)
        self.assertEqual(snapshot["remote_requests"], 1)
        self.assertEqual(
            snapshot["coalesced_waiters"] + snapshot["cache_hits"], 49
        )

    def test_success_cache_is_short_lived_and_returns_defensive_copies(self) -> None:
        client = self._client(verify_cache_ttl_seconds=0.05)
        remote_count = 0

        def remote(*_args, **_kwargs):
            nonlocal remote_count
            remote_count += 1
            return {
                "valid": True,
                "user": {"user_id": "user-1", "roles": ["editor"]},
            }

        with patch.object(client, "_post", side_effect=remote), patch(
            "jyd_probe.auth_center.log_event"
        ):
            first = client.verify("cache-token")
            first["roles"].append("mutated")
            second = client.verify("cache-token")
            self.assertEqual(second["roles"], ["editor"])
            self.assertEqual(remote_count, 1)
            time.sleep(0.07)
            client.verify("cache-token")

        self.assertEqual(remote_count, 2)

    def test_different_tokens_do_not_share_results(self) -> None:
        client = self._client()

        def remote(_path, payload, **_kwargs):
            token = payload["access_token"]
            return {"valid": True, "user": {"user_id": token}}

        with patch.object(client, "_post", side_effect=remote), patch(
            "jyd_probe.auth_center.log_event"
        ):
            with ThreadPoolExecutor(max_workers=2) as pool:
                first = pool.submit(client.verify, "token-a")
                second = pool.submit(client.verify, "token-b")
                self.assertEqual(first.result(timeout=3)["user_id"], "token-a")
                self.assertEqual(second.result(timeout=3)["user_id"], "token-b")
        self.assertEqual(client.verification_snapshot()["remote_requests"], 2)

    def test_network_error_wakes_every_coalesced_waiter(self) -> None:
        client = self._client()
        started = threading.Event()
        release = threading.Event()
        remote_count = 0

        def remote(*_args, **_kwargs):
            nonlocal remote_count
            remote_count += 1
            started.set()
            self.assertTrue(release.wait(timeout=3))
            raise AuthCenterConnectionError("center unavailable")

        with patch.object(client, "_post", side_effect=remote), patch(
            "jyd_probe.auth_center.log_event"
        ):
            with ThreadPoolExecutor(max_workers=20) as pool:
                futures = [pool.submit(client.verify, "same-token") for _ in range(20)]
                self.assertTrue(started.wait(timeout=3))
                time.sleep(0.05)
                release.set()
                errors = []
                for future in futures:
                    with self.assertRaises(AuthCenterConnectionError) as caught:
                        future.result(timeout=3)
                    errors.append(str(caught.exception))

        self.assertEqual(remote_count, 1)
        self.assertEqual(len(set(errors)), 1)
        self.assertIn("请稍后重试", errors[0])
        self.assertEqual(client.verification_snapshot()["in_flight"], 0)

    def test_three_network_failures_open_breaker_and_one_half_open_probe_recovers(self) -> None:
        client = self._client(
            verify_breaker_failure_threshold=3,
            verify_breaker_window_seconds=1,
            verify_breaker_open_seconds=0.05,
        )
        remote_count = 0

        def unavailable(*_args, **_kwargs):
            nonlocal remote_count
            remote_count += 1
            raise AuthCenterConnectionError("center unavailable")

        with patch.object(client, "_post", side_effect=unavailable), patch(
            "jyd_probe.auth_center.log_event"
        ):
            for index in range(3):
                with self.assertRaises(AuthCenterConnectionError):
                    client.verify(f"failure-{index}")
            with self.assertRaises(AuthCenterConnectionError) as rejected:
                client.verify("rejected-without-remote-call")
            self.assertIn("请稍后重试", str(rejected.exception))
            self.assertEqual(remote_count, 3)
            self.assertEqual(client.verification_snapshot()["breaker_state"], "OPEN")

        time.sleep(0.07)
        with patch.object(
            client,
            "_post",
            return_value={"valid": True, "user": {"user_id": "recovered"}},
        ), patch("jyd_probe.auth_center.log_event"):
            self.assertEqual(client.verify("probe")["user_id"], "recovered")
        self.assertEqual(client.verification_snapshot()["breaker_state"], "CLOSED")

    def test_half_open_state_allows_only_one_remote_probe(self) -> None:
        client = self._client(
            verify_breaker_failure_threshold=1,
            verify_breaker_open_seconds=0.05,
        )
        with patch.object(
            client,
            "_post",
            side_effect=AuthCenterConnectionError("center unavailable"),
        ), patch("jyd_probe.auth_center.log_event"):
            with self.assertRaises(AuthCenterConnectionError):
                client.verify("failure")

        time.sleep(0.07)
        probe_started = threading.Event()
        release_probe = threading.Event()
        remote_count = 0

        def probe(*_args, **_kwargs):
            nonlocal remote_count
            remote_count += 1
            probe_started.set()
            self.assertTrue(release_probe.wait(timeout=3))
            return {"valid": True, "user": {"user_id": "probe"}}

        with patch.object(client, "_post", side_effect=probe), patch(
            "jyd_probe.auth_center.log_event"
        ):
            with ThreadPoolExecutor(max_workers=2) as pool:
                accepted = pool.submit(client.verify, "probe-a")
                self.assertTrue(probe_started.wait(timeout=3))
                with self.assertRaises(AuthCenterConnectionError):
                    client.verify("probe-b")
                release_probe.set()
                self.assertEqual(accepted.result(timeout=3)["user_id"], "probe")
        self.assertEqual(remote_count, 1)

    def test_invalidation_wakes_waiters_and_discards_late_success(self) -> None:
        client = self._client()
        remote_started = threading.Event()
        release_remote = threading.Event()

        def remote(*_args, **_kwargs):
            remote_started.set()
            self.assertTrue(release_remote.wait(timeout=3))
            return {"valid": True, "user": {"user_id": "stale"}}

        with patch.object(client, "_post", side_effect=remote), patch(
            "jyd_probe.auth_center.log_event"
        ):
            with ThreadPoolExecutor(max_workers=2) as pool:
                leader = pool.submit(client.verify, "token")
                self.assertTrue(remote_started.wait(timeout=3))
                waiter = pool.submit(client.verify, "token")
                time.sleep(0.02)
                client.invalidate_verification("token")
                with self.assertRaisesRegex(Exception, "切换或退出"):
                    waiter.result(timeout=1)
                release_remote.set()
                with self.assertRaisesRegex(Exception, "切换或退出"):
                    leader.result(timeout=3)
        self.assertEqual(client.verification_snapshot()["cache_entries"], 0)

    def test_http_unauthorized_does_not_open_network_breaker(self) -> None:
        client = self._client(verify_breaker_failure_threshold=1)

        from jyd_probe.auth_center import AuthCenterError

        with patch.object(
            client,
            "_post",
            side_effect=AuthCenterError("expired", status_code=401),
        ), patch("jyd_probe.auth_center.log_event"):
            self.assertIsNone(client.verify("expired-token"))
        snapshot = client.verification_snapshot()
        self.assertEqual(snapshot["breaker_state"], "CLOSED")
        self.assertEqual(snapshot["remote_network_failures"], 0)
        self.assertEqual(snapshot["remote_unauthorized"], 1)

    def test_explicit_invalidation_forces_a_new_remote_verification(self) -> None:
        client = self._client()
        remote_count = 0

        def remote(*_args, **_kwargs):
            nonlocal remote_count
            remote_count += 1
            return {"valid": True, "user": {"user_id": "user-1"}}

        with patch.object(client, "_post", side_effect=remote), patch(
            "jyd_probe.auth_center.log_event"
        ):
            client.verify("token")
            client.verify("token")
            client.invalidate_verification("token")
            client.verify("token")
        self.assertEqual(remote_count, 2)

    def test_unexpected_executor_error_does_not_leave_a_stuck_flight(self) -> None:
        client = self._client()
        with patch.object(client, "_post", side_effect=RuntimeError("boom")), patch(
            "jyd_probe.auth_center.log_event"
        ):
            with self.assertRaisesRegex(Exception, "数字人账号校验发生内部错误"):
                client.verify("token")
        self.assertEqual(client.verification_snapshot()["in_flight"], 0)
        with patch.object(
            client,
            "_post",
            return_value={"valid": True, "user": {"user_id": "recovered"}},
        ), patch("jyd_probe.auth_center.log_event"):
            self.assertEqual(client.verify("token")["user_id"], "recovered")

    def test_verify_uses_dedicated_eight_second_timeout(self) -> None:
        client = self._client(timeout_seconds=30, verify_timeout_seconds=8)
        with patch(
            "jyd_probe.auth_center.urlopen",
            return_value=_JsonResponse(
                {"valid": True, "user": {"user_id": "user-1"}}
            ),
        ) as remote, patch("jyd_probe.auth_center.log_event"):
            self.assertEqual(client.verify("token")["user_id"], "user-1")
        self.assertEqual(remote.call_args.kwargs["timeout"], 8.0)

    def test_middleware_and_project_handler_verify_only_once_per_request(self) -> None:
        configured_tmp = os.environ.get("JYD_TEST_TMP_ROOT")
        root = Path(
            tempfile.mkdtemp(
                prefix=f"jyd-auth-storm-{uuid.uuid4().hex}-",
                dir=configured_tmp or None,
            )
        )
        settings = WebApiSettings(
            storage_root=root / "storage",
            template_library_root=root / "templates",
            default_draft_root=root / "drafts",
            audio_library_root=root / "audio",
            admin_password="admin-pass",
            admin_session_secret="admin-secret",
            auth_authority=False,
            auth_server_url="https://video.example",
            execution_mode="agent",
        )
        for directory in (
            settings.storage_root,
            settings.template_library_root,
            settings.default_draft_root,
            settings.audio_library_root,
        ):
            directory.mkdir(parents=True, exist_ok=True)
        user = {"user_id": "user-1", "username": "tester", "enabled": True}
        try:
            with patch(
                "jyd_probe.auth_center.AuthCenterClient.login",
                return_value={"access_token": "token", "user": user},
            ), patch(
                "jyd_probe.auth_center.AuthCenterClient.verify", return_value=user
            ) as verify:
                with TestClient(create_app(settings)) as browser:
                    login = browser.post(
                        "/api/auth/login",
                        json={"username": "tester", "password": "pass123"},
                    )
                    self.assertEqual(login.status_code, 200, login.text)
                    verify.reset_mock()
                    response = browser.get("/api/new/projects")
                    self.assertEqual(response.status_code, 200, response.text)
                    self.assertEqual(verify.call_count, 1)
        finally:
            shutil.rmtree(root, ignore_errors=True)

    def test_slow_remote_verify_does_not_block_unprotected_health_endpoint(self) -> None:
        configured_tmp = os.environ.get("JYD_TEST_TMP_ROOT")
        root = Path(
            tempfile.mkdtemp(
                prefix=f"jyd-auth-loop-{uuid.uuid4().hex}-",
                dir=configured_tmp or None,
            )
        )
        settings = WebApiSettings(
            storage_root=root / "storage",
            template_library_root=root / "templates",
            default_draft_root=root / "drafts",
            audio_library_root=root / "audio",
            admin_password="admin-pass",
            admin_session_secret="admin-secret",
            auth_authority=False,
            auth_server_url="https://video.example",
            execution_mode="agent",
        )
        for directory in (
            settings.storage_root,
            settings.template_library_root,
            settings.default_draft_root,
            settings.audio_library_root,
        ):
            directory.mkdir(parents=True, exist_ok=True)
        started = threading.Event()
        release = threading.Event()
        user = {"user_id": "user-1", "username": "tester", "enabled": True}

        def slow_verify(_client, _token):
            started.set()
            self.assertTrue(release.wait(timeout=3))
            return user

        try:
            with patch(
                "jyd_probe.auth_center.AuthCenterClient.verify", new=slow_verify
            ):
                with TestClient(create_app(settings)) as browser:
                    browser.cookies.set(settings.site_cookie_name, "token")
                    with ThreadPoolExecutor(max_workers=1) as pool:
                        protected = pool.submit(browser.get, "/api/new/projects")
                        self.assertTrue(started.wait(timeout=3))
                        health_started = time.monotonic()
                        health = browser.get("/api/health")
                        health_elapsed = time.monotonic() - health_started
                        self.assertEqual(health.status_code, 200, health.text)
                        self.assertLess(health_elapsed, 1.0)
                        release.set()
                        self.assertEqual(
                            protected.result(timeout=3).status_code, 200
                        )
        finally:
            release.set()
            shutil.rmtree(root, ignore_errors=True)


class _JsonResponse:
    status = 200

    def __init__(self, payload: dict):
        import io
        import json

        self._stream = io.BytesIO(json.dumps(payload).encode("utf-8"))

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return None

    def read(self) -> bytes:
        return self._stream.read()


if __name__ == "__main__":
    unittest.main()
