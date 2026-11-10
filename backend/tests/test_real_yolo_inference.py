"""Opt-in, headless YOLO inference test on committed sample video frames.

This verifies model compatibility and the real inference-to-space-data path.
It does NOT measure classification accuracy without independently annotated
ground truth, assess movement/parking duration, or test the OpenCV GUI.
"""

import math
import os
from pathlib import Path
import unittest

import cv2
import numpy as np

from backend.parking_config import load_config
from backend.space_matching import assign_detections_to_spaces, build_space_statuses
from backend.yolo_detection import (
    DETECTION_CONFIDENCE, INFERENCE_IMAGE_SIZE,
    VEHICLE_CLASS_IDS, boxes_from_yolo_result,
)


ROOT = Path(__file__).resolve().parents[2]
CAMERAS = (
    ("camera_1", "footage/stockvidsample2.mp4"),
    ("camera_2", "footage/parkinglotfootage1_1.mp4"),
)
EXPECTED_CLASSES = {2: "car", 3: "motorcycle", 7: "truck"}


@unittest.skipUnless(
    os.getenv("RUN_REAL_YOLO_SMOKE") == "1",
    "Real YOLO inference runs only in the dedicated CI job",
)
class RealYOLOInferenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from ultralytics import YOLO

        weights = ROOT / "yolo26n.pt"
        if not weights.is_file():
            raise AssertionError("Committed YOLO model weights were not found")
        cls.model = YOLO(str(weights))
        names = cls.model.names
        for class_id, expected in EXPECTED_CLASSES.items():
            actual = names[class_id] if isinstance(names, (dict, list)) else None
            if actual != expected:
                raise AssertionError(
                    f"Model class {class_id} is {actual!r}; expected {expected!r}"
                )

    def test_real_inference_and_configured_space_results(self):
        for camera, relative_path in CAMERAS:
            path = ROOT / relative_path
            config = load_config(ROOT / "configs" / f"{camera}.json")
            contours = [
                np.asarray(space["points"], dtype=np.int32).reshape((-1, 1, 2))
                for space in config["spaces"]
            ]
            video = cv2.VideoCapture(str(path))
            try:
                self.assertTrue(video.isOpened(), f"Cannot open {relative_path}")
                frame_count = int(video.get(cv2.CAP_PROP_FRAME_COUNT))
                self.assertGreater(frame_count, 30, f"Video too short: {relative_path}")
                for frame_index in (0, 30):
                    with self.subTest(camera=camera, frame=frame_index):
                        self.assertTrue(
                            video.set(cv2.CAP_PROP_POS_FRAMES, frame_index),
                            f"Cannot seek to frame {frame_index} in {relative_path}",
                        )
                        success, frame = video.read()
                        self.assertTrue(success, f"Cannot decode {relative_path} frame {frame_index}")
                        height, width = frame.shape[:2]

                        result = self.model(
                            frame,
                            classes=list(VEHICLE_CLASS_IDS),
                            conf=DETECTION_CONFIDENCE,
                            imgsz=INFERENCE_IMAGE_SIZE,
                            device="cpu",
                            verbose=False,
                        )[0]
                        self.assertEqual(tuple(result.orig_shape), (height, width))
                        detected = boxes_from_yolo_result(result)
                        self.assertEqual(len(detected), len(result.boxes))
                        for box, item in zip(result.boxes, detected):
                            x1, y1, x2, y2, confidence = item
                            self.assertIn(int(box.cls[0]), VEHICLE_CLASS_IDS)
                            self.assertTrue(math.isfinite(confidence))
                            self.assertGreaterEqual(confidence, DETECTION_CONFIDENCE - 1e-5)
                            self.assertLessEqual(confidence, 1)
                            self.assertTrue(0 <= x1 <= x2 <= width)
                            self.assertTrue(0 <= y1 <= y2 <= height)

                        matches, occupied = assign_detections_to_spaces(
                            detected, contours
                        )
                        statuses = build_space_statuses(config["spaces"], occupied)
                        self.assertEqual(
                            [item["id"] for item in statuses],
                            [item["id"] for item in config["spaces"]],
                        )
                        self.assertTrue(all(type(item["open"]) is bool for item in statuses))
                        self.assertEqual(len(matches), len(detected))
                        self.assertLessEqual(sum(occupied), len(detected))

                        inside = sum(index is not None for index in matches)
                        outside = len(matches) - inside
                        self.assertEqual(inside + outside, len(detected))
                        print(
                            f"{camera} frame {frame_index}: "
                            f"{len(detected)} vehicle detections, "
                            f"{inside} matched, {outside} outside, "
                            f"{sum(occupied)} occupied configured spaces"
                        )
            finally:
                video.release()


if __name__ == "__main__":
    unittest.main()
