"""Read-only history endpoint tests; no external database required."""

from datetime import datetime, timezone
from threading import Lock
from unittest import TestCase
from unittest.mock import Mock

from fastapi.testclient import TestClient

from backend.status_api import create_status_app


class HistoryApiTests(TestCase):
    def setUp(self):
        self.repository = Mock()
        self.repository.lot_spaces.return_value = ["1", "7"]
        self.repository.hourly_occupancy_trends.return_value = [
            {"hour_utc": 13, "observations": 4, "occupied_observations": 3,
             "occupied_percent": 75.0}
        ]
        self.repository.space_history.return_value = [
            {"status": "OCCUPIED",
             "observed_at": datetime(2026, 10, 10, 13, 0, tzinfo=timezone.utc)}
        ]
        app = create_status_app({"camera_1": object()}, {}, Lock(), self.repository)
        self.client = TestClient(app)

    def test_trend_has_sample_counts_and_utc_label_not_prediction(self):
        response = self.client.get("/api/trends/lot1")
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["days"], 7)
        self.assertEqual(body["timezone"], "UTC")
        self.assertEqual(body["space_ids"], ["1", "7"])
        self.assertTrue(body["has_history"])
        self.assertEqual(body["hourly"][0]["occupied_percent"], 75.0)
        self.assertIn("not parked duration or prediction", body["basis"])
        self.repository.hourly_occupancy_trends.assert_called_once_with("lot1", 7)

    def test_requested_31_day_window_is_forwarded(self):
        response = self.client.get("/api/trends/lot1?days=31")
        self.assertEqual(response.status_code, 200)
        self.repository.hourly_occupancy_trends.assert_called_with("lot1", 31)

    def test_invalid_or_out_of_range_day_filters_are_rejected(self):
        for value in ("0", "32", "1.5", "-1", "abc", "2%20days", "１２"):
            with self.subTest(value=value):
                self.assertEqual(
                    self.client.get("/api/trends/lot1?days=" + value).status_code,
                    400,
                )
        self.repository.hourly_occupancy_trends.reset_mock()
        self.assertEqual(
            self.client.get("/api/trends/lot1?days=0").status_code, 400
        )
        self.repository.hourly_occupancy_trends.assert_not_called()

    def test_unconfigured_lot_is_not_invented(self):
        self.repository.lot_spaces.return_value = None
        self.assertEqual(self.client.get("/api/trends/not_here").status_code, 404)
        self.repository.hourly_occupancy_trends.assert_not_called()

    def test_zero_history_is_explicit_not_zero_occupancy(self):
        self.repository.hourly_occupancy_trends.return_value = []
        response = self.client.get("/api/trends/lot1")
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json()["has_history"])
        self.assertEqual(response.json()["hourly"], [])

    def test_space_history_is_bounded_and_has_iso_timestamps(self):
        response = self.client.get("/api/history/lot1/7")
        self.assertEqual(response.status_code, 200)
        self.repository.space_history.assert_called_once_with(
            "lot1", "7", limit=100
        )
        body = response.json()
        self.assertTrue(body["has_history"])
        self.assertEqual(body["records"][0]["status"], "OCCUPIED")
        self.assertEqual(body["records"][0]["observed_at"], "2026-10-10T13:00:00+00:00")

    def test_unknown_space_is_404(self):
        self.assertEqual(self.client.get("/api/history/lot1/999").status_code, 404)
        self.repository.space_history.assert_not_called()

    def test_no_space_history_is_explicit(self):
        self.repository.space_history.return_value = []
        response = self.client.get("/api/history/lot1/1")
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json()["has_history"])

    def test_database_errors_are_safe_and_return_unavailable(self):
        self.repository.hourly_occupancy_trends.side_effect = RuntimeError("password=secret")
        response = self.client.get("/api/trends/lot1")
        self.assertEqual(response.status_code, 503)
        self.assertNotIn("secret", response.text)

    def test_database_not_configured_is_unavailable_not_empty(self):
        app = create_status_app({}, {}, Lock(), persistence=None)
        client = TestClient(app)
        self.assertEqual(client.get("/api/trends/lot1").status_code, 503)
        self.assertEqual(client.get("/api/history/lot1/1").status_code, 503)
