from __future__ import annotations

import hashlib
import json
from pathlib import Path
import shutil
import sys
import unittest
import uuid
import zipfile


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from jyd_probe.draft_transfer import (  # noqa: E402
    build_transfer_package,
    import_transfer_package,
)


class DraftTransferTest(unittest.TestCase):
    def setUp(self) -> None:
        root = PROJECT_ROOT / "runtime" / "test_tmp"
        root.mkdir(exist_ok=True)
        self.temp = root / f"draft_transfer_{uuid.uuid4().hex}"
        self.temp.mkdir()

    def tearDown(self) -> None:
        shutil.rmtree(self.temp, ignore_errors=True)

    def test_builds_imports_and_rewrites_uploaded_asset_paths(self) -> None:
        draft_dir = self.temp / "plain_draft"
        draft_dir.mkdir()
        video = self.temp / "source video.mp4"
        video.write_bytes(b"video-content")
        skipped_audio = self.temp / "old.mp3"
        skipped_audio.write_bytes(b"old-audio")
        draft = {
            "duration": 5_000_000,
            "tracks": [{"type": "video", "segments": []}],
            "materials": {
                "videos": [{"id": "video-1", "path": str(video)}],
                "audios": [{"id": "audio-1", "path": str(skipped_audio)}],
                "texts": [
                    {
                        "id": "text-1",
                        "content": json.dumps(
                            {"nested_path": str(video)}, ensure_ascii=False
                        ),
                    }
                ],
            },
        }
        (draft_dir / "draft_content.json").write_text(
            json.dumps(draft, ensure_ascii=False), encoding="utf-8"
        )
        (draft_dir / "draft_meta_info.json").write_text(
            json.dumps(
                {"draft_materials": [{"value": [{"file_Path": str(video)}]}]},
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        plan = {
            "plan_id": "plan1",
            "report_id": "report1",
            "draft": {
                "name": "剪辑母版",
                "analyzed_draft_dir": str(draft_dir),
            },
            "policies": {"audio": "replace", "video_effects": "replace"},
            "summary": {"ready_for_upload": True, "upload_count": 1},
            "dependencies": [
                {
                    "kind": "video",
                    "path": str(video),
                    "original_path": str(video).replace("\\", "/"),
                    "decision": "upload",
                    "size_bytes": video.stat().st_size,
                    "references": [],
                },
                {
                    "kind": "audio",
                    "path": str(skipped_audio),
                    "decision": "skip_replaced",
                    "size_bytes": skipped_audio.stat().st_size,
                },
            ],
        }

        package_path = self.temp / "transfer.zip"
        package = build_transfer_package(plan, package_path)
        self.assertEqual(package["asset_count"], 1)
        with zipfile.ZipFile(package_path) as archive:
            names = archive.namelist()
        self.assertTrue(any(name.endswith("source video.mp4") for name in names))
        self.assertFalse(any(name.endswith("old.mp3") for name in names))

        result = import_transfer_package(
            package_path,
            imports_root=self.temp / "imports",
            template_library_root=self.temp / "templates",
            expires_at="2026-07-17T12:00:00",
        )
        template = result["template"]
        imported = json.loads(
            (Path(template["draft_dir"]) / "draft_content.json").read_text(encoding="utf-8")
        )
        rewritten_path = imported["materials"]["videos"][0]["path"]
        self.assertNotEqual(rewritten_path, str(video))
        self.assertTrue(Path(rewritten_path).is_file())
        nested = json.loads(imported["materials"]["texts"][0]["content"])
        self.assertEqual(nested["nested_path"], rewritten_path)
        imported_meta = json.loads(
            (Path(template["draft_dir"]) / "draft_meta_info.json").read_text(encoding="utf-8")
        )
        self.assertEqual(imported_meta["draft_materials"][0]["value"][0]["file_Path"], rewritten_path)
        self.assertEqual(imported["materials"]["audios"][0]["path"], str(skipped_audio))
        self.assertEqual(result["rewritten_path_count"], 3)
        self.assertEqual(template["import_info"]["policies"]["audio"], "replace")
        self.assertEqual(template["expires_at"], "2026-07-17T12:00:00")

    def test_rejects_archive_path_traversal(self) -> None:
        package_path = self.temp / "unsafe.zip"
        with zipfile.ZipFile(package_path, "w") as archive:
            archive.writestr("../outside.txt", "unsafe")
        with self.assertRaisesRegex(ValueError, "不安全路径"):
            import_transfer_package(
                package_path,
                imports_root=self.temp / "imports",
                template_library_root=self.temp / "templates",
            )
        self.assertFalse((self.temp / "outside.txt").exists())

    def test_relinks_missing_font_path_to_verified_server_library_file(self) -> None:
        draft_dir = self.temp / "font_draft"
        draft_dir.mkdir()
        old_font_path = r"C:\Users\editor\AppData\Local\JianyingPro\Cache\OldFont.otf"
        draft = {
            "duration": 1_000_000,
            "tracks": [],
            "materials": {
                "texts": [
                    {
                        "id": "text-1",
                        "font_path": old_font_path,
                        "content": json.dumps(
                            {"styles": [{"font": {"id": "font-1", "path": old_font_path}}]},
                            ensure_ascii=False,
                        ),
                    }
                ]
            },
        }
        (draft_dir / "draft_content.json").write_text(
            json.dumps(draft, ensure_ascii=False), encoding="utf-8"
        )
        font_root = self.temp / "libraries" / "font_library"
        font_file = font_root / "files" / "OldFont_font-1.otf"
        font_file.parent.mkdir(parents=True)
        font_file.write_bytes(b"same-font-file")
        checksum = hashlib.sha256(font_file.read_bytes()).hexdigest()
        plan = {
            "plan_id": "font-plan",
            "report_id": "font-report",
            "draft": {"name": "字幕母版", "analyzed_draft_dir": str(draft_dir)},
            "policies": {"text_style": "keep"},
            "summary": {"ready_for_upload": True, "upload_count": 0},
            "dependencies": [
                {
                    "kind": "font",
                    "path": old_font_path,
                    "original_path": old_font_path.replace("\\", "/"),
                    "decision": "reuse_library",
                    "central_match": {
                        "identity": "resource_id:font-1",
                        "library_file": "files/OldFont_font-1.otf",
                        "checksum_sha256": checksum,
                    },
                    "references": [],
                }
            ],
        }

        package_path = self.temp / "font-transfer.zip"
        package = build_transfer_package(plan, package_path)
        self.assertEqual(package["manifest"]["library_references"][0]["identity"], "resource_id:font-1")
        result = import_transfer_package(
            package_path,
            imports_root=self.temp / "imports",
            template_library_root=self.temp / "templates",
            font_library_root=font_root,
        )
        imported = json.loads(
            (Path(result["template"]["draft_dir"]) / "draft_content.json").read_text(encoding="utf-8")
        )
        self.assertEqual(imported["materials"]["texts"][0]["font_path"], str(font_file.resolve()))
        nested = json.loads(imported["materials"]["texts"][0]["content"])
        self.assertEqual(nested["styles"][0]["font"]["path"], str(font_file.resolve()))
        self.assertEqual(result["library_reference_count"], 1)
        self.assertEqual(result["rewritten_path_count"], 2)


if __name__ == "__main__":
    unittest.main()
