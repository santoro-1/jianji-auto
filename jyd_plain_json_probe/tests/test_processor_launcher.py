from __future__ import annotations

import json
from pathlib import Path
import shutil
import sys
import unittest
import uuid


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from apps.processor.processor_windows import (  # noqa: E402
    _load_processor_config,
    _resolved_network_config,
    _write_shared_connection_files,
)


class ProcessorLauncherTest(unittest.TestCase):
    def test_shared_launcher_keeps_loopback_file_management_enabled(self) -> None:
        launcher = (PROJECT_ROOT / "apps" / "processor" / "processor_windows.py").read_text(
            encoding="utf-8"
        )
        source_launcher = (PROJECT_ROOT / "start_processor.ps1").read_text(encoding="utf-8")
        self.assertIn('os.environ["JYD_ALLOW_LOCAL_FILE_ACCESS"] = "true"', launcher)
        self.assertIn('$env:JYD_ALLOW_LOCAL_FILE_ACCESS = "true"', source_launcher)
        self.assertIn("_start_embedded_collector()", launcher)
        processor_spec = (PROJECT_ROOT / "apps" / "processor" / "processor_windows.spec").read_text(
            encoding="utf-8"
        )
        self.assertIn('apps" / "collector" / "frontend', processor_spec)
        self.assertIn('"tkinter.filedialog"', processor_spec)

    def test_reads_shared_config_written_with_utf8_bom(self) -> None:
        root = PROJECT_ROOT / "runtime" / "test_tmp" / f"processor_config_{uuid.uuid4().hex}"
        root.mkdir(parents=True)
        try:
            payload = {"deployment_mode": "shared", "host": "0.0.0.0"}
            (root / "processor_config.json").write_text(
                json.dumps(payload), encoding="utf-8-sig"
            )
            self.assertEqual(_load_processor_config(root), payload)
        finally:
            shutil.rmtree(root, ignore_errors=True)

    def test_migrates_old_public_machine_auth_config_to_cloud(self) -> None:
        auth_url, shared_url, authority = _resolved_network_config(
            {
                "deployment_mode": "shared",
                "auth_server_url": "http://192.168.11.28:8000",
                "auth_authority": "true",
            }
        )
        self.assertEqual(auth_url, "https://auth.lanyingjk01.com")
        self.assertEqual(shared_url, "")
        self.assertEqual(authority, "false")

    def test_removes_legacy_shared_processor_url(self) -> None:
        auth_url, shared_url, authority = _resolved_network_config(
            {
                "shared_processor_url": "http://192.168.11.28:8000",
                "auth_authority": "false",
            }
        )
        self.assertEqual(auth_url, "https://auth.lanyingjk01.com")
        self.assertEqual(shared_url, "")
        self.assertEqual(authority, "false")

    def test_shared_launcher_writes_clickable_connection_files(self) -> None:
        root = PROJECT_ROOT / "runtime" / "test_tmp" / f"shared_connection_{uuid.uuid4().hex}"
        root.mkdir(parents=True)
        try:
            _write_shared_connection_files(
                root,
                ["http://192.168.1.20:8000/app"],
                "agent-secret",
            )
            shortcut = (root / "打开公用工作台.url").read_text(encoding="utf-8-sig")
            instructions = (root / "公用工作台连接说明.txt").read_text(encoding="utf-8-sig")
            self.assertIn("URL=http://192.168.1.20:8000/app", shortcut)
            self.assertIn("agent-secret", instructions)
            self.assertIn("JianyingRenderAgent", instructions)
        finally:
            shutil.rmtree(root, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
