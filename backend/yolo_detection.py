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
    },
    "camera_3": {
        "weights": "yolo26n-obb.pt", "imgsz": AERIAL_IMAGE_SIZE,
        "classes": None, "oriented": True,
    },
}


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
        return boxes_from_obb_result(result)
    return boxes_from_yolo_result(result)
