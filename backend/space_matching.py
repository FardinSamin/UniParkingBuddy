"""Associate vehicle detections with configured parking-space polygons.

This is a spatial match, not proof a vehicle is stationary or parked.
For overlapping polygons, a detection is assigned to the first matching
configured space; one detection must never occupy multiple spaces.
"""

import cv2


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
