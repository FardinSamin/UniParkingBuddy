"""Independent, local benchmark of automatically proposed parking-stall geometry.

Annotation is performed BLIND on a paused original video frame, without
algorithm overlays. Results never alter approved camera configs or database
history. Geometry matching uses one-to-one polygon IoU, not YOLO accuracy.
"""

import argparse
import json
import math
from pathlib import Path
import sys

import cv2
import numpy as np

from .accuracy_evaluation import file_sha256
from .calibrate_spaces import display_to_source, source_to_display
from .parking_config import ParkingConfigError, validate_config


IOU_THRESHOLDS = (0.25, 0.50, 0.75)  # exploratory benchmark, NOT SRS requirements


def convex_quad(points, shape):
    """Validate a four-corner polygon in original-video pixel coordinates."""
    if not isinstance(points, list) or len(points) != 4:
        raise ValueError("Expected exactly four polygon corners")
    if any(
        not isinstance(point, list) or len(point) != 2
        or any(type(x) is not int for x in point)
        for point in points
    ):
        raise ValueError("Polygon corners must be integer [x,y] coordinates")
    height, width = shape[:2]
    if any(not 0 <= x < width or not 0 <= y < height for x, y in points):
        raise ValueError("Polygon extends outside source video frame")
    polygon = np.array(points, dtype=np.float32).reshape((-1, 1, 2))
    if len({tuple(point) for point in points}) != 4:
        raise ValueError("Polygon points must be distinct")
    if not cv2.isContourConvex(polygon) or cv2.contourArea(polygon) <= 0:
        raise ValueError("Polygon must be convex with positive area")
    return polygon


def validate_truth(truth):
    if not isinstance(truth, dict) or truth.get("format") != "uniparkingbuddy-stall-layout-truth-v1":
        raise ValueError("Invalid stall-layout ground truth format")
    dimensions = truth.get("frame_size")
    if (not isinstance(dimensions, list) or len(dimensions) != 2
            or any(type(n) is not int or n < 16 for n in dimensions)):
        raise ValueError("Ground truth requires [width,height] frame size")
    shape = (dimensions[1], dimensions[0], 3)
    if not isinstance(truth.get("source_video_sha256"), str) or len(truth["source_video_sha256"]) != 64:
        raise ValueError("Ground truth video checksum missing")
    if type(truth.get("frame_index")) is not int or truth["frame_index"] < 0:
        raise ValueError("Ground truth frame index must be nonnegative")
    roi = truth.get("evaluation_roi_xyxy")
    if (not isinstance(roi, list) or len(roi) != 4
            or any(type(n) is not int for n in roi)):
        raise ValueError("Ground truth requires a rectangular evaluation ROI")
    x1, y1, x2, y2 = roi
    if not (0 <= x1 < x2 < dimensions[0] and 0 <= y1 < y2 < dimensions[1]):
        raise ValueError("Evaluation ROI must lie inside original video frame")
    spaces = truth.get("spaces")
    if not isinstance(spaces, list) or not spaces:
        raise ValueError("Human reviewer must mark at least one verifiable stall")
    for space in spaces:
        if not isinstance(space, dict) or set(space) != {"id", "points"}:
            raise ValueError("Each truth stall must have an ID and four points")
        convex_quad(space["points"], shape)
        if not all(x1 <= x <= x2 and y1 <= y <= y2 for x, y in space["points"]):
            raise ValueError("Every truth stall must lie completely inside its ROI")
    validate_config({
        "version": 1,
        "next_space_id": len(spaces) + 1,
        "spaces": spaces,
    })
    return shape


def video_frame(video_path, index):
    capture = cv2.VideoCapture(str(video_path))
    try:
        if not capture.isOpened():
            raise ValueError(f"Cannot open video {video_path}")
        if not capture.set(cv2.CAP_PROP_POS_FRAMES, index):
            raise ValueError(f"Cannot seek to frame {index}")
        success, frame = capture.read()
        if not success or frame is None:
            raise ValueError(f"Cannot decode frame {index}")
        return frame
    finally:
        capture.release()


class BlindLayoutAnnotation:
    """Edits separate local evidence only, never production configured spaces."""

    def __init__(self, video, frame, frame_index=0, display_width=1280):
        if type(display_width) is not int or not 480 <= display_width <= 1920:
            raise ValueError("Preview width must be between 480 and 1920")
        self.video = Path(video).resolve()
        self.frame = frame
        self.frame_index = frame_index
        self.height, self.width = frame.shape[:2]
        self.display_width = display_width
        self.display_height = max(1, round(self.height * display_width / self.width))
        self.spaces = []
        self.pending = []
        self.evaluation_roi = [0, 0, self.width - 1, self.height - 1]
        self.roi_select = []
        self.message = "R: choose a small evaluation region; then mark ALL visible stalls there."

    def click(self, x, y):
        if y >= self.display_height:
            return
        point = display_to_source(
            x, y, self.width, self.height, self.display_width, self.display_height
        )
        if self.roi_select == [[-1, -1]]:
            self.roi_select = [point]
            self.message = "Click opposite corner of evaluation ROI"
            return
        if self.roi_select:
            first = self.roi_select[0]
            left, right = sorted((first[0], point[0]))
            top, bottom = sorted((first[1], point[1]))
            self.roi_select = []
            if right - left < 20 or bottom - top < 20:
                self.message = "ROI too small; press R to select again."
                return
            self.evaluation_roi = [left, top, right, bottom]
            self.message = "ROI saved in memory. Mark ALL verifiable real stalls inside it."
            return
        next_pending = self.pending + [point]
        if len(next_pending) < 4:
            self.pending = next_pending
            self.message = f"Corner {len(self.pending)}/4; keep going around the same stall"
            return
        try:
            if not all(
                self.evaluation_roi[0] <= px <= self.evaluation_roi[2]
                and self.evaluation_roi[1] <= py <= self.evaluation_roi[3]
                for px, py in next_pending
            ):
                raise ParkingConfigError("Stall lies outside selected evaluation ROI")
            proposed = self.spaces + [{
                "id": len(self.spaces) + 1, "points": next_pending,
            }]
            validate_config({
                "version": 1, "next_space_id": len(proposed) + 1,
                "spaces": proposed,
            })
        except ParkingConfigError as error:
            self.pending = []
            self.message = f"Invalid or overlapping stall: {error}"
            return
        self.spaces = proposed
        self.pending = []
        self.message = f"Marked stall {len(self.spaces)}; mark next or press S to save"

    def start_roi(self):
        if self.pending or self.spaces:
            self.message = "Choose ROI before marking stalls; Q exits without saving."
        else:
            # A sentinel first corner allows normal clicks to select the ROI.
            self.roi_select = [[-1, -1]]
            self.message = "Click first ROI corner, then its opposite corner"

    def undo(self):
        if self.roi_select:
            self.roi_select = []
            self.message = "ROI selection cancelled"
        elif self.pending:
            self.pending.pop()
            self.message = f"Unfinished corners remaining: {len(self.pending)}"
        elif self.spaces:
            self.spaces.pop()
            self.message = f"Removed last completed stall; {len(self.spaces)} remain"
        else:
            self.message = "Nothing to undo"

    def truth(self):
        if self.pending or self.roi_select:
            raise ValueError("Finish or undo unfinished corners/ROI before saving")
        report = {
            "format": "uniparkingbuddy-stall-layout-truth-v1",
            "source_video": str(self.video),
            "source_video_sha256": file_sha256(self.video),
            "frame_index": self.frame_index,
            "frame_size": [self.width, self.height],
            "evaluation_roi_xyxy": self.evaluation_roi,
            "annotation_method": "human_independent_original_frame",
            "scope_note": (
                "Every clearly visible, verifiable stall inside the selected ROI "
                "must be annotated; any ambiguous areas should be excluded from the ROI. "
                "No algorithm proposal was displayed to the annotator."
            ),
            "spaces": self.spaces,
        }
        validate_truth(report)
        return report

    def draw(self):
        preview = cv2.resize(
            self.frame, (self.display_width, self.display_height)
        )
        canvas = np.zeros((self.display_height + 85, self.display_width, 3), dtype=np.uint8)
        canvas[:self.display_height] = preview
        rx1, ry1, rx2, ry2 = self.evaluation_roi
        r1 = source_to_display(
            [rx1, ry1], self.width, self.height, self.display_width, self.display_height
        )
        r2 = source_to_display(
            [rx2, ry2], self.width, self.height, self.display_width, self.display_height
        )
        cv2.rectangle(canvas, r1, r2, (255, 190, 0), 2)
        for space in self.spaces:
            points = np.array([
                source_to_display(
                    p, self.width, self.height,
                    self.display_width, self.display_height,
                )
                for p in space["points"]
            ], dtype=np.int32)
            cv2.polylines(canvas, [points], True, (0, 220, 0), 2)
            mid = tuple(points.mean(axis=0).astype(int))
            cv2.putText(
                canvas, str(space["id"]), mid,
                cv2.FONT_HERSHEY_SIMPLEX, 0.65, (255, 255, 255), 2
            )
        if self.pending:
            points = np.array([
                source_to_display(
                    p, self.width, self.height,
                    self.display_width, self.display_height,
                )
                for p in self.pending
            ], dtype=np.int32)
            for point in points:
                cv2.circle(canvas, tuple(point), 4, (0, 230, 255), -1)
            if len(points) > 1:
                cv2.polylines(canvas, [points], False, (0, 230, 255), 2)
        for i, line in enumerate((
            f"INDEPENDENT HUMAN GROUND TRUTH | frame {self.frame_index} | stalls {len(self.spaces)}",
            "R: select ROI first (2 corners) | LEFT: stall corners | U: undo | S: save | Q: quit",
            self.message[:max(12, self.display_width // 11)],
        )):
            cv2.putText(
                canvas, line, (10, self.display_height + 23 + 26 * i),
                cv2.FONT_HERSHEY_SIMPLEX, 0.52, (240, 240, 240), 1
            )
        return canvas


def annotate(video_path, output, frame_index=0, width=1280):
    """Capture human truth; deliberately no algorithm proposals in this GUI."""
    video_path = Path(video_path).resolve()
    output = Path(output)
    if output.exists():
        raise FileExistsError("Output already exists; existing annotations are protected")
    if type(frame_index) is not int or frame_index < 0:
        raise ValueError("Frame index must be a nonnegative integer")
    frame = video_frame(video_path, frame_index)
    session = BlindLayoutAnnotation(video_path, frame, frame_index, width)
    title = f"Blind stall annotation - frame {frame_index}"
    print("Mark only verifiable real stalls. Unclear/occluded stalls may be omitted.")
    print("S saves local benchmark truth ONLY. Q discards unsaved annotation.")
    cv2.namedWindow(title, cv2.WINDOW_AUTOSIZE)

    def on_mouse(event, x, y, _flags, _param):
        if event == cv2.EVENT_LBUTTONDOWN:
            session.click(x, y)

    try:
        cv2.setMouseCallback(title, on_mouse)
        while True:
            cv2.imshow(title, session.draw())
            key = cv2.waitKey(45) & 0xFF
            if key in (ord("q"), 27):
                print("Discarded unsaved layout annotation")
                return None
            if key == ord("u"):
                session.undo()
            if key == ord("r"):
                session.start_roi()
            if key == ord("s"):
                try:
                    truth = session.truth()
                except (ValueError, ParkingConfigError) as error:
                    session.message = f"Cannot save: {error}"
                    print(session.message, file=sys.stderr)
                    continue
                output.mkdir(parents=True, exist_ok=False)
                with (output / "ground_truth.json").open("x", encoding="utf-8") as dest:
                    json.dump(truth, dest, indent=2)
                    dest.write("\n")
                print(f"Saved {len(session.spaces)} HUMAN-marked stalls to "
                      f"{output / 'ground_truth.json'}")
                print("No approved camera config or production database was changed.")
                return truth
    finally:
        cv2.destroyWindow(title)


def _proposed_sets(report):
    kind = report.get("format")
    if kind == "uniparkingbuddy-unverified-stall-geometry-v1":
        return {"phase2_all": report["candidates"]}
    if kind == "uniparkingbuddy-unverified-stall-review-v1":
        return {
            "phase3_all": report["candidates"],
            "phase3_shortlist": [
                p for p in report["candidates"]
                if p.get("review_tier") in ("multiple_cues", "row_evidence", "vehicle_evidence")
            ]
        }
    if kind == "uniparkingbuddy-unverified-row-continuity-v1":
        return {
            f"joined_{source}_{selection}": (
                data["review"]["candidates"] if selection == "all" else [
                    p for p in data["review"]["candidates"]
                    if p.get("review_tier") in (
                        "multiple_cues", "row_evidence", "vehicle_evidence"
                    )
                ]
            )
            for source, data in report["variants"].items()
            for selection in ("all", "shortlist")
        }
    raise ValueError("Unsupported candidate proposal report")


def polygon_iou(a, b):
    left = np.asarray(a, dtype=np.float32).reshape((4, 2))
    right = np.asarray(b, dtype=np.float32).reshape((4, 2))
    intersection, _ = cv2.intersectConvexConvex(left, right)
    area = float(cv2.contourArea(left) + cv2.contourArea(right) - intersection)
    return float(intersection) / area if area > 0 else 0.0


def _one_to_one_scores(truth, proposals, threshold):
    """Maximum-cardinality unique matches; preference ordered by polygon IoU."""
    overlap = [
        [polygon_iou(t["points"], p["suggested_quadrilateral_xy"]) for p in proposals]
        for t in truth
    ]
    neighbors = [
        sorted(
            (j for j, iou in enumerate(row) if iou >= threshold),
            key=lambda j: (-row[j], j)
        )
        for row in overlap
    ]
    matched_proposal = {}

    def assign(i, visited):
        for j in neighbors[i]:
            if j in visited:
                continue
            visited.add(j)
            if j not in matched_proposal or assign(matched_proposal[j], visited):
                matched_proposal[j] = i
                return True
        return False

    for index in range(len(truth)):
        assign(index, set())
    tp = len(matched_proposal)
    fp = len(proposals) - tp
    fn = len(truth) - tp
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    return {
        "minimum_polygon_iou": threshold,
        "true_positive": tp,
        "false_positive": fp,
        "false_negative": fn,
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1": round(2 * precision * recall / (precision + recall), 4)
        if precision + recall else 0.0,
        "matched_pairs": [
            {
                "truth_stall_id": truth[i]["id"],
                "candidate_id": proposals[j].get("candidate_id", f"candidate_{j + 1}"),
                "polygon_iou": round(overlap[i][j], 4)
            }
            for j, i in sorted(matched_proposal.items())
        ]
    }


def score_ground_truth(truth, report):
    shape = validate_truth(truth)
    if report.get("source_video_sha256") != truth["source_video_sha256"]:
        raise ValueError("Proposal source video does not match independently labeled video")
    results = {}
    roi = truth["evaluation_roi_xyxy"]
    for name, proposals in _proposed_sets(report).items():
        if not isinstance(proposals, list):
            raise ValueError("Expected candidate proposal list")
        for candidate in proposals:
            if candidate.get("review_state") != "unverified":
                raise ValueError("Only unverified experimental candidates supported")
            convex_quad(candidate.get("suggested_quadrilateral_xy"), shape)
        # Only fully contained proposals belong to the independently
        # exhaustively labeled ROI. Do not penalize unknown parts of the scene.
        eligible = [
            p for p in proposals
            if all(
                roi[0] <= x <= roi[2] and roi[1] <= y <= roi[3]
                for x, y in p["suggested_quadrilateral_xy"]
            )
        ]
        results[name] = {
            "predicted_candidate_count": len(eligible),
            "excluded_outside_roi": len(proposals) - len(eligible),
            "iou_thresholds": {
                str(threshold): _one_to_one_scores(
                    truth["spaces"], eligible, threshold
                )
                for threshold in IOU_THRESHOLDS
            },
        }
    return {
        "format": "uniparkingbuddy-stall-discovery-evaluation-v1",
        "source_video_sha256": truth["source_video_sha256"],
        "independently_labeled_stalls": len(truth["spaces"]),
        "ground_truth_frame_index": truth["frame_index"],
        "evaluation_roi_xyxy": roi,
        "metrics": results,
        "limitations": [
            "Manually visible/verifiable marked stalls in one selected fixed-view ROI.",
            "Every clearly visible real stall in ROI must be labeled; missing human labels bias precision.",
            "Unmarked, permanently occluded or out-of-view stalls are not evaluated.",
            "Pixel-space IoU is affected by viewpoint, annotation ambiguity and perspective.",
            "IoU thresholds are exploratory benchmark choices, not approved SRS criteria.",
            "One sample video is not evidence of generalization to unseen lots.",
            "Scoring geometry does not measure AVAILABLE/OCCUPIED classification.",
            "A proposal overlapping an actual stall is not automatically approved for live use.",
        ]
    }


def score_file(truth_path, proposals_path, output_path):
    output_path = Path(output_path)
    if output_path.exists():
        raise FileExistsError("Existing benchmark report will not be overwritten")
    with Path(truth_path).open(encoding="utf-8") as handle:
        truth = json.load(handle)
    with Path(proposals_path).open(encoding="utf-8") as handle:
        proposed = json.load(handle)
    source = Path(truth.get("source_video", "")) if truth.get("source_video") else None
    # Verify source again if the annotator's original absolute path is available.
    if source and source.is_file() and file_sha256(source) != truth["source_video_sha256"]:
        raise ValueError("Original source video checksum changed")
    result = score_ground_truth(truth, proposed)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("x", encoding="utf-8") as stream:
        json.dump(result, stream, indent=2)
        stream.write("\n")
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    a = sub.add_parser("annotate", help="Blindly mark verifiable stalls on an original video frame")
    a.add_argument("--video", required=True, type=Path)
    a.add_argument("--output", required=True, type=Path)
    a.add_argument("--frame", type=int, default=0)
    a.add_argument("--width", type=int, default=1280)
    s = sub.add_parser("score", help="Compare frozen human labels with experimental proposals")
    s.add_argument("--truth", required=True, type=Path)
    s.add_argument("--proposals", required=True, type=Path)
    s.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        if args.command == "annotate":
            annotate(args.video, args.output, args.frame, args.width)
        else:
            metrics = score_file(args.truth, args.proposals, args.output)
            print(f"Evaluated {metrics['independently_labeled_stalls']} human-verified stalls")
            for label, group in metrics["metrics"].items():
                result = group["iou_thresholds"]["0.5"]
                print(
                    f"{label}: candidates={group['predicted_candidate_count']}, "
                    f"matched={result['true_positive']}, "
                    f"FP={result['false_positive']}, FN={result['false_negative']}, "
                    f"precision={result['precision']:.3f}, recall={result['recall']:.3f}"
                )
            print(f"Saved experimental geometry benchmark: {args.output}")
            print("These are NOT live occupancy accuracy measurements.")
    except (OSError, ValueError, KeyError, TypeError, ParkingConfigError,
            json.JSONDecodeError) as error:
        print(f"Stall geometry benchmark unavailable: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
