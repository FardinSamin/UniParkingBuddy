"""Shared settings and result conversion for configured vehicle detection.

The Ultralytics model is created by the application (or the dedicated smoke
test); this module does not download weights or launch video windows.
"""

VEHICLE_CLASS_IDS = (2, 3, 7)  # COCO: car, motorcycle, truck
DETECTION_CONFIDENCE = 0.20
INFERENCE_IMAGE_SIZE = 1280
INFERENCE_EVERY_FRAMES = 30  # Live inference cadence, also used for evaluation


def boxes_from_yolo_result(result):
    """Return the same anonymous 5-tuples consumed by spatial matching.

    Each tuple is (x1, y1, x2, y2, confidence). No plates, identities,
    image data or detected-vehicle tracking IDs are recorded here.
    """
    boxes = []
    for box in result.boxes:
        x1, y1, x2, y2 = map(int, box.xyxy[0])
        boxes.append((x1, y1, x2, y2, float(box.conf[0])))
    return boxes
