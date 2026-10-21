from types import SimpleNamespace
from backend.yolo_detection import boxes_from_yolo_result


def make_fake_result(boxes):
    # boxes is list of tuples (x1,y1,x2,y2,conf)
    class Box:
        def __init__(self, xyxy, conf):
            self.xyxy = [xyxy]
            self.conf = [conf]
    class Result:
        def __init__(self, boxes):
            self.boxes = boxes
    return Result([Box([b[0], b[1], b[2], b[3]], b[4]) for b in boxes])


def test_boxes_from_yolo_result():
    res = make_fake_result([(1.2,2.3,3.4,4.5,0.77)])
    out = boxes_from_yolo_result(res)
    assert isinstance(out, list)
    assert out[0][0] == 1 and out[0][4] == 0.77
