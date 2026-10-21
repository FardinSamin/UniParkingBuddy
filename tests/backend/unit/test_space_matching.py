import numpy as np
from backend.space_matching import assign_detections_to_spaces, build_space_statuses
import pytest


def contour_from_rect(x1,y1,x2,y2):
    arr = np.array([[x1,y1],[x2,y1],[x2,y2],[x1,y2]], dtype=np.int32).reshape((-1,1,2))
    return arr


def test_vehicle_centered_inside_space():
    contours = [contour_from_rect(0,0,10,10)]
    boxes = [(2,2,4,4,0.9)]  # center (3,3) inside
    matches, occupied = assign_detections_to_spaces(boxes, contours)
    assert matches == [0]
    assert occupied == [True]


def test_vehicle_between_spaces():
    contours = [contour_from_rect(0,0,10,10), contour_from_rect(20,0,30,10)]
    boxes = [(11,2,13,4,0.8)]  # center (12,3) between
    matches, occupied = assign_detections_to_spaces(boxes, contours)
    assert matches == [None]
    assert occupied == [False, False]


def test_vehicle_on_boundary():
    contours = [contour_from_rect(0,0,10,10)]
    # center exactly on right edge x=10
    boxes = [(9,2,11,4,0.7)]  # center (10,3)
    matches, occupied = assign_detections_to_spaces(boxes, contours)
    # pointPolygonTest >= 0 treated as inside
    assert matches == [0]
    assert occupied == [True]


def test_multiple_occupied_spaces():
    contours = [contour_from_rect(0,0,10,10), contour_from_rect(20,0,30,10)]
    boxes = [(2,2,4,4,0.9), (22,2,24,4,0.85)]
    matches, occupied = assign_detections_to_spaces(boxes, contours)
    assert matches == [0,1]
    assert occupied == [True, True]


def test_no_detections():
    contours = [contour_from_rect(0,0,10,10)]
    boxes = []
    matches, occupied = assign_detections_to_spaces(boxes, contours)
    assert matches == []
    assert occupied == [False]


def test_build_space_statuses_mismatch():
    with pytest.raises(ValueError):
        build_space_statuses([{"id": 1}], [True, False])
