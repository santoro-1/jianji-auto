from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
import shutil
import sys
import unittest
from unittest.mock import patch
import uuid


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from jyd_probe.cli import copy_template_draft  # noqa: E402
from jyd_probe.render_job import _export_mp4  # noqa: E402


class DraftCopyMetadataTest(unittest.TestCase):
    def setUp(self) -> None:
        root = PROJECT_ROOT / "runtime" / "test_tmp"
        root.mkdir(parents=True, exist_ok=True)
        self.root = root / f"draft_copy_metadata_{uuid.uuid4().hex}"
        self.root.mkdir()

    def tearDown(self) -> None:
        shutil.rmtree(self.root, ignore_errors=True)

    def test_copy_rebuilds_plain_jianying_catalogue_metadata(self) -> None:
        template = self.root / "templates" / "old-name"
        template.mkdir(parents=True)
        (template / "draft_content.json").write_text("{}", encoding="utf-8")
        (template / "draft_meta_info.json").write_text(
            json.dumps(
                {
                    "draft_name": "old-name",
                    "draft_id": "OLD-DRAFT-ID",
                    "draft_root_path": "D:/old-root",
                    "draft_fold_path": "D:/old-root/old-name",
                    "tm_draft_create": 1,
                    "tm_draft_modified": 2,
                    "tm_draft_removed": 99,
                    "draft_is_invisible": True,
                }
            ),
            encoding="utf-8",
        )
        (template / "draft_meta.dec.json").write_text(
            json.dumps({"draft_name": "stale-name"}), encoding="utf-8"
        )
        output_root = self.root / "JianyingPro Drafts"
        before_us = int(datetime.now().timestamp() * 1_000_000)

        output = copy_template_draft(template, output_root, "new-output")

        meta = json.loads((output / "draft_meta_info.json").read_text(encoding="utf-8"))
        self.assertEqual(meta["draft_name"], "new-output")
        self.assertNotEqual(meta["draft_id"], "OLD-DRAFT-ID")
        self.assertEqual(meta["draft_root_path"], str(output_root.resolve()).replace("\\", "/"))
        self.assertEqual(meta["draft_fold_path"], str(output.resolve()).replace("\\", "/"))
        self.assertGreaterEqual(meta["tm_draft_create"], before_us)
        self.assertEqual(meta["tm_draft_modified"], meta["tm_draft_create"])
        self.assertEqual(meta["tm_draft_removed"], 0)
        self.assertFalse(meta["draft_is_invisible"])
        self.assertFalse((output / "draft_meta.dec.json").exists())

    def test_copy_leaves_encrypted_metadata_untouched(self) -> None:
        template = self.root / "templates" / "encrypted"
        template.mkdir(parents=True)
        (template / "draft_content.json").write_text("{}", encoding="utf-8")
        encrypted = "not-plain-json-payload"
        (template / "draft_meta_info.json").write_text(encrypted, encoding="utf-8")

        output = copy_template_draft(template, self.root / "outputs", "copied")

        self.assertEqual((output / "draft_meta_info.json").read_text(encoding="utf-8"), encrypted)


class DraftDiscoveryRetryTest(unittest.TestCase):
    def test_export_retries_only_draft_not_found(self) -> None:
        class DraftNotFound(Exception):
            pass

        class Controller:
            attempts = 0

            def export_draft(self, draft_name, output_path, **kwargs):
                Controller.attempts += 1
                if Controller.attempts < 3:
                    raise DraftNotFound(draft_name)

        with (
            patch("jyd_probe.render_job._load_export_api", return_value=(Controller, (), ())),
            patch("jyd_probe.render_job.time.sleep") as sleep,
        ):
            _export_mp4("new-draft", self.root_path("out.mp4"))

        self.assertEqual(Controller.attempts, 3)
        self.assertEqual(sleep.call_count, 2)

    def test_export_does_not_retry_other_failures(self) -> None:
        class Controller:
            attempts = 0

            def export_draft(self, draft_name, output_path, **kwargs):
                Controller.attempts += 1
                raise RuntimeError("automation failed")

        with (
            patch("jyd_probe.render_job._load_export_api", return_value=(Controller, (), ())),
            patch("jyd_probe.render_job.time.sleep") as sleep,
            self.assertRaisesRegex(RuntimeError, "automation failed"),
        ):
            _export_mp4("new-draft", self.root_path("out.mp4"))

        self.assertEqual(Controller.attempts, 1)
        sleep.assert_not_called()

    def test_export_retries_when_draft_click_did_not_enter_editor(self) -> None:
        class AutomationError(Exception):
            pass

        class Controller:
            attempts = 0

            def export_draft(self, draft_name, output_path, **kwargs):
                Controller.attempts += 1
                if Controller.attempts < 3:
                    raise AutomationError("未在编辑窗口中找到导出按钮")

        with (
            patch("jyd_probe.render_job._load_export_api", return_value=(Controller, (), ())),
            patch("jyd_probe.render_job.time.sleep") as sleep,
        ):
            _export_mp4("click-missed-draft", self.root_path("out.mp4"))

        self.assertEqual(Controller.attempts, 3)
        self.assertEqual(sleep.call_count, 2)

    def test_export_reports_editor_entry_failure_after_retries(self) -> None:
        class Controller:
            attempts = 0

            def export_draft(self, draft_name, output_path, **kwargs):
                Controller.attempts += 1
                raise RuntimeError("未在编辑窗口中找到导出按钮")

        with (
            patch("jyd_probe.render_job._load_export_api", return_value=(Controller, (), ())),
            patch("jyd_probe.render_job.time.sleep"),
            self.assertRaisesRegex(RuntimeError, "点击草稿后未进入编辑页"),
        ):
            _export_mp4("never-opened-draft", self.root_path("out.mp4"))

        self.assertEqual(Controller.attempts, 10)

    @staticmethod
    def root_path(name: str) -> Path:
        root = PROJECT_ROOT / "runtime" / "test_tmp" / "draft_discovery_retry"
        root.mkdir(parents=True, exist_ok=True)
        return root / f"{uuid.uuid4().hex}_{name}"


if __name__ == "__main__":
    unittest.main()
