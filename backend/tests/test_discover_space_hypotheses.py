"""Synthetic regression cases for automatic *hypothesis* discovery.

These tests verify grouping/guardrails, not real-world stall detection accuracy.
No YOLO download, camera, video, or PostgreSQL is used.
"""

import tempfile
from pathlib import Path
import unittest

import numpy as np

from backend.discover_space_hypotheses import (
    analyze_video, propose_locations, render_preview,
)


def box(x, y, width=34, height=54):
    return (x, y, x + width, y + height, 0.85)


class SpaceHypothesisTests(unittest.TestCase):
    def test_repeated_position_produces_unverified_candidate(self):
        frames = {
            0: [box(100, 60)],
            30: [box(101, 60)],
            60: [box(99, 61)],
            90: [box(101, 59)],
        }
        candidates = propose_locations(frames)
        self.assertEqual(len(candidates), 1)
        result = candidates[0]
        self.assertEqual(result["proposal_id"], "P001")
        self.assertEqual(result["supporting_sampled_frames"], 4)
        self.assertEqual(result["sampled_frame_fraction"], 1.0)
        self.assertEqual(result["frame_indices"], [0, 30, 60, 90])
        self.assertEqual(result["review_state"], "unverified")
        self.assertEqual(result["evidence_type"], "repeated_vehicle_detection_only")
        self.assertEqual(result["proxy_vehicle_box_xyxy"], [101, 60, 135, 114])
        self.assertNotIn("points", result)  # not a valid parking-config polygon

    def test_transient_passing_car_does_not_generate_candidate(self):
        frames = {
            0: [box(20, 40)],
            30: [box(95, 40)],
            60: [box(170, 40)],
            90: [],
            120: [],
        }
        self.assertEqual(propose_locations(frames), [])

    def test_adjacent_fixed_cars_are_distinct_candidates(self):
        frames = {
            idx: [box(100, 60), box(160, 60)]
            for idx in (0, 30, 60, 90)
        }
        candidates = propose_locations(frames)
        self.assertEqual(len(candidates), 2)
        self.assertEqual([c["supporting_sampled_frames"] for c in candidates], [4, 4])
        self.assertNotEqual(candidates[0]["ground_anchor_xy"],
                            candidates[1]["ground_anchor_xy"])

    def test_two_detections_in_same_frame_never_count_twice(self):
        frames = {
            0: [box(100, 60), box(102, 60)],
            30: [box(101, 61)],
            60: [box(100, 59)],
            90: [box(101, 60)],
        }
        candidates = propose_locations(frames, min_frames=3)
        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0]["supporting_sampled_frames"], 4)

    def test_min_support_fraction_rejects_sparse_evidence(self):
        frames = {0: [box(100, 60)], 30: [box(100, 60)],
                  60: [], 90: [], 120: []}
        self.assertEqual(propose_locations(frames, min_frames=2, min_support=0.5), [])
        self.assertEqual(len(propose_locations(
            frames, min_frames=2, min_support=0.4
        )), 1)

    def test_box_center_and_ground_anchor_are_distinct(self):
        results = propose_locations({
            0: [box(80, 30)], 30: [box(80, 30)], 60: [box(80, 30)]
        })
        self.assertEqual(results[0]["ground_anchor_xy"], [97.0, 84.0])

    def test_no_detections_means_no_proposals_not_available_spaces(self):
        self.assertEqual(propose_locations({0: [], 30: [], 60: []}), [])

    def test_invalid_geometry_and_options_fail_closed(self):
        cases = [
            ({0: [(0, 0, 0, 10)], 30: []}, {}),
            ({0: [(0, 0, float("nan"), 10)], 30: []}, {}),
            ({-1: [box(100, 60)]}, {}),
            ({0: [box(100, 60)]}, {"min_frames": 1}),
            ({0: [box(100, 60)]}, {"min_support": 1.2}),
            ({0: [box(100, 60)]}, {"horizontal_fraction": 0}),
            ({0: [box(100, 60)]}, {"vertical_fraction": float("inf")}),
            ({}, {}),
        ]
        for frames, settings in cases:
            with self.subTest(frames=frames, settings=settings):
                with self.assertRaises(ValueError):
                    propose_locations(frames, **settings)

    def test_preview_only_labels_hypotheses(self):
        frame = np.zeros((140, 230, 3), dtype=np.uint8)
        proposals = propose_locations({
            0: [box(30, 30)], 30: [box(30, 30)], 60: [box(30, 30)]
        })
        output = render_preview(frame, proposals)
        self.assertEqual(output.shape, frame.shape)
        self.assertFalse(np.array_equal(output, frame))
        self.assertTrue(np.array_equal(frame, np.zeros_like(frame)))

    def test_existing_output_cannot_be_overwritten(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "existing"
            output.mkdir()
            marker = output / "marker.txt"
            marker.write_text("preserve")
            with self.assertRaises(FileExistsError):
                analyze_video("not_a_video.mp4", output)
            self.assertEqual(marker.read_text(), "preserve")


if __name__ == "__main__":
    unittest.main()
