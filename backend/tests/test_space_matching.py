"""Regression tests for spatial vehicle-to-space matching."""

import unittest

import numpy as np

from backend.space_matching import assign_detections_to_spaces, build_space_statuses


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



if __name__ == '__main__':
    unittest.main()
