"""Smoke test the CV geometry -> persistence gate -> Flask API chain.

Uses a synthetic fixed-view scene and real disposable PostgreSQL server.
No GUI or YOLO model is launched; this cannot measure inference accuracy.
"""

from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
import os
import unittest

import cv2
import numpy as np
import psycopg

from backend.occupancy_repository import OccupancyRepository, SCHEMA_PATH
from backend.space_matching import assign_detections_to_spaces, build_space_statuses
from backend.status_api import create_status_app, invalidate_camera_status
from backend.status_publisher import publish_space_result


def configured_scene():
    return {
        "version": 1,
        "next_space_id": 8,
        "spaces": [
            {"id": 2, "points": [[0, 0], [30, 0], [30, 30], [0, 30]]},
            {"id": 7, "points": [[40, 0], [70, 0], [70, 30], [40, 30]]},
        ],
    }


class CVToPostgreSQLToAPITests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dsn = os.getenv("TEST_DATABASE_URL")
        if not cls.dsn:
            raise unittest.SkipTest("TEST_DATABASE_URL is not set")
        with psycopg.connect(cls.dsn) as conn:
            actual = conn.execute("SELECT current_database()").fetchone()[0]
            if actual != "uniparkingbuddy_test":
                raise RuntimeError("Refusing to alter a non-test database")
            if conn.execute("SELECT to_regclass('parking_lot')").fetchone()[0] is None:
                conn.execute(Path(SCHEMA_PATH).read_text(encoding="utf-8"))

    def setUp(self):
        with psycopg.connect(self.dsn) as conn:
            conn.execute(
                "TRUNCATE occupancy_record, parking_space_region, parking_space, "
                "parking_lot RESTART IDENTITY"
            )
        self.repo = OccupancyRepository(self.dsn)
        self.config = configured_scene()
        self.repo.register_lot_configuration("lot1", "Lot 1", self.config)
        self.live = {}
        self.lock = Lock()
        self.app = create_status_app({"camera_1": object()}, self.live, self.lock, self.repo)
        self.app.testing = True
        self.client = self.app.test_client()
        self.when = datetime.now(timezone.utc)

    def detect_and_publish(self, boxes):
        contours = [
            np.array(space["points"], dtype=np.int32).reshape((-1, 1, 2))
            for space in self.config["spaces"]
        ]
        matched, occupied = assign_detections_to_spaces(boxes, contours)
        statuses = build_space_statuses(self.config["spaces"], occupied)
        inside = sum(match is not None for match in matched)
        outside = len(boxes) - inside
        done = publish_space_result(
            "camera_1", statuses, len(boxes), inside, outside,
            repository=self.repo, newly_inferred=True,
            latest_status=self.live, status_lock=self.lock,
            observed_at=self.when,
        )
        return done, matched

    def test_synthetic_inside_outside_matches_both_api_and_history(self):
        # One synthetic vehicle inside configured ID 2; another outside both.
        done, matched = self.detect_and_publish([
            (5, 5, 15, 15, 0.9),
            (85, 60, 95, 70, 0.8),
        ])
        self.assertTrue(done)
        self.assertEqual(matched, [0, None])

        current = self.client.get("/api/status/camera_1")
        self.assertEqual(current.status_code, 200)
        self.assertEqual(current.get_json(), {
            "cars_detected": 2,
            "vehicles_in_spaces": 1,
            "vehicles_outside_spaces": 1,
            "parking_spaces": [
                {"id": 2, "occupied": True},
                {"id": 7, "occupied": False},
            ],
        })

        self.assertEqual(self.repo.lot_summary("lot1")["occupied_spaces"], 1)
        self.assertEqual(self.repo.lot_summary("lot1")["available_spaces"], 1)
        self.assertEqual(
            self.repo.space_history("lot1", "2")[0]["status"], "OCCUPIED"
        )
        self.assertEqual(
            self.repo.space_history("lot1", "7")[0]["status"], "AVAILABLE"
        )

        history = self.client.get("/api/history/lot1/2")
        self.assertEqual(history.status_code, 200)
        self.assertEqual(history.get_json()["records"][0]["status"], "OCCUPIED")

        trend = self.client.get("/api/trends/lot1?days=7")
        self.assertEqual(trend.status_code, 200)
        hour = next(
            item for item in trend.get_json()["hourly"]
            if item["hour_utc"] == self.when.hour
        )
        self.assertEqual(hour["observations"], 2)
        self.assertEqual(hour["occupied_observations"], 1)
        self.assertEqual(hour["occupied_percent"], 50.0)

    def test_missing_observations_do_not_create_false_open_spaces(self):
        self.assertEqual(self.client.get("/api/status/camera_1").status_code, 503)
        self.assertEqual(self.repo.lot_summary("lot1")["spaces_with_current_state"], 0)
        trends = self.client.get("/api/trends/lot1")
        self.assertFalse(trends.get_json()["has_history"])
        self.assertEqual(trends.get_json()["hourly"], [])

    def test_camera_read_failure_invalidates_live_but_keeps_history(self):
        self.detect_and_publish([(5, 5, 15, 15, 0.9)])
        self.assertEqual(self.client.get("/api/status/camera_1").status_code, 200)
        invalidate_camera_status("camera_1", self.live, self.lock)
        self.assertEqual(self.client.get("/api/status/camera_1").status_code, 503)
        self.assertEqual(len(self.repo.space_history("lot1", "2")), 1)

    def test_rejected_snapshot_cannot_publish_or_corrupt_history(self):
        self.detect_and_publish([(5, 5, 15, 15, 0.9)])
        before = len(self.repo.space_history("lot1", "2"))
        with self.assertRaises(ValueError):
            publish_space_result(
                "camera_1",
                [{"id": 2, "open": False}, {"id": 999, "open": True}],
                1, 1, 0,
                repository=self.repo, newly_inferred=True,
                latest_status=self.live, status_lock=self.lock,
                observed_at=self.when,
            )
        self.assertEqual(self.client.get("/api/status/camera_1").status_code, 503)
        self.assertEqual(len(self.repo.space_history("lot1", "2")), before)


if __name__ == "__main__":
    unittest.main()
