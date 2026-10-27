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


# Camera 3 is a straight-down aerial view. COCO-trained weights detect no
# vehicles there, so it uses an aerial (DOTA) oriented-box model instead.
AERIAL_VEHICLE_NAMES = ("small vehicle", "large vehicle")
AERIAL_IMAGE_SIZE = 1024

DETECTOR_SETTINGS = {
    "default": {
        "weights": "yolo26n.pt", "imgsz": INFERENCE_IMAGE_SIZE,
        "classes": list(VEHICLE_CLASS_IDS), "oriented": False,
        "matching": "center",
    },
    # Camera 1 has angled rows with cars overlapping stall lines: the larger
    # model plus overlap matching placed 41 of 46 cars (centre rule: 24 of 45).
    "camera_1": {
        "weights": "yolo26m.pt", "imgsz": INFERENCE_IMAGE_SIZE,
        "classes": list(VEHICLE_CLASS_IDS), "oriented": False,
        "matching": "overlap",
    },
    "camera_3": {
        "weights": "yolo26n-obb.pt", "imgsz": AERIAL_IMAGE_SIZE,
        "classes": None, "oriented": True,
        "matching": "center",
    },
}


def box_iou(a, b):
    ix = max(0, min(a[2], b[2]) - max(a[0], b[0]))
    iy = max(0, min(a[3], b[3]) - max(a[1], b[1]))
    inter = ix * iy
    union = ((a[2] - a[0]) * (a[3] - a[1])
             + (b[2] - b[0]) * (b[3] - b[1]) - inter)
    return inter / union if union > 0 else 0.0


def dedupe_boxes(boxes, iou_threshold=0.7):
    """Drop duplicate detections of one vehicle (e.g. same car, two classes).

    Keeps the higher-confidence box. Two distinct neighbouring cars overlap
    far less than 0.7 IoU, so they are both kept.
    """
    kept = []
    for box in sorted(boxes, key=lambda b: -b[4]):
        if all(box_iou(box, other) < iou_threshold for other in kept):
            kept.append(box)
    return kept


def detector_settings(camera):
    return DETECTOR_SETTINGS.get(camera, DETECTOR_SETTINGS["default"])


def boxes_from_obb_result(result, vehicle_names=AERIAL_VEHICLE_NAMES):
    """Axis-aligned anonymous 5-tuples from an oriented-box result.

    Only vehicle classes are kept; the bounding rectangle of each rotated
    box is used so the shared matching code needs no changes.
    """
    obb = getattr(result, "obb", None)
    if obb is None:
        return []
    names = result.names
    boxes = []
    for xyxy, conf, cls in zip(obb.xyxy, obb.conf, obb.cls):
        if names[int(cls)] not in vehicle_names:
            continue
        x1, y1, x2, y2 = map(int, xyxy)
        boxes.append((x1, y1, x2, y2, float(conf)))
    return boxes


def detect_boxes(model, frame, camera):
    """Run the camera's configured detector and return anonymous boxes."""
    settings = detector_settings(camera)
    kwargs = {"conf": DETECTION_CONFIDENCE, "imgsz": settings["imgsz"], "verbose": False}
    if settings["classes"] is not None:
        kwargs["classes"] = settings["classes"]
    result = model(frame, **kwargs)[0]
    if settings["oriented"]:
        return dedupe_boxes(boxes_from_obb_result(result))
    return dedupe_boxes(boxes_from_yolo_result(result))
