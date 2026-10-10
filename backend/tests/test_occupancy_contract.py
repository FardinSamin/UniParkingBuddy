"""Strict trusted CV/backend occupancy contract: never corrupt previous data."""

from datetime import datetime, timezone
import unittest
from unittest.mock import Mock

from pydantic import ValidationError

from backend.occupancy_contract import (
    OccupancyUpdate, accept_occupancy_update, snapshot_from_cv,
)
from backend.occupancy_writer import CAMERA_LOTS


class OccupancyContractTests(unittest.TestCase):
    def setUp(self):
        self.repo = Mock()
        self.at = datetime(2026, 10, 10, 12, 0, tzinfo=timezone.utc)
        self.valid = {
            "lot_id": "lot1",
            "observed_at": self.at,
            "spaces": [
                {"space_id": "1", "status": "AVAILABLE"},
                {"space_id": "7", "status": "OCCUPIED"},
            ],
        }

    def test_valid_timestamped_snapshot_commits_exactly_one_batch(self):
        result = accept_occupancy_update(self.repo, self.valid)
        self.assertIsInstance(result, OccupancyUpdate)
        self.repo.record_observations.assert_called_once_with(
            "lot1",
            [{"space_id": "1", "status": "AVAILABLE"},
             {"space_id": "7", "status": "OCCUPIED"}],
            self.at,
        )

    def test_unknown_payload_keys_cannot_be_saved(self):
        for extra in (
            {"person_id": "a"},
            {"video_data": "raw"},
            {"plate_number": "abc"},
        ):
            self.repo.reset_mock()
            with self.subTest(extra=extra):
                with self.assertRaises(ValidationError):
                    accept_occupancy_update(self.repo, {**self.valid, **extra})
                self.repo.record_observations.assert_not_called()

    def test_naive_timestamp_is_rejected_without_touching_history(self):
        payload = {**self.valid, "observed_at": datetime(2026, 10, 10, 12)}
        with self.assertRaises(ValidationError):
            accept_occupancy_update(self.repo, payload)
        self.repo.record_observations.assert_not_called()

    def test_missing_snapshot_fields_are_rejected(self):
        for key in ("lot_id", "observed_at", "spaces"):
            with self.subTest(key=key):
                with self.assertRaises(ValidationError):
                    accept_occupancy_update(
                        self.repo, {k: v for k, v in self.valid.items() if k != key}
                    )
        self.repo.record_observations.assert_not_called()

    def test_invalid_domain_status_rejected(self):
        for value in ("UNKNOWN", "PARKING", None, True, 0):
            with self.subTest(value=value):
                payload = {**self.valid, "spaces": [
                    {"space_id": "1", "status": value},
                ]}
                with self.assertRaises(ValidationError):
                    accept_occupancy_update(self.repo, payload)
        self.repo.record_observations.assert_not_called()

    def test_duplicate_space_ids_rejected(self):
        payload = {**self.valid, "spaces": [
            {"space_id": "1", "status": "AVAILABLE"},
            {"space_id": "1", "status": "OCCUPIED"},
        ]}
        with self.assertRaises(ValidationError):
            accept_occupancy_update(self.repo, payload)
        self.repo.record_observations.assert_not_called()

    def test_noncanonical_space_ids_rejected(self):
        for value in ("0", "01", "-1", "+1", " 1", "", "1 "):
            with self.subTest(value=value):
                payload = {**self.valid, "spaces": [
                    {"space_id": value, "status": "AVAILABLE"},
                ]}
                with self.assertRaises(ValidationError):
                    accept_occupancy_update(self.repo, payload)
        self.repo.record_observations.assert_not_called()

    def test_empty_or_invalid_snapshot_is_rejected(self):
        for snapshot in (
            {**self.valid, "spaces": []},
            {**self.valid, "spaces": "oops"},
            {**self.valid, "lot_id": " "},
            {**self.valid, "lot_id": None},
        ):
            with self.subTest(snapshot=snapshot):
                with self.assertRaises(ValidationError):
                    accept_occupancy_update(self.repo, snapshot)
        self.repo.record_observations.assert_not_called()

    def test_cv_bool_conversion_matches_domain_states_and_lot(self):
        snapshot = snapshot_from_cv(
            "camera_2", [{"id": 2, "open": True}, {"id": 7, "open": False}],
            self.at, CAMERA_LOTS,
        )
        self.assertEqual(snapshot.lot_id, "lot2")
        self.assertEqual(
            [s.model_dump() for s in snapshot.spaces],
            [{"space_id": "2", "status": "AVAILABLE"},
             {"space_id": "7", "status": "OCCUPIED"}],
        )
        self.assertEqual(snapshot.observed_at, self.at)

    def test_cv_duplicate_or_nonboolean_fails_pre_database(self):
        for spaces in (
            [{"id": 1, "open": True}, {"id": 1, "open": False}],
            [{"id": 1, "open": 1}],
            [{"id": True, "open": False}],
            [],
            [{"id": 1, "open": False, "person_id": "x"}],
        ):
            with self.subTest(spaces=spaces):
                with self.assertRaises(ValueError):
                    snapshot_from_cv("camera_1", spaces, self.at, CAMERA_LOTS)

    def test_cv_timestamp_requires_timezone(self):
        with self.assertRaises(ValidationError):
            snapshot_from_cv(
                "camera_1", [{"id": 1, "open": False}],
                datetime(2026, 10, 10, 12), CAMERA_LOTS,
            )

    def test_repository_failure_never_reports_success(self):
        self.repo.record_observations.side_effect = ValueError("Unknown configured space")
        with self.assertRaisesRegex(ValueError, "Unknown configured space"):
            accept_occupancy_update(self.repo, self.valid)
        self.assertEqual(self.repo.record_observations.call_count, 1)


if __name__ == "__main__":
    unittest.main()
