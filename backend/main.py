import cv2
import pickle
import numpy as np
import threading
from ultralytics import YOLO
from flask import Flask, jsonify
from flask_cors import CORS


#grab video and store inside of cap variable
cap = cv2.VideoCapture('stockvidsample2.mp4')
#raise error if video is not found
if not cap.isOpened(): 
    raise RuntimeError("Could not open video - check the path/filename")


#for testing saved videos, delete for live video
fps = cap.get(cv2.CAP_PROP_FPS)
if fps <= 0:
    fps = 30
frame_delay = int(1000 / fps)


#formatiting and controlling video display window
cv2.namedWindow("image", cv2.WINDOW_NORMAL) #allows to manually resize window
cv2.resizeWindow("image", 1280, 720) #sets initial window size


#yolo model 
model = YOLO('yolo26n.pt')
CARS = [2,3,7] #2=car, 3=motorcycle, 7=truck


DETECT_EVERY = 30 #run yolo model every nth frame
frame_idx=0 #keeps track of how many video frames have been processed
last_boxes = [] #store the amount of bounding boxes of cars detected by yolo


#parking Position drawing functionality
try:
    with open('CarPos', 'rb') as f:
        posList = pickle.load(f)
except FileNotFoundError:
    posList = []

current_points = []
mode = "play"

def save():
    with open('CarPos', 'wb') as f:
        pickle.dump(posList, f)

def mouseClick(event, x, y, _flags, _params):
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
            contour = np.array(pts, dtype=np.int32).reshape((-1, 1, 2))
            if cv2.pointPolygonTest(contour, (float(x), float(y)), False) >= 0:
                posList.pop(i)
                save()
                break

cv2.setMouseCallback("image", mouseClick)

#API SERVER
app = Flask(__name__)
CORS(app) #enables Cross-Region Resource Sharing, allows frontend to send requests to flask API

latest_status = []
latest_car_count = 0
status_lock = threading.Lock()

@app.route('/api/status')
def get_status():
    with status_lock:
        return jsonify({
            "cars_detected": latest_car_count,
            "parking_spaces": latest_status
        })

def run_api():
    app.run(port=5000, debug=False, use_reloader=False)

threading.Thread(target=run_api, daemon=True).start()

while True:
    #rewind function
    success, frame = cap.read()
    if not success:
        cap.set(cv2.CAP_PROP_POS_FRAMES, 0) #go back to first frame
        frame_idx=0 #reset
        last_boxes = [] #reset
        continue


    img = frame.copy() #create copy of current video frame and store it in img


    if frame_idx % DETECT_EVERY == 0: #run yolo every detect_every frames
        results = model(frame, classes=CARS, conf=0.25, imgsz=1280, verbose=False)[0]
        last_boxes = []

        for box in results.boxes:
            x1, y1, x2, y2 = map(int, box.xyxy[0])
            last_boxes.append((x1, y1, x2, y2, float(box.conf[0])))


    frame_idx += 1

    #visual cue for detected vehicles
    for x1, y1, x2, y2, conf in last_boxes:
        cx = (x1 + x2) // 2
        cy = (y1 + y2) // 2
        cv2.circle(img, (cx, cy), 6, (0,0,225), -1) #display circle for each detection

        #display confidence score
        confidence_text = f"{conf:.2f}" #variable containing text format for the visual confidence score
        cv2.putText(img, confidence_text, (cx+10, cy-5), 
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
        
    #display cars Detected
    count_text = f"Cars Detected: {len(last_boxes)}" #variable containing cars count
    cv2.putText(img, count_text, (10, 32),
                cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 0, 0), 2)

    # Draw saved parking polygons and check occupancy
    status = []
    for i, pts in enumerate(posList):
        contour = np.array(pts, dtype=np.int32).reshape((-1, 1, 2))

        # always compute occupancy so the dashboard keeps updating in either mode
        occupied = False
        for x1, y1, x2, y2, conf in last_boxes:
            bx = float((x1 + x2) // 2)
            by = float((y1 + y2) // 2)
            if cv2.pointPolygonTest(contour, (bx, by), False) >= 0:
                occupied = True
                break

        status.append({"id": i + 1, "occupied": occupied})

        if mode == "mark":
            color = (255, 0, 0)
        else:
            color = (0, 0, 255) if occupied else (0, 255, 0)

        cv2.polylines(img, [contour], isClosed=True, color=color, thickness=2)

        lx = int(np.mean(contour[:, 0, 0]))
        ly = int(np.mean(contour[:, 0, 1]))
        cv2.putText(img, str(i + 1), (lx, ly),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)

    # outside the for loop, so it runs every frame
    with status_lock:
        latest_status = status
        latest_car_count = len(last_boxes)


    # Draw points while creating a polygon
    if mode == "mark":
        for pt in current_points:
            cv2.circle(img, pt, 3, (0, 255, 255), -1)
        if len(current_points) > 1:
            cv2.polylines(img, [np.array(current_points, dtype=np.int32)], isClosed=False, color=(0, 255, 255), thickness=2)

    cv2.putText(img, f"Mode: {mode} (press 'm' to toggle)",
            (10, 65), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 2)










    cv2.imshow("image", img) #takes frame stored in img and puts it in window named "image"

    #close video tab function by pressing 'q', or clicking the X (close button)
    key = cv2.waitKey(frame_delay) & 0xFF
    if key == ord('q') or cv2.getWindowProperty("image", cv2.WND_PROP_VISIBLE) < 1:
        break
    elif key == ord('m'):
        mode = "mark" if mode == "play" else "play"
        current_points = []

cap.release()
cv2.destroyAllWindows()