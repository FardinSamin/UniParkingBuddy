"""Read-only research prototype: recurring vehicle locations -> stall hypotheses.

A repeated vehicle position is NOT proof of a legal parking stall. Output
contains local, unverified vehicle-box proxies, never approved stall polygons.
This module never modifies configs, occupancy history, or application state.
"""

from collections import defaultdict
from pathlib import Path
from statistics import median
import argparse
import json
import math
import sys

import cv2
import numpy as np

from .accuracy_evaluation import (
    PROJECT_ROOT, file_sha256, sample_frame_indices,
)
from .yolo_detection import (
    DETECTION_CONFIDENCE, INFERENCE_IMAGE_SIZE, VEHICLE_CLASS_IDS,
    boxes_from_yolo_result,
)


def _check_positive_number(value, label):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{label} must be a positive finite number")
    if not math.isfinite(value) or value <= 0:
        raise ValueError(f"{label} must be a positive finite number")


def _read_observation(frame_index, box):
    """Extract anonymous, frame-local detection geometry; discard bad boxes."""
    if type(frame_index) is not int or frame_index < 0:
        raise ValueError("Frame index must be a nonnegative integer")
    if len(box) < 4:
        raise ValueError("Vehicle box must contain four coordinates")
    x1, y1, x2, y2 = box[:4]
    if any(not isinstance(v, (int, float)) or isinstance(v, bool) or
           not math.isfinite(v) for v in (x1, y1, x2, y2)):
        raise ValueError("Vehicle box coordinates must be finite numbers")
    if x2 <= x1 or y2 <= y1:
        raise ValueError("Vehicle box must have positive area")
    return {
        "frame": frame_index,
        "box": (float(x1), float(y1), float(x2), float(y2)),
        "anchor": ((x1 + x2) / 2.0, float(y2)),  # approximate ground contact
        "width": float(x2 - x1),
        "height": float(y2 - y1),
    }


def _representative(cluster):
    return {
        "anchor": (
            median(o["anchor"][0] for o in cluster),
            median(o["anchor"][1] for o in cluster),
        ),
        "width": median(o["width"] for o in cluster),
        "height": median(o["height"] for o in cluster),
    }


def _distance(observation, cluster, horizontal_fraction, vertical_fraction):
    reference = _representative(cluster)
    dx = abs(observation["anchor"][0] - reference["anchor"][0])
    dy = abs(observation["anchor"][1] - reference["anchor"][1])
    width = min(observation["width"], reference["width"])
    height = min(observation["height"], reference["height"])
    return math.hypot(
        dx / (horizontal_fraction * width),
        dy / (vertical_fraction * height),
    )


def propose_locations(frame_boxes, min_frames=3, min_support=0.3,
                      horizontal_fraction=0.45, vertical_fraction=0.40):
    """Return hypotheses from anonymous detection boxes grouped by frame.

    frame_boxes is a mapping {sampled_frame_index: [(x1,y1,x2,y2,...), ...]}.
    Heuristic spacing fractions are *research knobs*, not SRS thresholds.
    At most one detection from each frame contributes to a hypothesis.
    """
    if type(min_frames) is not int or min_frames < 2:
        raise ValueError("min_frames must be an integer >= 2")
    for label, value in (
        ("min_support", min_support), ("horizontal_fraction", horizontal_fraction),
        ("vertical_fraction", vertical_fraction)
    ):
        _check_positive_number(value, label)
    if min_support > 1:
        raise ValueError("min_support must be <= 1")
    if not isinstance(frame_boxes, dict) or not frame_boxes:
        raise ValueError("A nonempty frame-to-box mapping is required")

    frames = sorted(frame_boxes)
    if any(type(frame) is not int or frame < 0 for frame in frames):
        raise ValueError("Frame keys must be nonnegative integers")
    if any(not isinstance(frame_boxes[frame], (list, tuple)) for frame in frames):
        raise ValueError("Each frame must contain a list of detections")

    clusters = []
    for frame in frames:
        observations = sorted(
            (_read_observation(frame, box) for box in frame_boxes[frame]),
            key=lambda o: (o["anchor"][0], o["anchor"][1])
        )
        for observation in observations:
            options = [
                (score, index)
                for index, cluster in enumerate(clusters)
                if all(sample["frame"] != frame for sample in cluster)
                for score in [_distance(
                    observation, cluster, horizontal_fraction, vertical_fraction
                )]
                if score <= 1.0
            ]
            if options:
                _, index = min(options)
                clusters[index].append(observation)
            else:
                clusters.append([observation])

    candidates = []
    total_frames = len(frames)
    for cluster in clusters:
        supporting_frames = len(cluster)
        if supporting_frames < min_frames or supporting_frames / total_frames < min_support:
            continue
        representative = _representative(cluster)
        raw_box = [
            median(o["box"][index] for o in cluster) for index in range(4)
        ]
        candidates.append({
            "review_state": "unverified",
            "evidence_type": "repeated_vehicle_detection_only",
            "proxy_vehicle_box_xyxy": [round(value) for value in raw_box],
            "ground_anchor_xy": [
                round(value, 1) for value in representative["anchor"]
            ],
            "supporting_sampled_frames": supporting_frames,
            "sampled_frame_fraction": round(supporting_frames / total_frames, 3),
            "frame_indices": sorted(o["frame"] for o in cluster),
        })
    candidates.sort(key=lambda candidate: (
        candidate["ground_anchor_xy"][1],
        candidate["ground_anchor_xy"][0],
    ))
    for index, candidate in enumerate(candidates, 1):
        candidate["proposal_id"] = f"P{index:03d}"
    return candidates


def render_preview(frame, candidates):
    """Render proxy vehicle boxes; NOT generated parking-space boundaries."""
    display = frame.copy()
    for candidate in candidates:
        x1, y1, x2, y2 = candidate["proxy_vehicle_box_xyxy"]
        cx, cy = [round(x) for x in candidate["ground_anchor_xy"]]
        cv2.rectangle(display, (x1, y1), (x2, y2), (255, 0, 255), 2)
        cv2.circle(display, (cx, cy), 4, (255, 0, 255), -1)
        cv2.putText(
            display, f"{candidate['proposal_id']} UNVERIFIED",
            (max(0, x1), max(18, y1 - 6)),
            cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 0, 255), 2
        )
    cv2.putText(
        display, "VEHICLE-LOCATION HYPOTHESES - NOT VERIFIED PARKING STALLS",
        (10, max(28, frame.shape[0] - 16)),
        cv2.FONT_HERSHEY_SIMPLEX, 0.65, (0, 0, 255), 2
    )
    return display


def analyze_video(video_path, output_dir, requested_frames=16, min_frames=3,
                  min_support=0.3, model_path=None):
    """Analyze a generic fixed-view video and save local review material.

    Explicitly does not detect painted lines, infer legal stall bounds, or
    validate camera stability. It does not accept or publish candidates.
    """
    if type(requested_frames) is not int or not 2 <= requested_frames <= 100:
        raise ValueError("requested_frames must be between 2 and 100")
    video_path = Path(video_path).resolve()
    output_dir = Path(output_dir)
    model_path = Path(model_path or PROJECT_ROOT / "yolo26n.pt").resolve()
    if output_dir.exists():
        raise FileExistsError("Output already exists: use a new experiment directory")
    if not video_path.is_file() or not model_path.is_file():
        raise ValueError("Video or local YOLO weights file is missing")
    if min_frames > requested_frames:
        raise ValueError("min_frames exceeds requested_frames")

    capture = cv2.VideoCapture(str(video_path))
    try:
        if not capture.isOpened():
            raise ValueError(f"Could not open video: {video_path}")
        count = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))
        frame_indices = sample_frame_indices(count, requested_frames)
        if len(frame_indices) < min_frames:
            raise ValueError(
                "Too few independently sampled video frames for the requested support"
            )

        # Import YOLO lazily; ordinary geometry tests never download or run it.
        from ultralytics import YOLO
        model = YOLO(str(model_path))
        frame_boxes = {}
        preview_frame = None
        for index in frame_indices:
            if not capture.set(cv2.CAP_PROP_POS_FRAMES, index):
                raise ValueError(f"Cannot seek to video frame {index}")
            ok, frame = capture.read()
            if not ok or frame is None:
                raise ValueError(f"Cannot read video frame {index}")
            if preview_frame is None:
                preview_frame = frame.copy()
            results = model(
                frame, classes=list(VEHICLE_CLASS_IDS), conf=DETECTION_CONFIDENCE,
                imgsz=INFERENCE_IMAGE_SIZE, device="cpu", verbose=False
            )[0]
            frame_boxes[index] = boxes_from_yolo_result(results)
    finally:
        capture.release()

    candidates = propose_locations(
        frame_boxes, min_frames=min_frames, min_support=min_support
    )
    report = {
        "format": "uniparkingbuddy-unverified-vehicle-locations-v1",
        "review_state": "unverified_proposals_only",
        "source_video": str(video_path),
        "source_video_sha256": file_sha256(video_path),
        "model_sha256": file_sha256(model_path),
        "sampled_frame_indices": frame_indices,
        "sampled_frame_count": len(frame_indices),
        "minimum_supporting_frames": min_frames,
        "minimum_sampled_frame_fraction": min_support,
        "algorithm": "greedy_repeated_bottom_center_clustering",
        "proposal_count": len(candidates),
        "proposals": candidates,
        "limitations": [
            "Proxy boxes are detected-vehicle outlines, NOT confirmed stall boundaries.",
            "Recurring stationary vehicles or illegal parking can create false proposals.",
            "Empty stalls never occupied in sampled frames cannot be discovered.",
            "Uncompensated camera motion and perspective can distort clusters.",
            "No parking-line corroboration, calibrated homography, or temporal independence proof.",
            "Unverified proposals must never affect production configuration or occupancy counts.",
        ],
    }
    output_dir.mkdir(parents=True, exist_ok=False)
    (output_dir / "hypotheses.json").write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8"
    )
    if not cv2.imwrite(str(output_dir / "preview.png"),
                       render_preview(preview_frame, candidates)):
        raise OSError("Failed to write the local preview")
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--video", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--frames", type=int, default=16)
    parser.add_argument("--min-frames", type=int, default=3)
    parser.add_argument("--min-support", type=float, default=0.3)
    args = parser.parse_args(argv)
    try:
        report = analyze_video(
            args.video, args.output, requested_frames=args.frames,
            min_frames=args.min_frames, min_support=args.min_support
        )
    except (OSError, ValueError) as error:
        print(f"Discovery experiment failed: {error}", file=sys.stderr)
        return 1
    print(f"Generated {report['proposal_count']} UNVERIFIED vehicle-location hypotheses.")
    print(f"Review local files in: {args.output}")
    print("This did NOT map confirmed parking stalls or change the live application.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
