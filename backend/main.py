import cv2
import pickle
import numpy as np
import threading
from ultralytics import YOLO
from flask import Flask, jsonify
from flask_cors import CORS

try:
    with open('CarPos', 'rb') as f:
        posList = pickle.load(f)
except FileNotFoundError:
    posList = []

current_points = []
mode = "play"

model = YOLO('yolov8n.pt')
VEHICLE_CLASSES = {2, 3, 5, 7}

latest_status = []
status_lock = threading.Lock()

def save():
    with open('CarPos', 'wb') as f:
        pickle.dump(posList, f)

def mouseClick(event, x, y, flags, params):
    global current_points
    if mode != "mark":
        return

    if event == cv2.EVENT_LBUTTONDOWN:
        current_points.append((x, y))
        if len(current_points) == 4:
            posList.append(current_points.copy())
            current_points = []
            save()

    elif event == cv2.EVENT_RBUTTONDOWN:
        for i, pts in enumerate(posList):
            contour = np.array(pts, dtype=np.int32)
            if cv2.pointPolygonTest(contour, (x, y), False) >= 0:
                posList.pop(i)
                break
        save()

def getVehicleAnchors(frame):
    results = model(frame, verbose=False)[0]
    anchors = []
    for box in results.boxes:
        if int(box.cls[0]) in VEHICLE_CLASSES:
            x1, y1, x2, y2 = box.xyxy[0].tolist()
            bottom_center = ((x1 + x2) / 2, y2)
            anchors.append(bottom_center)
    return anchors

def checkParkingSpace(img, vehicle_centers):
    global latest_status
    occupied_count = 0
    status = []

    for i, pts in enumerate(posList):
        contour = np.array(pts, dtype=np.int32)

        is_occupied = any(
            cv2.pointPolygonTest(contour, center, False) >= 0
            for center in vehicle_centers
        )
        if is_occupied:
            occupied_count += 1

        status.append({"id": i, "occupied": is_occupied, "points": pts})

        color = (0, 0, 255) if is_occupied else (0, 255, 0)
        cv2.polylines(img, [contour], isClosed=True, color=color, thickness=2)

        #number label for each box
        cx = int(np.mean(contour[:, 0]))
        cy = int(np.mean(contour[:, 1]))
        label = str(i)
        (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.7, 2)
        cv2.rectangle(img, (cx - tw // 2 - 4, cy - th // 2 - 4),
                      (cx + tw // 2 + 4, cy + th // 2 + 4), (0, 0, 0), -1)
        cv2.putText(img, label, (cx - tw // 2, cy + th // 2),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)

    with status_lock:
        latest_status = status

    cv2.putText(img, f'Occupied: {occupied_count}/{len(posList)}', (10, 60),
                cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 0, 255), 2)

#api server
app = Flask(__name__)
CORS(app)

@app.route('/api/spaces')
def get_spaces():
    with status_lock:
        return jsonify(latest_status)

def run_api():
    app.run(port=5000, debug=False, use_reloader=False)


#video source
cap = cv2.VideoCapture('stockparkinglot2.mp4')
if not cap.isOpened():
    raise RuntimeError("Could not open video — check the path/filename")

cv2.namedWindow("image", cv2.WINDOW_NORMAL)
cv2.resizeWindow("image", 1280, 720)
cv2.setMouseCallback("image", mouseClick)

threading.Thread(target=run_api, daemon=True).start()

frame_count = 0
vehicle_anchors = []
DETECT_EVERY_N_FRAMES = 5 

while True:
    success, frame = cap.read()
    if not success:
        cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
        continue

    img = frame.copy()

    if mode == "play":
        if frame_count % DETECT_EVERY_N_FRAMES == 0:
            vehicle_anchors = getVehicleAnchors(frame)
        checkParkingSpace(img, vehicle_anchors)
        frame_count += 1
    else:
        for i, pts in enumerate(posList):
            contour = np.array(pts, dtype=np.int32)
            cv2.polylines(img, [contour], isClosed=False, color=(255, 0, 0), thickness=2)

            cx = int(np.mean(contour[:, 0]))
            cy = int(np.mean(contour[:, 1]))
            label = str(i)
            (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.7, 2)
            cv2.rectangle(img, (cx - tw // 2 - 4, cy - th // 2 - 4),
                          (cx + tw // 2 + 4, cy + th // 2 + 4), (0, 0, 0), -1)
            cv2.putText(img, label, (cx - tw // 2, cy + th // 2),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
            
    if mode == "mark":
        for pt in current_points:
            cv2.circle(img, pt, 3, (0, 255, 255), -1)
        if len(current_points) > 1:
            cv2.polylines(img, [np.array(current_points, dtype=np.int32)], isClosed=False, color=(0, 255, 255), thickness=1)

    cv2.putText(img, f"mode: {mode} (press 'm' to toggle)", (10, 30),
                cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 2)

    cv2.imshow("image", img)
    key = cv2.waitKey(10) & 0xFF
    if key == ord('q'):
        break
    elif key == ord('m'):
        mode = "mark" if mode == "play" else "play"

cap.release()
cv2.destroyAllWindows()