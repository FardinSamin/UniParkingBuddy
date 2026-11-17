"""Real-video smoke of the BLIND annotation preview only.

Does not label stalls, fabricate ground truth, or claim geometry accuracy.
"""

import os
import unittest

from backend.accuracy_evaluation import PROJECT_ROOT, file_sha256
from backend.stall_discovery_benchmark import (
    BlindLayoutAnnotation, video_frame,
)


@unittest.skipUnless(os.getenv("RUN_REAL_YOLO_SMOKE") == "1",
                     "Run with committed real-video CI jobs only")
class BlindGeometryBenchmarkRealVideoSmoke(unittest.TestCase):
    def test_readonly_clean_original_frame_preview_for_each_source(self):
        originals = [
            PROJECT_ROOT / "configs" / "camera_1.json",
            PROJECT_ROOT / "configs" / "camera_2.json",
        ]
        before = [file_sha256(path) for path in originals]
        for file in ("stockvidsample2.mp4", "parkinglotfootage1_1.mp4"):
            with self.subTest(file=file):
                video = PROJECT_ROOT / "footage" / file
                frame = video_frame(video, 0)
                session = BlindLayoutAnnotation(video, frame, display_width=640)
                preview = session.draw()
                self.assertEqual(preview.shape[1], 640)
                self.assertGreater(preview.shape[0], 85)
                self.assertEqual(session.spaces, [])
                with self.assertRaises(ValueError):
                    session.truth()  # No human labels; do not invent any.
        self.assertEqual([file_sha256(path) for path in originals], before)


if __name__ == "__main__":
    unittest.main()
