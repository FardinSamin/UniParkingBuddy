import cv2
from ultralytics import YOLO
from pathlib import Path
import numpy as np
import threading
from flask import Flask, jsonify
from flask_cors import CORS
from space_matching import assign_detections_to_spaces
from parking_config import (
    ParkingConfigError, add_space, load_config, remove_space, save_config,
)

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def config_path(camera_name):
    return PROJECT_ROOT / 'configs' / f'{camera_name}.json'

#camera sources
def make_camera(path):
    return {
        "source": cv2.VideoCapture(str(PROJECT_ROOT / path)),
        "config": None,
        "current_points": [],
        "last_boxes": [],
        "frame_idx": 0,
        "frame": None,
    }

#add or remove if needed
camera_captures = {
    "camera_1": make_camera("footage/stockvidsample2.mp4"),
    "camera_2": make_camera("footage/parkinglotfootage1_1.mp4"),
}

# Fail clearly if a saved lot configuration is missing or invalid.
# Never silently turn a damaged configuration into an apparently empty lot.
try:
    for name, cam in camera_captures.items():
        cam["config"] = load_config(config_path(name))
except ParkingConfigError as error:
    for cam in camera_captures.values():
        cam["source"].release()
    raise SystemExit(f"Parking configuration error: {error}")

#format video display window
for i in camera_captures:
    cv2.namedWindow(i, cv2.WINDOW_NORMAL)
    cv2.resizeWindow(i, 1280, 720)

#yolo model
model = YOLO(str(PROJECT_ROOT / 'yolo26n.pt'))
CARS = [2,3,7] #2=car, 3=motorcycle, 7=truck
DETECT_EVERY = 30

mode = "play"

def mouseClick(event, x, y, _flags, name):
    if mode != "mark" or name not in camera_captures:
        return
    cam = camera_captures[name]

    if event == cv2.EVENT_LBUTTONDOWN:
        cam["current_points"].append((x, y))
        if len(cam["current_points"]) == 4:
            try:
                updated = add_space(cam["config"], cam["current_points"])
                save_config(config_path(name), updated)
            except (ParkingConfigError, OSError) as error:
                print(f"{name}: unable to add parking space: {error}")
            else:
                cam["config"] = updated
                print(f"{name}: added space {updated['next_space_id'] - 1}")
            finally:
                cam["current_points"].clear()

    elif event == cv2.EVENT_RBUTTONDOWN:
        for space in cam["config"]["spaces"]:
            contour = np.array(space["points"], dtype=np.int32).reshape((-1, 1, 2))
            if cv2.pointPolygonTest(contour, (float(x), float(y)), False) >= 0:
                try:
                    updated = remove_space(cam["config"], space["id"])
                    save_config(config_path(name), updated)
                except (ParkingConfigError, OSError) as error:
                    print(f"{name}: unable to remove parking space: {error}")
                else:
                    cam["config"] = updated
                    print(f"{name}: removed space {space['id']}")
                break

for name in camera_captures:
    cv2.setMouseCallback(name, mouseClick, name)


app = Flask(__name__)
CORS(app)

latest_status = {} 
status_lock = threading.Lock()

@app.route('/api/status/<camera>')
def get_status(camera):
    if camera not in camera_captures:
        return jsonify({"error": "Camera is not configured or active"}), 404

    with status_lock:
        c = latest_status.get(camera)
    if c is None:
        return jsonify({"error": "Parking status is not ready"}), 503
    if not c["spaces"]:
        return jsonify({"error": "No configured parking spaces available"}), 503

    return jsonify({
        "cars_detected": c["cars"],
        "vehicles_in_spaces": c["in_space_vehicles"],
        "vehicles_outside_spaces": c["outside_space_vehicles"],
        "parking_spaces": [
            {"id": s["id"], "occupied": not s["open"]} for s in c["spaces"]
        ],
    })

def run_api():
    app.run(port=5000, debug=False, use_reloader=False)

threading.Thread(target=run_api, daemon=True).start()


while True:
    for name, cap in list(camera_captures.items()):

        success, frame = cap["source"].read()
        if not success:
            cap["source"].set(cv2.CAP_PROP_POS_FRAMES, 0)
            cap["frame_idx"] = 0
            continue
        cap["frame"] = frame

        if cap["frame_idx"] % DETECT_EVERY == 0:
            results = model(frame, classes=CARS, conf=0.20, imgsz=1280, verbose=False)[0]
            cap["last_boxes"] = []
            for box in results.boxes:
                x1, y1, x2, y2 = map(int, box.xyxy[0])
                cap["last_boxes"].append((x1, y1, x2, y2, float(box.conf[0])))
        cap["frame_idx"] += 1

        display = cap["frame"].copy()

        # Use one spatial association result for both the occupancy counts
        # and the visual markers. A vehicle matches at most one space.
        contours = [
            np.array(space["points"], dtype=np.int32).reshape((-1, 1, 2))
            for space in cap["config"]["spaces"]
        ]
        matched_spaces, occupied_spaces = assign_detections_to_spaces(
            cap["last_boxes"], contours
        )

        # Detected vehicles outside the marked spaces remain visible,
        # but do not change occupied-space counts.
        in_spaces = sum(index is not None for index in matched_spaces)
        outside_spaces = len(matched_spaces) - in_spaces

        for (x1, y1, x2, y2, conf), space_index in zip(
            cap["last_boxes"], matched_spaces
        ):
            if space_index is None:
                color = (0, 255, 255)  # yellow: outside marked spaces (BGR)
                label = f"OUTSIDE SPACE {conf:.2f}"
            else:
                color = (0, 0, 255)  # red: matched to a space (BGR)
                label = f"SPACE {cap['config']['spaces'][space_index]['id']} {conf:.2f}"

            cx, cy = (x1 + x2) // 2, (y1 + y2) // 2
            cv2.rectangle(display, (x1, y1), (x2, y2), color, 2)
            cv2.circle(display, (cx, cy), 5, color, -1)
            cv2.putText(
                display, label, (max(0, x1), max(18, y1 - 6)),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2
            )

        cv2.putText(
            display, f"Vehicles Detected: {len(cap['last_boxes'])}", (10, 32),
            cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 0, 0), 2
        )
        cv2.putText(
            display, f"In spaces: {in_spaces} | Outside spaces: {outside_spaces}",
            (10, 103), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2
        )

        space_status = []
        for i, contour in enumerate(contours):
            occupied = occupied_spaces[i]
            space_id = cap["config"]["spaces"][i]["id"]
            space_status.append({"id": space_id, "open": not occupied})

            if mode == "mark":
                color = (255, 0, 0)  # blue while marking (BGR)
            else:
                color = (0, 0, 255) if occupied else (0, 255, 0)

            cv2.polylines(display, [contour], True, color, 2)
            lx = int(np.mean(contour[:, 0, 0]))
            ly = int(np.mean(contour[:, 0, 1]))
            cv2.putText(
                display, str(space_id), (lx, ly),
                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2
            )

        with status_lock:
            latest_status[name] = {
                "cars": len(cap["last_boxes"]),
                "in_space_vehicles": in_spaces,
                "outside_space_vehicles": outside_spaces,
                "spaces": space_status,
            }

        if mode == "mark":
            for pt in cap["current_points"]:
                cv2.circle(display, pt, 3, (0, 255, 255), -1)
            if len(cap["current_points"]) > 1:
                cv2.polylines(display, [np.array(cap["current_points"], dtype=np.int32)],
                              False, (0, 255, 255), 2)

        cv2.putText(display, f"Mode: {mode} (press 'm' to toggle)", (10, 65),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 2)

        cv2.imshow(name, display)

    key = cv2.waitKey(1) & 0xFF

    if key == ord('q'):
        break
    if key == ord('m'):
        mode = "mark" if mode == "play" else "play"
        for c in camera_captures.values():
            c["current_points"].clear()

    for k, cam_name in ((ord('1'), "camera_1"), (ord('2'), "camera_2")):
        if key == k:
            removed = camera_captures.pop(cam_name, None)
            if removed is not None:
                removed["source"].release()
                cv2.destroyWindow(cam_name)

                with status_lock:
                    latest_status.pop(cam_name, None)

    if not camera_captures:
        break

for c in camera_captures.values():
    c["source"].release()
cv2.destroyAllWindows()