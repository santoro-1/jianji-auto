from __future__ import annotations

from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from jyd_probe.bgm_loudness import (  # noqa: E402
    BGM_FALLBACK_VOLUME,
    automatic_bgm_mix,
    build_backtimed_bgm_plan,
    fallback_bgm_volume,
    recommended_bgm_fade_in_us,
    volume_from_loudness,
)
from jyd_probe.project_postprocess import resolve_project_cover_image  # noqa: E402


class AutomaticBgmLoudnessTest(unittest.TestCase):
    def test_volume_is_relative_to_voice_and_bounded(self) -> None:
        self.assertAlmostEqual(volume_from_loudness(-16.0, -14.0), 0.2239, places=4)
        self.assertEqual(volume_from_loudness(-16.0, -40.0), 1.9953)
        self.assertEqual(volume_from_loudness(-16.0, 0.0), 0.0447)

    @patch("jyd_probe.bgm_loudness.measure_bgm_program_loudness")
    @patch("jyd_probe.bgm_loudness.measure_audio_loudness")
    def test_one_mix_snapshot_is_reused_by_preview_and_export(
        self, measure_audio, measure_program
    ) -> None:
        measure_audio.side_effect = [
            {"integrated_lufs": -16.0, "true_peak_dbtp": -2.0},
            {"integrated_lufs": -14.0, "true_peak_dbtp": -0.5},
        ]
        measure_program.return_value = {
            "integrated_lufs": -14.0,
            "true_peak_dbtp": -8.0,
            "short_term_p95_lufs": -16.0,
            "silence_ratio": 0.0,
            "bgm_duration_us": 90_000_000,
            "video_duration_us": 30_000_000,
            "crossfade_us": 200_000,
            "fade_in_us": 1_500_000,
            "segments": [],
        }
        mix = automatic_bgm_mix(
            "voice.mp3", "bgm.mp3", video_duration_us=30_000_000
        )
        self.assertEqual(mix["algorithm"], "speech-relative-program-lufs.v2")
        self.assertEqual(mix["volume"], 0.2239)
        self.assertEqual(mix["bgm_program_lufs"], -14.0)
        self.assertFalse(mix["fallback"])

    @patch("jyd_probe.bgm_loudness.measure_audio_loudness", side_effect=ValueError("bad audio"))
    def test_analysis_failure_uses_conservative_program_default(self, _measure) -> None:
        mix = automatic_bgm_mix(
            "voice.mp3", "bgm.mp3", video_duration_us=30_000_000
        )
        self.assertEqual(mix["volume"], BGM_FALLBACK_VOLUME)
        self.assertEqual(mix["applied_gain_db"], -10.0)
        self.assertTrue(mix["fallback"])

    @patch("jyd_probe.bgm_loudness.measure_bgm_program_loudness")
    @patch("jyd_probe.bgm_loudness.measure_audio_loudness")
    def test_strong_vocals_get_four_more_db_of_narration_headroom(
        self, measure_audio, measure_program
    ) -> None:
        measure_audio.side_effect = [
            {"integrated_lufs": -16.0, "true_peak_dbtp": -2.0},
            {"integrated_lufs": -14.0, "true_peak_dbtp": -0.5},
        ]
        measure_program.return_value = {
            "integrated_lufs": -14.0,
            "true_peak_dbtp": -8.0,
            "short_term_p95_lufs": -16.0,
            "silence_ratio": 0.0,
            "bgm_duration_us": 90_000_000,
            "video_duration_us": 30_000_000,
            "crossfade_us": 200_000,
            "fade_in_us": 1_500_000,
            "segments": [],
        }
        mix = automatic_bgm_mix(
            "voice.mp3",
            "bgm.mp3",
            strong_vocals=True,
            video_duration_us=30_000_000,
        )
        self.assertEqual(mix["target_gap_db"], 15.0)
        self.assertEqual(mix["volume"], 0.1413)
        self.assertTrue(mix["strong_vocals"])
        self.assertLess(mix["volume"], 0.2239)

    def test_strong_vocal_fallback_is_lower_than_normal_fallback(self) -> None:
        self.assertEqual(fallback_bgm_volume(strong_vocals=True), 0.1995)
        self.assertLess(fallback_bgm_volume(strong_vocals=True), BGM_FALLBACK_VOLUME)

    @patch("jyd_probe.bgm_loudness.measure_bgm_program_loudness")
    @patch("jyd_probe.bgm_loudness.measure_audio_loudness")
    def test_dynamic_peak_limit_can_raise_quiet_used_tail_above_one(
        self, measure_audio, measure_program
    ) -> None:
        measure_audio.side_effect = [
            {"integrated_lufs": -10.66, "true_peak_dbtp": -1.0},
            {"integrated_lufs": -15.67, "true_peak_dbtp": -0.2},
        ]
        measure_program.return_value = {
            "integrated_lufs": -25.31,
            "true_peak_dbtp": -9.5,
            "short_term_p95_lufs": -24.0,
            "silence_ratio": 0.0,
            "bgm_duration_us": 90_000_000,
            "video_duration_us": 29_667_000,
            "crossfade_us": 200_000,
            "fade_in_us": 1_500_000,
            "segments": [],
        }
        mix = automatic_bgm_mix(
            "voice.mp3", "bgm.mp3", video_duration_us=29_667_000
        )
        self.assertEqual(mix["applied_gain_db"], 3.5)
        self.assertEqual(mix["volume"], 1.4962)
        self.assertEqual(mix["post_gain_true_peak_dbtp"], -6.0)
        self.assertIn("true_peak", mix["constraints_hit"])

    def test_backtimed_plan_measures_the_used_tail_and_natural_end(self) -> None:
        long_music = build_backtimed_bgm_plan(
            30_000_000,
            90_000_000,
            crossfade_us=200_000,
            fade_in_us=1_500_000,
        )
        self.assertEqual(len(long_music), 1)
        self.assertEqual(long_music[0]["source_start_us"], 60_000_000)
        self.assertEqual(long_music[0]["duration_us"], 30_000_000)
        self.assertEqual(long_music[0]["fade_in_us"], 1_500_000)

        looped = build_backtimed_bgm_plan(
            100_000_000,
            30_000_000,
            crossfade_us=200_000,
            fade_in_us=1_500_000,
        )
        self.assertEqual(looped[0]["target_start_us"], 0)
        self.assertEqual(looped[-1]["source_start_us"], 0)
        self.assertEqual(
            looped[-1]["target_start_us"] + looped[-1]["duration_us"],
            100_000_000,
        )
        self.assertEqual(looped[-1]["fade_out_us"], 0)

    def test_fade_in_is_ten_percent_with_a_one_point_five_second_cap(self) -> None:
        self.assertEqual(recommended_bgm_fade_in_us(4_000_000), 400_000)
        self.assertEqual(recommended_bgm_fade_in_us(60_000_000), 1_500_000)


class FrozenCoverImageTest(unittest.TestCase):
    def test_existing_video_uses_matching_historical_image(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            current_path = root / "current.png"
            frozen_path = root / "frozen.png"
            current_path.write_bytes(b"current")
            frozen_path.write_bytes(b"frozen")
            item = {
                "row_key": "3",
                "inputs": {
                    "image": {
                        "asset_id": "current",
                        "managed_path": str(current_path),
                        "metadata": {"sha256": "current-sha"},
                    }
                },
                "outputs": {
                    "base_video": {
                        "metadata": {
                            "input_image_asset_id": "frozen",
                            "input_image_sha256": "frozen-sha",
                        }
                    }
                },
                "asset_history": {
                    "input_image": [
                        {
                            "asset_id": "frozen",
                            "managed_path": str(frozen_path),
                            "metadata": {"sha256": "frozen-sha"},
                        }
                    ]
                },
            }

            resolved = resolve_project_cover_image(item)

            self.assertEqual(resolved["asset_id"], "frozen")

    def test_missing_frozen_image_never_silently_uses_current_image(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            current_path = Path(temporary) / "current.png"
            current_path.write_bytes(b"current")
            item = {
                "row_key": "9",
                "inputs": {
                    "image": {
                        "asset_id": "current",
                        "managed_path": str(current_path),
                        "metadata": {"sha256": "current-sha"},
                    }
                },
                "outputs": {
                    "base_video": {
                        "metadata": {"input_image_sha256": "missing-sha"}
                    }
                },
                "asset_history": {"input_image": []},
            }

            with self.assertRaisesRegex(ValueError, "已停止生成可能配错的封面"):
                resolve_project_cover_image(item)


if __name__ == "__main__":
    unittest.main()
