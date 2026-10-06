import cv2
from ultralytics import YOLO
import pickle
import numpy as np
import threading
from flask import Flask, jsonify
from flask_cors import CORS

#camera sources
def make_camera(path):
    return {
        "source": cv2.VideoCapture(path),
        "posList": [],
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

#format video display window
for i in camera_captures: 
    cv2.namedWindow(i, cv2.WINDOW_NORMAL) #allows to manually resize window
    cv2.resizeWindow(i, 1280, 720) #sets initial window size


#yolo model
model = YOLO('yolo26n.pt')
CARS = [2,3,7] #2=car, 3=motorcycle, 7=truck
DETECT_EVERY = 30


def pos_file(name):
    return f"CarPos_{name}"

def save_positions(name):
    with open(pos_file(name), "wb") as f:
        pickle.dump(camera_captures[name]["posList"], f)

for name, cam in camera_captures.items():
    try:
        with open(pos_file(name), "rb") as f:
            cam["posList"] = pickle.load(f)
    except FileNotFoundError:
        pass

mode = "play"

def mouseClick(event, x, y, _flags, name):
    if mode != "mark" or name not in camera_captures:
        return
    cam = camera_captures[name]

    if event == cv2.EVENT_LBUTTONDOWN:
        cam["current_points"].append((x, y))
        if len(cam["current_points"]) == 4:
            cam["posList"].append(cam["current_points"].copy())
            cam["current_points"].clear()
            save_positions(name)

    elif event == cv2.EVENT_RBUTTONDOWN:
        for idx, pts in enumerate(cam["posList"]):
            contour = np.array(pts, dtype=np.int32).reshape((-1, 1, 2))
            if cv2.pointPolygonTest(contour, (float(x), float(y)), False) >= 0:
                cam["posList"].pop(idx)
                save_positions(name)
                break

for name in camera_captures:
    cv2.setMouseCallback(name, mouseClick, name)


app = Flask(__name__)
CORS(app)

latest_status = {} 
status_lock = threading.Lock()

@app.route('/api/status/<camera>')
def get_status(camera):
    with status_lock:
        c = latest_status.get(camera)
    if c is None:
        return jsonify({"cars_detected": 0, "parking_spaces": []})
    return jsonify({
        "cars_detected": c["cars"],
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

        #detections
        for x1, y1, x2, y2, conf in cap["last_boxes"]:
            cx, cy = (x1 + x2) // 2, (y1 + y2) // 2
            cv2.circle(display, (cx, cy), 6, (0, 0, 255), -1)
            cv2.putText(display, f"{conf:.2f}", (cx + 10, cy - 5),
                        cv2.FONT_HERSHEY_COMPLEX, 0.6, (0, 255, 0), 2)

        cv2.putText(display, f"Cars Detected: {len(cap['last_boxes'])}", (10, 32),
                    cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 0, 0), 2)

        #parking spaces & occupancy 
        space_status = []
        for i, pts in enumerate(cap["posList"]):
            contour = np.array(pts, dtype=np.int32).reshape((-1, 1, 2))

            occupied = any(
                cv2.pointPolygonTest(contour, (float((x1 + x2) // 2), float((y1 + y2) // 2)), False) >= 0
                for x1, y1, x2, y2, _ in cap["last_boxes"]
            )
            space_status.append({"id": i + 1, "open": not occupied})

            if mode == "mark":
                color = (255, 0, 0)
            else:
                color = (0, 0, 255) if occupied else (0, 255, 0)

            cv2.polylines(display, [contour], True, color, 2)
            lx = int(np.mean(contour[:, 0, 0]))
            ly = int(np.mean(contour[:, 0, 1]))
            cv2.putText(display, str(i + 1), (lx, ly),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)

        with status_lock:
            latest_status[name] = {
                "cars": len(cap["last_boxes"]),
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