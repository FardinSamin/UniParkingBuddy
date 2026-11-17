"""Regression tests for spatial vehicle-to-space matching."""

import unittest

import numpy as np

import json
from pathlib import Path

from backend.space_matching import (
    OccupancySmoother, assign_detections_by_overlap, match_detections, assign_detections_to_spaces,
    build_space_statuses,
)


def rectangle(x1, y1, x2, y2):
    return np.array(
        [(x1, y1), (x2, y1), (x2, y2), (x1, y2)], dtype=np.int32
    ).reshape((-1, 1, 2))


class SpaceMatchingTests(unittest.TestCase):
    def setUp(self):
        self.spaces = [
            rectangle(0, 0, 99, 99),
            rectangle(100, 0, 199, 99),
        ]

    def test_vehicle_inside_first_space(self):
        matches, occupied = assign_detections_to_spaces(
            [(20, 20, 60, 60, 0.9)], self.spaces
        )
        self.assertEqual(matches, [0])
        self.assertEqual(occupied, [True, False])

    def test_vehicle_in_second_space_is_not_counted_in_first(self):
        matches, occupied = assign_detections_to_spaces(
            [(120, 20, 160, 60, 0.9)], self.spaces
        )
        self.assertEqual(matches, [1])
        self.assertEqual(occupied, [False, True])

    def test_outside_vehicle_never_increases_occupied_count(self):
        matches, occupied = assign_detections_to_spaces(
            [(220, 20, 260, 60, 0.9)], self.spaces
        )
        self.assertEqual(matches, [None])
        self.assertEqual(occupied, [False, False])

    def test_inside_and_outside_vehicle_are_counted_separately(self):
        matches, occupied = assign_detections_to_spaces(
            [(20, 20, 60, 60, 0.9), (220, 20, 260, 60, 0.8)], self.spaces
        )
        self.assertEqual(matches, [0, None])
        self.assertEqual(occupied, [True, False])
        self.assertEqual(len([space for space in matches if space is None]), 1)

    def test_two_detections_in_one_space_occupy_one_space(self):
        matches, occupied = assign_detections_to_spaces(
            [(10, 10, 40, 40, 0.9), (50, 50, 70, 70, 0.9)], self.spaces
        )
        self.assertEqual(matches, [0, 0])
        self.assertEqual(occupied, [True, False])

    def test_no_detections_leaves_all_spaces_open(self):
        matches, occupied = assign_detections_to_spaces([], self.spaces)
        self.assertEqual(matches, [])
        self.assertEqual(occupied, [False, False])

    def test_no_configured_spaces_never_assigns_vehicle(self):
        matches, occupied = assign_detections_to_spaces(
            [(20, 20, 60, 60, 0.9)], []
        )
        self.assertEqual(matches, [None])
        self.assertEqual(occupied, [])

    def test_overlapping_regions_assign_to_single_space(self):
        overlapping = [rectangle(0, 0, 90, 90), rectangle(10, 10, 99, 99)]
        matches, occupied = assign_detections_to_spaces(
            [(20, 20, 60, 60, 0.9)], overlapping
        )
        self.assertEqual(matches, [0])
        self.assertEqual(occupied, [True, False])

    def test_boundary_point_is_inclusive(self):
        matches, occupied = assign_detections_to_spaces(
            [(0, 20, 0, 50, 0.9)], self.spaces
        )
        self.assertEqual(matches, [0])
        self.assertEqual(occupied, [True, False])

    def test_partial_box_overlap_without_center_inside_is_outside(self):
        matches, occupied = assign_detections_to_spaces(
            [(80, 20, 140, 60, 0.9)], [self.spaces[0]]
        )
        self.assertEqual(matches, [None])
        self.assertEqual(occupied, [False])


    def test_statuses_use_stable_ids_not_list_positions(self):
        configured = [{"id": 2}, {"id": 7}]
        statuses = build_space_statuses(configured, [True, False])
        self.assertEqual(statuses, [
            {"id": 2, "open": False},
            {"id": 7, "open": True},
        ])

    def test_statuses_reject_mismatched_space_count(self):
        with self.assertRaises(ValueError):
            build_space_statuses([{"id": 2}], [])


class OverlapMatchingTests(unittest.TestCase):
    def setUp(self):
        self.spaces = [rectangle(0, 0, 99, 99), rectangle(100, 0, 199, 99)]

    def test_vehicle_inside_space(self):
        matches, occupied = assign_detections_by_overlap(
            [(20, 10, 80, 90, 0.9)], self.spaces)
        self.assertEqual(matches, [0])
        self.assertEqual(occupied, [True, False])

    def test_vehicle_straddling_goes_to_the_space_it_overlaps_most(self):
        matches, occupied = assign_detections_by_overlap(
            [(70, 10, 150, 90, 0.9)], self.spaces, footprint_fraction=1.0)
        self.assertEqual(matches, [1])
        self.assertEqual(occupied, [False, True])

    def test_one_detection_never_occupies_two_spaces(self):
        _, occupied = assign_detections_by_overlap(
            [(50, 0, 150, 99, 0.9)], self.spaces, footprint_fraction=1.0)
        self.assertEqual(sum(occupied), 1)

    def test_outside_vehicle_matches_nothing(self):
        matches, occupied = assign_detections_by_overlap(
            [(300, 0, 360, 90, 0.9)], self.spaces)
        self.assertEqual(matches, [None])
        self.assertEqual(occupied, [False, False])

    def test_degenerate_box_matches_nothing(self):
        matches, _ = assign_detections_by_overlap([(10, 10, 10, 50, 0.9)], self.spaces)
        self.assertEqual(matches, [None])

    def test_small_distant_space_is_filled_by_a_larger_vehicle_box(self):
        tiny = [rectangle(40, 40, 80, 52)]
        # The centre rule and the footprint-share rule would both be borderline.
        matches, occupied = assign_detections_by_overlap(
            [(20, 10, 100, 60, 0.9)], tiny)
        self.assertEqual(matches, [0])
        self.assertEqual(occupied, [True])

    def test_vehicle_leaving_a_space_is_still_counted_with_full_box_footprint(self):
        # camera_2 space 4 and a car pulling out whose centre is ~4 px south of
        # the space's bottom edge. The centre rule misses it; overlap does not.
        config = json.loads((Path(__file__).resolve().parents[2]
                             / "configs" / "camera_2.json").read_text())
        contours = [np.array(s["points"], dtype=np.int32).reshape((-1, 1, 2))
                    for s in config["spaces"]]
        box = (852, 273, 897, 343, 0.9)
        _, center_occupied = assign_detections_to_spaces([box], contours)
        _, overlap_occupied = assign_detections_by_overlap(
            [box], contours, footprint_fraction=1.0)
        self.assertFalse(center_occupied[3])
        self.assertTrue(overlap_occupied[3])


class MatchDetectionsDispatchTests(unittest.TestCase):
    def test_modes_and_unknown_mode(self):
        spaces = [rectangle(0, 0, 99, 99)]
        box = [(20, 10, 80, 90, 0.9)]
        self.assertEqual(match_detections(box, spaces, "camera_1", "center")[0], [0])
        self.assertEqual(match_detections(box, spaces, "camera_1", "overlap")[0], [0])
        with self.assertRaises(ValueError):
            match_detections(box, spaces, "camera_1", "bogus")


class OccupancySmootherTests(unittest.TestCase):
    def test_first_pass_sets_state_without_delay(self):
        smoother = OccupancySmoother(2)
        self.assertEqual(smoother.update([True, False]), [True, False])

    def test_needs_consecutive_passes_to_change(self):
        smoother = OccupancySmoother(1, confirm=2, clear=3)
        smoother.update([False])
        self.assertEqual(smoother.update([True]), [False])
        self.assertEqual(smoother.update([True]), [True])
        self.assertEqual(smoother.update([False]), [True])
        self.assertEqual(smoother.update([False]), [True])
        self.assertEqual(smoother.update([False]), [False])

    def test_a_single_missed_detection_does_not_flip_the_space(self):
        smoother = OccupancySmoother(1)
        smoother.update([True])
        smoother.update([False])
        self.assertEqual(smoother.update([True]), [True])

    def test_streak_resets_when_the_observation_agrees_again(self):
        smoother = OccupancySmoother(1, confirm=2, clear=3)
        smoother.update([False])
        smoother.update([True])
        smoother.update([False])
        self.assertEqual(smoother.update([True]), [False])

    def test_rejects_wrong_length_and_bad_parameters(self):
        with self.assertRaises(ValueError):
            OccupancySmoother(2).update([True])
        with self.assertRaises(ValueError):
            OccupancySmoother(1, confirm=0)


if __name__ == "__main__":
    unittest.main()
