"""Real sample video -> real YOLO -> PostgreSQL -> FastAPI integration.

Runs only in the dedicated GitHub Actions job with disposable PostgreSQL and
the committed model. It is NOT a ground-truth accuracy or React browser test.
No video frames or identifying data are sent to the database.
"""

from datetime import datetime, timedelta, timezone
from pathlib import Path
from threading import Lock
import os
import unittest

import cv2
import numpy as np
import psycopg
from fastapi.testclient import TestClient

from backend.occupancy_repository import OccupancyRepository, SCHEMA_PATH
from backend.occupancy_writer import CAMERA_LOTS, initialize_lots
from backend.parking_config import load_config
from backend.space_matching import assign_detections_to_spaces, build_space_statuses
from backend.status_api import create_status_app, invalidate_camera_status
from backend.status_publisher import publish_space_result
from backend.yolo_detection import (
    DETECTION_CONFIDENCE, INFERENCE_IMAGE_SIZE, VEHICLE_CLASS_IDS,
    boxes_from_yolo_result,
)


ROOT = Path(__file__).resolve().parents[2]
VIDEO_SOURCES = {
    "camera_1": "footage/stockvidsample2.mp4",
    "camera_2": "footage/parkinglotfootage1_1.mp4",
}


@unittest.skipUnless(
    os.getenv("RUN_REAL_YOLO_SMOKE") == "1" and os.getenv("TEST_DATABASE_URL"),
    "Real model + disposable PostgreSQL required",
)
class RealVideoDatabaseAPITests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from ultralytics import YOLO

        cls.dsn = os.environ["TEST_DATABASE_URL"]
        # Never let an integration test change an arbitrary local database.
        with psycopg.connect(cls.dsn) as conn:
            dbname = conn.execute("SELECT current_database()").fetchone()[0]
            if dbname != "uniparkingbuddy_test":
                raise RuntimeError("Refusing to alter a non-test PostgreSQL database")
            if conn.execute("SELECT to_regclass('parking_lot')").fetchone()[0] is None:
                conn.execute(Path(SCHEMA_PATH).read_text(encoding="utf-8"))
        cls.model = YOLO(str(ROOT / "yolo26n.pt"))

    def setUp(self):
        with psycopg.connect(self.dsn) as conn:
            conn.execute(
                "TRUNCATE occupancy_record, parking_space_region, parking_space, "
                "parking_lot RESTART IDENTITY"
            )
        self.repo = OccupancyRepository(self.dsn)
        self.cameras = {
            camera: {
                "config": load_config(ROOT / "configs" / f"{camera}.json")
            }
            for camera in VIDEO_SOURCES
        }
        initialize_lots(self.repo, self.cameras)
        self.live = {}
        self.lock = Lock()
        self.client = TestClient(
            create_status_app(self.cameras, self.live, self.lock, self.repo)
        )
        # Wall-clock inference observations from prerecorded videos are
        # prototype events, NOT original recording timestamps.
        self.observed_at = datetime.now(timezone.utc) - timedelta(minutes=1)

    def infer_and_publish(self, camera, frame_index, timestamp):
        video = cv2.VideoCapture(str(ROOT / VIDEO_SOURCES[camera]))
        try:
            self.assertTrue(video.isOpened())
            self.assertTrue(video.set(cv2.CAP_PROP_POS_FRAMES, frame_index))
            ok, frame = video.read()
            self.assertTrue(ok, f"Unable to decode {camera} frame {frame_index}")
        finally:
            video.release()

        result = self.model(
            frame,
            classes=list(VEHICLE_CLASS_IDS),
            conf=DETECTION_CONFIDENCE,
            imgsz=INFERENCE_IMAGE_SIZE,
            device="cpu",
            verbose=False,
        )[0]
        detections = boxes_from_yolo_result(result)
        config = self.cameras[camera]["config"]
        contours = [
            np.asarray(space["points"], dtype=np.int32).reshape((-1, 1, 2))
            for space in config["spaces"]
        ]
        matched, occupied = assign_detections_to_spaces(detections, contours)
        statuses = build_space_statuses(config["spaces"], occupied)
        inside = sum(index is not None for index in matched)
        outside = len(detections) - inside

        self.assertTrue(publish_space_result(
            camera, statuses, len(detections), inside, outside,
            repository=self.repo,
            newly_inferred=True,
            latest_status=self.live,
            status_lock=self.lock,
            observed_at=timestamp,
        ))
        return detections, statuses, inside, outside

    def test_two_videos_flow_through_real_inference_storage_and_http(self):
        # Both cameras must start with unknown live data, but configured
        # IDs must still be visible without inventing current counts.
        initial = self.client.get("/api/lots")
        self.assertEqual(initial.status_code, 200)
        self.assertEqual([lot["lot_id"] for lot in initial.json()["lots"]], ["lot1", "lot2"])
        self.assertTrue(all(
            not lot["has_current_data"] and lot["available_spaces"] is None
            for lot in initial.json()["lots"]
        ))

        for camera, (lot_id, label) in CAMERA_LOTS.items():
            config = self.cameras[camera]["config"]
            expected_ids = [space["id"] for space in config["spaces"]]
            self.assertEqual(
                self.client.get(f"/api/lots/{lot_id}/spaces").json()["spaces"],
                [{"id": sid, "occupied": None} for sid in expected_ids],
            )
            for iteration, frame_idx in enumerate((0, 30)):
                with self.subTest(camera=camera, frame=frame_idx):
                    timestamp = self.observed_at + timedelta(seconds=iteration)
                    detections, statuses, inside, outside = self.infer_and_publish(
                        camera, frame_idx, timestamp,
                    )
                    self.assertEqual(inside + outside, len(detections))
                    expected_spaces = [
                        {"id": s["id"], "occupied": not s["open"]}
                        for s in statuses
                    ]
                    expected_occupied = sum(space["occupied"] for space in expected_spaces)
                    expected_available = len(expected_spaces) - expected_occupied

                    current = self.client.get(f"/api/status/{camera}")
                    self.assertEqual(current.status_code, 200)
                    self.assertEqual(current.json(), {
                        "cars_detected": len(detections),
                        "vehicles_in_spaces": inside,
                        "vehicles_outside_spaces": outside,
                        "parking_spaces": expected_spaces,
                    })

                    lots = self.client.get("/api/lots").json()["lots"]
                    lot = next(item for item in lots if item["lot_id"] == lot_id)
                    self.assertEqual(lot["display_label"], label)
                    self.assertTrue(lot["has_current_data"])
                    self.assertEqual(lot["space_ids"], expected_ids)
                    self.assertEqual(lot["total_spaces"], len(expected_ids))
                    self.assertEqual(lot["occupied_spaces"], expected_occupied)
                    self.assertEqual(lot["available_spaces"], expected_available)

                    spaces_response = self.client.get(
                        f"/api/lots/{lot_id}/spaces"
                    )
                    self.assertEqual(spaces_response.status_code, 200)
                    self.assertEqual(spaces_response.json()["spaces"], expected_spaces)

                    stored = self.repo.lot_summary(lot_id)
                    self.assertTrue(stored["complete"])
                    self.assertEqual(stored["occupied_spaces"], expected_occupied)
                    self.assertEqual(stored["available_spaces"], expected_available)

                    for space in expected_spaces:
                        response = self.client.get(
                            f"/api/history/{lot_id}/{space['id']}"
                        )
                        self.assertEqual(response.status_code, 200)
                        self.assertEqual(
                            len(response.json()["records"]), iteration + 1
                        )
                        recent = response.json()["records"][0]
                        self.assertEqual(
                            recent["status"],
                            "OCCUPIED" if space["occupied"] else "AVAILABLE",
                        )
                        self.assertEqual(
                            datetime.fromisoformat(recent["observed_at"]), timestamp
                        )

            trend = self.client.get(f"/api/trends/{lot_id}?days=7")
            self.assertEqual(trend.status_code, 200)
            rows = trend.json()["hourly"]
            self.assertTrue(trend.json()["has_history"])
            self.assertEqual(
                sum(row["observations"] for row in rows), len(expected_ids) * 2
            )
            self.assertEqual(
                sum(row["occupied_observations"] for row in rows),
                sum(
                    sum(record["status"] == "OCCUPIED" for record in
                        self.repo.space_history(lot_id, str(sid)))
                    for sid in expected_ids
                ),
            )
            print(
                f"{camera}: two REAL YOLO frames, {len(expected_ids)} "
                "configured spaces, live API and historical DB records agree"
            )

    def test_invalid_update_retracts_live_status_and_allows_recovery(self):
        camera, lot_id = "camera_1", "lot1"
        _, first, _, _ = self.infer_and_publish(
            camera, 0, self.observed_at,
        )
        old_history = {
            s["id"]: list(self.repo.space_history(lot_id, str(s["id"])))
            for s in first
        }
        old_summary = self.repo.lot_summary(lot_id)
        bad_snapshot = list(first) + [{"id": 99999, "open": True}]
        with self.assertRaises(ValueError):
            publish_space_result(
                camera, bad_snapshot, 0, 0, 0,
                repository=self.repo,
                newly_inferred=True,
                latest_status=self.live,
                status_lock=self.lock,
                observed_at=self.observed_at + timedelta(seconds=1),
            )

        # The live API must not serve a previously cached result as fresh,
        # but valid, committed historical rows must remain unchanged.
        self.assertEqual(self.client.get("/api/status/camera_1").status_code, 503)
        lot = self.client.get("/api/lots").json()["lots"][0]
        self.assertFalse(lot["has_current_data"])
        self.assertIsNone(lot["available_spaces"])
        self.assertEqual(self.repo.lot_summary(lot_id), old_summary)
        for sid, earlier in old_history.items():
            self.assertEqual(self.repo.space_history(lot_id, str(sid)), earlier)

        # An ended/broken video also invalidates live results without
        # erasing history; the next valid inferred frame restores current.
        invalidate_camera_status(camera, self.live, self.lock)
        self.assertEqual(self.client.get("/api/status/camera_1").status_code, 503)
        _, new_statuses, _, _ = self.infer_and_publish(
            camera, 30, self.observed_at + timedelta(seconds=2),
        )
        self.assertEqual(self.client.get("/api/status/camera_1").status_code, 200)
        for space in new_statuses:
            history = self.repo.space_history(lot_id, str(space["id"]))
            self.assertEqual(len(history), 2)
            self.assertEqual(
                history[0]["status"],
                "AVAILABLE" if space["open"] else "OCCUPIED",
            )

    def test_cached_frames_are_not_persisted_or_republished(self):
        camera, lot_id = "camera_2", "lot2"
        detections, statuses, inside, outside = self.infer_and_publish(
            camera, 0, self.observed_at,
        )
        before = {
            s["id"]: len(self.repo.space_history(lot_id, str(s["id"])))
            for s in statuses
        }
        self.assertFalse(publish_space_result(
            camera, statuses, len(detections), inside, outside,
            repository=self.repo,
            newly_inferred=False,
            latest_status=self.live,
            status_lock=self.lock,
            observed_at=self.observed_at + timedelta(seconds=1),
        ))
        for sid, count in before.items():
            self.assertEqual(
                len(self.repo.space_history(lot_id, str(sid))), count
            )


if __name__ == "__main__":
    unittest.main()
