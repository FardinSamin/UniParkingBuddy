"""Headless smoke checks for committed video/configuration compatibility.

Opens only the first frame with OpenCV; does not launch a GUI, run YOLO,
or claim that computer-vision classification is accurate.
"""

from pathlib import Path
import unittest

import cv2

from backend.parking_config import load_config


ROOT = Path(__file__).resolve().parents[2]
CAMERAS = (
    ("camera_1", "footage/stockvidsample2.mp4"),
    ("camera_2", "footage/parkinglotfootage1_1.mp4"),
)


class VideoConfigurationSmokeTests(unittest.TestCase):
    def test_configured_video_sources_are_decodable_and_regions_fit_frame(self):
        for camera, relative_video in CAMERAS:
            with self.subTest(camera=camera):
                path = ROOT / relative_video
                self.assertTrue(path.is_file(), f"Missing configured video: {relative_video}")
                video = cv2.VideoCapture(str(path))
                try:
                    self.assertTrue(video.isOpened(), f"Cannot open {relative_video}")
                    success, frame = video.read()
                    self.assertTrue(success, f"Cannot decode first frame: {relative_video}")
                    self.assertIsNotNone(frame)
                    height, width = frame.shape[:2]
                    self.assertGreater(width, 0)
                    self.assertGreater(height, 0)

                    config = load_config(ROOT / "configs" / f"{camera}.json")
                    self.assertGreater(len(config["spaces"]), 0)
                    for space in config["spaces"]:
                        for x, y in space["points"]:
                            self.assertLess(
                                x, width,
                                f"{camera} space {space['id']} x={x} outside width {width}",
                            )
                            self.assertLess(
                                y, height,
                                f"{camera} space {space['id']} y={y} outside height {height}",
                            )
                finally:
                    video.release()

    def test_model_file_is_present_not_placeholder(self):
        # File presence alone is NOT a successful YOLO model/inference test.
        model = ROOT / "yolo26n.pt"
        self.assertTrue(model.is_file(), "The configured YOLO weights are missing")
        self.assertGreater(model.stat().st_size, 0, "YOLO model file is empty")


if __name__ == "__main__":
    unittest.main()
