"""CLI for independent manual ground-truth annotation and scoring.

Examples (from repository root):
  python -m backend.evaluate_accuracy prepare --output evaluation_runs/round1
  python -m backend.evaluate_accuracy predict --output evaluation_runs/round1
  # Human reviewer fills in ground_truth.csv independently.
  python -m backend.evaluate_accuracy report --output evaluation_runs/round1

This script never invents ground truth, and it will not print an accuracy
percentage while labels are missing. Local frames/results stay out of Git.
"""

import argparse
import json
from pathlib import Path
import sys

from .accuracy_evaluation import (
    prepare_evaluation, predict_evaluation, score_evaluation,
)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    prepare = subparsers.add_parser("prepare", help="Create blind space-by-space annotation previews")
    prepare.add_argument("--output", type=Path, required=True)
    prepare.add_argument("--frames-per-camera", type=int, default=8)

    predict = subparsers.add_parser("predict", help="Run current YOLO model on prepared samples")
    predict.add_argument("--output", type=Path, required=True)

    report = subparsers.add_parser("report", help="Score completed human labels against YOLO")
    report.add_argument("--output", type=Path, required=True)

    args = parser.parse_args(argv)
    try:
        if args.command == "prepare":
            summary = prepare_evaluation(args.output, args.frames_per_camera)
            count = sum(
                len(entry["space_ids"]) * len(entry["frame_indices"])
                for entry in summary["cameras"].values()
            )
            print(f"Created {count} BLANK ground-truth rows at {args.output / 'ground_truth.csv'}")
            print(f"Inspect previews in {args.output / 'frames'} and label independently.")
            print("No accuracy result exists until a reviewer fills EVERY row.")
        elif args.command == "predict":
            count = predict_evaluation(args.output)
            print(f"Saved {count} independent model predictions to {args.output / 'predictions.csv'}")
            print("Model predictions are not ground truth.")
        else:
            metrics = score_evaluation(args.output)
            destination = args.output / "accuracy_report.json"
            if destination.exists():
                raise FileExistsError(
                    "Existing accuracy report will not be overwritten; use a new run"
                )
            with destination.open("x", encoding="utf-8") as handle:
                json.dump(metrics, handle, indent=2)
                handle.write("\n")
            overall = metrics["overall"]
            print(
                f"Configured-space accuracy: {overall['correct']}/"
                f"{overall['evaluated']} = {overall['accuracy_percent']}%"
            )
            print(f"Unverifiable annotations excluded: {metrics['excluded_unverifiable']}")
            print(f"Saved full evaluation to {destination}")
    except (OSError, ValueError, KeyError) as error:
        print(f"Evaluation cannot proceed: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
