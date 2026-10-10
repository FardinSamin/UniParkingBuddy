"""Synthetic tests for line-supported, review-only stall geometry proposals.

No ground-truth accuracy is claimed. No network, model or actual video needed.
"""

import copy
import math
from pathlib import Path
import tempfile
import unittest

import cv2
import numpy as np

from backend.discover_stall_geometry import (
    analyze_video_markings, correlate_vehicle_hypotheses, detect_marking_lines,
    marking_mask, persistent_markings, propose_stall_geometry,
    render_geometry_preview,
)


class StallGeometryTests(unittest.TestCase):
    def setUp(self):
        self.dividers = [
            (60, 45, 60, 175),
            (120, 45, 120, 175),
            (180, 45, 180, 175),
        ]
        self.shape = (240, 320, 3)

    def test_adjacent_line_pairs_propose_two_stall_quadrilaterals(self):
        proposed = propose_stall_geometry(self.dividers, self.shape)
        self.assertEqual(len(proposed), 2)
        self.assertEqual([p["candidate_id"] for p in proposed], ["L001", "L002"])
        for proposal in proposed:
            self.assertEqual(proposal["review_state"], "unverified")
            self.assertEqual(len(proposal["suggested_quadrilateral_xy"]), 4)
            self.assertEqual(len(proposal["supporting_marking_lines_xyxy"]), 2)
            self.assertNotIn("id", proposal)
            self.assertNotIn("spaces", proposal)

    def test_angled_lines_can_generate_convex_polygon(self):
        lines = [
            (35, 60, 55, 170),
            (95, 60, 115, 170),
        ]
        candidates = propose_stall_geometry(lines, self.shape)
        self.assertEqual(len(candidates), 1)
        quad = np.asarray(candidates[0]["suggested_quadrilateral_xy"], dtype=np.int32)
        self.assertTrue(cv2.isContourConvex(quad.reshape((-1, 1, 2))))
        self.assertGreater(cv2.contourArea(quad), 100)

    def test_single_line_and_perpendicular_lines_do_not_form_stall(self):
        self.assertEqual(propose_stall_geometry([self.dividers[0]], self.shape), [])
        self.assertEqual(propose_stall_geometry([
            (30, 40, 30, 140), (20, 110, 120, 110)
        ], self.shape), [])

    def test_distant_strokes_fail_width_depth_geometry(self):
        self.assertEqual(propose_stall_geometry([
            (10, 15, 10, 145), (300, 15, 300, 145)
        ], self.shape), [])

    def test_input_validation(self):
        with self.assertRaises(ValueError):
            propose_stall_geometry(self.dividers, (0, 0, 3))
        with self.assertRaises(ValueError):
            propose_stall_geometry(self.dividers, self.shape, max_candidates=0)

    def test_fixed_white_and_yellow_markings_survive_temporal_vote(self):
        a = np.full(self.shape, 55, dtype=np.uint8)
        b = a.copy()
        c = a.copy()
        for frame in (a, b, c):
            cv2.line(frame, (60, 45), (60, 175), (255, 255, 255), 4)
            cv2.line(frame, (120, 45), (120, 175), (255, 255, 255), 4)
            cv2.line(frame, (180, 45), (180, 175), (0, 255, 255), 4)
        # Transient paint-like object should not appear in majority mask.
        cv2.line(a, (220, 45), (220, 175), (255, 255, 255), 4)
        mask = persistent_markings([a, b, c], support_fraction=0.66)
        self.assertEqual(int(mask[110, 60]), 255)
        self.assertEqual(int(mask[110, 180]), 255)
        self.assertEqual(int(mask[110, 220]), 0)
        lines = detect_marking_lines(mask)
        self.assertGreaterEqual(len(lines), 2)
        self.assertTrue(propose_stall_geometry(lines, self.shape))

    def test_dark_scene_no_marks_no_candidates(self):
        blank = np.full(self.shape, 48, dtype=np.uint8)
        mask = marking_mask(blank)
        self.assertFalse(np.any(mask))
        self.assertEqual(detect_marking_lines(mask), [])
        self.assertEqual(propose_stall_geometry([], self.shape), [])

    def test_invalid_temporal_samples_fail(self):
        frame = np.zeros(self.shape, dtype=np.uint8)
        with self.assertRaises(ValueError):
            persistent_markings([])
        with self.assertRaises(ValueError):
            persistent_markings([frame], 0)
        with self.assertRaises(ValueError):
            persistent_markings([frame], 1.5)
        with self.assertRaises(ValueError):
            persistent_markings([frame, frame[:100]])

    def test_vehicle_correspondence_is_research_evidence_not_approval(self):
        candidates = propose_stall_geometry(self.dividers, self.shape)
        report = {
            "format": "uniparkingbuddy-unverified-vehicle-locations-v1",
            "source_video_sha256": "same-video",
            "proposals": [
                {"proposal_id": "P010", "ground_anchor_xy": [90, 130]},
                {"proposal_id": "P020", "ground_anchor_xy": [250, 130]},
            ]
        }
        correlated = correlate_vehicle_hypotheses(candidates, report, "same-video")
        matched = [c for c in correlated if c["corroborating_vehicle_location_ids"]]
        self.assertEqual(len(matched), 1)
        self.assertEqual(matched[0]["corroborating_vehicle_location_ids"], ["P010"])
        self.assertIn("recurring_vehicle_location", matched[0]["evidence_sources"])
        self.assertTrue(all(c["review_state"] == "unverified" for c in correlated))

    def test_mismatched_video_hash_or_malformed_anchor_is_rejected(self):
        candidates = propose_stall_geometry(self.dividers, self.shape)
        valid = {
            "format": "uniparkingbuddy-unverified-vehicle-locations-v1",
            "source_video_sha256": "old",
            "proposals": [{"proposal_id": "P001", "ground_anchor_xy": [90, 130]}],
        }
        with self.assertRaisesRegex(ValueError, "different video"):
            correlate_vehicle_hypotheses(copy.deepcopy(candidates), valid, "new")
        valid["source_video_sha256"] = "new"
        valid["proposals"][0]["ground_anchor_xy"] = [math.nan, 130]
        with self.assertRaisesRegex(ValueError, "Malformed vehicle anchor"):
            correlate_vehicle_hypotheses(copy.deepcopy(candidates), valid, "new")

    def test_visualization_is_an_overlay_and_does_not_modify_input(self):
        blank = np.full(self.shape, 65, dtype=np.uint8)
        original = blank.copy()
        drawn = render_geometry_preview(
            blank, self.dividers,
            propose_stall_geometry(self.dividers, self.shape)
        )
        self.assertEqual(drawn.shape, blank.shape)
        self.assertTrue(np.array_equal(blank, original))
        self.assertFalse(np.array_equal(drawn, original))

    def test_rejects_overwriting_existing_experiment_folder(self):
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder) / "existing"
            output.mkdir()
            marker = output / "record.txt"
            marker.write_text("preserve")
            with self.assertRaises(FileExistsError):
                analyze_video_markings("nonexistent.mp4", output)
            self.assertEqual(marker.read_text(), "preserve")


if __name__ == "__main__":
    unittest.main()
