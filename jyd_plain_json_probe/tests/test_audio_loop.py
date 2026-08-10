from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
import sys
import unittest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from jyd_probe.cli import add_audio_track_segment  # noqa: E402
from jyd_probe.render_job import _build_audio_replacements  # noqa: E402


class FakeTimerange:
    def __init__(self, start: int, duration: int) -> None:
        self.start = start
        self.duration = duration


class FakeDraft:
    class TrackType:
        audio = "audio"

    class TrackSpec:
        def __init__(self, track_type, track_name, mute=False) -> None:
            self.track_type = track_type
            self.track_name = track_name
            self.mute = mute

    Timerange = FakeTimerange

    class AudioMaterial:
        def __init__(self, path: str) -> None:
            self.path = path
            self.duration = 10_000_000

    class AudioSegment:
        def __init__(self, material, target_timerange, *, source_timerange, volume) -> None:
            self.material = material
            self.target_timerange = target_timerange
            self.source_timerange = source_timerange
            self.volume = volume


class FakeScript:
    def __init__(self) -> None:
        self.tracks = []
        self.segments = []

    def append_track(self, track_spec) -> None:
        self.tracks.append(track_spec)

    def add_segment(self, segment, track_name) -> None:
        self.segments.append((segment, track_name))


class AudioLoopTest(unittest.TestCase):
    def test_short_bgm_repeats_and_trims_last_segment(self) -> None:
        script = FakeScript()
        changed = add_audio_track_segment(
            FakeDraft,
            script,
            SimpleNamespace(
                add_audio_path=str(Path(__file__)),
                audio_source_start_us=-1,
                audio_source_duration_us=0,
                audio_target_start_us=2_000_000,
                audio_target_duration_us=25_000_000,
                audio_volume=0.3,
                audio_loop_to_target=True,
            ),
        )

        self.assertTrue(changed)
        self.assertEqual(
            [
                (segment.target_timerange.start, segment.target_timerange.duration)
                for segment, _ in script.segments
            ],
            [
                (2_000_000, 10_000_000),
                (12_000_000, 10_000_000),
                (22_000_000, 5_000_000),
            ],
        )
        self.assertEqual(
            [segment.source_timerange.duration for segment, _ in script.segments],
            [10_000_000, 10_000_000, 5_000_000],
        )
        self.assertEqual(len({track_name for _, track_name in script.segments}), 1)

    def test_non_looping_audio_keeps_existing_truncation_behavior(self) -> None:
        script = FakeScript()
        add_audio_track_segment(
            FakeDraft,
            script,
            SimpleNamespace(
                add_audio_path=str(Path(__file__)),
                audio_source_start_us=-1,
                audio_source_duration_us=0,
                audio_target_start_us=0,
                audio_target_duration_us=25_000_000,
                audio_volume=1.0,
                audio_loop_to_target=False,
            ),
        )
        self.assertEqual(len(script.segments), 1)
        self.assertEqual(script.segments[0][0].target_timerange.duration, 10_000_000)

    def test_render_job_defaults_only_fitted_bgm_to_loop(self) -> None:
        media_path = str(Path(__file__).resolve())
        _, _, bgm_additions = _build_audio_replacements(
            {
                "audios": [
                    {
                        "type": "bgm",
                        "media_path": media_path,
                        "fit_to_video": True,
                    }
                ]
            },
            timeline_duration_us=25_000_000,
        )
        _, _, plain_additions = _build_audio_replacements(
            {
                "audios": [
                    {
                        "type": "add",
                        "media_path": media_path,
                        "fit_to_video": True,
                    }
                ]
            },
            timeline_duration_us=25_000_000,
        )

        self.assertTrue(bgm_additions[0].loop_to_target)
        self.assertEqual(bgm_additions[0].target_duration_us, 25_000_000)
        self.assertFalse(plain_additions[0].loop_to_target)


if __name__ == "__main__":
    unittest.main()
