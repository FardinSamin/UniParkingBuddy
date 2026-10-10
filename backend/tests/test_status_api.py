"""FastAPI contract tests without YOLO or OpenCV GUI startup."""

import threading
import unittest

from fastapi.testclient import TestClient

from backend.status_api import create_status_app, invalidate_camera_status


def processed_status():
    return {
        "cars": 2,
        "in_space_vehicles": 1,
        "outside_space_vehicles": 1,
        "spaces": [
            {"id": 2, "open": True},
            {"id": 7, "open": False},
        ],
    }


class StatusApiTests(unittest.TestCase):
    def setUp(self):
        self.cameras = {"camera_1": object()}
        self.status = {}
        self.lock = threading.Lock()
        self.app = create_status_app(self.cameras, self.status, self.lock)
        self.client = TestClient(self.app)

    def test_unrecognized_camera_returns_404(self):
        response = self.client.get("/api/status/camera_99")
        self.assertEqual(response.status_code, 404)
        self.assertIn("error", response.json())

    def test_active_camera_without_processed_frame_returns_503(self):
        response = self.client.get("/api/status/camera_1")
        self.assertEqual(response.status_code, 503)
        self.assertIn("not ready", response.json()["error"].lower())

    def test_empty_configured_spot_list_returns_503(self):
        self.status["camera_1"] = {
            "cars": 0, "in_space_vehicles": 0, "outside_space_vehicles": 0,
            "spaces": [],
        }
        response = self.client.get("/api/status/camera_1")
        self.assertEqual(response.status_code, 503)

    def test_valid_processed_status_preserves_space_ids(self):
        self.status["camera_1"] = processed_status()
        response = self.client.get("/api/status/camera_1")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {
            "cars_detected": 2,
            "vehicles_in_spaces": 1,
            "vehicles_outside_spaces": 1,
            "parking_spaces": [
                {"id": 2, "occupied": False},
                {"id": 7, "occupied": True},
            ],
        })

    def test_true_full_lot_is_allowed(self):
        self.status["camera_1"] = {
            "cars": 2, "in_space_vehicles": 2, "outside_space_vehicles": 0,
            "spaces": [
                {"id": 4, "open": False},
                {"id": 8, "open": False},
            ],
        }
        response = self.client.get("/api/status/camera_1")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(all(
            item["occupied"] for item in response.json()["parking_spaces"]
        ))

    def test_after_read_failure_status_becomes_unavailable(self):
        self.status["camera_1"] = processed_status()
        self.assertEqual(self.client.get("/api/status/camera_1").status_code, 200)
        invalidate_camera_status("camera_1", self.status, self.lock)
        self.assertEqual(self.client.get("/api/status/camera_1").status_code, 503)

    def test_after_camera_removal_status_returns_404(self):
        self.status["camera_1"] = processed_status()
        del self.cameras["camera_1"]
        invalidate_camera_status("camera_1", self.status, self.lock)
        self.assertEqual(self.client.get("/api/status/camera_1").status_code, 404)

    def test_new_processed_frame_replaces_unavailable_status(self):
        self.status["camera_1"] = processed_status()
        invalidate_camera_status("camera_1", self.status, self.lock)
        self.assertEqual(self.client.get("/api/status/camera_1").status_code, 503)
        self.status["camera_1"] = processed_status()
        self.assertEqual(self.client.get("/api/status/camera_1").status_code, 200)

    def test_invalidating_missing_camera_is_idempotent(self):
        invalidate_camera_status("camera_1", self.status, self.lock)
        self.assertEqual(self.status, {})


if __name__ == "__main__":
    unittest.main()
