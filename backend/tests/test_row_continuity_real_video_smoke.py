"""Read-only smoke comparison of joined line fragments on two actual videos."""

import json
import os
from pathlib import Path
import tempfile
import unittest

from backend.accuracy_evaluation import PROJECT_ROOT, file_sha256
from backend.discover_stall_geometry import analyze_video_markings
from backend.row_continuity_experiment import analyze_row_continuity


@unittest.skipUnless(
    os.getenv("RUN_REAL_YOLO_SMOKE") == "1",
    "Actual video test runs only in dedicated CI",
)
class ActualRowContinuitySmoke(unittest.TestCase):
    def test_two_views_produce_ungated_and_ground_variants_without_mutating_config(self):
        configs = [PROJECT_ROOT / "configs" / f"camera_{i}.json" for i in (1, 2)]
        hashes = [file_sha256(path) for path in configs]
        for name in ("stockvidsample2.mp4", "parkinglotfootage1_1.mp4"):
            with self.subTest(video=name), tempfile.TemporaryDirectory() as folder:
                video = PROJECT_ROOT / "footage" / name
                phase2 = Path(folder) / "phase2"
                analyze_video_markings(video, phase2, requested_frames=3)
                output = Path(folder) / "rows"
                report = analyze_row_continuity(
                    video, phase2 / "stall_candidates.json", output
                )
                self.assertEqual(report["review_state"], "unverified_proposals_only")
                self.assertTrue((output / "row_comparison.json").exists())
                self.assertEqual(
                    report,
                    json.loads((output / "row_comparison.json").read_text(encoding="utf-8"))
                )
                for variant in ("raw", "ground"):
                    self.assertTrue((output / f"joined_{variant}.png").is_file())
                    self.assertTrue((output / f"row_candidates_{variant}.png").is_file())
                    data = report["variants"][variant]
                    self.assertLessEqual(
                        data["joined_segment_count"], data["raw_segment_count"]
                    )
                    self.assertTrue(
                        all(c["review_state"] == "unverified"
                            for c in data["review"]["candidates"])
                    )
                print(
                    f"{name}: raw candidate total="
                    f"{report['variants']['raw']['review']['candidate_count']}; "
                    f"ground candidate total="
                    f"{report['variants']['ground']['review']['candidate_count']}",
                    flush=True,
                )
        self.assertEqual(hashes, [file_sha256(path) for path in configs])


if __name__ == "__main__":
    unittest.main()
