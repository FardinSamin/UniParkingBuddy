"""Repeatable, blind, configured-space evaluation of Occupied/Available states.

Preparation writes local preview images with configured-space outlines ONLY:
there are deliberately no YOLO predictions or artificial truth labels in the
annotation images or ground_truth.csv. A human must independently review them.
Raw video remains local and is never written to PostgreSQL.
"""

import csv
import hashlib
import json
from pathlib import Path

import cv2
import numpy as np

from .parking_config import load_config
from .space_matching import assign_detections_to_spaces, build_space_statuses
from .yolo_detection import (
    DETECTION_CONFIDENCE, INFERENCE_IMAGE_SIZE, INFERENCE_EVERY_FRAMES,
    VEHICLE_CLASS_IDS, boxes_from_yolo_result,
)

PROJECT_ROOT = Path(__file__).resolve().parent.parent

# These are the two existing fixed-view sources used by backend/main.py.
CAMERA_VIDEOS = {
    "camera_1": "footage/stockvidsample2.mp4",
    "camera_2": "footage/parkinglotfootage1_1.mp4",
}
TRUTH_FIELDS = ("camera", "frame_index", "space_id", "ground_truth", "reviewer_notes")
PREDICTION_FIELDS = ("camera", "frame_index", "space_id", "predicted_status")
OCCUPANCY_STATES = frozenset(("AVAILABLE", "OCCUPIED"))
UNVERIFIABLE = "UNVERIFIABLE"  # annotation exclusion, never an app status


def file_sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sample_frame_indices(total_frames, requested=8):
    """Uniform deterministic sampling among frames the live app would infer."""
    if type(total_frames) is not int or total_frames < 1:
        raise ValueError("Frame count must be positive")
    if type(requested) is not int or requested < 1:
        raise ValueError("Requested frame count must be positive")
    eligible = list(range(0, total_frames, INFERENCE_EVERY_FRAMES))
    count = min(requested, len(eligible))
    if count == 1:
        return [eligible[0]]
    return [
        eligible[(i * (len(eligible) - 1)) // (count - 1)]
        for i in range(count)
    ]


def _frame(video, index, relative_video):
    if not video.set(cv2.CAP_PROP_POS_FRAMES, index):
        raise ValueError(f"Cannot seek to frame {index} of {relative_video}")
    success, frame = video.read()
    if not success or frame is None:
        raise ValueError(f"Cannot decode frame {index} of {relative_video}")
    return frame


def _contours(config):
    return [
        np.array(space["points"], dtype=np.int32).reshape((-1, 1, 2))
        for space in config["spaces"]
    ]


def prepare_evaluation(output_dir, requested=8, root=PROJECT_ROOT):
    """Create a NEW local evaluation bundle without overwriting annotations."""
    output_dir, root = Path(output_dir), Path(root)
    if output_dir.exists():
        raise FileExistsError(
            "Evaluation destination already exists; use a new directory to "
            "protect previous human annotations and test evidence"
        )
    if type(requested) is not int or not 1 <= requested <= 100:
        raise ValueError("Requested frames per camera must be in 1..100")

    manifest = {
        "version": 1,
        "inference_every_frames": INFERENCE_EVERY_FRAMES,
        "cameras": {},
    }
    annotations = []
    output_dir.mkdir(parents=True)
    for camera, relative_video in CAMERA_VIDEOS.items():
        video_path = root / relative_video
        config_path = root / "configs" / f"{camera}.json"
        config = load_config(config_path)
        video = cv2.VideoCapture(str(video_path))
        try:
            if not video.isOpened():
                raise ValueError(f"Cannot open {relative_video}")
            total = int(video.get(cv2.CAP_PROP_FRAME_COUNT))
            indices = sample_frame_indices(total, requested)
            camera_dir = output_dir / "frames" / camera
            camera_dir.mkdir(parents=True)
            contours = _contours(config)
            height = width = None
            for index in indices:
                raw = _frame(video, index, relative_video)
                height, width = raw.shape[:2]
                # Draw only the configured geometry; NO model outputs or guesses.
                preview = raw.copy()
                for space, contour in zip(config["spaces"], contours):
                    cv2.polylines(preview, [contour], True, (255, 180, 0), 3)
                    cx = int(np.mean(contour[:, 0, 0]))
                    cy = int(np.mean(contour[:, 0, 1]))
                    cv2.putText(
                        preview, str(space["id"]), (cx, cy),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.9, (255, 255, 255), 3,
                    )
                preview_path = camera_dir / f"frame_{index:06d}.png"
                if not cv2.imwrite(str(preview_path), preview):
                    raise OSError(f"Failed to save preview {preview_path}")
                for space in config["spaces"]:
                    annotations.append({
                        "camera": camera,
                        "frame_index": str(index),
                        "space_id": str(space["id"]),
                        "ground_truth": "",
                        "reviewer_notes": "",
                    })
            manifest["cameras"][camera] = {
                "video": relative_video,
                "video_sha256": file_sha256(video_path),
                "config_sha256": file_sha256(config_path),
                "space_ids": [space["id"] for space in config["spaces"]],
                "frame_indices": indices,
                "width": width,
                "height": height,
            }
        finally:
            video.release()

    (output_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )
    with (output_dir / "ground_truth.csv").open(
        "w", encoding="utf-8", newline=""
    ) as handle:
        writer = csv.DictWriter(handle, fieldnames=TRUTH_FIELDS)
        writer.writeheader()
        writer.writerows(annotations)
    return manifest


def _validated_manifest(folder, root):
    manifest = json.loads((folder / "manifest.json").read_text(encoding="utf-8"))
    if not isinstance(manifest, dict) or manifest.get("version") != 1:
        raise ValueError("Unsupported evaluation manifest")
    if manifest.get("inference_every_frames") != INFERENCE_EVERY_FRAMES:
        raise ValueError("The inference cadence differs from the saved evaluation")
    cameras = manifest.get("cameras")
    if not isinstance(cameras, dict) or set(cameras) != set(CAMERA_VIDEOS):
        raise ValueError("Manifest camera list has changed")

    expected = set()
    for camera, relative_video in CAMERA_VIDEOS.items():
        entry = cameras[camera]
        if not isinstance(entry, dict) or entry.get("video") != relative_video:
            raise ValueError("Manifest video does not match configured source")
        if (
            file_sha256(root / relative_video) != entry.get("video_sha256")
            or file_sha256(root / "configs" / f"{camera}.json")
            != entry.get("config_sha256")
        ):
            raise ValueError("Video or configured regions changed since annotation")
        config = load_config(root / "configs" / f"{camera}.json")
        ids = entry.get("space_ids")
        frames = entry.get("frame_indices")
        if ids != [space["id"] for space in config["spaces"]]:
            raise ValueError("Space IDs differ from the annotated version")
        if not isinstance(frames, list) or not frames or any(
            type(f) is not int or f < 0 or f % INFERENCE_EVERY_FRAMES
            for f in frames
        ) or len(frames) != len(set(frames)) or frames != sorted(frames):
            raise ValueError("Invalid sampled frame indices")
        for frame in frames:
            for space_id in ids:
                expected.add((camera, str(frame), str(space_id)))
    return manifest, expected


def predict_evaluation(folder, root=PROJECT_ROOT):
    """Write model results separately from human labels, without overwriting."""
    folder, root = Path(folder), Path(root)
    manifest, expected = _validated_manifest(folder, root)
    destination = folder / "predictions.csv"
    if destination.exists():
        raise FileExistsError("Predictions exist; do not overwrite evaluation evidence")

    # Import lazily so scoring/testing never needs YOLO or a network download.
    from ultralytics import YOLO
    weights = root / "yolo26n.pt"
    model = YOLO(str(weights))
    entries = []
    for camera, relative_video in CAMERA_VIDEOS.items():
        config = load_config(root / "configs" / f"{camera}.json")
        contours = _contours(config)
        video = cv2.VideoCapture(str(root / relative_video))
        try:
            if not video.isOpened():
                raise ValueError(f"Cannot open {relative_video}")
            for index in manifest["cameras"][camera]["frame_indices"]:
                raw = _frame(video, index, relative_video)
                result = model(
                    raw, classes=list(VEHICLE_CLASS_IDS),
                    conf=DETECTION_CONFIDENCE, imgsz=INFERENCE_IMAGE_SIZE,
                    device="cpu", verbose=False,
                )[0]
                boxes = boxes_from_yolo_result(result)
                _, occupied = assign_detections_to_spaces(boxes, contours)
                statuses = build_space_statuses(config["spaces"], occupied)
                for space in statuses:
                    entries.append({
                        "camera": camera,
                        "frame_index": str(index),
                        "space_id": str(space["id"]),
                        "predicted_status": "AVAILABLE" if space["open"] else "OCCUPIED",
                    })
        finally:
            video.release()
    if {(x["camera"], x["frame_index"], x["space_id"]) for x in entries} != expected:
        raise ValueError("Prediction set does not cover every sampled space")

    with destination.open("x", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=PREDICTION_FIELDS)
        writer.writeheader()
        writer.writerows(entries)
    return len(entries)


def _read_rows(path, fields, expected, field):
    with Path(path).open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames != list(fields):
            raise ValueError(f"{path}: unexpected CSV headers")
        result = {}
        for row in reader:
            if None in row or any(value is None for value in row.values()):
                raise ValueError(f"{path}: malformed CSV row")
            key = (row["camera"], row["frame_index"], row["space_id"])
            if key in result or key not in expected:
                raise ValueError(f"{path}: duplicate or unexpected space/frame row")
            result[key] = row[field]
    if set(result) != expected:
        raise ValueError(f"{path}: missing annotation/prediction rows")
    return result


def _metric(rows):
    total = len(rows)
    correct = sum(truth == predicted for truth, predicted in rows)
    tp = sum(truth == predicted == "OCCUPIED" for truth, predicted in rows)
    tn = sum(truth == predicted == "AVAILABLE" for truth, predicted in rows)
    fp = sum(truth == "AVAILABLE" and predicted == "OCCUPIED" for truth, predicted in rows)
    fn = sum(truth == "OCCUPIED" and predicted == "AVAILABLE" for truth, predicted in rows)
    return {
        "evaluated": total, "correct": correct,
        "accuracy_percent": round(100 * correct / total, 2) if total else None,
        "true_positive": tp, "true_negative": tn,
        "false_positive": fp, "false_negative": fn,
    }


def score_evaluation(folder, root=PROJECT_ROOT):
    """Return honest metrics ONLY after complete human labels and predictions."""
    folder, root = Path(folder), Path(root)
    _, expected = _validated_manifest(folder, root)
    truth = _read_rows(
        folder / "ground_truth.csv", TRUTH_FIELDS, expected, "ground_truth"
    )
    predicted = _read_rows(
        folder / "predictions.csv", PREDICTION_FIELDS, expected, "predicted_status"
    )
    valid_truth = OCCUPANCY_STATES | {UNVERIFIABLE}
    unlabeled = [key for key, label in truth.items() if not label.strip()]
    if unlabeled:
        raise ValueError(
            f"{len(unlabeled)} of {len(expected)} human labels are blank; "
            "no accuracy metric can be computed yet"
        )
    if any(label not in valid_truth for label in truth.values()):
        raise ValueError("Human annotations must be AVAILABLE, OCCUPIED or UNVERIFIABLE")
    if any(label not in OCCUPANCY_STATES for label in predicted.values()):
        raise ValueError("Model predictions must be AVAILABLE or OCCUPIED")

    scored = [
        (key, label, predicted[key]) for key, label in truth.items()
        if label != UNVERIFIABLE
    ]
    if not scored:
        raise ValueError("All annotations are unverifiable; cannot compute accuracy")
    per_camera = {}
    per_space = {}
    for camera in CAMERA_VIDEOS:
        items = [(truth, pred) for (cam, _, _), truth, pred in scored if cam == camera]
        per_camera[camera] = _metric(items)
    for camera, frame, space in expected:
        per_space.setdefault(camera, {}).setdefault(space, [])
    for (camera, _, space), truth_label, pred in scored:
        per_space[camera][space].append((truth_label, pred))
    per_space = {
        camera: {space: _metric(items) for space, items in sorted(space_data.items(), key=lambda x: int(x[0]))}
        for camera, space_data in per_space.items()
    }
    return {
        "method": "manually_verified_configured_space_classification",
        "states": ["AVAILABLE", "OCCUPIED"],
        "sampled_space_frame_pairs": len(expected),
        "excluded_unverifiable": len(expected) - len(scored),
        "overall": _metric([(label, pred) for _, label, pred in scored]),
        "by_camera": per_camera,
        "by_space": per_space,
        "limitations": (
            "Accuracy on selected prerecorded frames only; not proof of real campus "
            "performance, parked-versus-moving classification, or future prediction"
        ),
    }
