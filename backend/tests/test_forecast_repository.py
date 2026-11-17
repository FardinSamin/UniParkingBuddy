"""Read-only forecast profile integration against disposable PostgreSQL only.

No schema changes or production data modifications. Truncation happens solely
in the CI database explicitly named uniparkingbuddy_test.
"""

from datetime import datetime, timezone
import os
from zoneinfo import ZoneInfo
import unittest

import psycopg

from backend.occupancy_repository import OccupancyRepository, SCHEMA_PATH
from backend.availability_forecast import historical_estimate, parse_target


CAMPUS = ZoneInfo("America/New_York")
AS_OF = datetime(2026, 11, 10, 15, tzinfo=timezone.utc)


def simple_config():
    return {
        "version": 1,
        "next_space_id": 4,
        "spaces": [
            {"id": index, "points": [
                [index * 20, 0], [index * 20 + 10, 0],
                [index * 20 + 10, 10], [index * 20, 10],
            ]}
            for index in (1, 2, 3)
        ],
    }


@unittest.skipUnless(
    os.getenv("TEST_DATABASE_URL"),
    "Only test against the configured disposable PostgreSQL database",
)
class ForecastPostgreSQLTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dsn = os.environ["TEST_DATABASE_URL"]
        with psycopg.connect(cls.dsn) as connection:
            db = connection.execute("SELECT current_database()").fetchone()[0]
            if db != "uniparkingbuddy_test":
                raise RuntimeError("Refusing to modify a non-test database")
            if connection.execute("SELECT to_regclass('parking_lot')").fetchone()[0] is None:
                connection.execute(SCHEMA_PATH.read_text(encoding="utf-8"))
        cls.repository = OccupancyRepository(cls.dsn)

    def setUp(self):
        with psycopg.connect(self.dsn) as connection:
            connection.execute(
                "TRUNCATE occupancy_record, parking_space_region, "
                "parking_space, parking_lot RESTART IDENTITY"
            )
        self.repository.register_lot_configuration(
            "lot1", "Lot 1", simple_config()
        )

    def write(self, day, minute, occupied_ids, *, ids=(1, 2, 3), month=10):
        observed = datetime(2026, month, day, 14, minute, tzinfo=CAMPUS)
        self.repository.record_observations(
            "lot1", [
                {"space_id": str(space),
                 "status": "OCCUPIED" if space in occupied_ids else "AVAILABLE"}
                for space in ids
            ], observed,
        )

    def test_day_balancing_complete_snapshots_timezone_and_no_writes(self):
        self.write(21, 0, ())
        self.write(21, 15, (1, 2, 3))  # same day: half occupancy, not 2 days
        self.write(28, 0, (1, 2, 3))
        self.write(4, 0, (1,), month=11)  # after US Eastern DST change
        self.write(14, 0, (1,), ids=(1,))  # incomplete snapshot must be excluded
        self.write(11, 0, (1, 2, 3), month=11)  # after AS_OF, must be excluded

        with psycopg.connect(self.dsn) as connection:
            count_before = connection.execute(
                "SELECT COUNT(*) FROM occupancy_record"
            ).fetchone()[0]

        rows = self.repository.forecast_hourly_profiles(
            "lot1", as_of_utc=AS_OF, lookback_days=56, required_spaces=3
        )
        wednesdays = [r for r in rows if r["weekday"] == 2 and r["hour"] == 14]
        self.assertEqual(len(wednesdays), 3)
        self.assertEqual(
            [row["snapshots"] for row in wednesdays], [2, 1, 1]
        )
        self.assertAlmostEqual(wednesdays[0]["occupied_share"], .5)
        self.assertAlmostEqual(wednesdays[1]["occupied_share"], 1)
        self.assertAlmostEqual(wednesdays[2]["occupied_share"], 1 / 3)

        result = historical_estimate(
            "lot1", "Lot 1", 3,
            parse_target("2026-11-11T14:00", now=AS_OF),
            rows,
        )
        self.assertEqual(result["status"], "historical_estimate")
        self.assertEqual(result["historical_days"], 3)
        self.assertEqual(result["historical_snapshots"], 4)
        self.assertEqual(result["estimated_occupied"], 2)
        self.assertEqual(result["estimated_available"], 1)

        with psycopg.connect(self.dsn) as connection:
            count_after = connection.execute(
                "SELECT COUNT(*) FROM occupancy_record"
            ).fetchone()[0]
        self.assertEqual(count_before, count_after, "Forecast must never write records")

    def test_invalid_inputs_fail_and_unknown_lot_has_no_data(self):
        self.assertEqual(
            self.repository.forecast_hourly_profiles(
                "lot-not-configured", as_of_utc=AS_OF, required_spaces=3
            ), []
        )
        with self.assertRaises(ValueError):
            self.repository.forecast_hourly_profiles(
                "lot1", as_of_utc=AS_OF, required_spaces=0
            )
        with self.assertRaises(ValueError):
            self.repository.forecast_hourly_profiles(
                "lot1", as_of_utc=AS_OF.replace(tzinfo=None),
                required_spaces=3
            )


if __name__ == "__main__":
    unittest.main()
