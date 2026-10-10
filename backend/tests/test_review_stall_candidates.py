"""Synthetic quality-gate tests; no real-world stall detection claims."""

from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest

import cv2
import numpy as np

from backend.discover_stall_geometry import propose_stall_geometry
from backend.review_stall_candidates import (
    assess_geometry, render_review, review_video_geometry,
)


def geometry(lines, source="sample-hash"):
    return {
        "format": "uniparkingbuddy-unverified-stall-geometry-v1",
        "source_video_sha256": source,
        "candidates": propose_stall_geometry(lines, (250, 350, 3)),
    }


def vehicle(candidate_id, anchor, box):
    return {
        "proposal_id": candidate_id,
        "ground_anchor_xy": list(anchor),
        "proxy_vehicle_box_xyxy": list(box),
    }


def phase1(items, source="sample-hash"):
    return {
        "format": "uniparkingbuddy-unverified-vehicle-locations-v1",
        "source_video_sha256": source,
        "proposals": items,
    }


class StallQualityGateTests(unittest.TestCase):
    def setUp(self):
        self.dividers = [
            (45, 40, 45, 170),
            (105, 40, 105, 170),
            (165, 40, 165, 170),
        ]
        self.scene = geometry(self.dividers)

    def test_shared_separator_forms_repeated_row_evidence(self):
        report = assess_geometry(self.scene)
        self.assertEqual(report["candidate_count"], 2)
        self.assertEqual(report["shortlist_count"], 2)
        self.assertEqual(report["suspected_artifact_count"], 0)
        assert_ids = sorted(c["candidate_id"] for c in report["candidates"])
        self.assertEqual(assert_ids, ["L001", "L002"])
        self.assertEqual(
            sorted(c["review_tier"] for c in report["candidates"]),
            ["row_evidence", "row_evidence"],
        )
        for item in report["candidates"]:
            self.assertEqual(len(item["row_neighbor_candidate_ids"]), 1)
            self.assertEqual(item["review_state"], "unverified")

    def test_vehicle_anchor_plus_row_continuity_priority(self):
        report = assess_geometry(
            self.scene,
            phase1([vehicle("P001", [80, 130], [58, 55, 100, 152])])
        )
        self.assertEqual(report["shortlist_count"], 2)
        self.assertEqual(report["candidates"][0]["review_tier"], "multiple_cues")
        self.assertEqual(
            report["candidates"][0]["corroborating_vehicle_location_ids"], ["P001"]
        )
        self.assertEqual(report["candidates"][1]["review_tier"], "row_evidence")

    def test_roof_or_window_sized_polygon_is_demoted_even_with_repeated_car(self):
        scene = geometry([(70, 70, 70, 105), (86, 70, 86, 105)])
        self.assertEqual(len(scene["candidates"]), 1)
        report = assess_geometry(
            scene,
            phase1([vehicle("P001", [77, 100], [55, 35, 105, 140])])
        )
        self.assertEqual(report["suspected_artifact_count"], 1)
        self.assertEqual(report["shortlist_count"], 0)
        self.assertEqual(report["candidates"][0]["review_tier"], "likely_artifact")
        self.assertIn(
            "tiny_polygon_largely_inside_repeated_vehicle_box",
            report["candidates"][0]["review_reasons"],
        )
        # The candidate is demoted, not silently discarded.
        self.assertEqual(report["candidate_count"], 1)

    def test_small_empty_candidate_remains_uncertain_not_auto_rejected(self):
        scene = geometry([(70, 70, 70, 105), (86, 70, 86, 105)])
        report = assess_geometry(scene, phase1([]))
        self.assertEqual(report["candidate_count"], 1)
        self.assertEqual(report["shortlist_count"], 0)
        self.assertEqual(report["candidates"][0]["review_tier"], "weak_evidence")

    def test_geometry_only_singleton_is_not_certified_stall(self):
        scene = geometry(self.dividers[:2])
        report = assess_geometry(scene)
        self.assertEqual(report["candidate_count"], 1)
        self.assertEqual(report["shortlist_count"], 0)
        self.assertEqual(report["candidates"][0]["review_tier"], "weak_evidence")
        self.assertFalse(any("approved" in c for c in report["candidates"]))

    def test_corresponding_anchor_can_promote_singleton_to_human_review(self):
        scene = geometry(self.dividers[:2])
        report = assess_geometry(
            scene, phase1([vehicle("P001", [78, 130], [60, 55, 105, 155])])
        )
        self.assertEqual(report["shortlist_count"], 1)
        self.assertEqual(report["candidates"][0]["review_tier"], "vehicle_evidence")
        self.assertEqual(report["candidates"][0]["review_state"], "unverified")

    def test_source_mismatch_fails_before_mutation(self):
        with self.assertRaisesRegex(ValueError, "hashes do not match"):
            assess_geometry(self.scene, phase1([], source="different"))

    def test_malformed_car_box_and_geometry_fail_closed(self):
        with self.assertRaisesRegex(ValueError, "Malformed Phase 1 proxy"):
            assess_geometry(
                self.scene, phase1([vehicle("P001", [80, 120], [40, 50, 40, 80])])
            )
        modified = deepcopy(self.scene)
        modified["candidates"][0]["suggested_quadrilateral_xy"] = [[0, 0]] * 4
        with self.assertRaises(ValueError):
            assess_geometry(modified)

    def test_input_reports_not_changed_and_preview_is_nonmutating(self):
        before = deepcopy(self.scene)
        report = assess_geometry(self.scene)
        self.assertEqual(self.scene, before)
        frame = np.zeros((250, 350, 3), dtype=np.uint8)
        preview = render_review(frame, report)
        self.assertFalse(np.array_equal(preview, frame))
        self.assertTrue(np.all(frame == 0))

    def test_never_overwrites_existing_review_output(self):
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder) / "run1"
            output.mkdir()
            sentinel = output / "notes.txt"
            sentinel.write_text("preserved")
            with self.assertRaises(FileExistsError):
                review_video_geometry(
                    "unused.mp4", "unused.json", output
                )
            self.assertEqual(sentinel.read_text(), "preserved")


if __name__ == "__main__":
    unittest.main()
