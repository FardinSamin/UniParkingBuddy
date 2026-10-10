"""Configured monitored lots/spaces API contract: availability never fabricated."""

import threading
import unittest

from fastapi.testclient import TestClient

from backend.status_api import create_status_app


def camera(ids):
    return {"config": {
        "version": 1, "next_space_id": max(ids, default=0) + 1,
        "spaces": [{"id": identifier, "points": []} for identifier in ids],
    }}


def result(ids):
    return {
        "cars": 1,
        "in_space_vehicles": 1,
        "outside_space_vehicles": 0,
        "spaces": [{"id": identifier, "open": identifier != 2} for identifier in ids],
    }


class ConfiguredLotsApiTests(unittest.TestCase):
    def setUp(self):
        self.cameras = {"camera_1": camera([1, 2]), "camera_2": camera([3])}
        self.live = {}
        self.lock = threading.Lock()
        self.app = create_status_app(self.cameras, self.live, self.lock)
        self.client = TestClient(self.app)

    def test_two_monitored_lots_only_and_no_fake_current_counts(self):
        response = self.client.get("/api/lots")
        self.assertEqual(response.status_code, 200)
        lots = response.json()["lots"]
        self.assertEqual([lot["lot_id"] for lot in lots], ["lot1", "lot2"])
        self.assertEqual([lot["camera"] for lot in lots], ["camera_1", "camera_2"])
        self.assertEqual(lots[0]["space_ids"], [1, 2])
        self.assertEqual(lots[0]["total_spaces"], 2)
        self.assertFalse(lots[0]["has_current_data"])
        self.assertIsNone(lots[0]["available_spaces"])
        self.assertIsNone(lots[0]["occupied_spaces"])
        self.assertNotIn("lot3", str(lots))

    def test_configured_space_list_is_available_before_first_cv_result(self):
        response = self.client.get("/api/lots/lot1/spaces")
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertFalse(body["has_current_data"])
        self.assertEqual(body["spaces"], [
            {"id": 1, "occupied": None},
            {"id": 2, "occupied": None},
        ])

    def test_valid_current_result_populates_summary_and_space_values(self):
        with self.lock:
            self.live["camera_1"] = result([1, 2])
        summary = self.client.get("/api/lots").json()["lots"][0]
        self.assertTrue(summary["has_current_data"])
        self.assertEqual(summary["available_spaces"], 1)
        self.assertEqual(summary["occupied_spaces"], 1)
        status = self.client.get("/api/lots/lot1/spaces").json()
        self.assertEqual(status["spaces"], [
            {"id": 1, "occupied": False},
            {"id": 2, "occupied": True},
        ])

    def test_true_full_lot_is_not_confused_with_unavailable(self):
        self.live["camera_1"] = {
            "spaces": [{"id": 1, "open": False}, {"id": 2, "open": False}],
        }
        full = self.client.get("/api/lots").json()["lots"][0]
        self.assertTrue(full["has_current_data"])
        self.assertEqual((full["available_spaces"], full["occupied_spaces"]), (0, 2))
        self.live.clear()
        unavailable = self.client.get("/api/lots").json()["lots"][0]
        self.assertFalse(unavailable["has_current_data"])
        self.assertIsNone(unavailable["available_spaces"])

    def test_partial_or_mismatched_results_are_not_trusted(self):
        for invalid in (
            [{"id": 1, "open": True}],
            [{"id": 1, "open": True}, {"id": 1, "open": False}],
            [{"id": 1, "open": True}, {"id": 999, "open": False}],
            [{"id": 1, "open": "yes"}, {"id": 2, "open": False}],
        ):
            with self.subTest(value=invalid):
                self.live["camera_1"] = {"spaces": invalid}
                lot = self.client.get("/api/lots").json()["lots"][0]
                self.assertFalse(lot["has_current_data"])
                self.assertIsNone(lot["occupied_spaces"])

    def test_inactive_camera_disappears_from_public_lot_list(self):
        self.cameras.pop("camera_1")
        lots = self.client.get("/api/lots").json()["lots"]
        self.assertEqual([lot["lot_id"] for lot in lots], ["lot2"])
        self.assertEqual(self.client.get("/api/lots/lot1/spaces").status_code, 404)

    def test_unknown_lot_has_explicit_404(self):
        response = self.client.get("/api/lots/lot3/spaces")
        self.assertEqual(response.status_code, 404)
        self.assertIn("error", response.json())

    def test_public_configured_lots_api_is_read_only(self):
        for path in ("/api/lots", "/api/lots/lot1/spaces", "/api/status/camera_1"):
            with self.subTest(path=path):
                self.assertEqual(self.client.post(path, json={}).status_code, 405)
        self.assertEqual(self.live, {})

    def test_openapi_documents_both_read_contracts(self):
        paths = self.client.get("/openapi.json").json()["paths"]
        self.assertIn("/api/lots", paths)
        self.assertIn("/api/lots/{lot_id}/spaces", paths)
        self.assertEqual(set(paths["/api/lots"]), {"get"})
        self.assertEqual(set(paths["/api/lots/{lot_id}/spaces"]), {"get"})


if __name__ == "__main__":
    unittest.main()
