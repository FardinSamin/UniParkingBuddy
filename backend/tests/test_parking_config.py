"""Regression tests for versioned, stable-ID parking-space configuration."""

import json
from pathlib import Path
import tempfile
import unittest

from backend.parking_config import (
    ParkingConfigError, add_space, load_config, remove_space, save_config,
    validate_config,
)


ROOT = Path(__file__).resolve().parents[2]


def square(x, y, size=10):
    return [
        [x, y],
        [x + size, y],
        [x + size, y + size],
        [x, y + size],
    ]


def sample():
    return {
        "version": 1,
        "next_space_id": 3,
        "spaces": [
            {"id": 1, "points": square(0, 0)},
            {"id": 2, "points": square(20, 0)},
        ],
    }


class ParkingConfigTests(unittest.TestCase):
    def test_committed_camera_regions_preserved(self):
        expected = [
            ("camera_1", 7, [90, 944], [1590, 818]),
            ("camera_2", 4, [693, 213], [846, 302]),
        ]
        for camera, count, first_point, last_point in expected:
            with self.subTest(camera=camera):
                config = load_config(ROOT / "configs" / f"{camera}.json")
                self.assertEqual(len(config["spaces"]), count)
                self.assertEqual([space["id"] for space in config["spaces"]],
                                 list(range(1, count + 1)))
                self.assertEqual(config["next_space_id"], count + 1)
                self.assertEqual(config["spaces"][0]["points"][0], first_point)
                self.assertEqual(config["spaces"][-1]["points"][-1], last_point)

    def test_removing_a_middle_space_does_not_renumber_survivors(self):
        updated = remove_space(sample(), 1)
        self.assertEqual([space["id"] for space in updated["spaces"]], [2])
        self.assertEqual(updated["next_space_id"], 3)

    def test_removed_id_is_not_reused(self):
        original = sample()
        after_remove = remove_space(original, 2)
        after_add = add_space(after_remove, square(40, 0))
        self.assertEqual([space["id"] for space in after_add["spaces"]], [1, 3])
        self.assertEqual(after_add["next_space_id"], 4)
        self.assertEqual([space["id"] for space in original["spaces"]], [1, 2])

    def test_empty_configuration_can_allocate_first_id(self):
        config = {"version": 1, "next_space_id": 1, "spaces": []}
        self.assertEqual(add_space(config, square(0, 0))["spaces"][0]["id"], 1)

    def test_round_trip_and_deletion_persist(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "camera_1.json"
            save_config(target, sample())
            updated = remove_space(load_config(target), 1)
            save_config(target, updated)
            self.assertEqual(load_config(target)["spaces"][0]["id"], 2)
            self.assertEqual(load_config(target)["next_space_id"], 3)

    def test_missing_json_is_reported_not_treated_as_empty(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(ParkingConfigError):
                load_config(Path(directory) / "missing.json")

    def test_malformed_json_is_reported(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "bad.json"
            target.write_text("{bad json", encoding="utf-8")
            with self.assertRaises(ParkingConfigError):
                load_config(target)

    def test_invalid_configuration_cannot_overwrite_saved_file(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "camera.json"
            save_config(target, sample())
            before = target.read_bytes()
            bad = sample()
            bad["spaces"][1]["id"] = 1
            with self.assertRaises(ParkingConfigError):
                save_config(target, bad)
            self.assertEqual(target.read_bytes(), before)

    def test_rejects_duplicate_ids(self):
        invalid = sample()
        invalid["spaces"][1]["id"] = 1
        with self.assertRaises(ParkingConfigError):
            validate_config(invalid)

    def test_rejects_next_id_that_would_be_reused(self):
        invalid = sample()
        invalid["next_space_id"] = 2
        with self.assertRaises(ParkingConfigError):
            validate_config(invalid)

    def test_rejects_incorrect_schema_and_version(self):
        for invalid in (
            {},
            {"version": 2, "next_space_id": 1, "spaces": []},
            {"version": True, "next_space_id": 1, "spaces": []},
            {"version": 1, "next_space_id": 1, "spaces": [], "other": "value"},
        ):
            with self.subTest(invalid=invalid):
                with self.assertRaises(ParkingConfigError):
                    validate_config(invalid)

    def test_rejects_noninteger_and_negative_coordinates(self):
        for bad_coordinate in (True, 1.5, -1, "9"):
            invalid = sample()
            invalid["spaces"][0]["points"][0][0] = bad_coordinate
            with self.subTest(coordinate=bad_coordinate):
                with self.assertRaises(ParkingConfigError):
                    validate_config(invalid)

    def test_rejects_degenerate_selfcrossing_or_concave_polygon(self):
        invalid_points = (
            [[0, 0], [10, 10], [0, 10], [10, 0]],
            [[0, 0], [10, 0], [20, 0], [0, 10]],
            [[0, 0], [10, 0], [5, 5], [0, 10]],
            [[0, 0], [0, 0], [10, 10], [0, 10]],
        )
        for points in invalid_points:
            invalid = sample()
            invalid["spaces"][0]["points"] = points
            with self.subTest(points=points):
                with self.assertRaises(ParkingConfigError):
                    validate_config(invalid)

    def test_rejects_positive_area_overlaps(self):
        invalid = sample()
        invalid["spaces"][1]["points"] = square(5, 0)
        with self.assertRaisesRegex(ParkingConfigError, "overlap"):
            validate_config(invalid)

    def test_adjacent_polygons_may_touch_but_not_overlap(self):
        config = sample()
        config["spaces"][1]["points"] = square(10, 0)
        self.assertIs(validate_config(config), config)

    def test_prevents_adding_overlapping_space_without_changing_original(self):
        original = sample()
        with self.assertRaises(ParkingConfigError):
            add_space(original, square(5, 5))
        self.assertEqual(original["next_space_id"], 3)
        self.assertEqual(len(original["spaces"]), 2)

    def test_remove_unknown_space_reports_error(self):
        with self.assertRaises(ParkingConfigError):
            remove_space(sample(), 99)

    def test_file_is_human_readable_json(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "camera.json"
            save_config(target, sample())
            self.assertEqual(json.loads(target.read_text(encoding="utf-8")), sample())


if __name__ == "__main__":
    unittest.main()
