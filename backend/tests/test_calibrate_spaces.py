"""Tests for the paused-frame parking-space calibration workflow.

These use synthetic geometry and never open a GUI or edit committed configs.
"""

import json
from pathlib import Path
import tempfile
import unittest

from backend.calibrate_spaces import CalibrationSession, display_to_source


def square(x, y, size=20):
    return [[x, y], [x + size, y], [x + size, y + size], [x, y + size]]


class CalibrationTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tempdir.cleanup)
        self.root = Path(self.tempdir.name)
        self.config_path = self.root / "camera_1.json"
        self.initial = {
            "version": 1,
            "next_space_id": 3,
            "spaces": [
                {"id": 1, "points": square(20, 20)},
                {"id": 2, "points": square(60, 20)},
            ],
        }
        self.config_path.write_text(json.dumps(self.initial), encoding="utf-8")

    def session(self):
        # Original frame 200x100; exact 2x downsizing to 100x50.
        return CalibrationSession(self.config_path, 200, 100, 100)

    def test_click_coordinates_retain_original_video_geometry(self):
        self.assertEqual(display_to_source(50, 25, 200, 100, 100, 50), [100, 50])
        self.assertEqual(display_to_source(99, 49, 200, 100, 100, 50), [198, 98])
        with self.assertRaises(ValueError):
            display_to_source(1, 50, 200, 100, 100, 50)

    def test_add_four_corners_preserves_old_ids_until_save(self):
        session = self.session()
        for x, y in ((60, 30), (70, 30), (70, 40), (60, 40)):
            session.add_corner(x, y)
        self.assertTrue(session.dirty)
        self.assertEqual(session.config["spaces"][-1],
                         {"id": 3, "points": square(120, 60)})
        self.assertEqual(json.loads(self.config_path.read_text()), self.initial)

        backup = session.save(root=self.root)
        self.assertTrue(backup.exists())
        self.assertEqual(json.loads(backup.read_text()), self.initial)
        saved = json.loads(self.config_path.read_text())
        self.assertEqual([p["id"] for p in saved["spaces"]], [1, 2, 3])
        self.assertEqual(saved["next_space_id"], 4)
        self.assertFalse(session.dirty)
        self.assertIsNone(session.save(root=self.root))

    def test_overlapping_new_space_is_rejected_without_change(self):
        session = self.session()
        for x, y in ((15, 15), (25, 15), (25, 25), (15, 25)):
            session.add_corner(x, y)
        self.assertFalse(session.dirty)
        self.assertEqual(len(session.config["spaces"]), 2)
        self.assertIn("Invalid stall", session.message)
        self.assertEqual(session.pending, [])

    def test_remove_by_right_click_does_not_recycle_space_id(self):
        session = self.session()
        session.remove_at(15, 15)  # original coordinate (30,30) inside space 1
        self.assertEqual([p["id"] for p in session.config["spaces"]], [2])
        self.assertEqual(session.config["next_space_id"], 3)
        self.assertEqual(json.loads(self.config_path.read_text()), self.initial)
        session.save(root=self.root)
        self.assertEqual([p["id"] for p in json.loads(self.config_path.read_text())["spaces"]],
                         [2])

    def test_no_changes_are_persisted_on_quit_without_save(self):
        session = self.session()
        session.remove_at(15, 15)
        self.assertTrue(session.dirty)
        self.assertEqual(json.loads(self.config_path.read_text()), self.initial)

    def test_unfinished_polygon_blocks_save(self):
        session = self.session()
        session.add_corner(60, 30)
        with self.assertRaisesRegex(ValueError, "pending corners"):
            session.save(root=self.root)
        session.undo_corner()
        self.assertEqual(session.pending, [])
        self.assertIsNone(session.save(root=self.root))

    def test_bad_corner_order_does_not_corrupt_configuration(self):
        session = self.session()
        for x, y in ((60, 30), (70, 40), (70, 30), (60, 40)):
            session.add_corner(x, y)
        self.assertFalse(session.dirty)
        self.assertEqual(len(session.config["spaces"]), 2)


if __name__ == "__main__":
    unittest.main()
