"""Read-only parking-marking / geometry proposals from a fixed-view video.

Phase 2 of adaptive discovery. White/yellow marking pixels accumulated across
sampled frames yield Hough segments; adjacent, approximately parallel
separators propose quadrilateral *hypotheses*. Optional Phase-1 vehicle
locations supply corroboration, never automatic approval.

Camera perspective, parked vehicles, lane lines and other bright scene edges
can cause false/missed proposals. This is not verified stall detection.
Nothing in this file writes configs, occupancy history or public UI state.
"""

import argparse
import json
import math
from pathlib import Path
import sys

import cv2
import numpy as np

from .accuracy_evaluation import PROJECT_ROOT, file_sha256, sample_frame_indices
from .ground_paint_evidence import (
    filter_ground_supported_lines, render_line_context,
)


def marking_mask(frame):
    """High-value, low-saturation paint plus yellow-ish markings.

    Experimental thresholds, not universal painted-line segmentation.
    """
    if not isinstance(frame, np.ndarray) or frame.ndim != 3 or frame.shape[2] != 3:
        raise ValueError("Expected a BGR color video frame")
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    white = cv2.inRange(hsv, (0, 0, 165), (179, 100, 255))
    yellow = cv2.inRange(hsv, (14, 85, 110), (43, 255, 255))
    result = cv2.bitwise_or(white, yellow)
    return cv2.morphologyEx(
        result, cv2.MORPH_OPEN, np.ones((2, 2), dtype=np.uint8)
    )


def persistent_markings(frames, support_fraction=0.5):
    """Keep bright marking pixels found in multiple same-size frames.

    Static white vehicles, curbs, buildings and signs may also survive.
    """
    if not 0 < support_fraction <= 1 or not math.isfinite(support_fraction):
        raise ValueError("support_fraction must be between 0 and 1")
    if not frames:
        raise ValueError("At least one frame is required")
    shape = frames[0].shape
    if any(frame.shape != shape for frame in frames):
        raise ValueError("Video frame sizes differ; fixed view required")
    votes = np.zeros(shape[:2], dtype=np.uint16)
    for frame in frames:
        votes += (marking_mask(frame) > 0).astype(np.uint16)
    mask = np.where(
        votes >= math.ceil(len(frames) * support_fraction), 255, 0
    ).astype(np.uint8)
    return cv2.morphologyEx(
        mask, cv2.MORPH_CLOSE, np.ones((3, 3), dtype=np.uint8)
    )


def _length(line):
    x1, y1, x2, y2 = line
    return math.hypot(x2 - x1, y2 - y1)


def _direction(line):
    d = np.array([line[2] - line[0], line[3] - line[1]], dtype=float)
    return d / np.linalg.norm(d)


def _line_angle_distance(first, second):
    return math.degrees(math.acos(
        min(1.0, abs(float(np.dot(_direction(first), _direction(second)))))
    ))


def _overlap_along(first, second):
    u = _direction(first)
    a = sorted([np.dot(first[:2], u), np.dot(first[2:], u)])
    b = sorted([np.dot(second[:2], u), np.dot(second[2:], u)])
    return max(0.0, min(a[1], b[1]) - max(a[0], b[0]))


def _perpendicular_distance(first, second):
    mid_a = np.array(
        [(first[0] + first[2]) / 2, (first[1] + first[3]) / 2],
        dtype=float
    )
    mid_b = np.array(
        [(second[0] + second[2]) / 2, (second[1] + second[3]) / 2],
        dtype=float
    )
    u = _direction(first)
    return abs(float(np.cross(u, mid_b - mid_a)))


def _consolidate_segments(lines, tolerance=7):
    """Suppress duplicate paint edges, retaining the longest local stroke."""
    selected = []
    for line in sorted(lines, key=_length, reverse=True):
        if not any(
            _line_angle_distance(line, old) < 9
            and _perpendicular_distance(old, line) <= tolerance
            and _overlap_along(old, line) >= 0.35 * min(_length(old), _length(line))
            for old in selected
        ):
            selected.append(line)
    return selected


def detect_marking_lines(mask, min_line_length=None):
    """Candidate visible strokes, not a classifier of parking lines."""
    if not isinstance(mask, np.ndarray) or mask.ndim != 2 or mask.dtype != np.uint8:
        raise ValueError("Expected an 8-bit single-channel marking mask")
    height, width = mask.shape
    if height < 16 or width < 16:
        return []
    line_length = min_line_length or max(16, round(min(height, width) / 55))
    if type(line_length) is not int or line_length < 2:
        raise ValueError("min_line_length must be an integer >= 2")
    edges = cv2.Canny(mask, 50, 130)
    segments = cv2.HoughLinesP(
        edges, rho=1, theta=np.pi / 180,
        threshold=max(9, round(line_length * 0.6)),
        minLineLength=line_length, maxLineGap=max(5, round(line_length * 0.25))
    )
    if segments is None:
        return []
    # OpenCV may return (N, 1, 4) or (N, 4); normalize before filtering.
    lines = [
        tuple(int(v) for v in segment)
        for segment in np.asarray(segments).reshape((-1, 4))
        if _length(segment) >= line_length
    ]
    return _consolidate_segments(lines, tolerance=max(4, round(min(height, width) / 180)))


def _point_at_projection(line, unit, projection):
    p = np.asarray(line[:2], dtype=float)
    q = np.asarray(line[2:], dtype=float)
    denominator = float(np.dot(q - p, unit))
    if abs(denominator) < 1e-8:
        raise ValueError("Projection is degenerate")
    return p + (q - p) * ((projection - np.dot(p, unit)) / denominator)


def _quadrilateral_between(a, b, image_shape):
    """Overlap longitudinal line ranges, without extrapolating unseen bays."""
    unit = _direction(a)
    aa = sorted([np.dot(a[:2], unit), np.dot(a[2:], unit)])
    bb = sorted([np.dot(b[:2], unit), np.dot(b[2:], unit)])
    start = max(aa[0], bb[0])
    end = min(aa[1], bb[1])
    if end <= start or end - start < 0.55 * min(_length(a), _length(b)):
        return None
    coordinates = [
        _point_at_projection(a, unit, start),
        _point_at_projection(b, unit, start),
        _point_at_projection(b, unit, end),
        _point_at_projection(a, unit, end),
    ]
    polygon = np.rint(coordinates).astype(np.int32)
    height, width = image_shape[:2]
    if (np.any(polygon[:, 0] < 0) or np.any(polygon[:, 0] >= width)
            or np.any(polygon[:, 1] < 0) or np.any(polygon[:, 1] >= height)):
        return None
    if len({tuple(p) for p in polygon.tolist()}) < 4:
        return None
    if not cv2.isContourConvex(polygon.reshape((-1, 1, 2))):
        return None
    if cv2.contourArea(polygon) < 64:
        return None
    return polygon


def _has_intermediate_separator(a, b, all_lines, min_overlap):
    """Skip nonadjacent line pairs if a third co-oriented separator lies between."""
    u = _direction(a)
    normal = np.array([-u[1], u[0]])
    mid_a = (np.array(a[:2]) + np.array(a[2:])) / 2
    mid_b = (np.array(b[:2]) + np.array(b[2:])) / 2
    pos_b = float(np.dot(mid_b - mid_a, normal))
    for other in all_lines:
        if other is a or other is b:
            continue
        if _line_angle_distance(a, other) > 14:
            continue
        middle = (np.array(other[:2]) + np.array(other[2:])) / 2
        pos = float(np.dot(middle - mid_a, normal))
        if min(0, pos_b) + 5 < pos < max(0, pos_b) - 5:
            if _overlap_along(a, other) >= min_overlap:
                return True
    return False


def propose_stall_geometry(lines, image_shape, max_candidates=150):
    """Create unverified quad suggestions from adjacent parallel paint strokes.

    Assumes visible portions of two *separating* marking strokes. Without
    knowledge of legal parking or perpendicular end lines, false candidates
    can occur. Uses experimental geometry ratios, not SRS thresholds.
    """
    if len(image_shape) < 2 or min(image_shape[:2]) < 16:
        raise ValueError("A valid image shape is required")
    if type(max_candidates) is not int or max_candidates < 1:
        raise ValueError("max_candidates must be a positive integer")
    proposals = []
    lines = list(lines)
    for i, a in enumerate(lines):
        for b in lines[i + 1:]:
            if _line_angle_distance(a, b) > 15:
                continue
            if _overlap_along(a, b) < 0.6 * min(_length(a), _length(b)):
                continue
            if min(_length(a), _length(b)) / max(_length(a), _length(b)) < 0.48:
                continue
            width = _perpendicular_distance(a, b)
            depth = (_length(a) + _length(b)) / 2
            if not (0.20 * depth <= width <= 1.6 * depth):
                continue
            if _has_intermediate_separator(a, b, lines, 0.5 * min(_length(a), _length(b))):
                continue
            polygon = _quadrilateral_between(a, b, image_shape)
            if polygon is None:
                continue
            # Prefer strong visible stroke length and near-parallelism.
            rating = round(
                min(_length(a), _length(b)) / max(1, min(image_shape[:2]))
                / (1 + _line_angle_distance(a, b) / 10), 5
            )
            proposals.append({
                "suggested_quadrilateral_xy": polygon.tolist(),
                "supporting_marking_lines_xyxy": [list(a), list(b)],
                "relative_geometry_score": rating,
                "review_state": "unverified",
                "evidence_sources": ["persistent_paint_like_line_pair"],
            })

    proposals.sort(key=lambda p: p["relative_geometry_score"], reverse=True)
    unique = []
    for suggestion in proposals:
        polygon = np.array(suggestion["suggested_quadrilateral_xy"], dtype=np.float32)
        overlapping = False
        for saved in unique:
            existing = np.array(saved["suggested_quadrilateral_xy"], dtype=np.float32)
            overlap_area, _ = cv2.intersectConvexConvex(polygon, existing)
            min_area = min(cv2.contourArea(polygon), cv2.contourArea(existing))
            if min_area and overlap_area / min_area > 0.5:
                overlapping = True
                break
        if not overlapping:
            unique.append(suggestion)
        if len(unique) >= max_candidates:
            break
    unique.sort(key=lambda p: (
        float(np.mean(np.array(p["suggested_quadrilateral_xy"])[:, 1])),
        float(np.mean(np.array(p["suggested_quadrilateral_xy"])[:, 0])),
    ))
    for idx, proposal in enumerate(unique, 1):
        proposal["candidate_id"] = f"L{idx:03d}"
    return unique


def correlate_vehicle_hypotheses(proposals, hypothesis_report, source_hash):
    """Annotate proposed quads with Phase-1 anonymous anchor evidence."""
    if hypothesis_report.get("format") != "uniparkingbuddy-unverified-vehicle-locations-v1":
        raise ValueError("Unsupported Phase-1 hypothesis format")
    if hypothesis_report.get("source_video_sha256") != source_hash:
        raise ValueError("Phase-1 hypotheses were generated from a different video")
    vehicles = hypothesis_report.get("proposals")
    if not isinstance(vehicles, list):
        raise ValueError("Malformed Phase-1 hypotheses")
    for proposal in proposals:
        contour = np.array(
            proposal["suggested_quadrilateral_xy"], dtype=np.float32
        ).reshape((-1, 1, 2))
        matched = []
        for vehicle in vehicles:
            anchor = vehicle.get("ground_anchor_xy")
            if (not isinstance(anchor, list) or len(anchor) != 2
                    or any(not isinstance(value, (int, float))
                           or not math.isfinite(value) for value in anchor)):
                raise ValueError("Malformed vehicle anchor in Phase-1 report")
            if cv2.pointPolygonTest(contour, tuple(float(x) for x in anchor), False) >= 0:
                matched.append(vehicle["proposal_id"])
        proposal["corroborating_vehicle_location_ids"] = sorted(set(matched))
        if matched:
            proposal["evidence_sources"].append("recurring_vehicle_location")
    return proposals


def render_geometry_preview(frame, lines, proposals):
    """Draw paint-like strokes and unverified quadrilaterals on a copy."""
    result = frame.copy()
    for x1, y1, x2, y2 in lines:
        cv2.line(result, (x1, y1), (x2, y2), (0, 220, 255), 1)
    for proposal in proposals:
        polygon = np.array(proposal["suggested_quadrilateral_xy"], dtype=np.int32)
        corroborated = bool(proposal.get("corroborating_vehicle_location_ids"))
        color = (255, 0, 255) if corroborated else (255, 210, 0)
        cv2.polylines(result, [polygon], True, color, 2)
        center = np.rint(np.mean(polygon, axis=0)).astype(int)
        cv2.putText(
            result, proposal["candidate_id"], tuple(center),
            cv2.FONT_HERSHEY_SIMPLEX, 0.55, color, 2
        )
    cv2.putText(
        result, "UNVERIFIED STALL HYPOTHESES - NOT LIVE OCCUPANCY",
        (10, max(24, result.shape[0] - 15)),
        cv2.FONT_HERSHEY_SIMPLEX, 0.58, (0, 0, 255), 2
    )
    return result


def analyze_video_markings(video_path, output_dir, requested_frames=12,
                           support_fraction=0.5, hypotheses_path=None,
                           use_ground_filter=False, ground_min_fraction=0.33):
    """Generate read-only local marking and geometry evidence for a video."""
    video_path = Path(video_path).resolve()
    output_dir = Path(output_dir)
    if output_dir.exists():
        raise FileExistsError("Output already exists: use a new experiment directory")
    if not video_path.is_file():
        raise ValueError("Input video does not exist")
    if type(requested_frames) is not int or not 2 <= requested_frames <= 60:
        raise ValueError("--frames must be between 2 and 60")

    cap = cv2.VideoCapture(str(video_path))
    frames = []
    try:
        if not cap.isOpened():
            raise ValueError("Cannot decode video")
        indices = sample_frame_indices(
            int(cap.get(cv2.CAP_PROP_FRAME_COUNT)), requested_frames
        )
        if len(indices) < 2:
            raise ValueError("Video is too short for multiple sampled frames")
        for index in indices:
            if not cap.set(cv2.CAP_PROP_POS_FRAMES, index):
                raise ValueError(f"Cannot seek to frame {index}")
            ok, frame = cap.read()
            if not ok or frame is None:
                raise ValueError(f"Cannot read frame {index}")
            frames.append(frame)
    finally:
        cap.release()

    persistence = persistent_markings(frames, support_fraction)
    raw_lines = detect_marking_lines(persistence)
    ground_lines, line_evidence = filter_ground_supported_lines(
        raw_lines, frames, minimum_fraction=ground_min_fraction
    )
    lines = ground_lines if use_ground_filter else raw_lines
    # Keep raw counts to make overly strict filtering visible to reviewers.
    raw_candidate_count = len(propose_stall_geometry(raw_lines, frames[0].shape))
    candidates = propose_stall_geometry(lines, frames[0].shape)
    source_hash = file_sha256(video_path)
    if hypotheses_path is not None:
        with Path(hypotheses_path).open("r", encoding="utf-8") as stream:
            hypothesis_report = json.load(stream)
        correlate_vehicle_hypotheses(candidates, hypothesis_report, source_hash)

    report = {
        "format": "uniparkingbuddy-unverified-stall-geometry-v1",
        "review_state": "unverified_proposals_only",
        "source_video": str(video_path),
        "source_video_sha256": source_hash,
        "sampled_frame_indices": indices,
        "paint_pixel_support_fraction": support_fraction,
        "detected_paint_like_line_count": len(raw_lines),
        "ground_supported_line_count": len(ground_lines),
        "ground_filter_enabled": use_ground_filter,
        "minimum_ground_contrast_fraction": ground_min_fraction,
        "line_context_evidence": line_evidence,
        "raw_geometry_candidate_count": raw_candidate_count,
        "geometry_candidate_count": len(candidates),
        "phase1_hypotheses_used": hypotheses_path is not None,
        "candidates": candidates,
        "limitations": [
            "Paint-like pixels and paired strokes can be curbs, vehicle edges, lanes or shadows.",
            "Dark-flank contrast rejects some vehicle-surface edges but can reject real lines on bright pavement.",
            "Line-context support is a heuristic and must be compared against original frames.",
            "The ungated candidate count is diagnostic only, not a count of real parking spaces.",
            "Two near-parallel lines alone do not establish a legal parking stall.",
            "Occluded markings, changing lighting and moving camera viewpoints can hide real stalls.",
            "No fixed-view motion compensation, homography or verified painted boundary mapping.",
            "Line scores and repeated vehicle anchors are heuristics, not calibrated accuracy.",
            "These review-only polygons are never automatically copied into configured-space JSON.",
        ],
    }
    output_dir.mkdir(parents=True, exist_ok=False)
    (output_dir / "stall_candidates.json").write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8"
    )
    if not cv2.imwrite(
        str(output_dir / "persistent_markings.png"), persistence
    ) or not cv2.imwrite(
        str(output_dir / "ground_line_evidence.png"),
        render_line_context(frames[0], line_evidence)
    ) or not cv2.imwrite(
        str(output_dir / "geometry_preview.png"),
        render_geometry_preview(frames[0], lines, candidates)
    ):
        raise OSError("Could not write local line-evidence previews")
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--video", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--frames", type=int, default=12)
    parser.add_argument("--paint-support", type=float, default=0.5)
    parser.add_argument(
        "--ground-min-fraction", type=float, default=0.33,
        help="Experimental bright-paint/dark-flank support fraction in sampled frames"
    )
    parser.add_argument(
        "--ground-filter", action="store_true",
        help="Opt-in experimental gate; compare with default ungated candidates"
    )
    parser.add_argument("--hypotheses", type=Path,
                        help="Optional Phase-1 hypotheses.json for matching evidence")
    args = parser.parse_args(argv)
    try:
        report = analyze_video_markings(
            args.video, args.output, args.frames,
            support_fraction=args.paint_support, hypotheses_path=args.hypotheses,
            use_ground_filter=args.ground_filter,
            ground_min_fraction=args.ground_min_fraction
        )
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as error:
        print(f"Parking-marking experiment failed: {error}", file=sys.stderr)
        return 1
    print(f"Found {report['detected_paint_like_line_count']} raw bright segments; "
          f"{report['ground_supported_line_count']} with dark-flank contrast support")
    print(f"Raw ungated geometry count: {report['raw_geometry_candidate_count']} "
          "(not a parking-stall count)")
    print(f"Proposed {report['geometry_candidate_count']} UNVERIFIED quadrilateral hypotheses")
    print(f"Review local results in {args.output}; no live parking data was changed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
