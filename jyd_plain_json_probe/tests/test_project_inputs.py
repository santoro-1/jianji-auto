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
TEMPLATE_PATH = (
    PROJECT_ROOT
    / "apps"
    / "processor"
    / "frontend"
    / "new"
    / "project-script-template.xlsx"
)
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from jyd_probe.web_api import WebApiSettings, create_app  # noqa: E402


PNG_1X1 = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="
)


class ProjectInputsApiTest(unittest.TestCase):
    def setUp(self) -> None:
        self.root = (
            PROJECT_ROOT / "runtime" / "test_tmp" / f"project_inputs_{uuid.uuid4().hex}"
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
        self.user = {"user_id": "user-1", "username": "tester", "enabled": True}

    def tearDown(self) -> None:
        shutil.rmtree(self.root, ignore_errors=True)

    def _client_context(self):
        user = self.user

        def verify(_client, token):
            return user if token == "center-token" else None

        return (
            patch(
                "jyd_probe.auth_center.AuthCenterClient.login",
                return_value={"access_token": "center-token", "user": user},
            ),
            patch("jyd_probe.auth_center.AuthCenterClient.verify", new=verify),
        )

    def _login(self, client: TestClient) -> None:
        response = client.post(
            "/api/auth/login",
            json={"username": "tester", "password": "pass123"},
        )
        self.assertEqual(response.status_code, 200, response.text)

    def test_two_column_csv_and_downloadable_xlsx_template_are_accepted(self) -> None:
        login_patch, verify_patch = self._client_context()
        with login_patch, verify_patch, TestClient(create_app(self.settings)) as client:
            self._login(client)
            template = client.get("/api/new/script-template")
            self.assertEqual(template.status_code, 200)
            self.assertEqual(template.content, TEMPLATE_PATH.read_bytes())

            xlsx_preview = client.post(
                "/api/new/script-imports/preview?filename=template.xlsx",
                content=template.content,
            )
            self.assertEqual(xlsx_preview.status_code, 200, xlsx_preview.text)
            self.assertEqual(xlsx_preview.json()["total_rows"], 3)
            self.assertEqual(xlsx_preview.json()["rows"][0]["row_key"], "1")

            csv_preview = client.post(
                "/api/new/script-imports/preview?filename=scripts.csv",
                content="任务ID,脚本内容\n1,第一条口播\n2,第二条口播\n".encode(
                    "utf-8-sig"
                ),
            )
            self.assertEqual(csv_preview.status_code, 200, csv_preview.text)
            self.assertEqual(
                csv_preview.json()["rows"],
                [
                    {"row_key": "1", "script_text": "第一条口播"},
                    {"row_key": "2", "script_text": "第二条口播"},
                ],
            )

            duplicate = client.post(
                "/api/new/script-imports/preview?filename=bad.csv",
                content="任务ID,脚本内容\n1,甲\n1,乙\n".encode("utf-8"),
            )
            self.assertEqual(duplicate.status_code, 422)
            self.assertIn("重复", duplicate.json()["detail"])

            extra_column = client.post(
                "/api/new/script-imports/preview?filename=bad.csv",
                content="任务ID,脚本内容,备注\n1,甲,多余\n".encode("utf-8"),
            )
            self.assertEqual(extra_column.status_code, 422)
            self.assertIn("两列", extra_column.json()["detail"])
            self.assertEqual(client.get("/api/new/projects").json()["total"], 0)

    def test_original_script_file_is_retained_for_result_batch_archives(self) -> None:
        login_patch, verify_patch = self._client_context()
        with login_patch, verify_patch, TestClient(create_app(self.settings)) as client:
            self._login(client)
            content = "任务ID,脚本内容\n1,第一条口播\n2,第二条口播\n".encode("utf-8-sig")
            preview = client.post(
                "/api/new/script-imports/preview?filename=原始脚本.csv", content=content
            ).json()
            project = client.post(
                "/api/new/projects",
                json={"name": "脚本归档", "items": preview["rows"]},
            ).json()

            saved = client.put(
                f"/api/new/projects/{project['project_id']}/script-source?filename=原始脚本.csv",
                content=content,
            )

            self.assertEqual(saved.status_code, 200, saved.text)
            source = saved.json()["script_source"]
            self.assertEqual(source["filename"], "原始脚本.csv")
            self.assertEqual(Path(source["managed_path"]).read_bytes(), content)
            self.assertEqual(len(saved.json()["script_source_history"]), 1)

    def test_image_pool_count_loop_manual_replace_and_refresh_are_persistent(self) -> None:
        login_patch, verify_patch = self._client_context()
        with login_patch, verify_patch, TestClient(create_app(self.settings)) as client:
            self._login(client)
            project = client.post(
                "/api/new/projects",
                json={
                    "name": "图片映射测试",
                    "items": [
                        {"row_key": str(index), "script_text": f"脚本 {index}"}
                        for index in range(1, 8)
                    ],
                },
            ).json()
            project_id = project["project_id"]

            images = []
            for name in ("a.png", "b.png", "c.png"):
                response = client.post(
                    f"/api/new/projects/{project_id}/images?filename={name}",
                    content=PNG_1X1,
                )
                self.assertEqual(response.status_code, 201, response.text)
                images.append(response.json())

            counted = client.put(
                f"/api/new/projects/{project_id}/image-mapping",
                json={"strategy": "count", "reuse_count": 2},
            )
            self.assertEqual(counted.status_code, 200, counted.text)
            self.assertEqual(
                [
                    item["inputs"]["image"]["external_ref"]["input_image_id"]
                    for item in counted.json()["items"]
                ],
                [
                    images[0]["image_id"],
                    images[0]["image_id"],
                    images[1]["image_id"],
                    images[1]["image_id"],
                    images[2]["image_id"],
                    images[2]["image_id"],
                    images[0]["image_id"],
                ],
            )

            looped = client.put(
                f"/api/new/projects/{project_id}/image-mapping",
                json={"strategy": "loop", "reuse_count": 9},
            )
            self.assertEqual(looped.status_code, 200, looped.text)
            self.assertEqual(
                [
                    item["inputs"]["image"]["external_ref"]["input_image_id"]
                    for item in looped.json()["items"]
                ],
                [images[index % 3]["image_id"] for index in range(7)],
            )

            first_item = looped.json()["items"][0]
            replaced = client.put(
                f"/api/new/projects/{project_id}/items/{first_item['item_id']}/image",
                json={"image_id": images[1]["image_id"]},
            )
            self.assertEqual(replaced.status_code, 200, replaced.text)
            first = replaced.json()["items"][0]
            self.assertEqual(first["inputs"]["image"]["version"], 2)
            self.assertEqual(len(first["asset_history"]["input_image"]), 2)

            refreshed = client.get(f"/api/new/projects/{project_id}").json()
            self.assertEqual(
                refreshed["items"][0]["inputs"]["image"]["external_ref"][
                    "input_image_id"
                ],
                images[1]["image_id"],
            )
            in_use = client.delete(
                f"/api/new/projects/{project_id}/images/{images[1]['image_id']}"
            )
            self.assertEqual(in_use.status_code, 409)

            remapped = client.put(
                f"/api/new/projects/{project_id}/image-mapping",
                json={"strategy": "count", "reuse_count": 100},
            )
            self.assertEqual(remapped.status_code, 200, remapped.text)
            self.assertTrue(
                all(
                    item["inputs"]["image"]["external_ref"]["input_image_id"]
                    == images[0]["image_id"]
                    for item in remapped.json()["items"]
                )
            )
            historical_path = Path(images[1]["managed_path"])
            historical_only = client.delete(
                f"/api/new/projects/{project_id}/images/{images[1]['image_id']}"
            )
            self.assertEqual(historical_only.status_code, 200, historical_only.text)
            self.assertFalse(historical_path.exists())
            after_historical_delete = client.get(
                f"/api/new/projects/{project_id}"
            ).json()
            self.assertNotIn(
                images[1]["image_id"],
                [image["image_id"] for image in after_historical_delete["input_images"]],
            )
            for item in after_historical_delete["items"]:
                self.assertFalse(
                    any(
                        asset["external_ref"].get("input_image_id")
                        == images[1]["image_id"]
                        for asset in item["asset_history"].get("input_image", [])
                    )
                )

            unused = client.post(
                f"/api/new/projects/{project_id}/images?filename=unused.png",
                content=PNG_1X1,
            ).json()
            unused_path = Path(unused["managed_path"])
            self.assertTrue(unused_path.is_file())
            removed = client.delete(
                f"/api/new/projects/{project_id}/images/{unused['image_id']}"
            )
            self.assertEqual(removed.status_code, 200, removed.text)
            self.assertFalse(unused_path.exists())

    def test_script_reimport_is_atomic_and_project_can_be_cleared(self) -> None:
        login_patch, verify_patch = self._client_context()
        with login_patch, verify_patch, TestClient(create_app(self.settings)) as client:
            self._login(client)
            project = client.post(
                "/api/new/projects",
                json={
                    "name": "重新导入",
                    "items": [
                        {"row_key": "1", "script_text": "原脚本一"},
                        {"row_key": "2", "script_text": "原脚本二"},
                    ],
                },
            ).json()
            project_id = project["project_id"]
            first_id = project["items"][0]["item_id"]

            replaced = client.put(
                f"/api/new/projects/{project_id}/inputs",
                json={
                    "items": [
                        {
                            "item_id": first_id,
                            "row_key": "10",
                            "script_text": "保留并修改",
                        },
                        {"row_key": "20", "script_text": "新脚本"},
                    ]
                },
            )
            self.assertEqual(replaced.status_code, 200, replaced.text)
            self.assertEqual(
                [item["row_key"] for item in replaced.json()["items"]], ["10", "20"]
            )
            self.assertEqual(replaced.json()["items"][0]["item_id"], first_id)

            invalid = client.put(
                f"/api/new/projects/{project_id}/inputs",
                json={
                    "items": [
                        {"row_key": "x", "script_text": "甲"},
                        {"row_key": "x", "script_text": "乙"},
                    ]
                },
            )
            self.assertEqual(invalid.status_code, 422)
            unchanged = client.get(f"/api/new/projects/{project_id}").json()
            self.assertEqual(
                [item["row_key"] for item in unchanged["items"]], ["10", "20"]
            )

            deleted = client.delete(f"/api/new/projects/{project_id}")
            self.assertEqual(deleted.status_code, 200, deleted.text)
            self.assertEqual(client.get("/api/new/projects").json()["total"], 0)


if __name__ == "__main__":
    unittest.main()
