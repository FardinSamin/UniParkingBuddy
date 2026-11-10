"""Opt-in CPU smoke of all active YOLO camera models and real sample frames.

This checks compatibility and space-status structure, NOT ground-truth accuracy.
"""

import math
import os
from pathlib import Path
import unittest

import cv2
import numpy as np

from backend.accuracy_evaluation import CAMERA_VIDEOS
from backend.parking_config import load_config
from backend.space_matching import build_space_statuses, match_detections
from backend.yolo_detection import AERIAL_VEHICLE_NAMES, detector_settings, detect_boxes

ROOT = Path(__file__).resolve().parents[2]
CAMERAS = tuple(CAMERA_VIDEOS.items())
EXPECTED_CLASSES = {2: "car", 3: "motorcycle", 7: "truck"}


@unittest.skipUnless(
    os.getenv("RUN_REAL_YOLO_SMOKE") == "1",
    "Real inference runs in the dedicated CPU CI job",
)
class RealYOLOInferenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from ultralytics import YOLO
        cls.models = {}
        for camera, _ in CAMERAS:
            settings = detector_settings(camera)
            weight = settings["weights"]
            if weight not in cls.models:
                path = ROOT / weight
                if not path.is_file():
                    raise AssertionError(f"Missing configured model: {weight}")
                cls.models[weight] = YOLO(str(path))
            names = cls.models[weight].names
            if settings["oriented"]:
                actual = set(names.values() if isinstance(names, dict) else names)
                if not set(AERIAL_VEHICLE_NAMES).issubset(actual):
                    raise AssertionError("Aerial vehicle labels absent from OBB model")
            else:
                for class_id, expected in EXPECTED_CLASSES.items():
                    actual = names[class_id] if isinstance(names, (dict, list)) else None
                    if actual != expected:
                        raise AssertionError(
                            f"Camera {camera} class {class_id}: {actual!r} not {expected!r}"
                        )

    def test_real_inference_and_configured_space_results(self):
        for camera, relative_path in CAMERAS:
            config = load_config(ROOT / "configs" / f"{camera}.json")
            contours = [
                np.asarray(space["points"], dtype=np.int32).reshape((-1, 1, 2))
                for space in config["spaces"]
            ]
            video = cv2.VideoCapture(str(ROOT / relative_path))
            try:
                self.assertTrue(video.isOpened(), f"Cannot open {relative_path}")
                count = int(video.get(cv2.CAP_PROP_FRAME_COUNT))
                self.assertGreater(count, 30, f"Video too short: {relative_path}")
                for frame_index in (0, 30):
                    with self.subTest(camera=camera, frame=frame_index):
                        self.assertTrue(video.set(cv2.CAP_PROP_POS_FRAMES, frame_index))
                        success, frame = video.read()
                        self.assertTrue(success, f"Cannot decode {relative_path} frame {frame_index}")
                        height, width = frame.shape[:2]
                        settings = detector_settings(camera)
                        boxes = detect_boxes(
                            self.models[settings["weights"]], frame, camera, device="cpu",
                        )
                        minimum = settings.get("conf", 0.20)
                        for x1, y1, x2, y2, confidence in boxes:
                            self.assertTrue(math.isfinite(confidence))
                            self.assertGreaterEqual(confidence, minimum - 1e-5)
                            self.assertLessEqual(confidence, 1.0)
                            self.assertTrue(0 <= x1 <= x2 <= width)
                            self.assertTrue(0 <= y1 <= y2 <= height)
                        matched, occupied = match_detections(
                            boxes, contours, camera=camera, mode=settings["matching"],
                        )
                        statuses = build_space_statuses(config["spaces"], occupied)
                        self.assertEqual(
                            [item["id"] for item in statuses],
                            [item["id"] for item in config["spaces"]],
                        )
                        self.assertTrue(all(type(item["open"]) is bool for item in statuses))
                        self.assertEqual(len(matched), len(boxes))
                        self.assertLessEqual(sum(occupied), len(boxes))
                        inside = sum(index is not None for index in matched)
                        outside = len(matched) - inside
                        self.assertEqual(inside + outside, len(boxes))
                        print(
                            f"{camera} frame {frame_index}: {len(boxes)} detections, "
                            f"{inside} matched, {outside} unassigned"
                        )
            finally:
                video.release()


if __name__ == "__main__":
    unittest.main()
