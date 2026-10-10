"""Preflight tests use fake video frames, never run YOLO or modify DB."""

import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from backend.preflight import (
    check_database, check_project_files, run_preflight,
)


class FakeFrame:
    def __init__(self, width=16, height=12):
        self.shape = (height, width, 3)


class FakeCapture:
    def __init__(self, *, width=16, height=12, opened=True, readable=True):
        self.frame = FakeFrame(width, height)
        self.opened = opened
        self.readable = readable
        self.released = False

    def isOpened(self):
        return self.opened

    def read(self):
        return self.readable, self.frame if self.readable else None

    def release(self):
        self.released = True


def valid_config():
    return {
        "version": 1,
        "next_space_id": 2,
        "spaces": [{
            "id": 1, "points": [[1, 1], [4, 1], [4, 4], [1, 4]],
        }],
    }


class WorkstationPreflightTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.captures = []
        for path in (
            "yolo26n.pt", "requirements.txt", "backend/schema.sql",
            "frontend/package.json", "frontend/package-lock.json",
            "footage/stockvidsample2.mp4",
            "footage/parkinglotfootage1_1.mp4",
        ):
            target = self.root / path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(b"fixture; no real media or model")
        for camera in ("camera_1", "camera_2"):
            path = self.root / "configs" / f"{camera}.json"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(valid_config()), encoding="utf-8")

    def opener(self, path):
        capture = FakeCapture()
        self.captures.append(capture)
        return capture

    def test_good_files_and_frames_are_read_only_and_report_success(self):
        before = (self.root / "configs/camera_1.json").read_bytes()
        results = check_project_files(self.root, self.opener)
        self.assertEqual(
            [item for item in results if item.level == "FAIL"], []
        )
        self.assertEqual(len(self.captures), 2)
        self.assertTrue(all(c.released for c in self.captures))
        self.assertEqual(
            (self.root / "configs/camera_1.json").read_bytes(), before
        )

    def test_missing_model_fails_without_opening_network(self):
        (self.root / "yolo26n.pt").unlink()
        results = check_project_files(self.root, self.opener)
        self.assertTrue(any(
            item.level == "FAIL" and item.topic == "yolo26n.pt"
            for item in results
        ))

    def test_missing_media_fails_and_other_camera_continues(self):
        (self.root / "footage/stockvidsample2.mp4").unlink()
        results = check_project_files(self.root, self.opener)
        self.assertTrue(any(
            item.level == "FAIL" and item.topic.endswith("stockvidsample2.mp4")
            for item in results
        ))
        self.assertTrue(any(
            item.level == "PASS" and item.topic.endswith("parkinglotfootage1_1.mp4")
            for item in results
        ))

    def test_bad_configuration_fails_instead_of_fabricating_empty_lot(self):
        (self.root / "configs/camera_1.json").write_text("{broken json")
        results = check_project_files(self.root, self.opener)
        self.assertTrue(any(
            item.level == "FAIL" and item.topic == "camera_1 configuration"
            for item in results
        ))

    def test_region_bounds_must_fit_decoded_frame(self):
        cfg = valid_config()
        cfg["spaces"][0]["points"] = [
            [20, 1], [23, 1], [23, 4], [20, 4],
        ]
        (self.root / "configs/camera_2.json").write_text(json.dumps(cfg))
        results = check_project_files(self.root, self.opener)
        self.assertTrue(any(
            item.level == "FAIL" and "exceed the frame" in item.message
            for item in results
        ))

    def test_corrupted_video_fails_and_always_releases_capture(self):
        def opener(path):
            cap = FakeCapture(readable=False)
            self.captures.append(cap)
            return cap

        results = check_project_files(self.root, opener)
        self.assertEqual(
            sum(x.level == "FAIL" and "cannot be decoded" in x.message
                for x in results), 2
        )
        self.assertTrue(all(cap.released for cap in self.captures))

    def test_full_check_without_optional_db_reports_missing_history(self):
        with patch.dict(os.environ, {}, clear=True):
            results = run_preflight(
                self.root, dependencies=False, node=False, database=False,
                capture_factory=self.opener,
            )
        self.assertFalse(any(x.level == "FAIL" for x in results))
        self.assertTrue(any(
            x.topic == "PostgreSQL" and x.level == "WARN" for x in results
        ))

    def test_database_is_never_modified_or_contacted_without_opt_in(self):
        with patch.dict(os.environ, {"DATABASE_URL": "postgresql://secret"}):
            with patch("psycopg.connect",
                       side_effect=AssertionError("Contacted database")):
                results = run_preflight(
                    self.root, dependencies=False, node=False, database=False,
                    capture_factory=self.opener,
                )
        self.assertFalse(any(x.level == "FAIL" for x in results))
        self.assertTrue(any(
            "not tested" in x.message for x in results
            if x.topic == "PostgreSQL"
        ))

    def test_connection_failure_never_exposes_database_password(self):
        with patch.dict(
            os.environ,
            {"DATABASE_URL": "postgresql://tester:super-secret-password@localhost/db"},
        ):
            with patch(
                "psycopg.connect",
                side_effect=RuntimeError("super-secret-password"),
            ):
                findings = check_database()
        self.assertEqual(findings[0].level, "FAIL")
        self.assertNotIn("super-secret-password", findings[0].message)


if __name__ == "__main__":
    unittest.main()
