"""Synthetic fixture tests for the ground-truth accuracy evaluation workflow.

The artificial labels in these tests verify arithmetic ONLY; they are not
real-space annotations or a claim about UniParkingBuddy performance.
"""

import csv
import json
from pathlib import Path
import tempfile
import unittest

from backend.accuracy_evaluation import (
    CAMERA_VIDEOS, PREDICTION_FIELDS, TRUTH_FIELDS,
    file_sha256, sample_frame_indices, score_evaluation,
)


def region(x):
    return [[x, 0], [x + 8, 0], [x + 8, 8], [x, 8]]


class EvaluationScoringTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        base = Path(self.temporary.name)
        self.root = base / "source"
        self.folder = base / "run"
        self.folder.mkdir()
        (self.root / "footage").mkdir(parents=True)
        (self.root / "configs").mkdir()
        (self.root / "yolo26n.pt").write_bytes(b"synthetic weights: tests only")
        self.labels = []
        self.predictions = []
        camera_data = {}
        for camera, relative_video in CAMERA_VIDEOS.items():
            source = self.root / relative_video
            source.write_bytes(f"synthetic video fixture for {camera}".encode())
            ids = [1, 7] if camera == "camera_1" else [2]
            configuration = {
                "version": 1,
                "next_space_id": max(ids) + 1,
                "spaces": [
                    {"id": sid, "points": region((offset + 1) * 20)}
                    for offset, sid in enumerate(ids)
                ],
            }
            config_path = self.root / "configs" / f"{camera}.json"
            config_path.write_text(json.dumps(configuration), encoding="utf-8")
            camera_data[camera] = {
                "video": relative_video,
                "video_sha256": file_sha256(source),
                "config_sha256": file_sha256(config_path),
                "space_ids": ids,
                "frame_indices": [0, 30],
                "width": 1920,
                "height": 1080,
            }
            for index in (0, 30):
                for sid in ids:
                    self.labels.append({
                        "camera": camera, "frame_index": str(index),
                        "space_id": str(sid), "ground_truth": "",
                        "reviewer_notes": "",
                    })
                    self.predictions.append({
                        "camera": camera, "frame_index": str(index),
                        "space_id": str(sid), "predicted_status": "AVAILABLE",
                    })
        manifest = {
            "version": 1, "inference_every_frames": 30,
            "model_sha256": file_sha256(self.root / "yolo26n.pt"),
            "cameras": camera_data,
        }
        (self.folder / "manifest.json").write_text(
            json.dumps(manifest), encoding="utf-8"
        )
        self.write_rows()

    def write_rows(self):
        for name, columns, rows in (
            ("ground_truth.csv", TRUTH_FIELDS, self.labels),
            ("predictions.csv", PREDICTION_FIELDS, self.predictions),
        ):
            with (self.folder / name).open(
                "w", encoding="utf-8", newline=""
            ) as handle:
                writer = csv.DictWriter(handle, fieldnames=columns)
                writer.writeheader()
                writer.writerows(rows)

    def result(self):
        return score_evaluation(self.folder, root=self.root)

    def test_samples_are_deterministic_live_inference_indices(self):
        self.assertEqual(sample_frame_indices(1), [0])
        self.assertEqual(sample_frame_indices(31, requested=2), [0, 30])
        self.assertEqual(sample_frame_indices(100, requested=3), [0, 30, 90])
        self.assertEqual(sample_frame_indices(360, requested=4), [0, 90, 210, 330])
        with self.assertRaises(ValueError):
            sample_frame_indices(0)
        with self.assertRaises(ValueError):
            sample_frame_indices(100, 0)

    def test_all_blank_ground_truth_refuses_accuracy_claim(self):
        with self.assertRaisesRegex(ValueError, "6 of 6 human labels are blank"):
            self.result()

    def test_partially_labeled_data_also_refuses_accuracy_claim(self):
        self.labels[0]["ground_truth"] = "OCCUPIED"
        self.write_rows()
        with self.assertRaisesRegex(ValueError, "5 of 6 human labels are blank"):
            self.result()

    def test_true_false_positives_and_exclusions_are_correct(self):
        # Deliberate synthetic example: 3 right / 5 evaluated (60%),
        # one excluded as unverifiable; NOT a real measured accuracy result.
        truth_by_key = {
            ("camera_1", "0", "1"): "OCCUPIED",
            ("camera_1", "0", "7"): "AVAILABLE",
            ("camera_1", "30", "1"): "OCCUPIED",
            ("camera_1", "30", "7"): "AVAILABLE",
            ("camera_2", "0", "2"): "UNVERIFIABLE",
            ("camera_2", "30", "2"): "AVAILABLE",
        }
        prediction_by_key = {
            ("camera_1", "0", "1"): "OCCUPIED",
            ("camera_1", "0", "7"): "AVAILABLE",
            ("camera_1", "30", "1"): "AVAILABLE",
            ("camera_1", "30", "7"): "OCCUPIED",
            ("camera_2", "0", "2"): "OCCUPIED",
            ("camera_2", "30", "2"): "AVAILABLE",
        }
        for label in self.labels:
            key = (label["camera"], label["frame_index"], label["space_id"])
            label["ground_truth"] = truth_by_key[key]
        for item in self.predictions:
            key = (item["camera"], item["frame_index"], item["space_id"])
            item["predicted_status"] = prediction_by_key[key]
        self.write_rows()
        result = self.result()
        self.assertEqual(result["sampled_space_frame_pairs"], 6)
        self.assertEqual(result["excluded_unverifiable"], 1)
        self.assertEqual(result["overall"]["evaluated"], 5)
        self.assertEqual(result["overall"]["correct"], 3)
        self.assertEqual(result["overall"]["accuracy_percent"], 60.0)
        self.assertEqual(result["overall"]["true_positive"], 1)
        self.assertEqual(result["overall"]["true_negative"], 2)
        self.assertEqual(result["overall"]["false_positive"], 1)
        self.assertEqual(result["overall"]["false_negative"], 1)
        self.assertEqual(result["by_camera"]["camera_1"]["evaluated"], 4)
        self.assertEqual(result["by_camera"]["camera_2"]["evaluated"], 1)
        self.assertEqual(result["by_space"]["camera_1"]["7"]["evaluated"], 2)
        self.assertEqual(result["by_space"]["camera_2"]["2"]["accuracy_percent"], 100.0)

    def test_all_unverifiable_never_emits_accuracy(self):
        for label in self.labels:
            label["ground_truth"] = "UNVERIFIABLE"
        self.write_rows()
        with self.assertRaisesRegex(ValueError, "All annotations are unverifiable"):
            self.result()

    def test_third_occupancy_domain_state_is_invalid(self):
        for label in self.labels:
            label["ground_truth"] = "AVAILABLE"
        self.labels[0]["ground_truth"] = "UNKNOWN"
        self.write_rows()
        with self.assertRaisesRegex(ValueError, "annotations must be"):
            self.result()

    def test_third_model_status_is_invalid(self):
        for label in self.labels:
            label["ground_truth"] = "AVAILABLE"
        self.predictions[0]["predicted_status"] = "UNKNOWN"
        self.write_rows()
        with self.assertRaisesRegex(ValueError, "Model predictions must be"):
            self.result()

    def test_missing_or_extra_rows_are_rejected(self):
        for label in self.labels:
            label["ground_truth"] = "AVAILABLE"
        self.labels.pop()
        self.write_rows()
        with self.assertRaisesRegex(ValueError, "missing annotation"):
            self.result()

    def test_duplicate_rows_are_rejected(self):
        for label in self.labels:
            label["ground_truth"] = "AVAILABLE"
        self.labels.append(self.labels[0].copy())
        self.write_rows()
        with self.assertRaisesRegex(ValueError, "duplicate"):
            self.result()

    def test_unexpected_camera_or_space_is_rejected(self):
        for label in self.labels:
            label["ground_truth"] = "AVAILABLE"
        self.labels[0]["space_id"] = "9999"
        self.write_rows()
        with self.assertRaisesRegex(ValueError, "unexpected space"):
            self.result()

    def test_modified_config_prevents_scoring_stale_annotations(self):
        for label in self.labels:
            label["ground_truth"] = "AVAILABLE"
        self.write_rows()
        path = self.root / "configs" / "camera_1.json"
        path.write_text(path.read_text() + "\n", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "changed since annotation"):
            self.result()

    def test_changed_weights_prevent_inconsistent_evidence(self):
        for label in self.labels:
            label["ground_truth"] = "AVAILABLE"
        self.write_rows()
        (self.root / "yolo26n.pt").write_bytes(b"different weights")
        with self.assertRaisesRegex(ValueError, "weights changed"):
            self.result()

    def test_malformed_csv_header_is_rejected(self):
        for label in self.labels:
            label["ground_truth"] = "AVAILABLE"
        self.write_rows()
        path = self.folder / "predictions.csv"
        data = path.read_text(encoding="utf-8")
        path.write_text(data.replace("predicted_status", "prediction"), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "unexpected CSV headers"):
            self.result()


if __name__ == "__main__":
    unittest.main()
