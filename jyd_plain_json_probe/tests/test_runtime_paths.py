from __future__ import annotations

from pathlib import Path
import sys
import unittest
import json
import os
import time
from unittest.mock import patch


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from jyd_probe.runtime_paths import (  # noqa: E402
    _best_populated_draft_root,
    _jianying_catalogue_roots,
    detect_jianying_draft_root,
    detect_jianying_draft_root_details,
)


class RuntimePathsTests(unittest.TestCase):
    def test_configured_draft_root_has_priority(self) -> None:
        configured = PROJECT_ROOT / "runtime" / "test_tmp" / "Custom JianyingPro Drafts"
        self.assertEqual(detect_jianying_draft_root(configured), configured.resolve())

    def test_fallback_is_used_when_no_known_directory_exists(self) -> None:
        fallback = PROJECT_ROOT / "runtime" / "test_tmp" / "fallback"
        with patch("jyd_probe.runtime_paths._jianying_catalogue_roots", return_value=[]), patch(
            "jyd_probe.runtime_paths.jianying_draft_root_candidates", return_value=[]
        ):
            detected = detect_jianying_draft_root_details("", fallback=fallback)
        self.assertEqual(detected.path, fallback.resolve())
        self.assertEqual(detected.source, "fallback")
        self.assertFalse(detected.confirmed)

    def test_empty_root_from_jianying_catalogue_beats_package_fallback(self) -> None:
        root = PROJECT_ROOT / "runtime" / "test_tmp" / "empty-jianying-root"
        root.mkdir(parents=True, exist_ok=True)
        fallback = PROJECT_ROOT / "runtime" / "test_tmp" / "package-data-drafts"
        with patch(
            "jyd_probe.runtime_paths._jianying_catalogue_roots", return_value=[root]
        ), patch("jyd_probe.runtime_paths.jianying_draft_root_candidates", return_value=[]):
            detected = detect_jianying_draft_root_details("", fallback=fallback)

        self.assertEqual(detected.path, root.resolve())
        self.assertEqual(detected.source, "jianying_catalogue")
        self.assertTrue(detected.confirmed)

    def test_catalogue_accepts_utf8_bom_and_draft_fold_path(self) -> None:
        root = PROJECT_ROOT / "runtime" / "test_tmp" / "catalogue-bom"
        draft_root = root / "custom" / "JianyingPro Drafts"
        catalogue_path = root / "root_meta_info.json"
        root.mkdir(parents=True, exist_ok=True)
        catalogue_path.write_text(
            json.dumps(
                {
                    "all_draft_store": [
                        {
                            "draft_fold_path": str(draft_root / "example-draft"),
                            "tm_draft_modified": 123,
                        }
                    ]
                },
                ensure_ascii=False,
            ),
            encoding="utf-8-sig",
        )
        with patch(
            "jyd_probe.runtime_paths._jianying_catalogue_paths",
            return_value=[catalogue_path],
        ):
            roots = _jianying_catalogue_roots()

        self.assertEqual(roots, [draft_root.resolve()])

    def test_best_populated_root_prefers_recently_used_draft_directory(self) -> None:
        root = PROJECT_ROOT / "runtime" / "test_tmp" / "runtime_paths_activity"
        older = root / "C-drive-drafts"
        newer = root / "D-drive-drafts"
        for directory in (older / "old-draft", newer / "new-draft"):
            directory.mkdir(parents=True, exist_ok=True)
            (directory / "draft_content.json").write_text("{}", encoding="utf-8")
        now = time.time()
        os.utime(older / "old-draft" / "draft_content.json", (now - 3600, now - 3600))
        os.utime(newer / "new-draft" / "draft_content.json", (now, now))

        self.assertEqual(_best_populated_draft_root([older, newer]), newer.resolve())


if __name__ == "__main__":
    unittest.main()
