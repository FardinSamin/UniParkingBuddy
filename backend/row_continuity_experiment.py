"""Offline stall-row continuity experiment from prior Phase 2 evidence.

Connects observed, nearly collinear paint-like fragments; attempts the old
line-pair geometry proposal on those merged observations; and runs the
existing Phase 3 review on both raw and ground-contrast-supported variants.

Neither joining paint fragments nor matching a row proves a legal stall.
This tool reads reports and source frames, writes only new local review
artifacts, and NEVER edits configured stalls or application occupancy.
"""

import argparse
import json
import math
from pathlib import Path
import sys

import cv2
import numpy as np

from .accuracy_evaluation import file_sha256
from .discover_stall_geometry import propose_stall_geometry
from .review_stall_candidates import assess_geometry, render_review


def _line(line):
    if (not isinstance(line, (list, tuple)) or len(line) != 4
            or any(type(v) not in (float, int) or not math.isfinite(v)
                   for v in line)):
        raise ValueError("Line must contain four finite coordinates")
    endpoints = np.asarray(line, dtype=np.float64).reshape(2, 2)
    if np.linalg.norm(endpoints[1] - endpoints[0]) < 2:
        raise ValueError("Line must have positive observable length")
    return endpoints


def _compatible(a, b):
    """Check direction, side-offset and endpoint gap; no blind extrapolation."""
    aa, bb = _line(a), _line(b)
    vec_a = aa[1] - aa[0]
    vec_b = bb[1] - bb[0]
    len_a = float(np.linalg.norm(vec_a))
    len_b = float(np.linalg.norm(vec_b))
    u = vec_a / len_a
    v = vec_b / len_b
    angle = math.degrees(math.acos(min(1.0, abs(float(np.dot(u, v))))))
    if angle > 8:
        return False
    normal = np.array([-u[1], u[0]])
    # Compare both endpoints of the shorter stroke to the same ground line.
    distances = [abs(float(np.dot(p - aa[0], normal))) for p in bb]
    offset_limit = min(9.0, max(3.5, min(len_a, len_b) * 0.055))
    if max(distances) > offset_limit:
        return False
    first_range = sorted(float(np.dot(p, u)) for p in aa)
    second_range = sorted(float(np.dot(p, u)) for p in bb)
    gap = max(
        0.0,
        max(first_range[0], second_range[0])
        - min(first_range[1], second_range[1]),
    )
    return gap <= min(18.0, max(5.0, min(len_a, len_b) * 0.32))


def _merge_group(parts):
    """Make a line joining actually observed extremes, with gap evidence."""
    coordinates = np.asarray(parts, dtype=np.float64).reshape((-1, 2, 2))
    lengths = np.linalg.norm(coordinates[:, 1] - coordinates[:, 0], axis=1)
    longest = coordinates[int(np.argmax(lengths))]
    unit = (longest[1] - longest[0]) / max(float(max(lengths)), 1e-9)
    normal = np.array([-unit[1], unit[0]])
    projected = [
        sorted([float(np.dot(line[0], unit)), float(np.dot(line[1], unit))])
        for line in coordinates
    ]
    lo = min(p[0] for p in projected)
    hi = max(p[1] for p in projected)
    offsets = [
        float(np.dot((line[0] + line[1]) / 2, normal)) for line in coordinates
    ]
    offset = float(np.average(offsets, weights=lengths))
    points = [
        [round(x) for x in (unit * t + normal * offset)]
        for t in (lo, hi)
    ]
    if points[0] == points[1]:
        return None
    # Actual fraction of longitudinal extent backed by paint observations.
    intervals = sorted(projected)
    covered = 0.0
    start, end = intervals[0]
    for a, b in intervals[1:]:
        if a <= end:
            end = max(end, b)
        else:
            covered += end - start
            start, end = a, b
    covered += end - start
    coverage = round(min(1.0, covered / max(hi - lo, 1)), 3)
    return {
        "line_xyxy": points[0] + points[1],
        "observed_fragment_count": len(parts),
        "observed_longitudinal_coverage_fraction": coverage,
    }


def join_collinear_fragments(lines):
    """Conservatively group broken line observations into continuous strokes.

    Reuses original segment endpoints. Merged span has no assumed support
    where line evidence is absent, so gap coverage must be reviewed.
    """
    strokes = [tuple(int(v) for v in _line(line).flatten()) for line in lines]
    parent = list(range(len(strokes)))

    def root(index):
        while parent[index] != index:
            parent[index] = parent[parent[index]]
            index = parent[index]
        return index

    for i in range(len(strokes)):
        for j in range(i + 1, len(strokes)):
            if _compatible(strokes[i], strokes[j]):
                pa, pb = root(i), root(j)
                if pa != pb:
                    parent[max(pa, pb)] = min(pa, pb)
    groups = {}
    for i, line in enumerate(strokes):
        groups.setdefault(root(i), []).append(line)

    merged = []
    for part_group in groups.values():
        entry = _merge_group(part_group)
        if entry:
            merged.append(entry)
    merged.sort(key=lambda item: (
        -math.hypot(
            item["line_xyxy"][2] - item["line_xyxy"][0],
            item["line_xyxy"][3] - item["line_xyxy"][1],
        ), item["line_xyxy"]
    ))
    return merged


def _review(geometry_report, lines, original_report, phase1):
    candidates = propose_stall_geometry(lines, original_report["frame_shape"])
    synthetic = {
        "format": "uniparkingbuddy-unverified-stall-geometry-v1",
        "source_video_sha256": geometry_report["source_video_sha256"],
        "candidates": candidates,
    }
    reviewed = assess_geometry(synthetic, phase1)
    # Extra source evidence, not a new confidence or approval state.
    reviewed["input_line_count"] = len(lines)
    return reviewed


def _frame(video_path, index):
    capture = cv2.VideoCapture(str(video_path))
    try:
        if not capture.isOpened() or not capture.set(cv2.CAP_PROP_POS_FRAMES, index):
            raise ValueError("Cannot open or seek the source video")
        valid, frame = capture.read()
        if not valid or frame is None:
            raise ValueError("Cannot decode the requested source frame")
        return frame
    finally:
        capture.release()


def _draw_fragments(frame, merged):
    result = frame.copy()
    for item in merged:
        stroke = item["line_xyxy"]
        p = tuple(stroke[:2])
        q = tuple(stroke[2:])
        color = (0, 180, 255) if item["observed_fragment_count"] > 1 else (100, 210, 100)
        cv2.line(result, p, q, color, 2)
    cv2.putText(
        result, "JOINED LINE FRAGMENTS (NOT VERIFIED STALLS)",
        (10, max(24, result.shape[0] - 16)),
        cv2.FONT_HERSHEY_SIMPLEX, 0.62, (0, 0, 255), 2,
    )
    return result


def analyze_row_continuity(video_path, geometry_path, output_dir, phase1_path=None):
    """Create independent raw/ground-supported line-joining comparisons."""
    video_path = Path(video_path).resolve()
    output_dir = Path(output_dir)
    if output_dir.exists():
        raise FileExistsError("Output exists: choose a new experiment directory")
    if not video_path.is_file():
        raise ValueError("Source video is missing")
    original_report = json.loads(Path(geometry_path).read_text(encoding="utf-8"))
    if original_report.get("format") != "uniparkingbuddy-unverified-stall-geometry-v1":
        raise ValueError("Expected Phase 2 geometry JSON")
    hash_value = file_sha256(video_path)
    if original_report.get("source_video_sha256") != hash_value:
        raise ValueError("Phase 2 geometry does not match source video")
    evidence = original_report.get("line_context_evidence")
    if not isinstance(evidence, list):
        raise ValueError("Phase 2 report is missing line contrast evidence")

    phase1 = None
    if phase1_path is not None:
        phase1 = json.loads(Path(phase1_path).read_text(encoding="utf-8"))
        if phase1.get("source_video_sha256") != hash_value:
            raise ValueError("Phase 1 location hypotheses do not match source video")

    indices = original_report.get("sampled_frame_indices")
    if not isinstance(indices, list) or not indices or type(indices[0]) is not int:
        raise ValueError("Phase 2 report lacks source frame indices")
    frame = _frame(video_path, indices[0])
    frame_shape = frame.shape

    raw_lines = []
    ground_lines = []
    for entry in evidence:
        if not isinstance(entry, dict) or not isinstance(
            entry.get("ground_supported_for_review"), bool
        ):
            raise ValueError("Invalid ground line evidence in Phase 2 report")
        stroke = entry.get("line_xyxy")
        _line(stroke)
        raw_lines.append(stroke)
        if entry["ground_supported_for_review"]:
            ground_lines.append(stroke)

    base_context = {"frame_shape": frame_shape}
    results = {}
    overlays = {}
    for label, segments in (("raw", raw_lines), ("ground", ground_lines)):
        joined = join_collinear_fragments(segments)
        reviewed = _review(
            original_report, [entry["line_xyxy"] for entry in joined],
            base_context, phase1
        )
        results[label] = {
            "raw_segment_count": len(segments),
            "joined_segment_count": len(joined),
            "joined_segments": joined,
            "review": reviewed,
        }
        overlays[f"joined_{label}.png"] = _draw_fragments(frame, joined)
        overlays[f"row_candidates_{label}.png"] = render_review(frame, reviewed)

    summary = {
        "format": "uniparkingbuddy-unverified-row-continuity-v1",
        "review_state": "unverified_proposals_only",
        "source_video_sha256": hash_value,
        "phase1_hypotheses_used": phase1 is not None,
        "input_phase2_candidate_count": len(original_report.get("candidates", [])),
        "variants": results,
        "limitations": [
            "Collinear Hough fragments can be car edges, roofs, curbs and lane paint.",
            "Joining strokes does not establish an entire painted bay or legal space.",
            "Disconnected observations along joined spans remain unverified gaps.",
            "Ground-filtered lines can miss legitimate stalls on bright pavement.",
            "No perspective correction, camera-motion validation, or accuracy measurement.",
            "No unverified candidate is a configured stall or a live occupancy state.",
        ],
    }
    output_dir.mkdir(parents=True, exist_ok=False)
    (output_dir / "row_comparison.json").write_text(
        json.dumps(summary, indent=2) + "\n", encoding="utf-8"
    )
    for name, image in overlays.items():
        if not cv2.imwrite(str(output_dir / name), image):
            raise OSError(f"Could not write overlay {name}")
    return summary


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--video", required=True, type=Path)
    parser.add_argument("--geometry", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--hypotheses", type=Path)
    args = parser.parse_args(argv)
    try:
        report = analyze_row_continuity(
            args.video, args.geometry, args.output, args.hypotheses
        )
    except (OSError, ValueError, TypeError, KeyError, json.JSONDecodeError) as error:
        print(f"Row-continuity experiment failed: {error}", file=sys.stderr)
        return 1
    for label, result in report["variants"].items():
        review = result["review"]
        print(
            f"{label}: {result['raw_segment_count']} observed lines -> "
            f"{result['joined_segment_count']} joined strokes -> "
            f"{review['candidate_count']} hypotheses -> "
            f"{review['shortlist_count']} human-review shortlist"
        )
    print("NOT verified parking stalls; no production configuration was changed.")
    print(f"See {args.output} for overlays and complete audit JSON.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
