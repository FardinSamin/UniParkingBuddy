"""Opt-in real-video, read-only parking-marking geometry smoke test.

Checks pipeline execution and nonmutation, not correct stall extraction.
"""
import json
import os
from pathlib import Path
import tempfile
import unittest

from backend.accuracy_evaluation import PROJECT_ROOT, file_sha256
from backend.discover_stall_geometry import analyze_video_markings


@unittest.skipUnless(
    os.getenv("RUN_REAL_YOLO_SMOKE") == "1",
    "Dedicated CI sample-video smoke only",
)
class RealParkingMarkingSmoke(unittest.TestCase):
    def test_both_video_views_generate_review_only_evidence(self):
        original_hashes = {
            camera: file_sha256(PROJECT_ROOT / "configs" / f"{camera}.json")
            for camera in ("camera_1", "camera_2")
        }
        for video in ("stockvidsample2.mp4", "parkinglotfootage1_1.mp4"):
            with self.subTest(video=video), tempfile.TemporaryDirectory() as folder:
                output = Path(folder) / "markings"
                report = analyze_video_markings(
                    PROJECT_ROOT / "footage" / video,
                    output, requested_frames=3,
                )
                self.assertTrue((output / "persistent_markings.png").is_file())
                self.assertTrue((output / "geometry_preview.png").is_file())
                self.assertTrue((output / "ground_line_evidence.png").is_file())
                self.assertEqual(json.loads(
                    (output / "stall_candidates.json").read_text(encoding="utf-8")
                ), report)
                self.assertEqual(report["review_state"], "unverified_proposals_only")
                self.assertEqual(report["geometry_candidate_count"], len(report["candidates"]))
                self.assertLessEqual(
                    report["ground_supported_line_count"],
                    report["detected_paint_like_line_count"]
                )
                self.assertLessEqual(
                    report["geometry_candidate_count"],
                    report["raw_geometry_candidate_count"]
                )
                self.assertTrue(report["ground_filter_enabled"])
                self.assertEqual(len(report["sampled_frame_indices"]), 3)
                self.assertTrue(all(
                    candidate["review_state"] == "unverified" for candidate
                    in report["candidates"]
                ))
        self.assertEqual(original_hashes, {
            camera: file_sha256(PROJECT_ROOT / "configs" / f"{camera}.json")
            for camera in original_hashes
        })


if __name__ == "__main__":
    unittest.main()
