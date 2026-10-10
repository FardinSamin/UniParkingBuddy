"""Synthetic tests: stall-geometry benchmark, not actual real-video accuracy."""

import json
from pathlib import Path
import tempfile
import unittest

import cv2
import numpy as np

from backend.stall_discovery_benchmark import (
    BlindLayoutAnnotation, convex_quad, polygon_iou,
    score_file, score_ground_truth, validate_truth,
)


def quad(x1, y1, x2, y2):
    return [[x1, y1], [x2, y1], [x2, y2], [x1, y2]]


HASH = "a" * 64


def truth(spaces):
    return {
        "format": "uniparkingbuddy-stall-layout-truth-v1",
        "source_video_sha256": HASH,
        "frame_index": 0,
        "frame_size": [360, 240],
        "spaces": [{"id": i, "points": p} for i, p in enumerate(spaces, 1)],
    }


def candidate(points, name="L001", tier=None):
    row = {
        "candidate_id": name,
        "review_state": "unverified",
        "suggested_quadrilateral_xy": points,
    }
    if tier:
        row["review_tier"] = tier
    return row


def phase2(spaces):
    return {
        "format": "uniparkingbuddy-unverified-stall-geometry-v1",
        "source_video_sha256": HASH,
        "candidates": spaces,
    }


class BenchmarkTests(unittest.TestCase):
    def setUp(self):
        self.actual = [
            quad(30, 40, 95, 150), quad(110, 40, 175, 150)
        ]
        self.gt = truth(self.actual)

    def test_perfect_geometry_has_complete_unique_matches(self):
        proposals = phase2([
            candidate(self.actual[0], "L001"),
            candidate(self.actual[1], "L002"),
        ])
        report = score_ground_truth(self.gt, proposals)
        for metric in report["metrics"]["phase2_all"]["iou_thresholds"].values():
            self.assertEqual(metric["true_positive"], 2)
            self.assertEqual(metric["false_positive"], 0)
            self.assertEqual(metric["false_negative"], 0)
            self.assertEqual(metric["precision"], 1.0)
            self.assertEqual(metric["recall"], 1.0)
            self.assertEqual(metric["f1"], 1.0)
            self.assertEqual(len(metric["matched_pairs"]), 2)

    def test_duplicates_count_as_false_positives_not_multiple_hits(self):
        report = score_ground_truth(self.gt, phase2([
            candidate(self.actual[0], "L001"),
            candidate(self.actual[0], "L002"),
            candidate(quad(230, 40, 290, 150), "L003"),
        ]))
        at_half = report["metrics"]["phase2_all"]["iou_thresholds"]["0.5"]
        self.assertEqual(
            (at_half["true_positive"], at_half["false_positive"],
             at_half["false_negative"]), (1, 2, 1)
        )

    def test_empty_proposals_have_zero_recall_not_fabricated_accuracy(self):
        report = score_ground_truth(self.gt, phase2([]))
        at_half = report["metrics"]["phase2_all"]["iou_thresholds"]["0.5"]
        self.assertEqual(at_half["true_positive"], 0)
        self.assertEqual(at_half["false_positive"], 0)
        self.assertEqual(at_half["false_negative"], 2)
        self.assertEqual(at_half["recall"], 0)
        self.assertEqual(at_half["precision"], 0)

    def test_partial_overlap_is_not_a_full_stall_at_strict_iou(self):
        self.assertAlmostEqual(
            polygon_iou(self.actual[0], quad(30, 40, 95, 95)), 0.5, places=4
        )
        metrics = score_ground_truth(self.gt, phase2([
            candidate(quad(30, 40, 95, 95), "L001")
        ]))["metrics"]["phase2_all"]["iou_thresholds"]
        self.assertEqual(metrics["0.25"]["true_positive"], 1)
        self.assertEqual(metrics["0.75"]["true_positive"], 0)

    def test_phase4_all_and_shortlist_are_scored_separately(self):
        report = {
            "format": "uniparkingbuddy-unverified-row-continuity-v1",
            "source_video_sha256": HASH,
            "variants": {
                "raw": {"review": {
                    "candidates": [
                        candidate(self.actual[0], "L001", "weak_evidence"),
                        candidate(self.actual[1], "L002", "row_evidence"),
                    ]
                }},
                "ground": {"review": {
                    "candidates": [candidate(self.actual[0], "L003", "likely_artifact")]
                }},
            },
        }
        metrics = score_ground_truth(self.gt, report)["metrics"]
        self.assertEqual(metrics["joined_raw_all"]["predicted_candidate_count"], 2)
        self.assertEqual(metrics["joined_raw_shortlist"]["predicted_candidate_count"], 1)
        self.assertEqual(metrics["joined_ground_all"]["predicted_candidate_count"], 1)
        self.assertEqual(metrics["joined_ground_shortlist"]["predicted_candidate_count"], 0)

    def test_phase3_shortlist_does_not_implicitly_accept_weak_shapes(self):
        report = {
            "format": "uniparkingbuddy-unverified-stall-review-v1",
            "source_video_sha256": HASH,
            "candidates": [
                candidate(self.actual[0], "L001", "multiple_cues"),
                candidate(self.actual[1], "L002", "weak_evidence"),
            ],
        }
        values = score_ground_truth(self.gt, report)["metrics"]
        self.assertEqual(values["phase3_all"]["predicted_candidate_count"], 2)
        self.assertEqual(values["phase3_shortlist"]["predicted_candidate_count"], 1)

    def test_bad_source_hash_fails_closed(self):
        report = phase2([])
        report["source_video_sha256"] = "other"
        with self.assertRaisesRegex(ValueError, "does not match"):
            score_ground_truth(self.gt, report)

    def test_malformed_and_out_of_bounds_polygons_are_rejected(self):
        for shape in (
            [[0, 0]] * 4,
            quad(-5, 5, 100, 120),
            quad(0, 10, 400, 120),
            [[0, 0], [100, 100], [100, 0], [0, 100]],
        ):
            with self.subTest(shape=shape), self.assertRaises(ValueError):
                convex_quad(shape, (240, 360, 3))
        with self.assertRaises(ValueError):
            validate_truth(truth([]))

    def test_duplicate_truth_and_overlapping_stalls_rejected(self):
        duplicate = truth([self.actual[0], self.actual[0]])
        with self.assertRaises(ValueError):
            validate_truth(duplicate)
        nearly_same = truth([
            self.actual[0], quad(60, 60, 125, 160)
        ])
        with self.assertRaises(ValueError):
            validate_truth(nearly_same)

    def test_annotations_are_blind_and_cannot_touch_config(self):
        with tempfile.TemporaryDirectory() as folder:
            # Geometry test only: the temporary file provides provenance,
            # but this does not produce real-world labels.
            media = Path(folder) / "placeholder.mp4"
            media.write_bytes(b"geometry-synthetic-test")
            original = np.zeros((120, 220, 3), dtype=np.uint8)
            s = BlindLayoutAnnotation(media, original, display_width=660)
            for x, y in ((30, 30), (120, 30), (120, 180), (30, 180)):
                s.click(x, y)
            self.assertEqual(len(s.spaces), 1)
            self.assertEqual(s.spaces[0]["points"], quad(10, 10, 40, 60))
            self.assertTrue(np.array_equal(s.frame, original))
            self.assertEqual(s.truth()["frame_size"], [220, 120])
            s.undo()
            self.assertEqual(s.spaces, [])
            with self.assertRaisesRegex(ValueError, "at least one"):
                s.truth()

    def test_score_file_refuses_to_overwrite_existing_report(self):
        with tempfile.TemporaryDirectory() as folder:
            destination = Path(folder) / "report.json"
            destination.write_text("original")
            with self.assertRaises(FileExistsError):
                score_file("missing.json", "missing_proposals.json", destination)
            self.assertEqual(destination.read_text(), "original")

    def test_input_truth_is_unchanged_after_scoring(self):
        before = json.dumps(self.gt, sort_keys=True)
        score_ground_truth(self.gt, phase2([candidate(self.actual[0])]))
        self.assertEqual(before, json.dumps(self.gt, sort_keys=True))


if __name__ == "__main__":
    unittest.main()
