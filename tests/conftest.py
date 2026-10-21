import pytest
from fastapi.testclient import TestClient
import threading

from backend import status_api


@pytest.fixture
def status_app_and_client():
    # Minimal camera_captures with two cameras and simple configs
    camera_captures = {
        "camera_1": {"config": {"spaces": [{"id": 1, "points": [[0,0],[10,0],[10,10],[0,10]]}]}},
        "camera_2": {"config": {"spaces": [{"id": 1, "points": [[20,0],[30,0],[30,10],[20,10]]}]}}
    }
    latest_status = {}
    status_lock = threading.Lock()
    app = status_api.create_status_app(camera_captures, latest_status, status_lock, persistence=None)
    client = TestClient(app)
    return client, camera_captures, latest_status, status_lock


@pytest.fixture
def fake_persistence():
    class FakePersistence:
        def __init__(self):
            self.registered = {}
        def register_lot_configuration(self, lot_id, label, configuration):
            self.registered[lot_id] = (label, configuration)
        def lot_spaces(self, lot_id):
            if lot_id == "lot1":
                return ["1"]
            return None
        def hourly_occupancy_trends(self, lot_id, days):
            return [{"hour_utc": 0, "observations": 1, "occupied_observations": 0, "occupied_percent": 0.0}]
        def space_history(self, lot_id, space_id, limit=100):
            return [{"status": "AVAILABLE", "observed_at": __import__('datetime').datetime.now(__import__('datetime').timezone.utc)}]
    return FakePersistence()
