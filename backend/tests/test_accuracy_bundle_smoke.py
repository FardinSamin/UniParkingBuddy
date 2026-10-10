"""Smoke-test reproducible preview/prediction generation, without fake truth."""

import csv
import os
from pathlib import Path
import tempfile
import unittest

from backend.accuracy_evaluation import (
    prepare_evaluation, predict_evaluation, score_evaluation,
)


@unittest.skipUnless(
    os.getenv("RUN_REAL_YOLO_SMOKE") == "1",
    "Real model bundle generation runs in dedicated CPU inference CI job",
)
class EvaluationBundleSmokeTests(unittest.TestCase):
    def test_generate_blind_previews_and_real_predictions_but_no_accuracy(self):
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary) / "round"
            manifest = prepare_evaluation(folder, requested=2)

            for camera, entry in manifest["cameras"].items():
                self.assertEqual(len(entry["frame_indices"]), 2)
                for frame_index in entry["frame_indices"]:
                    image = folder / "frames" / camera / f"frame_{frame_index:06d}.png"
                    self.assertTrue(image.exists(), f"Missing preview: {image}")
                    self.assertGreater(image.stat().st_size, 0)

            expected = sum(
                len(entry["frame_indices"]) * len(entry["space_ids"])
                for entry in manifest["cameras"].values()
            )
            with (folder / "ground_truth.csv").open(encoding="utf-8", newline="") as handle:
                truth = list(csv.DictReader(handle))
            self.assertEqual(len(truth), expected)
            self.assertTrue(all(row["ground_truth"] == "" for row in truth))

            actual = predict_evaluation(folder)
            self.assertEqual(actual, expected)
            with (folder / "predictions.csv").open(encoding="utf-8", newline="") as handle:
                predictions = list(csv.DictReader(handle))
            self.assertEqual(len(predictions), expected)
            self.assertTrue(all(
                row["predicted_status"] in {"AVAILABLE", "OCCUPIED"}
                for row in predictions
            ))

            with self.assertRaisesRegex(ValueError, "human labels are blank"):
                score_evaluation(folder)

            with self.assertRaises(FileExistsError):
                prepare_evaluation(folder, requested=2)
            with self.assertRaises(FileExistsError):
                predict_evaluation(folder)


if __name__ == "__main__":
    unittest.main()
