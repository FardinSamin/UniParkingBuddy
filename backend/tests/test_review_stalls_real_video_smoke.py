"""Read-only end-to-end geometry quality-gate smoke with actual videos."""

import json
import os
from pathlib import Path
import tempfile
import unittest

from backend.accuracy_evaluation import PROJECT_ROOT, file_sha256
from backend.discover_stall_geometry import analyze_video_markings
from backend.review_stall_candidates import review_video_geometry


@unittest.skipUnless(
    os.getenv("RUN_REAL_YOLO_SMOKE") == "1",
    "Real video smoke checks run in dedicated CI",
)
class Phase3RealVideoTests(unittest.TestCase):
    def test_review_two_video_views_without_touching_config(self):
        configs = [
            PROJECT_ROOT / "configs" / "camera_1.json",
            PROJECT_ROOT / "configs" / "camera_2.json",
        ]
        before = [file_sha256(path) for path in configs]
        for filename in ("stockvidsample2.mp4", "parkinglotfootage1_1.mp4"):
            with self.subTest(filename=filename), tempfile.TemporaryDirectory() as tmp:
                source = PROJECT_ROOT / "footage" / filename
                geometry_output = Path(tmp) / "geometry"
                analyze_video_markings(source, geometry_output, requested_frames=3)
                review_output = Path(tmp) / "review"
                report = review_video_geometry(
                    source, geometry_output / "stall_candidates.json", review_output
                )
                self.assertTrue((review_output / "review_preview.png").is_file())
                self.assertEqual(
                    json.loads((review_output / "review.json").read_text(encoding="utf-8")),
                    report
                )
                self.assertEqual(report["review_state"], "unverified_proposals_only")
                self.assertEqual(report["source_video_sha256"], file_sha256(source))
                self.assertEqual(report["candidate_count"], len(report["candidates"]))
                self.assertTrue(all(
                    candidate["review_state"] == "unverified"
                    for candidate in report["candidates"]
                ))
        self.assertEqual(before, [file_sha256(path) for path in configs])


if __name__ == "__main__":
    unittest.main()
