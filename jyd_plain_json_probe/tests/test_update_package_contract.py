from pathlib import Path
import unittest


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class UpdatePackageContractTest(unittest.TestCase):
    def test_update_build_copies_only_music_profile_from_audio_library(self) -> None:
        script = (
            PROJECT_ROOT / "scripts" / "build" / "build_processor.ps1"
        ).read_text(encoding="utf-8")

        self.assertIn(
            'data\\libraries\\audio_library\\manifest\\music_profiles.v1.json',
            script,
        )
        self.assertIn(
            '$MusicProfileDestination = Join-Path $LibrariesDir "audio_library\\manifest"',
            script,
        )
        update_block = script.split("if ($UpdateOnly) {", 1)[1]
        self.assertNotIn(
            'Copy-Item -LiteralPath (Join-Path $ProjectRoot "data\\libraries\\audio_library")',
            update_block,
        )

    def test_update_instructions_name_the_music_profile_contract(self) -> None:
        instructions = (PROJECT_ROOT / "docs" / "PROCESSOR_UPDATE.md").read_text(
            encoding="utf-8"
        )
        self.assertIn("music_profiles.v1.json", instructions)
        self.assertIn("不会携带\n音乐文件", instructions)


if __name__ == "__main__":
    unittest.main()
