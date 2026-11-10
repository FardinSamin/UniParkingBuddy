"""Tests for read-only fragment joining and optional stall-row evidence."""

from copy import deepcopy
import tempfile
from pathlib import Path
import unittest

import cv2
import numpy as np

from backend.discover_stall_geometry import propose_stall_geometry
from backend.row_continuity_experiment import (
    _compatible, analyze_row_continuity, join_collinear_fragments,
)


class RowContinuityTests(unittest.TestCase):
    def test_split_dividers_restore_two_empty_stall_hypotheses(self):
        # No vehicle detections required to find line-pair geometry.
        lines = [
            [60, 40, 60, 94], [60, 97, 60, 174],
            [120, 40, 120, 94], [120, 97, 120, 174],
            [180, 40, 180, 94], [180, 97, 180, 174],
        ]
        before = propose_stall_geometry(lines, (240, 280, 3))
        # Separate short fragments can produce misleading *partial* bays.
        self.assertTrue(before)
        self.assertTrue(all(
            max(point[1] for point in proposal["suggested_quadrilateral_xy"])
            - min(point[1] for point in proposal["suggested_quadrilateral_xy"]) < 100
            for proposal in before
        ))
        joined = join_collinear_fragments(lines)
        self.assertEqual(len(joined), 3)
        self.assertTrue(all(entry["observed_fragment_count"] == 2 for entry in joined))
        self.assertTrue(all(0.95 < entry["observed_longitudinal_coverage_fraction"] <= 1
                            for entry in joined))
        after = propose_stall_geometry(
            [entry["line_xyxy"] for entry in joined], (240, 280, 3)
        )
        self.assertEqual(len(after), 2)
        self.assertTrue(all(c["review_state"] == "unverified" for c in after))

    def test_perspective_angled_strokes_can_join(self):
        lines = [
            [38, 30, 48, 85], [49, 88, 63, 165],
            [94, 30, 104, 85], [105, 88, 119, 165],
        ]
        joined = join_collinear_fragments(lines)
        self.assertEqual(len(joined), 2)
        shapes = propose_stall_geometry(
            [entry["line_xyxy"] for entry in joined], (240, 280, 3)
        )
        self.assertEqual(len(shapes), 1)

    def test_large_missing_gap_is_not_invented_as_line(self):
        lines = [
            [60, 40, 60, 75], [60, 140, 60, 175],
        ]
        merged = join_collinear_fragments(lines)
        self.assertEqual(len(merged), 2)
        self.assertFalse(_compatible(lines[0], lines[1]))

    def test_different_adjacent_stalls_are_not_merged_together(self):
        merged = join_collinear_fragments([
            [60, 40, 60, 170], [120, 40, 120, 170]
        ])
        self.assertEqual(len(merged), 2)

    def test_short_cross_mark_is_not_mistaken_for_main_separator(self):
        self.assertFalse(_compatible(
            [60, 40, 60, 170], [50, 150, 100, 150]
        ))

    def test_collinear_overlapping_edges_join_without_extending_farther(self):
        merged = join_collinear_fragments([
            [60, 40, 60, 110], [60, 80, 60, 175]
        ])
        self.assertEqual(len(merged), 1)
        self.assertEqual(sorted([
            merged[0]["line_xyxy"][1],
            merged[0]["line_xyxy"][3]
        ]), [40, 175])
        self.assertEqual(merged[0]["observed_longitudinal_coverage_fraction"], 1.0)

    def test_invalid_line_geometry_rejected(self):
        for invalid in ([1, 2, 1, 2], [0, 1, 2], [0, 2, float("nan"), 5]):
            with self.subTest(invalid=invalid):
                with self.assertRaises(ValueError):
                    join_collinear_fragments([invalid])

    def test_empty_segment_list_returns_empty_not_approved_spaces(self):
        self.assertEqual(join_collinear_fragments([]), [])

    def test_existing_output_is_not_overwritten(self):
        with tempfile.TemporaryDirectory() as folder:
            dest = Path(folder) / "existing"
            dest.mkdir()
            marker = dest / "important.txt"
            marker.write_text("keep")
            with self.assertRaises(FileExistsError):
                analyze_row_continuity(
                    "notpresent.mp4", "notpresent.json", dest
                )
            self.assertEqual(marker.read_text(), "keep")


if __name__ == "__main__":
    unittest.main()
