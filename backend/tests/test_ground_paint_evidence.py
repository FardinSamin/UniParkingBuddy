"""Synthetic experiments for distinguishing painted pavement from car edges.

This checks expected pixel-contrast behavior only, NOT actual parking
space accuracy or robustness across lighting, viewpoints and pavement.
"""

import unittest

import cv2
import numpy as np

from backend.ground_paint_evidence import (
    filter_ground_supported_lines, measure_line_pavement_contrast,
    render_line_context,
)


class PavementPaintEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.shape = (230, 330, 3)

    def dark_pavement(self):
        return np.full(self.shape, 55, dtype=np.uint8)

    def test_bright_paint_between_dark_pavement_accepted(self):
        frames = [self.dark_pavement() for _ in range(3)]
        for frame in frames:
            cv2.line(frame, (75, 35), (75, 188), (255, 255, 255), 5)
        line = (73, 38, 73, 183)  # an observed edge, not the stroke center
        supported, evidence = filter_ground_supported_lines([line], frames)
        self.assertEqual(supported, [line])
        self.assertGreaterEqual(evidence[0]["dark_flank_contrast_fraction"], 0.9)
        self.assertTrue(evidence[0]["ground_supported_for_review"])

    def test_bright_stroke_inside_white_vehicle_body_is_not_pavement(self):
        frames = [self.dark_pavement() for _ in range(3)]
        for frame in frames:
            cv2.rectangle(frame, (130, 30), (195, 200), (230, 230, 230), -1)
            cv2.line(frame, (162, 45), (162, 188), (255, 255, 255), 3)
        line = (162, 50, 162, 185)
        supported, evidence = filter_ground_supported_lines([line], frames)
        self.assertEqual(supported, [])
        self.assertEqual(evidence[0]["dark_flank_contrast_fraction"], 0.0)

    def test_weak_contrast_on_light_substrate_is_not_silently_confirmed(self):
        frames = [np.full(self.shape, 205, dtype=np.uint8) for _ in range(3)]
        for frame in frames:
            cv2.line(frame, (75, 35), (75, 188), (245, 245, 245), 4)
        accepted, evidence = filter_ground_supported_lines(
            [(75, 35, 75, 188)], frames
        )
        self.assertEqual(accepted, [])
        self.assertFalse(evidence[0]["ground_supported_for_review"])

    def test_line_with_only_one_dark_flank_is_rejected(self):
        frames = [self.dark_pavement() for _ in range(3)]
        for frame in frames:
            cv2.rectangle(frame, (80, 35), (160, 188), (240, 240, 240), -1)
        # x=80 is a sharp car-body border: left dark, right bright
        accepted, evidence = filter_ground_supported_lines(
            [(80, 35, 80, 188)], frames
        )
        self.assertEqual(accepted, [])
        self.assertFalse(evidence[0]["ground_supported_for_review"])

    def test_transient_bright_line_lacks_support_across_frames(self):
        frames = [self.dark_pavement() for _ in range(4)]
        cv2.line(frames[0], (75, 35), (75, 188), (255, 255, 255), 5)
        line = (73, 38, 73, 183)
        supported, evidence = filter_ground_supported_lines(
            [line], frames, minimum_fraction=0.5
        )
        self.assertEqual(supported, [])
        self.assertLess(evidence[0]["dark_flank_contrast_fraction"], 0.5)

    def test_near_image_edge_has_no_unbounded_array_access(self):
        gray = cv2.cvtColor(self.dark_pavement(), cv2.COLOR_BGR2GRAY)
        score = measure_line_pavement_contrast(
            (0, 20, 0, 205), [gray]
        )
        self.assertEqual(score, 0.0)

    def test_invalid_inputs_fail_closed(self):
        valid = [self.dark_pavement()]
        with self.assertRaises(ValueError):
            filter_ground_supported_lines([], [])
        with self.assertRaises(ValueError):
            filter_ground_supported_lines([], valid, minimum_fraction=0)
        with self.assertRaises(ValueError):
            filter_ground_supported_lines([], valid, minimum_fraction=1.5)
        with self.assertRaises(ValueError):
            filter_ground_supported_lines([], [np.zeros((20, 20))])
        with self.assertRaises(ValueError):
            filter_ground_supported_lines([], [
                self.dark_pavement(), np.zeros((200, 300, 3), dtype=np.uint8)
            ])
        gray = cv2.cvtColor(valid[0], cv2.COLOR_BGR2GRAY)
        with self.assertRaises(ValueError):
            measure_line_pavement_contrast((1, 2, 3), [gray])
        with self.assertRaises(ValueError):
            measure_line_pavement_contrast((1, 2, float("nan"), 3), [gray])

    def test_audit_overlay_never_mutates_source_frame(self):
        frame = self.dark_pavement()
        original = frame.copy()
        evidence = [
            {"line_xyxy": [75, 30, 75, 188],
             "ground_supported_for_review": True},
            {"line_xyxy": [155, 30, 155, 188],
             "ground_supported_for_review": False},
        ]
        overlay = render_line_context(frame, evidence)
        self.assertFalse(np.array_equal(overlay, frame))
        self.assertTrue(np.array_equal(frame, original))


if __name__ == "__main__":
    unittest.main()
