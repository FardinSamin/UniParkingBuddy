"""Opt-in real-video smoke for the read-only discovery experiment.

No accuracy or correctness of generated parking stalls is asserted.
Only checks that the real model and committed video produce a safe,
locally inspectable report without mutating approved configurations.
"""

import json
import os
from pathlib import Path
import tempfile
import unittest

from backend.accuracy_evaluation import PROJECT_ROOT, file_sha256
from backend.discover_space_hypotheses import analyze_video


@unittest.skipUnless(os.getenv("RUN_REAL_YOLO_SMOKE") == "1",
                     "Real model/video tests run in dedicated CI")
class RealSpaceDiscoverySmoke(unittest.TestCase):
    def test_existing_video_produces_read_only_hypotheses(self):
        originals = {
            camera: file_sha256(PROJECT_ROOT / "configs" / f"{camera}.json")
            for camera in ("camera_1", "camera_2")
        }
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder) / "proposals"
            result = analyze_video(
                PROJECT_ROOT / "footage" / "stockvidsample2.mp4",
                output, requested_frames=3, min_frames=2, min_support=0.5,
            )
            self.assertTrue((output / "preview.png").is_file())
            stored = json.loads((output / "hypotheses.json").read_text(encoding="utf-8"))
            self.assertEqual(stored, result)
            self.assertEqual(result["review_state"], "unverified_proposals_only")
            self.assertEqual(result["sampled_frame_count"], 3)
            self.assertEqual(result["proposal_count"], len(result["proposals"]))
            self.assertTrue(all(
                proposal["review_state"] == "unverified" and
                "points" not in proposal
                for proposal in result["proposals"]
            ))
        self.assertEqual(originals, {
            camera: file_sha256(PROJECT_ROOT / "configs" / f"{camera}.json")
            for camera in originals
        })


if __name__ == "__main__":
    unittest.main()
