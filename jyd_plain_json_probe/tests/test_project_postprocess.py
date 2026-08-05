from __future__ import annotations

from pathlib import Path
import shutil
import sys
import unittest
import uuid
from unittest.mock import patch

from fastapi.testclient import TestClient


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from jyd_probe.project_store import ProjectStore  # noqa: E402
from jyd_probe.web_api import WebApiSettings, create_app  # noqa: E402


class ProjectPostprocessApiTest(unittest.TestCase):
    def setUp(self) -> None:
        self.root = (
            PROJECT_ROOT
            / "runtime"
            / "test_tmp"
            / f"project_postprocess_{uuid.uuid4().hex}"
        )
        self.root.mkdir(parents=True)
        self.settings = WebApiSettings(
            storage_root=self.root / "storage",
            template_library_root=self.root / "templates",
            default_draft_root=self.root / "drafts",
            audio_library_root=PROJECT_ROOT / "data" / "libraries" / "audio_library",
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
        ):
            directory.mkdir(parents=True, exist_ok=True)

    def tearDown(self) -> None:
        shutil.rmtree(self.root, ignore_errors=True)

    def test_4b_uses_real_font_width_one_line_position_and_bgm(self) -> None:
        user = {"user_id": "postprocess-user", "username": "tester", "enabled": True}
        store = ProjectStore(self.settings.storage_root / "control.db")
        project = store.create_project(
            owner_user_id=user["user_id"],
            owner_username=user["username"],
            name="4B 测试",
            items=[
                {
                    "row_key": "1",
                    "script_text": "这是一段需要使用真实字体宽度拆成多条单行字幕的较长测试文案。",
                }
            ],
        )
        item = project["items"][0]
        audio_path = self.settings.storage_root / "seed-audio.mp3"
        audio_path.write_bytes(b"audio")
        audio = store.add_asset(
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
        store.set_item_subtitles(
            user["user_id"],
            project["project_id"],
            item["item_id"],
            {
                "source": "minimax_timestamps",
                "raw_cues": [
                    {
                        "start_us": 0,
                        "end_us": 4_000_000,
                        "text": "这是一段需要使用真实字体宽度拆成多条单行字幕的较长测试文案。",
                    }
                ],
                "render_cues": [],
                "bound_audio_asset_id": audio["asset_id"],
                "bound_video_asset_id": None,
                "style": {},
                "status": "READY",
                "overflow_risk": False,
            },
        )
        base_path = self.settings.storage_root / "seed-base.mp4"
        base_path.write_bytes(b"base-video")
        store.add_asset(
            owner_user_id=user["user_id"],
            project_id=project["project_id"],
            item_id=item["item_id"],
            asset_type="base_video",
            source_type="runninghub_merge",
            status="READY",
            filename="1-base.mp4",
            managed_path=str(base_path),
            make_current=True,
        )

        captured: dict[str, object] = {"submit_count": 0}

        def fake_submit_batch(_queue, jobs, variants):
            captured["submit_count"] = int(captured["submit_count"]) + 1
            captured["job"] = jobs[0]
            captured["variant"] = variants[0]
            output = Path(jobs[0]["output"]["mp4_path"])
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_bytes(b"captioned-with-bgm")
            captured["output"] = output
            return {"batch_id": "export-batch-1", "job_ids": ["export-job-1"]}

        def fake_get_status(_queue, job_id):
            self.assertEqual(job_id, "export-job-1")
            return {
                "job_id": job_id,
                "status": "completed",
                "result": {"output_mp4": str(captured["output"])},
            }

        with patch(
            "jyd_probe.auth_center.AuthCenterClient.login",
            return_value={"access_token": "token", "user": user},
        ), patch(
            "jyd_probe.auth_center.AuthCenterClient.verify", return_value=user
        ), patch(
            "jyd_probe.web_api.RenderJobQueue.submit_batch", new=fake_submit_batch
        ), patch(
            "jyd_probe.web_api.RenderJobQueue.get_status", new=fake_get_status
        ):
            with TestClient(create_app(self.settings)) as client:
                login = client.post(
                    "/api/auth/login",
                    json={"username": "tester", "password": "pass123"},
                )
                self.assertEqual(login.status_code, 200, login.text)
                options = client.get("/api/new/postprocess/options")
                self.assertEqual(options.status_code, 200, options.text)
                self.assertEqual(options.json()["caption"]["bottom_offset_ratio"], 0.2)
                self.assertEqual(
                    options.json()["default_font_identity"],
                    "resource_id:7244518590332801592",
                )
                font = options.json()["fonts"][0]
                self.assertEqual(font["name"], "DouyinSansBold")
                bgm = options.json()["bgm"][0]
                font_preview = client.get(font["preview_url"])
                self.assertEqual(font_preview.status_code, 200, font_preview.text)
                self.assertGreater(len(font_preview.content), 1024)
                self.assertTrue(
                    font_preview.headers["content-type"].startswith("font/")
                    or font_preview.headers["content-type"] == "application/octet-stream"
                )
                bgm_preview = client.get(bgm["preview_url"])
                self.assertEqual(bgm_preview.status_code, 200, bgm_preview.text)
                self.assertGreater(len(bgm_preview.content), 1024)
                generated = client.post(
                    f"/api/new/projects/{project['project_id']}/postprocess/generate",
                    json={
                        "idempotency_key": "postprocess-1",
                        "items": [
                            {
                                "item_id": item["item_id"],
                                "font_identity": font["identity"],
                                "bgm_identity": bgm["identity"],
                                "text_color": "#FFFFFF",
                            }
                        ],
                    },
                )
                self.assertEqual(generated.status_code, 200, generated.text)
                row = generated.json()["items"][0]
                self.assertEqual(row["status"], "COMPOSITION_READY")
                self.assertIsNone(row["outputs"]["composition_video"])
                self.assertEqual(row["subtitles"]["status"], "PREVIEW_READY")
                self.assertEqual(
                    row["subtitles"]["bound_video_asset_id"],
                    row["outputs"]["base_video"]["asset_id"],
                )
                self.assertEqual(row["subtitles"]["style"]["max_lines"], 1)
                self.assertEqual(row["subtitles"]["style"]["max_width_ratio"], 0.8)
                self.assertEqual(row["subtitles"]["style"]["bottom_offset_ratio"], 0.2)
                self.assertEqual(row["subtitles"]["style"]["transform_y"], -0.6)
                self.assertGreater(len(row["subtitles"]["render_cues"]), 1)
                self.assertTrue(
                    all("\n" not in cue["text"] for cue in row["subtitles"]["render_cues"])
                )

                self.assertTrue(row["allowed_actions"]["generate_variants"])
                self.assertFalse(row["allowed_actions"]["download_current_video"])
                operation = generated.json()["operations"][-1]
                self.assertEqual(operation["status"], "SUCCEEDED")
                self.assertEqual(operation["result"]["preview_mode"], "browser")
                self.assertNotIn("job_id", operation["result"])
                self.assertEqual(captured["submit_count"], 0)

                downloaded = client.get(
                    f"/api/new/projects/{project['project_id']}/items/{item['item_id']}/current-video"
                )
                self.assertEqual(downloaded.status_code, 404, downloaded.text)
                base_download = client.get(
                    f"/api/new/projects/{project['project_id']}/items/{item['item_id']}/base-video"
                )
                self.assertEqual(base_download.status_code, 200, base_download.text)
                self.assertEqual(base_download.content, b"base-video")

                exported = client.post(
                    f"/api/new/projects/{project['project_id']}/items/{item['item_id']}/postprocess/export",
                    json={"idempotency_key": "explicit-download-1"},
                )
                self.assertEqual(exported.status_code, 200, exported.text)
                exported_row = exported.json()["items"][0]
                self.assertIsNotNone(exported_row["outputs"]["composition_video"])
                self.assertEqual(captured["submit_count"], 1)
                job = captured["job"]
                self.assertTrue(job["captions"]["single_line"])
                self.assertEqual(job["captions"]["max_lines"], 1)
                self.assertEqual(job["captions"]["transform_y"], -0.6)
                self.assertEqual(job["audios"][0]["volume"], 0.3)
                downloaded = client.get(
                    f"/api/new/projects/{project['project_id']}/items/{item['item_id']}/current-video"
                )
                self.assertEqual(downloaded.status_code, 200, downloaded.text)
                self.assertEqual(downloaded.content, b"captioned-with-bgm")

                changed = client.patch(
                    f"/api/new/projects/{project['project_id']}/items/{item['item_id']}/postprocess-settings",
                    json={
                        "font_identity": font["identity"],
                        "bgm_identity": "",
                        "text_color": "#00FF00",
                    },
                )
                self.assertEqual(changed.status_code, 200, changed.text)
                changed_row = changed.json()["items"][0]
                self.assertEqual(changed_row["status"], "BASE_VIDEO_READY")
                self.assertIsNotNone(changed_row["outputs"]["base_video"])
                self.assertIsNone(changed_row["outputs"]["composition_video"])
                self.assertEqual(
                    len(changed_row["asset_history"].get("composition_video", [])), 1
                )
                self.assertTrue(changed_row["allowed_actions"]["start_postprocess"])


if __name__ == "__main__":
    unittest.main()
