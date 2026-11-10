"""Non-destructive recovery regression tests for the active three-camera setup.

All files and labels in the evaluation tests are synthetic fixtures; none are
recorded vehicle data or measured model accuracy.
"""

import csv
import json
from pathlib import Path
import tempfile
import unittest

from backend.accuracy_evaluation import (
    CAMERA_VIDEOS, PREDICTION_FIELDS, TRUTH_FIELDS, detector_evidence,
    file_sha256, score_evaluation,
)
from backend.parking_config import load_config
from backend.yolo_detection import detector_settings


ROOT = Path(__file__).resolve().parents[2]


class ThreeCameraContractTests(unittest.TestCase):
    def test_active_camera_model_and_configuration_inventory(self):
        self.assertEqual(set(CAMERA_VIDEOS), {"camera_1", "camera_2", "camera_3"})
        self.assertEqual(detector_settings("camera_1")["weights"], "yolo26m.pt")
        self.assertEqual(detector_settings("camera_2")["weights"], "yolo26m.pt")
        self.assertEqual(detector_settings("camera_3")["weights"], "yolo26m-obb.pt")
        self.assertTrue(detector_settings("camera_3")["oriented"])
        for camera in CAMERA_VIDEOS:
            config = load_config(ROOT / "configs" / f"{camera}.json")
            self.assertGreater(len(config["spaces"]), 0)

    def test_schematic_only_uses_real_configured_ids(self):
        for camera, lot in (("camera_1", "lot1"),
                            ("camera_2", "lot2"),
                            ("camera_3", "lot3")):
            config = load_config(ROOT / "configs" / f"{camera}.json")
            layout = json.loads(
                (ROOT / "frontend" / "public" / "diagrams" / f"{lot}.json").read_text(
                    encoding="utf-8"
                )
            )
            diagram_ids = [item["id"] for item in layout.get("stalls", [])]
            next_id = 1
            for column in layout.get("columns", []):
                for _ in range(len(column["lines"]) - 1):
                    diagram_ids.append(next_id)
                    next_id += 1
            config_ids = {item["id"] for item in config["spaces"]}
            self.assertEqual(len(diagram_ids), len(set(diagram_ids)))
            self.assertFalse(set(diagram_ids) - config_ids,
                             f"{lot}: diagram contains IDs absent from the backend")
            # Any missing schematic position must be visibly represented by the
            # LotDiagram unmapped-space list; never synthesize coordinates here.
            self.assertEqual(len(config_ids),
                             len(diagram_ids) + len(config_ids - set(diagram_ids)))


class VersionTwoEvidenceTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        base = Path(temporary.name)
        self.root = base / "source"
        self.folder = base / "eval"
        self.folder.mkdir()
        (self.root / "footage").mkdir(parents=True)
        (self.root / "configs").mkdir()
        for weight in ("yolo26m.pt", "yolo26m-obb.pt"):
            (self.root / weight).write_bytes(f"synthetic model {weight}".encode())

        manifest = {"version": 2, "inference_every_frames": 30, "cameras": {}}
        self.truth = []
        self.predictions = []
        for camera, video in CAMERA_VIDEOS.items():
            source = self.root / video
            source.write_bytes(f"synthetic video {camera}".encode())
            config_path = self.root / "configs" / f"{camera}.json"
            config_path.write_text(json.dumps({
                "version": 1,
                "next_space_id": 2,
                "spaces": [{"id": 1, "points": [[2, 2], [12, 2],
                                                 [12, 12], [2, 12]]}],
            }), encoding="utf-8")
            manifest["cameras"][camera] = {
                "detector": detector_evidence(camera, self.root),
                "video": video,
                "video_sha256": file_sha256(source),
                "config_sha256": file_sha256(config_path),
                "space_ids": [1],
                "frame_indices": [0],
                "width": 20,
                "height": 20,
            }
            self.truth.append({
                "camera": camera, "frame_index": "0", "space_id": "1",
                "ground_truth": "AVAILABLE", "reviewer_notes": "synthetic test only",
            })
            self.predictions.append({
                "camera": camera, "frame_index": "0", "space_id": "1",
                "predicted_status": "AVAILABLE",
            })
        (self.folder / "manifest.json").write_text(
            json.dumps(manifest), encoding="utf-8"
        )
        self.write_rows()
        self.write_metadata()

    def write_rows(self):
        for filename, header, rows in (
            ("ground_truth.csv", TRUTH_FIELDS, self.truth),
            ("predictions.csv", PREDICTION_FIELDS, self.predictions),
        ):
            with (self.folder / filename).open("w", encoding="utf-8", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=header)
                writer.writeheader()
                writer.writerows(rows)

    def write_metadata(self, *, overrides=None):
        modes = {camera: detector_settings(camera)["matching"]
                 for camera in CAMERA_VIDEOS}
        modes.update(overrides or {})
        (self.folder / "prediction_settings.json").write_text(json.dumps({
            "manifest_version": 2,
            "source": "active_camera_models",
            "matching_by_camera": modes,
            "predictions_sha256": file_sha256(self.folder / "predictions.csv"),
        }), encoding="utf-8")

    def score(self):
        return score_evaluation(self.folder, root=self.root)

    def test_three_camera_results_and_provenance_are_labeled_synthetic(self):
        result = self.score()
        self.assertEqual(set(result["by_camera"]), set(CAMERA_VIDEOS))
        self.assertEqual(result["sampled_space_frame_pairs"], 3)
        self.assertEqual(result["overall"]["evaluated"], 3)
        self.assertTrue(result["prediction_provenance"]["matches_live_matching"])

    def test_explicit_alternative_matching_is_not_reported_as_live(self):
        self.write_metadata(overrides={"camera_1": "center"})
        result = self.score()
        self.assertFalse(result["prediction_provenance"]["matches_live_matching"])

    def test_corrupt_model_bytes_refuse_reuse_of_saved_labels(self):
        (self.root / "yolo26m.pt").write_bytes(b"unexpected model update")
        with self.assertRaisesRegex(ValueError, "weights or detector settings changed"):
            self.score()

    def test_tampered_predictions_refuse_an_accuracy_result(self):
        path = self.folder / "predictions.csv"
        path.write_text(path.read_text(encoding="utf-8") + "\n", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "Invalid, changed or untraceable"):
            self.score()

    def test_missing_prediction_provenance_refuses_accuracy(self):
        (self.folder / "prediction_settings.json").unlink()
        with self.assertRaisesRegex(ValueError, "Missing prediction_settings"):
            self.score()

    def test_missing_human_labels_still_cannot_be_scored(self):
        self.truth[0]["ground_truth"] = ""
        self.write_rows()
        self.write_metadata()
        with self.assertRaisesRegex(ValueError, "human labels are blank"):
            self.score()


if __name__ == "__main__":
    unittest.main()
