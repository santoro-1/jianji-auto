from __future__ import annotations

import base64
from pathlib import Path
import shutil
import sys
import unittest
import uuid
from unittest.mock import patch

from fastapi.testclient import TestClient


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from jyd_probe.web_api import WebApiSettings, create_app  # noqa: E402
from jyd_probe.project_audio import _current_audio_links  # noqa: E402


PNG_1X1 = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="
)


class ProjectAudioApiTest(unittest.TestCase):
    def setUp(self) -> None:
        self.root = PROJECT_ROOT / "runtime" / "test_tmp" / f"project_audio_{uuid.uuid4().hex}"
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

    def test_only_latest_remote_audio_link_can_update_each_item(self) -> None:
        links = [
            {
                "system": "runninghub",
                "relation": "digital_human_audio_batch",
                "external_id": "old-batch",
            },
            {
                "system": "runninghub",
                "relation": "digital_human_audio_item",
                "external_id": "old-item",
                "item_id": "local-item",
                "metadata": {"batch_id": "old-batch"},
            },
            {
                "system": "runninghub",
                "relation": "digital_human_audio_batch",
                "external_id": "new-batch",
            },
            {
                "system": "runninghub",
                "relation": "digital_human_audio_item",
                "external_id": "new-item",
                "item_id": "local-item",
                "metadata": {"batch_id": "new-batch"},
            },
        ]

        batches, items = _current_audio_links(links)

        self.assertEqual([link["external_id"] for link in batches], ["new-batch"])
        self.assertEqual(list(items), ["new-item"])

    def test_saved_voice_can_be_applied_to_every_project_item(self) -> None:
        user = {"user_id": "voice-user", "username": "tester", "enabled": True}
        voices = [
            {
                "voice_asset_id": "saved-voice-1",
                "provider_voice_id": "custom-provider-1",
                "name": "已保存克隆音色",
                "source": "custom",
                "method": "clone",
            }
        ]

        with patch(
            "jyd_probe.auth_center.AuthCenterClient.login",
            return_value={"access_token": "voice-token", "user": user},
        ), patch(
            "jyd_probe.auth_center.AuthCenterClient.verify", return_value=user
        ), patch(
            "jyd_probe.auth_center.AuthCenterClient.list_workbench_voices",
            return_value={"voices": voices, "creation_tasks": []},
        ):
            with TestClient(create_app(self.settings)) as client:
                client.post(
                    "/api/auth/login",
                    json={"username": "tester", "password": "pass123"},
                )
                project = client.post(
                    "/api/new/projects",
                    json={
                        "name": "批量音色接口测试",
                        "items": [
                            {"row_key": "1", "script_text": "第一条。"},
                            {"row_key": "2", "script_text": "第二条。"},
                        ],
                    },
                ).json()

                selected = client.put(
                    f"/api/new/projects/{project['project_id']}/voice",
                    json={"voice_asset_id": "saved-voice-1"},
                )
                self.assertEqual(selected.status_code, 200, selected.text)
                payload = selected.json()
                self.assertEqual(
                    payload["preferences"]["default_voice_asset_id"],
                    "saved-voice-1",
                )
                self.assertTrue(
                    all(
                        item["settings"]["voice_asset_id"] == "saved-voice-1"
                        for item in payload["project"]["items"]
                    )
                )

                invalid = client.put(
                    f"/api/new/projects/{project['project_id']}/voice",
                    json={"voice_asset_id": "other-account-voice"},
                )
                self.assertEqual(invalid.status_code, 422)

    def test_unactivated_voice_cannot_be_selected_and_used_voice_cannot_be_deleted(self) -> None:
        user = {"user_id": "voice-user", "username": "tester", "enabled": True}
        unactivated = {
            "voice_asset_id": "saved-voice-1",
            "provider_voice_id": "custom-provider-1",
            "name": "待激活音色",
            "source": "custom",
            "method": "clone",
            "selectable": False,
        }

        with patch(
            "jyd_probe.auth_center.AuthCenterClient.login",
            return_value={"access_token": "voice-token", "user": user},
        ), patch(
            "jyd_probe.auth_center.AuthCenterClient.verify", return_value=user
        ), patch(
            "jyd_probe.auth_center.AuthCenterClient.list_workbench_voices",
            return_value={"voices": [unactivated], "creation_tasks": []},
        ), patch(
            "jyd_probe.auth_center.AuthCenterClient.activate_workbench_voice",
            return_value={**unactivated, "selectable": True, "activated": True},
        ) as activate, patch(
            "jyd_probe.auth_center.AuthCenterClient.delete_workbench_voice",
            return_value={"deleted": True, "voice_asset_id": "saved-voice-1"},
        ) as delete:
            with TestClient(create_app(self.settings)) as client:
                client.post(
                    "/api/auth/login",
                    json={"username": "tester", "password": "pass123"},
                )
                project = client.post(
                    "/api/new/projects",
                    json={
                        "name": "激活与删除测试",
                        "items": [{"row_key": "1", "script_text": "第一条。"}],
                    },
                ).json()

                denied = client.put(
                    f"/api/new/projects/{project['project_id']}/voice",
                    json={"voice_asset_id": "saved-voice-1"},
                )
                self.assertEqual(denied.status_code, 422)

                activated = client.post(
                    "/api/new/voices/saved-voice-1/activate",
                    json={"cost_confirmed": True},
                )
                self.assertEqual(activated.status_code, 200, activated.text)
                activate.assert_called_once()

                unactivated["selectable"] = True
                selected = client.put(
                    f"/api/new/projects/{project['project_id']}/voice",
                    json={"voice_asset_id": "saved-voice-1"},
                )
                self.assertEqual(selected.status_code, 200, selected.text)
                blocked = client.delete("/api/new/voices/saved-voice-1")
                self.assertEqual(blocked.status_code, 409)
                delete.assert_not_called()

    def test_project_audio_uses_remote_batch_and_keeps_precise_captions(self) -> None:
        user = {"user_id": "voice-user", "username": "tester", "enabled": True}
        voices = [
            {
                "voice_asset_id": "official-voice-1",
                "provider_voice_id": "Chinese (Mandarin)_Reliable_Executive",
                "name": "沉稳男声",
                "description": "专业内容",
                "source": "official",
                "method": "system",
                "preview_available": False,
            }
        ]
        remote_status = {
            "value": {
                "batch_id": "remote-batch-1",
                "items": [
                    {
                        "item_id": "remote-item-1",
                        "row_key": "1",
                        "status": "PENDING",
                        "generation_version": 1,
                        "audio_ready": False,
                        "captions": None,
                    }
                ],
            }
        }

        def fake_login(_self, _username, _password):
            return {"access_token": "voice-token", "user": user}

        def fake_verify(_self, _token):
            return user

        def fake_upload(_self, _token, _path, *, kind, filename):
            self.assertEqual(kind, "image")
            return {"asset_id": "remote-image-1", "original_name": filename}

        def fake_create(_self, _token, payload):
            self.assertTrue(payload["speech_options"]["costConfirmed"])
            self.assertEqual(payload["speech_options"]["voiceAssetId"], "official-voice-1")
            return remote_status["value"]

        def fake_status(_self, _token, _batch_id):
            return remote_status["value"]

        def fake_download(_self, _token, _batch_id, _item_id, target, *, max_bytes):
            del max_bytes
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(b"ID3-real-audio")
            return len(b"ID3-real-audio")

        patches = [
            patch("jyd_probe.auth_center.AuthCenterClient.login", new=fake_login),
            patch("jyd_probe.auth_center.AuthCenterClient.verify", new=fake_verify),
            patch(
                "jyd_probe.auth_center.AuthCenterClient.list_workbench_voices",
                return_value={"voices": voices, "creation_tasks": []},
            ),
            patch(
                "jyd_probe.auth_center.AuthCenterClient.upload_workbench_batch_asset",
                new=fake_upload,
            ),
            patch(
                "jyd_probe.auth_center.AuthCenterClient.create_workbench_audio_batch",
                new=fake_create,
            ),
            patch(
                "jyd_probe.auth_center.AuthCenterClient.get_workbench_audio_batch",
                new=fake_status,
            ),
            patch(
                "jyd_probe.auth_center.AuthCenterClient.download_workbench_audio",
                new=fake_download,
            ),
        ]
        for active in patches:
            active.start()
            self.addCleanup(active.stop)

        with TestClient(create_app(self.settings)) as client:
            login = client.post(
                "/api/auth/login", json={"username": "tester", "password": "pass123"}
            )
            self.assertEqual(login.status_code, 200)
            library = client.get("/api/new/voices")
            self.assertEqual(library.status_code, 200)
            self.assertEqual(
                library.json()["preferences"]["default_voice_asset_id"],
                "official-voice-1",
            )
            project = client.post(
                "/api/new/projects",
                json={
                    "name": "声音模块测试",
                    "items": [{"row_key": "1", "script_text": "第一条真实声音。"}],
                },
            ).json()
            project_id = project["project_id"]
            image = client.post(
                f"/api/new/projects/{project_id}/images?filename=person.png",
                content=PNG_1X1,
                headers={"Content-Type": "application/octet-stream"},
            )
            self.assertEqual(image.status_code, 201, image.text)
            mapped = client.put(
                f"/api/new/projects/{project_id}/image-mapping",
                json={"strategy": "loop", "reuse_count": 1},
            )
            self.assertEqual(mapped.status_code, 200)

            started = client.post(
                f"/api/new/projects/{project_id}/audio/generate",
                json={
                    "default_voice_asset_id": "official-voice-1",
                    "voice_assignments": {},
                    "voice_settings": {"model": "speech-2.8-hd", "speed": 1},
                    "idempotency_key": "audio-generation-1",
                    "cost_confirmed": True,
                },
            )
            self.assertEqual(started.status_code, 200, started.text)
            self.assertEqual(started.json()["items"][0]["status"], "AUDIO_QUEUED")
            self.assertIn(
                "digital_human_audio_batch",
                {link["relation"] for link in started.json()["links"]},
            )

            remote_status["value"] = {
                "batch_id": "remote-batch-1",
                "items": [
                    {
                        "item_id": "remote-item-1",
                        "row_key": "1",
                        "status": "AWAITING_REVIEW",
                        "generation_version": 1,
                        "audio_ready": True,
                        "captions": {
                            "source": "minimax_timestamps",
                            "cues": [
                                {
                                    "start_us": 0,
                                    "end_us": 1_200_000,
                                    "duration_us": 1_200_000,
                                    "text": "第一条。",
                                }
                            ],
                        },
                    }
                ],
            }
            synced = client.get(f"/api/new/projects/{project_id}/audio/status")
            self.assertEqual(synced.status_code, 200, synced.text)
            row = synced.json()["items"][0]
            self.assertEqual(row["status"], "AUDIO_READY")
            self.assertEqual(row["outputs"]["audio"]["version"], 1)
            self.assertEqual(row["subtitles"]["source"], "minimax_timestamps")
            self.assertEqual(row["subtitles"]["raw_cues"][0]["end_us"], 1_200_000)
            audio = client.get(
                f"/api/new/projects/{project_id}/items/{row['item_id']}/audio"
            )
            self.assertEqual(audio.status_code, 200)
            self.assertEqual(audio.content, b"ID3-real-audio")


if __name__ == "__main__":
    unittest.main()
