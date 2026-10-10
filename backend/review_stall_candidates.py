"""Phase 3, read-only quality review of proposed parking-stall geometry.

Re-ranks Phase 2 candidates using row continuity and optional independent
Phase 1 vehicle-box scale evidence. Explicitly demotes roof/window-sized
shapes and isolated paint-pair artifacts; never approves parking stalls.

No config, FastAPI, database, React or official documents are modified.
All values are exploratory heuristics, NOT validated model thresholds.
"""

import argparse
from copy import deepcopy
import json
import math
from pathlib import Path
import sys

import cv2
import numpy as np

from .accuracy_evaluation import file_sha256


def _quad(candidate):
    points = np.asarray(candidate.get("suggested_quadrilateral_xy"), dtype=np.float32)
    if points.shape != (4, 2) or not np.isfinite(points).all():
        raise ValueError("Candidate quadrilateral must contain four finite 2D points")
    polygon = points.reshape((-1, 1, 2))
    if not cv2.isContourConvex(polygon) or cv2.contourArea(polygon) <= 0:
        raise ValueError("Candidate quadrilateral must be convex and nondegenerate")
    return points


def _lines(candidate):
    lines = np.asarray(candidate.get("supporting_marking_lines_xyxy"), dtype=np.float64)
    if lines.shape != (2, 4) or not np.isfinite(lines).all():
        raise ValueError("Candidate requires two finite supporting line segments")
    if np.any(np.linalg.norm(lines[:, 2:] - lines[:, :2], axis=1) <= 0):
        raise ValueError("Candidate includes a zero-length separator")
    return lines


def _same_stroke(first, second):
    a, b = np.asarray(first, dtype=float).reshape(2, 2)
    c, d = np.asarray(second, dtype=float).reshape(2, 2)
    max_length = max(np.linalg.norm(a - b), np.linalg.norm(c - d))
    tolerance = min(18.0, 4.0 + max_length * 0.055)
    return min(
        max(np.linalg.norm(a - c), np.linalg.norm(b - d)),
        max(np.linalg.norm(a - d), np.linalg.norm(b - c))
    ) <= tolerance


def _row_neighbors(first, second):
    """Adjacent spaces should share a divider, not just both be rectangular."""
    lines_a, lines_b = _lines(first), _lines(second)
    shared = any(_same_stroke(a, b) for a in lines_a for b in lines_b)
    if not shared:
        return False
    a = _quad(first)
    b = _quad(second)
    areas = (cv2.contourArea(a), cv2.contourArea(b))
    if min(areas) / max(areas) < 0.34:
        return False
    # The adjacent stalls should have similar apparent depth.
    lens = [
        float(np.median(np.linalg.norm(lines[:, 2:] - lines[:, :2], axis=1)))
        for lines in (lines_a, lines_b)
    ]
    if min(lens) / max(lens) < 0.55:
        return False
    return True


def _boxes(vehicles):
    boxes = []
    for vehicle in vehicles:
        raw = vehicle.get("proxy_vehicle_box_xyxy")
        box = np.asarray(raw, dtype=np.float32)
        if box.shape != (4,) or not np.isfinite(box).all():
            raise ValueError("Malformed Phase 1 proxy vehicle box")
        x1, y1, x2, y2 = map(float, box)
        if x2 <= x1 or y2 <= y1:
            raise ValueError("Phase 1 proxy vehicle box must have positive area")
        boxes.append((x1, y1, x2, y2))
    return boxes


def _rectangle(box):
    x1, y1, x2, y2 = box
    return np.array(
        [[x1, y1], [x2, y1], [x2, y2], [x1, y2]], dtype=np.float32
    )


def _car_interior_artifact(polygon, vehicle_boxes, area_fraction=0.27,
                           contained_fraction=0.78):
    """Strongly demote a tiny proposed bay *inside* a repeatedly seen car box.

    This catches window/roof edges that Phase 2 mistook for stall paint.
    It intentionally leaves larger or only partially intersecting bays
    for human review. Pixel box bounds are NOT ground-plane car footprints.
    """
    area = cv2.contourArea(polygon)
    for box in vehicle_boxes:
        car_area = (box[2] - box[0]) * (box[3] - box[1])
        if area >= area_fraction * car_area:
            continue
        intersection, _ = cv2.intersectConvexConvex(polygon, _rectangle(box))
        if float(intersection) / area >= contained_fraction:
            return True
    return False


def assess_geometry(geometry_report, vehicle_report=None):
    """Return all hypotheses with traceable review tiers and rejection reasons.

    A row-shaped hypothesis can enter the *review shortlist*, never the
    approved config. Singletons remain in secondary review for possible
    isolated real spaces and missing neighboring evidence.
    """
    if geometry_report.get("format") != "uniparkingbuddy-unverified-stall-geometry-v1":
        raise ValueError("Expected Phase 2 stall-geometry report")
    proposals = geometry_report.get("candidates")
    if not isinstance(proposals, list):
        raise ValueError("Phase 2 candidates list is malformed")

    vehicles = []
    if vehicle_report is not None:
        if vehicle_report.get("format") != "uniparkingbuddy-unverified-vehicle-locations-v1":
            raise ValueError("Expected Phase 1 vehicle-location report")
        if vehicle_report.get("source_video_sha256") != geometry_report.get("source_video_sha256"):
            raise ValueError("Phase 1 and Phase 2 video hashes do not match")
        vehicles = vehicle_report.get("proposals")
        if not isinstance(vehicles, list):
            raise ValueError("Phase 1 vehicle proposals list is malformed")
    car_boxes = _boxes(vehicles)
    for candidate in proposals:
        _quad(candidate)
        _lines(candidate)
        if not isinstance(candidate.get("candidate_id"), str):
            raise ValueError("Missing candidate_id")

    neighbor_sets = []
    for i, candidate in enumerate(proposals):
        neighbor_sets.append(sorted(
            other["candidate_id"] for j, other in enumerate(proposals)
            if i != j and _row_neighbors(candidate, other)
        ))

    assessed = []
    for candidate, neighbors in zip(proposals, neighbor_sets):
        item = deepcopy(candidate)
        polygon = _quad(item)
        area = round(float(cv2.contourArea(polygon)), 1)
        center = [round(float(x), 1) for x in polygon.mean(axis=0)]
        matched_ids = []
        for vehicle, box in zip(vehicles, car_boxes):
            # Approximate ground anchor (not a physical footprint).
            anchor = vehicle.get("ground_anchor_xy")
            if (not isinstance(anchor, list) or len(anchor) != 2
                    or any(type(x) not in (int, float) or not math.isfinite(x)
                           for x in anchor)):
                raise ValueError("Malformed Phase 1 ground anchor")
            if cv2.pointPolygonTest(
                polygon.reshape((-1, 1, 2)),
                (float(anchor[0]), float(anchor[1])), False
            ) >= 0:
                matched_ids.append(vehicle["proposal_id"])
        item["row_neighbor_candidate_ids"] = neighbors
        item["corroborating_vehicle_location_ids"] = sorted(set(matched_ids))
        item["polygon_area_pixels"] = area
        item["center_xy"] = center
        item["review_state"] = "unverified"
        item["review_reasons"] = []
        if _car_interior_artifact(polygon, car_boxes):
            item["review_tier"] = "likely_artifact"
            item["review_reasons"].append("tiny_polygon_largely_inside_repeated_vehicle_box")
        elif neighbors and matched_ids:
            item["review_tier"] = "multiple_cues"
            item["review_reasons"].extend([
                "shares_marked_divider_with_row_neighbor",
                "recurring_vehicle_ground_anchor_in_polygon",
            ])
        elif neighbors:
            item["review_tier"] = "row_evidence"
            item["review_reasons"].append("shares_marked_divider_with_row_neighbor")
        elif matched_ids:
            item["review_tier"] = "vehicle_evidence"
            item["review_reasons"].append("recurring_vehicle_ground_anchor_in_polygon")
        else:
            item["review_tier"] = "weak_evidence"
            item["review_reasons"].append("isolated_line_pair_no_repeated_vehicle_anchor")
        assessed.append(item)

    order = {"multiple_cues": 0, "row_evidence": 1, "vehicle_evidence": 2,
             "weak_evidence": 3, "likely_artifact": 4}
    assessed.sort(key=lambda item: (
        order[item["review_tier"]],
        -float(item["relative_geometry_score"]),
        item["candidate_id"],
    ))
    return {
        "format": "uniparkingbuddy-unverified-stall-review-v1",
        "review_state": "unverified_proposals_only",
        "source_video_sha256": geometry_report["source_video_sha256"],
        "phase1_hypotheses_used": vehicle_report is not None,
        "candidate_count": len(assessed),
        "shortlist_count": sum(
            item["review_tier"] in ("multiple_cues", "row_evidence", "vehicle_evidence")
            for item in assessed
        ),
        "suspected_artifact_count": sum(
            item["review_tier"] == "likely_artifact" for item in assessed
        ),
        "candidates": assessed,
        "limitations": [
            "Candidate shortlist is a human-review queue, NOT certified parking stalls.",
            "Shared paint-like segments can be lane lines or static car edges.",
            "Repeated vehicle boxes cannot prove legal parking or correct depth.",
            "Unobserved isolated true bays can remain in weak_evidence, not the shortlist.",
            "No homography, camera-motion validation, calibration, or field accuracy claim.",
            "Never feed these unapproved polygons into the live availability dashboard.",
        ],
    }


def render_review(frame, report):
    """Show shortlist only, with tiny excluded artifacts optionally as red crosses."""
    result = frame.copy()
    for candidate in report["candidates"]:
        tier = candidate["review_tier"]
        center = tuple(int(x) for x in candidate["center_xy"])
        if tier == "likely_artifact":
            cv2.line(result, (center[0] - 5, center[1] - 5),
                     (center[0] + 5, center[1] + 5), (0, 0, 230), 1)
            continue
        if tier == "weak_evidence":
            continue
        polygon = np.array(candidate["suggested_quadrilateral_xy"], dtype=np.int32)
        color = (30, 200, 30) if tier == "multiple_cues" else (0, 190, 255)
        cv2.polylines(result, [polygon], True, color, 2)
        cv2.putText(result, candidate["candidate_id"], center,
                    cv2.FONT_HERSHEY_SIMPLEX, 0.55, color, 2)
    cv2.putText(result, "REVIEW SHORTLIST ONLY - NOT VERIFIED PARKING STALLS",
                (10, max(22, result.shape[0] - 12)),
                cv2.FONT_HERSHEY_SIMPLEX, 0.62, (0, 0, 255), 2)
    return result


def review_video_geometry(video_path, phase2_path, output_dir, phase1_path=None):
    """Read existing experiment reports, check input hash, save local review."""
    video_path = Path(video_path).resolve()
    output_dir = Path(output_dir)
    if output_dir.exists():
        raise FileExistsError("Review output already exists; use a new folder")
    source_hash = file_sha256(video_path)
    geometry = json.loads(Path(phase2_path).read_text(encoding="utf-8"))
    if geometry.get("source_video_sha256") != source_hash:
        raise ValueError("Phase 2 geometry report belongs to a different video")
    vehicle = None
    if phase1_path:
        vehicle = json.loads(Path(phase1_path).read_text(encoding="utf-8"))
    report = assess_geometry(geometry, vehicle)
    indices = geometry.get("sampled_frame_indices")
    if (not isinstance(indices, list) or not indices
            or type(indices[0]) is not int or indices[0] < 0):
        raise ValueError("Phase 2 sampled frame index missing or invalid")
    capture = cv2.VideoCapture(str(video_path))
    try:
        if not capture.isOpened() or not capture.set(cv2.CAP_PROP_POS_FRAMES, indices[0]):
            raise ValueError("Cannot open or seek to original video frame")
        ok, frame = capture.read()
        if not ok or frame is None:
            raise ValueError("Cannot read referenced source video frame")
    finally:
        capture.release()
    output_dir.mkdir(parents=True, exist_ok=False)
    (output_dir / "review.json").write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8"
    )
    if not cv2.imwrite(str(output_dir / "review_preview.png"),
                       render_review(frame, report)):
        raise OSError("Unable to create review preview")
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--video", required=True, type=Path)
    parser.add_argument("--geometry", required=True, type=Path,
                        help="Phase 2 stall_candidates.json")
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--hypotheses", type=Path,
                        help="Optional Phase 1 hypotheses.json")
    args = parser.parse_args(argv)
    try:
        report = review_video_geometry(
            args.video, args.geometry, args.output, args.hypotheses
        )
    except (OSError, ValueError, TypeError, KeyError, json.JSONDecodeError) as error:
        print(f"Geometry review cannot proceed: {error}", file=sys.stderr)
        return 1
    print(f"Phase 3: {report['candidate_count']} unverified hypotheses, "
          f"{report['shortlist_count']} review shortlist, "
          f"{report['suspected_artifact_count']} suspected car-surface artifacts.")
    print(f"Inspect review_preview.png and review.json in {args.output}")
    print("No stall was approved, and no configuration or occupancy data changed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
