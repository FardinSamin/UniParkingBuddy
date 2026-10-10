"""Read-only contextual validation of paint-like Hough line segments.

Bright-pixel persistence alone treats car windows, roofs and buildings as
potential parking markings. This module tests whether a line also has
bright-on-dark support on BOTH sides across sampled frames. It is an
experimental, dark-pavement-friendly heuristic, not a pavement segmenter,
homography, or legally verified parking-stall detector.
"""

import math

import cv2
import numpy as np


def _gray_frames(frames):
    if not isinstance(frames, (list, tuple)) or not frames:
        raise ValueError("At least one BGR frame is required")
    original = frames[0]
    if (not isinstance(original, np.ndarray) or original.ndim != 3
            or original.shape[2] != 3 or original.dtype != np.uint8):
        raise ValueError("Expected 8-bit BGR video frames")
    result = []
    for frame in frames:
        if (not isinstance(frame, np.ndarray)
                or frame.shape != original.shape
                or frame.dtype != np.uint8):
            raise ValueError("Fixed-view source frames must have matching BGR dimensions")
        result.append(cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY))
    return result


def _pixel(gray, x, y):
    h, w = gray.shape
    ix, iy = round(x), round(y)
    if ix < 0 or iy < 0 or ix >= w or iy >= h:
        return None
    return int(gray[iy, ix])


def measure_line_pavement_contrast(
    line, grayscale_frames, minimum_contrast=45, max_flank_brightness=190
):
    """Fraction of sampled observations with a bright center and dark flanks.

    Hough operates on marking-mask *edges*, so the center search includes
    a small ±3px region normal to each line. An actual divider between
    two dark pavement regions should be much brighter than BOTH flanks.
    A long car window edge with bright paint on one side should usually
    fail, even when temporally static.

    The returned [0, 1] value is relative evidence, NOT calibrated confidence.
    """
    if len(line) != 4 or not all(
        isinstance(v, (int, float, np.integer, np.floating))
        and math.isfinite(float(v)) for v in line
    ):
        raise ValueError("Line must contain four finite coordinates")
    if type(minimum_contrast) is not int or not 1 <= minimum_contrast <= 255:
        raise ValueError("minimum_contrast must be an integer between 1 and 255")
    if type(max_flank_brightness) is not int or not 1 <= max_flank_brightness <= 255:
        raise ValueError("max_flank_brightness must be an integer between 1 and 255")
    x1, y1, x2, y2 = (float(v) for v in line)
    length = math.hypot(x2 - x1, y2 - y1)
    if length < 10:
        return 0.0
    nx, ny = -(y2 - y1) / length, (x2 - x1) / length
    flank = min(14.0, max(6.0, length * 0.095))
    accepted = tested = 0
    for gray in grayscale_frames:
        for fraction in np.linspace(0.12, 0.88, 15):
            x = x1 + fraction * (x2 - x1)
            y = y1 + fraction * (y2 - y1)
            core_samples = [
                _pixel(gray, x + nx * d, y + ny * d)
                for d in (-3, -2, -1, 0, 1, 2, 3)
            ]
            left_samples = [
                _pixel(gray, x - nx * d, y - ny * d)
                for d in (flank - 1, flank, flank + 1)
            ]
            right_samples = [
                _pixel(gray, x + nx * d, y + ny * d)
                for d in (flank - 1, flank, flank + 1)
            ]
            if (None in core_samples or None in left_samples
                    or None in right_samples):
                continue
            center = max(core_samples)
            left = float(np.median(left_samples))
            right = float(np.median(right_samples))
            tested += 1
            if (center - max(left, right) >= minimum_contrast
                    and max(left, right) <= max_flank_brightness):
                accepted += 1
    return round(accepted / tested, 4) if tested else 0.0


def filter_ground_supported_lines(
    lines, frames, minimum_fraction=0.33, minimum_contrast=45
):
    """Retain line candidates with contrast support, preserving audit metrics.

    This is an independent experimental evidence filter. In concrete
    garages, painted stalls with low contrast, night footage or heavily
    occupied rows, many true lines may be rejected; the caller must
    retain raw evidence for human comparison.
    """
    if (type(minimum_fraction) not in (int, float)
            or not math.isfinite(minimum_fraction)
            or not 0 < minimum_fraction <= 1):
        raise ValueError("minimum_fraction must be between 0 and 1")
    grays = _gray_frames(frames)
    evidence = []
    supported = []
    for line in lines:
        score = measure_line_pavement_contrast(
            line, grays, minimum_contrast=minimum_contrast
        )
        accepted = score >= minimum_fraction
        entry = {
            "line_xyxy": [int(x) for x in line],
            "dark_flank_contrast_fraction": score,
            "ground_supported_for_review": accepted,
        }
        evidence.append(entry)
        if accepted:
            supported.append(tuple(int(x) for x in line))
    return supported, evidence


def render_line_context(frame, evidence):
    """Color-code tentative ground-supported versus rejected bright lines."""
    output = frame.copy()
    for entry in evidence:
        p1 = tuple(entry["line_xyxy"][:2])
        p2 = tuple(entry["line_xyxy"][2:])
        color = ((10, 220, 45) if entry["ground_supported_for_review"]
                 else (0, 0, 220))
        cv2.line(output, p1, p2, color, 2)
    cv2.putText(
        output, "GREEN: GROUND-LIKE CONTRAST   RED: REJECTED BRIGHT EDGE",
        (12, max(24, frame.shape[0] - 15)), cv2.FONT_HERSHEY_SIMPLEX,
        0.62, (0, 220, 220), 2
    )
    return output
