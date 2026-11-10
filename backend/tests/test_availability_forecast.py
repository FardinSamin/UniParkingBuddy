"""Forecast unit/API contract tests: every scenario explicitly synthetic.

No database, live camera, accuracy claim or trained model is involved.
"""

from datetime import date, datetime, timezone
from threading import Lock
from unittest import TestCase
from unittest.mock import Mock, patch

from fastapi.testclient import TestClient

from backend.availability_forecast import (
    demo_estimate, forecast_response, historical_estimate, parse_target,
)
from backend.status_api import create_status_app


NOW = datetime(2026, 11, 10, 15, 0, tzinfo=timezone.utc)
TARGET = "2026-11-11T14:00"


def configuration(ids):
    return {
        "config": {
            "version": 1,
            "next_space_id": max(ids) + 1,
            "spaces": [
                {"id": identifier, "points": []}
                for identifier in ids
            ],
        }
    }


def daily_profile(day, occupied, snapshots=1):
    return {
        "local_date": date(2026, 10, day),
        "weekday": 2,
        "hour": 14,
        "occupied_share": occupied,
        "snapshots": snapshots,
    }


class ForecastClockTests(TestCase):
    def test_future_wall_clock_uses_campus_timezone_not_device_timezone(self):
        target = parse_target(TARGET, now=NOW)
        self.assertEqual(target.isoformat(), "2026-11-11T14:00:00-05:00")
        self.assertEqual(target.weekday(), 2)

    def test_bad_values_are_rejected(self):
        for value in (
            "", "2026-11-11", "2026-11-11T25:00", "2026-11-11T14:00Z",
            "2026-11-11T14:00-05:00", "2026-11-11T14:00:00",
            "not-a-date", "2026-11-10T09:00", "2026-12-01T14:00",
            "２０２６-11-11T14:00",
        ):
            with self.subTest(value=value), self.assertRaises(ValueError):
                parse_target(value, now=NOW)

    def test_daylight_saving_gaps_and_folds_are_explicitly_rejected(self):
        with self.assertRaisesRegex(ValueError, "daylight-saving"):
            parse_target("2027-03-14T02:30", now=datetime(2027, 3, 13, tzinfo=timezone.utc))
        with self.assertRaisesRegex(ValueError, "daylight-saving"):
            parse_target("2026-11-01T01:30", now=datetime(2026, 10, 31, tzinfo=timezone.utc))

    def test_demo_is_deterministic_bounded_and_changes_by_time(self):
        early = parse_target("2026-11-11T08:00", now=NOW)
        midday = parse_target(TARGET, now=NOW)
        first = demo_estimate("lot1", "Lot 1", 139, midday)
        self.assertEqual(first, demo_estimate("lot1", "Lot 1", 139, midday))
        self.assertEqual(first["status"], "illustrative")
        self.assertEqual(first["estimated_available"] + first["estimated_occupied"], 139)
        self.assertEqual(first["historical_days"], 0)
        self.assertNotEqual(
            first["estimated_available"],
            demo_estimate("lot1", "Lot 1", 139, early)["estimated_available"],
        )

    def test_demo_never_calls_history_provider(self):
        persistence = Mock()
        configured = [
            ("lot1", "Lot 1", "camera_1", list(range(1, 140)), None),
            ("lot2", "Lot 2", "camera_2", list(range(1, 58)), None),
            ("lot3", "Lot 3", "camera_3", list(range(1, 70)), None),
        ]
        result = forecast_response(
            configured, parse_target(TARGET, now=NOW), "demo",
            history_provider=persistence, now=NOW,
        )
        self.assertEqual([lot["total_spaces"] for lot in result["lots"]], [139, 57, 69])
        self.assertEqual(result["source"], "synthetic_demo")
        persistence.assert_not_called()
        persistence.forecast_hourly_profiles.assert_not_called()


class HistoricalBaselineTests(TestCase):
    def test_day_balanced_mean_uses_matching_weekday_hour_only(self):
        profiles = [
            daily_profile(21, 0.0, snapshots=100),  # many readings on one day
            daily_profile(28, 1.0, snapshots=1),
            daily_profile(14, 0.5, snapshots=2),
            {"local_date": date(2026, 10, 20), "weekday": 1,
             "hour": 14, "occupied_share": 1.0, "snapshots": 99},
        ]
        out = historical_estimate(
            "lot2", "Lot 2", 60, parse_target(TARGET, now=NOW), profiles
        )
        self.assertEqual(out["status"], "historical_estimate")
        self.assertEqual(out["historical_days"], 3)
        self.assertEqual(out["historical_snapshots"], 103)
        self.assertEqual(out["estimated_occupied"], 30)
        self.assertEqual(out["estimated_available"], 30)

    def test_two_days_returns_null_not_fake_zero_availability(self):
        out = historical_estimate(
            "lot2", "Lot 2", 57, parse_target(TARGET, now=NOW),
            [daily_profile(21, 1.0), daily_profile(28, 0.0)],
        )
        self.assertEqual(out["status"], "insufficient_history")
        self.assertEqual(out["historical_days"], 2)
        self.assertIsNone(out["estimated_available"])
        self.assertIsNone(out["estimated_open_percent"])

    def test_duplicate_days_refused_as_independent_evidence(self):
        with self.assertRaisesRegex(ValueError, "Duplicate"):
            historical_estimate(
                "lot1", "Lot 1", 139, parse_target(TARGET, now=NOW),
                [daily_profile(21, 0.1), daily_profile(21, 0.2)],
            )

    def test_only_explicit_history_provider_can_return_real_estimate(self):
        with self.assertRaises(PermissionError):
            forecast_response(
                [("lot1", "Lot 1", "camera_1", [1], None)],
                parse_target(TARGET, now=NOW), "historical", now=NOW,
            )


class ForecastApiTests(TestCase):
    def setUp(self):
        self.provider = Mock()
        self.provider.forecast_hourly_profiles.return_value = [
            daily_profile(21, 0.0),
            daily_profile(28, 1.0),
            daily_profile(14, 0.5),
        ]
        captures = {
            "camera_1": configuration([1, 2, 3]),
            "camera_2": configuration([1, 2]),
            "camera_3": configuration([1]),
        }
        self.client = TestClient(create_status_app(captures, {}, Lock(), self.provider))
        self.path = "/api/forecast?at=2026-11-11T14%3A00"

    def test_demo_available_without_history_and_no_write_routes(self):
        with patch.dict("os.environ", {}, clear=True):
            response = self.client.get(self.path)
            self.assertEqual(response.status_code, 200)
            body = response.json()
            self.assertEqual(body["mode"], "demo")
            self.assertEqual(body["source"], "synthetic_demo")
            self.assertFalse(body["historical_enabled"])
            self.assertEqual([lot["lot_id"] for lot in body["lots"]], ["lot1", "lot2", "lot3"])
            self.assertEqual(sum(lot["total_spaces"] for lot in body["lots"]), 6)
            for lot in body["lots"]:
                self.assertEqual(lot["status"], "illustrative")
                self.assertEqual(lot["estimated_occupied"] + lot["estimated_available"],
                                 lot["total_spaces"])
            self.provider.forecast_hourly_profiles.assert_not_called()
            self.assertEqual(self.client.post("/api/forecast", json={}).status_code, 405)

    def test_historical_disabled_without_deliberate_operator_flag(self):
        with patch.dict("os.environ", {}, clear=True):
            response = self.client.get(self.path + "&mode=historical")
        self.assertEqual(response.status_code, 503)
        self.assertNotIn("password", response.text)
        self.provider.forecast_hourly_profiles.assert_not_called()

    def test_trusted_history_opt_in_then_calls_read_only_provider(self):
        with patch.dict("os.environ", {"PARKING_FORECAST_TRUSTED_HISTORY": "1"}):
            res = self.client.get(self.path + "&mode=historical")
        self.assertEqual(res.status_code, 200)
        body = res.json()
        self.assertEqual(body["source"], "verified_history")
        self.assertTrue(body["historical_enabled"])
        self.assertTrue(all(lot["historical_days"] == 3 for lot in body["lots"]))
        self.assertTrue(all(lot["status"] == "historical_estimate" for lot in body["lots"]))
        self.assertEqual(self.provider.forecast_hourly_profiles.call_count, 3)

    def test_no_db_means_historical_unavailable_even_with_flag(self):
        client = TestClient(create_status_app(
            {"camera_1": configuration([1])}, {}, Lock(), persistence=None
        ))
        with patch.dict("os.environ", {"PARKING_FORECAST_TRUSTED_HISTORY": "1"}):
            self.assertEqual(
                client.get(self.path + "&mode=historical").status_code, 503
            )
            self.assertEqual(client.get(self.path).status_code, 200)

    def test_validation_errors_have_no_storage_side_effects(self):
        with patch.dict("os.environ", {}, clear=True):
            self.assertEqual(self.client.get("/api/forecast?at=bad").status_code, 400)
            self.assertEqual(self.client.get(self.path + "&mode=anything").status_code, 400)
            self.assertEqual(self.client.get("/api/forecast").status_code, 400)
        self.provider.forecast_hourly_profiles.assert_not_called()

    def test_provider_failure_does_not_leak_credentials(self):
        self.provider.forecast_hourly_profiles.side_effect = RuntimeError(
            "password=very-secret"
        )
        with patch.dict("os.environ", {"PARKING_FORECAST_TRUSTED_HISTORY": "1"}):
            res = self.client.get(self.path + "&mode=historical")
        self.assertEqual(res.status_code, 503)
        self.assertNotIn("very-secret", res.text)


if __name__ == "__main__":
    import unittest
    unittest.main()
