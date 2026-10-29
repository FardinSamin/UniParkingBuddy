"""Associate vehicle detections with configured parking-space polygons.

This is a spatial match, not proof a vehicle is stationary or parked.
For overlapping polygons, a detection is assigned to the first matching
configured space; one detection must never occupy multiple spaces.
"""

import cv2
import numpy as np


def assign_detections_to_spaces(boxes, contours):
    """Return (matched_space_indices, occupied_flags) for one processed frame.

    Each box contains x1, y1, x2, y2 and optionally other values.
    Indices refer to the input contours; None means outside all spaces.
    """
    matches = []
    occupied = [False] * len(contours)

    for box in boxes:
        x1, y1, x2, y2 = box[:4]
        center = (float((x1 + x2) // 2), float((y1 + y2) // 2))
        matched = None

        for index, contour in enumerate(contours):
            if cv2.pointPolygonTest(contour, center, False) >= 0:
                matched = index
                occupied[index] = True
                break

        matches.append(matched)

    return matches, occupied


def _box_polygon(x1, y1, x2, y2, footprint_fraction):
    """Ground-contact region of a detection: the bottom part of its box.

    Vehicles are seen from above at an angle, so the roof and body overhang
    the space they stand in. The lower part of the box is closer to the
    pavement, so it is the better proxy for the vehicle's footprint.
    """
    top = y2 - footprint_fraction * (y2 - y1)
    return np.array([[x1, top], [x2, top], [x2, y2], [x1, y2]], dtype=np.float32)


def assign_detections_by_overlap(
    boxes, contours, footprint_fraction=0.5,
    min_footprint_overlap=0.30, min_space_overlap=0.60,
):
    """Overlap-based alternative to the box-centre rule.

    A detection claims the space it overlaps most (largest intersection
    area) when EITHER at least ``min_footprint_overlap`` of its footprint lies
    in that space OR at least ``min_space_overlap`` of the space is covered by
    the footprint. The second test lets vehicles occupy small, distant spaces
    that a large footprint can never fill 30% of. Each detection is assigned
    to at most one space. Spaces must be convex polygons (the configuration
    validator guarantees this). Returns the same shape as
    ``assign_detections_to_spaces``.
    """
    polygons = [np.asarray(c, dtype=np.float32).reshape(-1, 2) for c in contours]
    space_areas = [abs(cv2.contourArea(p)) for p in polygons]
    matches = []
    occupied = [False] * len(contours)

    for box in boxes:
        x1, y1, x2, y2 = box[:4]
        footprint = _box_polygon(x1, y1, x2, y2, footprint_fraction)
        footprint_area = abs(cv2.contourArea(footprint))
        best, best_area = None, 0.0
        if footprint_area > 0:
            for index, polygon in enumerate(polygons):
                if space_areas[index] <= 0:
                    continue
                area, _ = cv2.intersectConvexConvex(footprint, polygon)
                if area <= best_area:
                    continue
                if (area / footprint_area >= min_footprint_overlap
                        or area / space_areas[index] >= min_space_overlap):
                    best, best_area = index, area
        if best is not None:
            occupied[best] = True
        matches.append(best)

    return matches, occupied


class OccupancySmoother:
    """Debounce per-space occupancy across detection passes.

    A space becomes occupied after ``confirm`` consecutive passes that saw a
    vehicle and becomes open after ``clear`` consecutive passes that did not.
    This stops a car pulling in or out, or a one-frame missed detection, from
    flipping a space back and forth. The first pass sets the initial state
    directly so start-up is not delayed.
    """

    def __init__(self, space_count, confirm=2, clear=3):
        if space_count < 0 or confirm < 1 or clear < 1:
            raise ValueError("Invalid smoother parameters")
        self.confirm, self.clear = confirm, clear
        self.state = [False] * space_count
        self._streak = [0] * space_count
        self.started = False

    def update(self, observed):
        if len(observed) != len(self.state):
            raise ValueError("Observation length must match the space count")
        if not self.started:
            self.state = list(observed)
            self.started = True
            return list(self.state)
        for i, seen in enumerate(observed):
            if seen == self.state[i]:
                self._streak[i] = 0
                continue
            self._streak[i] += 1
            needed = self.confirm if seen else self.clear
            if self._streak[i] >= needed:
                self.state[i] = seen
                self._streak[i] = 0
        return list(self.state)


# camera_1 looks across the lot at an angle, so the lower half of a vehicle box
# approximates its footprint. camera_2 looks almost straight down, so the whole
# box is the footprint.
CAMERA_FOOTPRINT_FRACTION = {"camera_1": 0.5, "camera_2": 1.0, "camera_3": 1.0}
MATCHING_MODES = ("center", "overlap")


def match_detections(boxes, contours, camera=None, mode="center"):
    """Single entry point used by the live app and by the evaluation tool."""
    if mode == "center":
        return assign_detections_to_spaces(boxes, contours)
    if mode == "overlap":
        return assign_detections_by_overlap(
            boxes, contours,
            footprint_fraction=CAMERA_FOOTPRINT_FRACTION.get(camera, 0.5),
        )
    raise ValueError(f"Unknown matching mode: {mode!r}")


def build_space_statuses(configured_spaces, occupied_flags):
    """Pair occupancy decisions with stable IDs rather than list positions."""
    if len(configured_spaces) != len(occupied_flags):
        raise ValueError("Space configuration and occupancy lengths must match")

    return [
        {"id": space["id"], "open": not occupied}
        for space, occupied in zip(configured_spaces, occupied_flags)
    ]
