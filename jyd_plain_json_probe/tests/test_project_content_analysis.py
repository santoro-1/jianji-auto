from __future__ import annotations

import hashlib
from pathlib import Path
import shutil
import sys
import threading
import time
import unittest
import uuid
from unittest.mock import patch

from fastapi.testclient import TestClient


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from jyd_probe.auth_center import AuthCenterError  # noqa: E402
from jyd_probe.project_content_analysis import ProjectContentAnalysisCoordinator  # noqa: E402
from jyd_probe.project_store import ProjectStore  # noqa: E402
from jyd_probe.web_api import WebApiSettings, create_app  # noqa: E402


def _remote_result(
    script: str,
    *,
    music_status: str = "SUCCESS",
    subtitle_status: str = "SUCCESS",
) -> dict[str, object]:
    import hashlib

    return {
        "schema_version": "jyd.content-analysis.v1",
        "prompt_version": "jyd.content-analysis.prompt.v1",
        "script_sha256": hashlib.sha256(script.encode("utf-8")).hexdigest(),
        "script_length": len(script),
        "model": "doubao-seed-2-0-lite-260428",
        "overall_status": (
            "SUCCESS"
            if music_status == subtitle_status == "SUCCESS"
            else ("PARTIAL" if "SUCCESS" in {music_status, subtitle_status} else "FAILED")
        ),
        "music_analysis_status": music_status,
        "subtitle_analysis_status": subtitle_status,
        "music_intent": {"primary_scene": "health_education"}
        if music_status == "SUCCESS"
        else None,
        "subtitle_units": [
            {
                "start": 0,
                "end": len(script),
                "text": script,
                "kind": "phrase",
                "bind": "none",
                "break_after": "allow",
            }
        ]
        if subtitle_status == "SUCCESS"
        else None,
        "errors": {
            "music": None
            if music_status == "SUCCESS"
            else {"code": "MUSIC_SCHEMA_INVALID", "summary": "音乐失败"},
            "subtitle": None
            if subtitle_status == "SUCCESS"
            else {"code": "SUBTITLE_TEXT_MISMATCH", "summary": "字幕失败"},
        },
        "provider_request_id": f"req-{uuid.uuid4().hex}",
        "provider_attempts": 1,
        "cache_hit": False,
        "cacheable": music_status == "SUCCESS" or subtitle_status == "SUCCESS",
    }


class ProjectContentAnalysisApiTest(unittest.TestCase):
    def setUp(self) -> None:
        self.root = (
            PROJECT_ROOT
            / "runtime"
            / "test_tmp"
            / f"project_content_analysis_{uuid.uuid4().hex}"
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
        self.user = {"user_id": "user-analysis", "username": "tester", "enabled": True}

    def tearDown(self) -> None:
        shutil.rmtree(self.root, ignore_errors=True)

    def _patches(self, analyze):
        user = self.user

        def verify(_client, token):
            return user if token == "center-token" else None

        return (
            patch(
                "jyd_probe.auth_center.AuthCenterClient.login",
                return_value={"access_token": "center-token", "user": user},
            ),
            patch("jyd_probe.auth_center.AuthCenterClient.verify", new=verify),
            patch(
                "jyd_probe.auth_center.AuthCenterClient.analyze_workbench_content",
                new=analyze,
            ),
        )

    @staticmethod
    def _login(client: TestClient) -> None:
        response = client.post(
            "/api/auth/login", json={"username": "tester", "password": "pass123"}
        )
        if response.status_code != 200:
            raise AssertionError(response.text)

    def test_project_batch_analyzes_one_script_per_request_with_limit_ten(self) -> None:
        lock = threading.Lock()
        active = 0
        peak = 0
        calls: list[str] = []

        def analyze(_client, _token, original_script, *, force_refresh=False):
            nonlocal active, peak
            with lock:
                active += 1
                peak = max(peak, active)
                calls.append(original_script)
            time.sleep(0.03)
            with lock:
                active -= 1
            return _remote_result(original_script)

        login_patch, verify_patch, analyze_patch = self._patches(analyze)
        with login_patch, verify_patch, analyze_patch, TestClient(
            create_app(self.settings)
        ) as client:
            self._login(client)
            project = client.post(
                "/api/new/projects",
                json={
                    "name": "并发分析",
                    "items": [
                        {"row_key": str(index), "script_text": f"第{index}条脚本"}
                        for index in range(12)
                    ],
                },
            ).json()
            response = client.post(
                f"/api/new/projects/{project['project_id']}/content-analysis",
                json={},
            )

        self.assertEqual(response.status_code, 200, response.text)
        result = response.json()
        self.assertEqual(len(calls), 12)
        self.assertEqual(peak, 10)
        self.assertTrue(all(item["content_analysis"]["overall_status"] == "SUCCESS" for item in result["items"]))
        self.assertEqual(result["content_analysis_summary"]["counts"]["SUCCESS"], 12)
        self.assertEqual(result["content_analysis_summary"]["concurrency_limit"], 10)

    def test_branches_and_project_items_fail_independently(self) -> None:
        def analyze(_client, _token, original_script, *, force_refresh=False):
            if original_script == "完整成功":
                return _remote_result(original_script)
            if original_script == "音乐成功字幕失败":
                return _remote_result(original_script, subtitle_status="FAILED")
            raise AuthCenterError("数字人网站暂时不可用")

        login_patch, verify_patch, analyze_patch = self._patches(analyze)
        with login_patch, verify_patch, analyze_patch, TestClient(
            create_app(self.settings)
        ) as client:
            self._login(client)
            project = client.post(
                "/api/new/projects",
                json={
                    "name": "部分失败",
                    "items": [
                        {"row_key": "1", "script_text": "完整成功"},
                        {"row_key": "2", "script_text": "音乐成功字幕失败"},
                        {"row_key": "3", "script_text": "请求失败"},
                    ],
                },
            ).json()
            result = client.post(
                f"/api/new/projects/{project['project_id']}/content-analysis", json={}
            ).json()

        first, second, third = result["items"]
        self.assertEqual(first["content_analysis"]["overall_status"], "SUCCESS")
        self.assertEqual(second["content_analysis"]["overall_status"], "PARTIAL")
        self.assertEqual(second["content_analysis"]["music_analysis_status"], "SUCCESS")
        self.assertEqual(second["content_analysis"]["subtitle_analysis_status"], "FAILED")
        self.assertEqual(third["content_analysis"]["overall_status"], "FAILED")
        self.assertIsNotNone(third["content_analysis"]["errors"]["request"])
        self.assertTrue(all(item["status"] == "DRAFT" for item in result["items"]))

    def test_unchanged_failed_script_is_not_reanalyzed_without_explicit_retry(self) -> None:
        calls = 0

        def analyze(_client, _token, _original_script, *, force_refresh=False):
            nonlocal calls
            calls += 1
            raise AuthCenterError("内容分析不可用")

        login_patch, verify_patch, analyze_patch = self._patches(analyze)
        with login_patch, verify_patch, analyze_patch, TestClient(
            create_app(self.settings)
        ) as client:
            self._login(client)
            project = client.post(
                "/api/new/projects",
                json={"name": "失败不自动重试", "items": [{"row_key": "1", "script_text": "文本未变"}]},
            ).json()
            project_id = project["project_id"]
            first = client.post(
                f"/api/new/projects/{project_id}/content-analysis", json={}
            ).json()
            second = client.post(
                f"/api/new/projects/{project_id}/content-analysis", json={}
            ).json()

        self.assertEqual(calls, 1)
        self.assertEqual(first["items"][0]["content_analysis"]["overall_status"], "FAILED")
        self.assertEqual(second["items"][0]["content_analysis"]["overall_status"], "FAILED")

    def test_script_change_invalidates_and_only_reanalyzes_changed_item(self) -> None:
        calls: list[tuple[str, bool]] = []

        def analyze(_client, _token, original_script, *, force_refresh=False):
            calls.append((original_script, force_refresh))
            return _remote_result(original_script)

        login_patch, verify_patch, analyze_patch = self._patches(analyze)
        with login_patch, verify_patch, analyze_patch, TestClient(
            create_app(self.settings)
        ) as client:
            self._login(client)
            project = client.post(
                "/api/new/projects",
                json={
                    "name": "单行失效",
                    "items": [
                        {"row_key": "1", "script_text": "原脚本一"},
                        {"row_key": "2", "script_text": "原脚本二"},
                    ],
                },
            ).json()
            project_id = project["project_id"]
            analyzed = client.post(
                f"/api/new/projects/{project_id}/content-analysis", json={}
            ).json()
            first_id = analyzed["items"][0]["item_id"]
            second_before = analyzed["items"][1]["content_analysis"]
            calls.clear()

            edited = client.patch(
                f"/api/new/projects/{project_id}/items/{first_id}",
                json={"script_text": "修改后的脚本一"},
            ).json()
            self.assertEqual(
                edited["items"][0]["content_analysis"]["overall_status"],
                "NOT_REQUESTED",
            )
            self.assertEqual(
                edited["items"][0]["content_analysis"]["invalidated_reason"],
                "SCRIPT_CHANGED",
            )
            self.assertEqual(edited["items"][1]["content_analysis"], second_before)

            refreshed = client.post(
                f"/api/new/projects/{project_id}/content-analysis", json={}
            ).json()

        self.assertEqual(calls, [("修改后的脚本一", False)])
        self.assertTrue(all(item["content_analysis"]["overall_status"] == "SUCCESS" for item in refreshed["items"]))

    def test_retry_preserves_a_previously_successful_branch(self) -> None:
        call_count = 0

        def analyze(_client, _token, original_script, *, force_refresh=False):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return _remote_result(original_script, subtitle_status="FAILED")
            return _remote_result(original_script, music_status="FAILED")

        login_patch, verify_patch, analyze_patch = self._patches(analyze)
        with login_patch, verify_patch, analyze_patch, TestClient(
            create_app(self.settings)
        ) as client:
            self._login(client)
            project = client.post(
                "/api/new/projects",
                json={"name": "分支保护", "items": [{"row_key": "1", "script_text": "测试脚本"}]},
            ).json()
            project_id = project["project_id"]
            partial = client.post(
                f"/api/new/projects/{project_id}/content-analysis", json={}
            ).json()
            item_id = partial["items"][0]["item_id"]
            retried = client.post(
                f"/api/new/projects/{project_id}/items/{item_id}/content-analysis/retry"
            ).json()

        snapshot = retried["items"][0]["content_analysis"]
        self.assertEqual(snapshot["overall_status"], "SUCCESS")
        self.assertEqual(snapshot["music_analysis_status"], "SUCCESS")
        self.assertEqual(snapshot["subtitle_analysis_status"], "SUCCESS")
        self.assertIsNotNone(snapshot["music_intent"])
        self.assertIsNotNone(snapshot["subtitle_units"])

    def test_analysis_failure_does_not_touch_audio_video_or_raw_cues(self) -> None:
        def analyze(_client, _token, original_script, *, force_refresh=False):
            raise AuthCenterError("内容分析不可用")

        login_patch, verify_patch, analyze_patch = self._patches(analyze)
        with login_patch, verify_patch, analyze_patch, TestClient(
            create_app(self.settings)
        ) as client:
            self._login(client)
            project = client.post(
                "/api/new/projects",
                json={"name": "安全降级", "items": [{"row_key": "1", "script_text": "测试脚本"}]},
            ).json()
            project_id = project["project_id"]
            item_id = project["items"][0]["item_id"]
            store = client.app.state.project_store
            audio = store.add_asset(
                owner_user_id=self.user["user_id"],
                project_id=project_id,
                item_id=item_id,
                asset_type="audio",
                source_type="minimax",
                status="READY",
                filename="audio.mp3",
                managed_path=str(self.root / "audio.mp3"),
                make_current=True,
            )
            base_video = store.add_asset(
                owner_user_id=self.user["user_id"],
                project_id=project_id,
                item_id=item_id,
                asset_type="base_video",
                source_type="runninghub",
                status="READY",
                filename="base.mp4",
                managed_path=str(self.root / "base.mp4"),
                make_current=True,
            )
            raw_cues = [{"start_us": 0, "end_us": 1_000_000, "text": "测试脚本"}]
            store.set_item_subtitles(
                self.user["user_id"],
                project_id,
                item_id,
                {
                    "source": "minimax_timestamps",
                    "raw_cues": raw_cues,
                    "render_cues": raw_cues,
                    "bound_audio_asset_id": audio["asset_id"],
                    "bound_video_asset_id": base_video["asset_id"],
                    "style": {},
                    "status": "READY",
                    "overflow_risk": False,
                },
            )

            result = client.post(
                f"/api/new/projects/{project_id}/content-analysis", json={}
            ).json()

        item = result["items"][0]
        self.assertEqual(item["content_analysis"]["overall_status"], "FAILED")
        self.assertEqual(item["outputs"]["audio"]["asset_id"], audio["asset_id"])
        self.assertEqual(item["outputs"]["base_video"]["asset_id"], base_video["asset_id"])
        self.assertEqual(item["subtitles"]["raw_cues"], raw_cues)

    def test_late_response_cannot_overwrite_a_newer_script(self) -> None:
        started = threading.Event()
        release = threading.Event()

        class BlockingClient:
            def analyze_workbench_content(
                self, _token, original_script, *, force_refresh=False
            ):
                started.set()
                release.wait(2)
                return _remote_result(original_script)

        store = ProjectStore(self.settings.storage_root / "race.db")
        project = store.create_project(
            owner_user_id=self.user["user_id"],
            owner_username=self.user["username"],
            name="并发修改保护",
            items=[{"row_key": "1", "script_text": "旧脚本"}],
        )
        item_id = project["items"][0]["item_id"]
        coordinator = ProjectContentAnalysisCoordinator(store, BlockingClient())
        result_box: list[dict[str, object]] = []

        worker = threading.Thread(
            target=lambda: result_box.append(
                coordinator.analyze(
                    self.user["user_id"], project["project_id"], "token"
                )
            )
        )
        worker.start()
        self.assertTrue(started.wait(1))
        store.update_item(
            self.user["user_id"],
            project["project_id"],
            item_id,
            script_text="新脚本",
        )
        release.set()
        worker.join(3)

        self.assertFalse(worker.is_alive())
        current = store.get_project(self.user["user_id"], project["project_id"])
        snapshot = current["items"][0]["content_analysis"]
        self.assertEqual(current["items"][0]["script_text"], "新脚本")
        self.assertEqual(snapshot["overall_status"], "NOT_REQUESTED")
        self.assertEqual(snapshot["invalidated_reason"], "SCRIPT_CHANGED")

    def test_any_script_character_change_invalidates_audio_cues_and_analysis_together(self) -> None:
        script = "糖原和呼吸"

        class SuccessfulClient:
            def analyze_workbench_content(
                self, _token, original_script, *, force_refresh=False
            ):
                return _remote_result(original_script)

        store = ProjectStore(self.settings.storage_root / "version_invalidation.db")
        project = store.create_project(
            owner_user_id=self.user["user_id"],
            owner_username=self.user["username"],
            name="任意字符失效",
            items=[{"row_key": "1", "script_text": script}],
        )
        item_id = project["items"][0]["item_id"]
        analyzed = ProjectContentAnalysisCoordinator(store, SuccessfulClient()).analyze(
            self.user["user_id"], project["project_id"], "token"
        )
        self.assertEqual(
            analyzed["items"][0]["content_analysis"]["overall_status"], "SUCCESS"
        )
        audio_path = self.settings.storage_root / "version-audio.mp3"
        audio_path.write_bytes(b"audio")
        audio = store.add_asset(
            owner_user_id=self.user["user_id"],
            project_id=project["project_id"],
            item_id=item_id,
            asset_type="audio",
            source_type="minimax",
            status="READY",
            filename="1.mp3",
            managed_path=str(audio_path),
            metadata={
                "script_sha256": hashlib.sha256(script.encode("utf-8")).hexdigest()
            },
            make_current=True,
        )
        raw_cues = [{"start_us": 0, "end_us": 1_000_000, "text": script}]
        store.set_item_subtitles(
            self.user["user_id"],
            project["project_id"],
            item_id,
            {
                "source": "minimax_timestamps",
                "raw_cues": raw_cues,
                "render_cues": raw_cues,
                "bound_audio_asset_id": audio["asset_id"],
                "status": "READY",
            },
        )

        changed = store.update_item(
            self.user["user_id"],
            project["project_id"],
            item_id,
            script_text=f"{script}~",
        )
        item = changed["items"][0]

        self.assertIsNone(item["outputs"]["audio"])
        self.assertEqual(item["subtitles"]["raw_cues"], [])
        self.assertEqual(item["subtitles"]["render_cues"], [])
        self.assertEqual(item["content_analysis"]["overall_status"], "NOT_REQUESTED")
        self.assertEqual(
            item["content_analysis"]["invalidated_reason"], "SCRIPT_CHANGED"
        )

    def test_successful_analysis_saves_ai_music_but_preserves_manual_choice(self) -> None:
        class SuccessfulClient:
            def analyze_workbench_content(
                self, _token, original_script, *, force_refresh=False
            ):
                return _remote_result(original_script)

        class FakeMusicSelector:
            def resolve_for_analysis(
                self, _project, item, *, recent_identity_counts=None
            ):
                identity = f"music_id:matched-{item['row_key']}"
                return identity, {
                    "schema": "jyd.project-music-selection.v1",
                    "status": "SUCCESS",
                    "selection_source": "ai",
                    "bgm_identity": identity,
                    "video_duration_us": 0,
                }

        store = ProjectStore(self.settings.storage_root / "music_selection.db")
        project = store.create_project(
            owner_user_id=self.user["user_id"],
            owner_username=self.user["username"],
            name="分析后匹配音乐",
            items=[
                {"row_key": "1", "script_text": "自动匹配"},
                {"row_key": "2", "script_text": "保持手选"},
            ],
        )
        manual_item_id = project["items"][1]["item_id"]
        store.configure_item_postprocess(
            self.user["user_id"],
            project["project_id"],
            manual_item_id,
            font_identity="font",
            bgm_identity="music_id:manual",
            bgm_selection_mode="manual",
            text_color="#FFFFFF",
        )
        analyzed = ProjectContentAnalysisCoordinator(
            store,
            SuccessfulClient(),
            music_selector=FakeMusicSelector(),
        ).analyze(self.user["user_id"], project["project_id"], "token")

        automatic = analyzed["items"][0]["settings"]["postprocess"]
        manual = analyzed["items"][1]["settings"]["postprocess"]
        self.assertEqual(automatic["bgm_identity"], "music_id:matched-1")
        self.assertEqual(automatic["bgm_selection_mode"], "auto")
        self.assertEqual(automatic["music_selection"]["status"], "SUCCESS")
        self.assertEqual(manual["bgm_identity"], "music_id:manual")
        self.assertEqual(manual["bgm_selection_mode"], "manual")

    def test_batch_analysis_passes_prior_auto_music_counts_in_row_order(self) -> None:
        class SuccessfulClient:
            def analyze_workbench_content(
                self, _token, original_script, *, force_refresh=False
            ):
                return _remote_result(original_script)

        class RecordingMusicSelector:
            def __init__(self) -> None:
                self.seen_counts: list[dict[str, int]] = []

            def resolve_for_analysis(
                self, _project, _item, *, recent_identity_counts=None
            ):
                counts = dict(recent_identity_counts or {})
                self.seen_counts.append(counts)
                identity = f"music_id:choice-{sum(counts.values()) + 1}"
                return identity, {
                    "schema": "jyd.project-music-selection.v1",
                    "status": "SUCCESS",
                    "selection_source": "ai",
                    "bgm_identity": identity,
                    "video_duration_us": 0,
                }

        store = ProjectStore(self.settings.storage_root / "music_diversity.db")
        project = store.create_project(
            owner_user_id=self.user["user_id"],
            owner_username=self.user["username"],
            name="同类脚本音乐轮换",
            items=[
                {"row_key": "1", "script_text": "第一条健康建议"},
                {"row_key": "2", "script_text": "第二条健康建议"},
                {"row_key": "3", "script_text": "第三条健康建议"},
            ],
        )
        selector = RecordingMusicSelector()

        analyzed = ProjectContentAnalysisCoordinator(
            store,
            SuccessfulClient(),
            music_selector=selector,
        ).analyze(self.user["user_id"], project["project_id"], "token")

        self.assertEqual(
            selector.seen_counts,
            [
                {},
                {"music_id:choice-1": 1},
                {"music_id:choice-1": 1, "music_id:choice-2": 1},
            ],
        )
        self.assertEqual(
            [
                item["settings"]["postprocess"]["bgm_identity"]
                for item in analyzed["items"]
            ],
            ["music_id:choice-1", "music_id:choice-2", "music_id:choice-3"],
        )

    def test_same_script_analysis_retry_preserves_saved_auto_music(self) -> None:
        class SuccessfulClient:
            def analyze_workbench_content(
                self, _token, original_script, *, force_refresh=False
            ):
                return _remote_result(original_script)

        class CountingMusicSelector:
            def __init__(self) -> None:
                self.calls = 0

            def resolve_for_analysis(
                self, _project, _item, *, recent_identity_counts=None
            ):
                self.calls += 1
                identity = f"music_id:matched-{self.calls}"
                return identity, {
                    "schema": "jyd.project-music-selection.v1",
                    "status": "SUCCESS",
                    "selection_source": "ai",
                    "bgm_identity": identity,
                    "video_duration_us": 0,
                }

        store = ProjectStore(self.settings.storage_root / "music_retry.db")
        project = store.create_project(
            owner_user_id=self.user["user_id"],
            owner_username=self.user["username"],
            name="同脚本重试保留音乐",
            items=[{"row_key": "1", "script_text": "字幕需要重新分析"}],
        )
        selector = CountingMusicSelector()
        coordinator = ProjectContentAnalysisCoordinator(
            store,
            SuccessfulClient(),
            music_selector=selector,
        )

        first = coordinator.analyze(
            self.user["user_id"], project["project_id"], "token"
        )
        retried = coordinator.analyze(
            self.user["user_id"],
            project["project_id"],
            "token",
            force_refresh=True,
        )

        first_postprocess = first["items"][0]["settings"]["postprocess"]
        retried_postprocess = retried["items"][0]["settings"]["postprocess"]
        self.assertEqual(selector.calls, 1)
        self.assertEqual(first_postprocess["bgm_identity"], "music_id:matched-1")
        self.assertEqual(retried_postprocess["bgm_identity"], "music_id:matched-1")
        self.assertEqual(
            retried_postprocess["music_selection"]["status"], "SUCCESS"
        )


if __name__ == "__main__":
    unittest.main()
