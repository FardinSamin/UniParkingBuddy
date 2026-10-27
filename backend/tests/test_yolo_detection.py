import unittest
from types import SimpleNamespace

from backend.yolo_detection import (
    boxes_from_obb_result, dedupe_boxes, detect_boxes, detector_settings,
)


def obb_result(rows, names):
    return SimpleNamespace(
        names=names,
        obb=SimpleNamespace(
            xyxy=[r[0] for r in rows],
            conf=[r[1] for r in rows],
            cls=[r[2] for r in rows],
        ),
    )


class ObbBoxTests(unittest.TestCase):
    names = {0: "plane", 9: "small vehicle", 10: "large vehicle"}

    def test_only_vehicle_classes_are_kept_as_anonymous_tuples(self):
        result = obb_result([
            ([10.4, 20.6, 50.2, 90.9], 0.8, 9),
            ([0, 0, 5, 5], 0.9, 0),
            ([100, 100, 200, 160], 0.5, 10),
        ], self.names)
        self.assertEqual(boxes_from_obb_result(result), [
            (10, 20, 50, 90, 0.8), (100, 100, 200, 160, 0.5),
        ])

    def test_result_without_obb_gives_no_boxes(self):
        self.assertEqual(
            boxes_from_obb_result(SimpleNamespace(names={}, obb=None)), [])

    def test_camera_3_uses_aerial_oriented_detector_others_use_coco(self):
        self.assertTrue(detector_settings("camera_3")["oriented"])
        for camera in ("camera_1", "camera_2"):
            self.assertFalse(detector_settings(camera)["oriented"])
            self.assertEqual(detector_settings(camera)["classes"], [2, 3, 7])

    def test_camera_3_uses_medium_aerial_model_with_low_confidence(self):
        settings = detector_settings("camera_3")
        self.assertEqual(settings["weights"], "yolo26m-obb.pt")
        self.assertEqual(settings["conf"], 0.08)

    def test_detect_boxes_does_not_filter_by_coco_ids_for_camera_3(self):
        seen = {}

        def model(frame, **kwargs):
            seen.update(kwargs)
            return [obb_result([([1, 2, 3, 4], 0.7, 9)], self.names)]

        self.assertEqual(detect_boxes(model, object(), "camera_3"),
                         [(1, 2, 3, 4, 0.7)])
        self.assertNotIn("classes", seen)
        self.assertEqual(seen["conf"], 0.08)


class DedupeTests(unittest.TestCase):
    def test_same_car_detected_twice_keeps_higher_confidence(self):
        boxes = [(30, 462, 253, 597, 0.55), (32, 462, 254, 597, 0.80)]
        self.assertEqual(dedupe_boxes(boxes), [(32, 462, 254, 597, 0.80)])

    def test_adjacent_distinct_cars_are_both_kept(self):
        boxes = [(0, 0, 100, 100, 0.9), (90, 0, 190, 100, 0.8)]
        self.assertEqual(len(dedupe_boxes(boxes)), 2)

    def test_camera_1_uses_larger_model_with_overlap_matching(self):
        settings = detector_settings("camera_1")
        self.assertEqual(settings["weights"], "yolo26m.pt")
        self.assertEqual(settings["matching"], "overlap")
        camera_2 = detector_settings("camera_2")
        self.assertEqual((camera_2["weights"], camera_2["imgsz"], camera_2["matching"]),
                         ("yolo26m.pt", 1920, "overlap"))


if __name__ == "__main__":
    unittest.main()
