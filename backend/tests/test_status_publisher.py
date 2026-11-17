"""Check live publication never invents occupancy after a failed write."""

from datetime import datetime, timezone
from threading import Lock
from unittest import TestCase
from unittest.mock import Mock

from backend.status_publisher import publish_space_result


class StatusPublisherTests(TestCase):
    def setUp(self):
        self.latest = {}
        self.lock = Lock()
        self.repo = Mock()
        self.when = datetime(2026, 10, 10, tzinfo=timezone.utc)
        self.spaces = [{"id": 1, "open": False}]

    def publish(self, repo, inferred=True, space_status=None):
        return publish_space_result(
            "camera_1", self.spaces if space_status is None else space_status,
            2, 1, 1,
            repository=repo, newly_inferred=inferred,
            latest_status=self.latest, status_lock=self.lock,
            observed_at=self.when,
        )

    def test_published_only_after_successful_database_transaction(self):
        self.assertTrue(self.publish(self.repo))
        self.repo.record_observations.assert_called_once()
        self.assertEqual(self.latest["camera_1"]["cars"], 2)

    def test_failed_write_retracts_old_status_and_raises(self):
        self.publish(self.repo)
        self.repo.record_observations.side_effect = RuntimeError("db disconnected")
        with self.assertRaisesRegex(RuntimeError, "disconnected"):
            self.publish(self.repo)
        self.assertNotIn("camera_1", self.latest)

    def test_cached_detection_frame_does_not_write_or_republish(self):
        self.publish(self.repo)
        self.repo.reset_mock()
        self.assertFalse(self.publish(self.repo, inferred=False))
        self.repo.record_observations.assert_not_called()

    def test_no_configured_spaces_invalidates_previous_result(self):
        self.publish(self.repo)
        self.repo.reset_mock()
        self.assertFalse(self.publish(self.repo, space_status=[]))
        self.assertNotIn("camera_1", self.latest)
        self.repo.record_observations.assert_not_called()

    def test_local_inmemory_mode_publishes_without_database(self):
        self.assertTrue(self.publish(None, inferred=False))
        self.assertIn("camera_1", self.latest)

    def test_invalid_cv_result_causes_unavailable_after_failed_validation(self):
        self.publish(self.repo)
        self.repo.reset_mock()
        self.assertRaises(ValueError, self.publish, self.repo, True,
                          [{"id": 1, "open": "occupied"}])
        self.assertNotIn("camera_1", self.latest)


    def test_invalid_cv_result_is_rejected_in_demo_mode_too(self):
        self.publish(None)
        with self.assertRaises(ValueError):
            self.publish(None, space_status=[{"id": 1, "open": "false"}])
        self.assertNotIn("camera_1", self.latest)

    def test_duplicate_space_id_is_rejected_before_demo_publication(self):
        with self.assertRaises(ValueError):
            self.publish(None, space_status=[
                {"id": 1, "open": True}, {"id": 1, "open": False},
            ])
        self.assertEqual(self.latest, {})


if __name__ == "__main__":
    import unittest
    unittest.main()
