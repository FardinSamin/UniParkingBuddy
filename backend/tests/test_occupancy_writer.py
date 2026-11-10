"""Unit tests for mapping fresh CV results to persistent occupancy history."""

from datetime import datetime, timezone
import unittest
from unittest.mock import Mock

from backend.occupancy_writer import (
    CAMERA_LOTS,
    initialize_lots,
    persist_processed_observation,
)


class OccupancyWriterTests(unittest.TestCase):
    def setUp(self):
        self.repository = Mock()
        self.when = datetime(2026, 10, 10, 1, 0, tzinfo=timezone.utc)

    def test_camera_lot_map_uses_existing_frontend_lots(self):
        self.assertEqual(CAMERA_LOTS["camera_1"][0], "lot1")
        self.assertEqual(CAMERA_LOTS["camera_2"][0], "lot2")

    def test_initialization_registers_configured_lots(self):
        cfg1 = {"spaces": [{"id": 1}]}
        cfg2 = {"spaces": [{"id": 2}]}
        initialize_lots(self.repository, {
            "camera_1": {"config": cfg1},
            "camera_2": {"config": cfg2},
        })
        self.assertEqual(self.repository.register_lot_configuration.call_count, 2)
        self.repository.register_lot_configuration.assert_any_call("lot1", "Lot 1", cfg1)
        self.repository.register_lot_configuration.assert_any_call("lot2", "Lot 2", cfg2)

    def test_valid_processed_spaces_convert_to_two_domain_states(self):
        persist_processed_observation(
            self.repository, "camera_1",
            [{"id": 2, "open": True}, {"id": 7, "open": False}],
            self.when,
        )
        self.repository.record_observations.assert_called_once_with(
            "lot1",
            [
                {"space_id": "2", "status": "AVAILABLE"},
                {"space_id": "7", "status": "OCCUPIED"},
            ],
            self.when,
        )

    def test_new_camera_two_writes_lot_two_not_lot_one(self):
        persist_processed_observation(
            self.repository, "camera_2", [{"id": 1, "open": False}], self.when
        )
        self.assertEqual(
            self.repository.record_observations.call_args.args[0], "lot2"
        )

    def test_unknown_camera_does_not_touch_database(self):
        with self.assertRaises(ValueError):
            persist_processed_observation(
                self.repository, "camera_99", [{"id": 1, "open": True}], self.when
            )
        self.repository.record_observations.assert_not_called()

    def test_empty_space_list_is_not_a_valid_snapshot(self):
        with self.assertRaises(ValueError):
            persist_processed_observation(self.repository, "camera_1", [], self.when)
        self.repository.record_observations.assert_not_called()

    def test_rejects_duplicate_configured_ids(self):
        with self.assertRaises(ValueError):
            persist_processed_observation(
                self.repository, "camera_1",
                [{"id": 3, "open": False}, {"id": 3, "open": True}], self.when
            )
        self.repository.record_observations.assert_not_called()

    def test_rejects_nonboolean_occupancy(self):
        with self.assertRaises(ValueError):
            persist_processed_observation(
                self.repository, "camera_1", [{"id": 1, "open": "yes"}], self.when
            )
        self.repository.record_observations.assert_not_called()

    def test_rejects_boolean_as_space_id(self):
        with self.assertRaises(ValueError):
            persist_processed_observation(
                self.repository, "camera_1", [{"id": True, "open": False}], self.when
            )
        self.repository.record_observations.assert_not_called()

    def test_database_error_is_not_silently_swallowed(self):
        self.repository.record_observations.side_effect = RuntimeError("DB failure")
        with self.assertRaisesRegex(RuntimeError, "DB failure"):
            persist_processed_observation(
                self.repository, "camera_1", [{"id": 1, "open": False}], self.when
            )


if __name__ == "__main__":
    unittest.main()
