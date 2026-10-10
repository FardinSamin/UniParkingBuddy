"""Actual PostgreSQL integration tests for the approved occupancy schema.

Only a disposable database NAMED uniparkingbuddy_test is accepted. The tests
truncate it between cases and must never run against an application database.
"""

import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
import unittest

import psycopg

from backend.occupancy_repository import OccupancyRepository, SCHEMA_PATH
from backend.occupancy_writer import persist_processed_observation


def sample_config():
    return {
        "version": 1,
        "next_space_id": 8,
        "spaces": [
            {"id": 2, "points": [[0, 0], [10, 0], [10, 10], [0, 10]]},
            {"id": 7, "points": [[20, 0], [30, 0], [30, 10], [20, 10]]},
        ],
    }


class PostgreSQLRepositoryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dsn = os.environ.get("TEST_DATABASE_URL")
        if not cls.dsn:
            raise unittest.SkipTest("TEST_DATABASE_URL is not set")
        with psycopg.connect(cls.dsn) as conn:
            name = conn.execute("SELECT current_database()").fetchone()[0]
            if name != "uniparkingbuddy_test":
                raise RuntimeError(
                    "Refusing to run destructive integration tests on a non-test database"
                )
            if conn.execute("SELECT to_regclass('parking_lot')").fetchone()[0] is None:
                conn.execute(SCHEMA_PATH.read_text(encoding="utf-8"))
        cls.repository = OccupancyRepository(cls.dsn)

    def setUp(self):
        # Only the strictly verified disposable test database is cleaned.
        with psycopg.connect(self.dsn) as conn:
            conn.execute(
                "TRUNCATE occupancy_record, parking_space_region, parking_space, "
                "parking_lot RESTART IDENTITY"
            )

    def register(self):
        self.repository.register_lot_configuration("lot1", "Lot 1", sample_config())

    def test_four_tables_and_two_state_enum_exist(self):
        with psycopg.connect(self.dsn) as conn:
            names = conn.execute(
                """
                SELECT tablename FROM pg_tables
                WHERE schemaname = current_schema()
                  AND tablename IN (
                      'parking_lot', 'parking_space',
                      'parking_space_region', 'occupancy_record'
                  )
                """
            ).fetchall()
            self.assertEqual(len(names), 4)
            values = conn.execute(
                """
                SELECT enumlabel
                FROM pg_enum
                WHERE enumtypid = 'occupancy_status'::regtype
                ORDER BY enumsortorder
                """
            ).fetchall()
            self.assertEqual([row[0] for row in values], ["AVAILABLE", "OCCUPIED"])

    def test_new_spaces_have_no_current_occupancy(self):
        self.register()
        summary = self.repository.lot_summary("lot1")
        self.assertEqual(summary["total_spaces"], 2)
        self.assertEqual(summary["spaces_with_current_state"], 0)
        self.assertEqual(summary["available_spaces"], 0)
        self.assertEqual(summary["occupied_spaces"], 0)
        self.assertFalse(summary["complete"])

    def test_missing_lot_does_not_report_complete_availability(self):
        summary = self.repository.lot_summary("not-configured")
        self.assertEqual(summary["total_spaces"], 0)
        self.assertFalse(summary["complete"])

    def test_stable_ids_and_regions_are_persisted(self):
        self.register()
        with psycopg.connect(self.dsn) as conn:
            rows = conn.execute(
                """
                SELECT space_id, region_definition
                FROM parking_space_region
                WHERE lot_id = 'lot1'
                ORDER BY space_id
                """
            ).fetchall()
        self.assertEqual(rows[0][0], "2")
        self.assertEqual(rows[1][0], "7")
        self.assertEqual(rows[0][1]["points"][0], [0, 0])

    def test_atomic_snapshot_updates_current_and_history(self):
        self.register()
        observed = datetime(2026, 10, 10, 1, 0, tzinfo=timezone.utc)
        self.repository.record_observations("lot1", [
            {"space_id": "2", "status": "AVAILABLE"},
            {"space_id": "7", "status": "OCCUPIED"},
        ], observed)
        summary = self.repository.lot_summary("lot1")
        self.assertEqual(summary["available_spaces"], 1)
        self.assertEqual(summary["occupied_spaces"], 1)
        self.assertTrue(summary["complete"])
        self.assertEqual(self.repository.space_history("lot1", "7"), [
            {"status": "OCCUPIED", "observed_at": observed},
        ])
        with psycopg.connect(self.dsn) as conn:
            self.assertEqual(
                conn.execute("SELECT COUNT(*) FROM occupancy_record").fetchone()[0], 2
            )

    def test_newer_current_state_does_not_get_overwritten_by_old_result(self):
        self.register()
        first = datetime(2026, 10, 10, 1, 0, tzinfo=timezone.utc)
        newer = first + timedelta(minutes=2)
        older = first + timedelta(minutes=1)
        self.repository.record_observations(
            "lot1", [{"space_id": "2", "status": "AVAILABLE"}], newer
        )
        self.repository.record_observations(
            "lot1", [{"space_id": "2", "status": "OCCUPIED"}], older
        )
        with psycopg.connect(self.dsn) as conn:
            status, at = conn.execute(
                """
                SELECT current_status, current_status_at
                FROM parking_space WHERE lot_id = 'lot1' AND space_id = '2'
                """
            ).fetchone()
        self.assertEqual(status, "AVAILABLE")
        self.assertEqual(at, newer)
        self.assertEqual(
            [item["status"] for item in self.repository.space_history("lot1", "2")],
            ["AVAILABLE", "OCCUPIED"],
        )

    def test_unknown_space_rolls_back_entire_snapshot(self):
        self.register()
        with self.assertRaises(ValueError):
            self.repository.record_observations("lot1", [
                {"space_id": "2", "status": "AVAILABLE"},
                {"space_id": "999", "status": "OCCUPIED"},
            ], datetime.now(timezone.utc))
        with psycopg.connect(self.dsn) as conn:
            count = conn.execute("SELECT COUNT(*) FROM occupancy_record").fetchone()[0]
        self.assertEqual(count, 0)
        self.assertFalse(self.repository.lot_summary("lot1")["complete"])

    def test_invalid_status_does_not_mutate_database(self):
        self.register()
        with self.assertRaises(ValueError):
            self.repository.record_observations("lot1", [
                {"space_id": "2", "status": "UNKNOWN"},
            ], datetime.now(timezone.utc))
        self.assertEqual(self.repository.space_history("lot1", "2"), [])

    def test_duplicate_snapshot_space_rejected(self):
        self.register()
        with self.assertRaises(ValueError):
            self.repository.record_observations("lot1", [
                {"space_id": "2", "status": "OCCUPIED"},
                {"space_id": "2", "status": "AVAILABLE"},
            ], datetime.now(timezone.utc))
        self.assertEqual(self.repository.space_history("lot1", "2"), [])

    def test_naive_timestamp_is_rejected(self):
        self.register()
        with self.assertRaises(ValueError):
            self.repository.record_observations("lot1", [
                {"space_id": "2", "status": "OCCUPIED"},
            ], datetime(2026, 10, 10, 1, 0))
        self.assertEqual(self.repository.space_history("lot1", "2"), [])

    def test_registration_again_preserves_history(self):
        self.register()
        self.repository.record_observations(
            "lot1", [{"space_id": "2", "status": "OCCUPIED"}],
            datetime.now(timezone.utc),
        )
        self.register()
        self.assertEqual(len(self.repository.space_history("lot1", "2")), 1)
        self.assertEqual(self.repository.lot_summary("lot1")["occupied_spaces"], 1)

    def test_registration_does_not_implicitly_remove_historical_spaces(self):
        self.register()
        fewer = {
            "version": 1,
            "next_space_id": 8,
            "spaces": [sample_config()["spaces"][1]],
        }
        with self.assertRaises(ValueError):
            self.repository.register_lot_configuration("lot1", "Lot 1", fewer)
        self.assertEqual(self.repository.lot_summary("lot1")["total_spaces"], 2)

    def test_two_lots_keep_same_space_id_separate(self):
        self.register()
        self.repository.register_lot_configuration("lot2", "Lot 2", {
            "version": 1, "next_space_id": 3,
            "spaces": [sample_config()["spaces"][0]],
        })
        at = datetime.now(timezone.utc)
        self.repository.record_observations(
            "lot1", [{"space_id": "2", "status": "AVAILABLE"}], at
        )
        self.repository.record_observations(
            "lot2", [{"space_id": "2", "status": "OCCUPIED"}], at
        )
        self.assertEqual(self.repository.lot_summary("lot1")["available_spaces"], 1)
        self.assertEqual(self.repository.lot_summary("lot2")["occupied_spaces"], 1)


    def test_processed_cv_result_flows_into_persisted_history(self):
        self.register()
        at = datetime.now(timezone.utc)
        persist_processed_observation(
            self.repository, "camera_1",
            [{"id": 2, "open": False}, {"id": 7, "open": True}],
            at,
        )
        self.assertEqual(
            self.repository.lot_summary("lot1")["occupied_spaces"], 1
        )
        self.assertEqual(
            self.repository.space_history("lot1", "2")[0],
            {"status": "OCCUPIED", "observed_at": at},
        )
        self.assertTrue(self.repository.lot_summary("lot1")["complete"])


if __name__ == "__main__":
    unittest.main()
