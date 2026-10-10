"""Testable Flask status API, independent of video windows and YOLO loading."""

from flask import Flask, jsonify
from flask_cors import CORS


def invalidate_camera_status(camera_name, latest_status, status_lock):
    """Discard a previously published result when frames stop being valid."""
    with status_lock:
        latest_status.pop(camera_name, None)


def create_status_app(camera_captures, latest_status, status_lock):
    """Expose current occupancy only for active, processed cameras.

    Inputs are shared with the video-processing loop. The API does not
    infer occupancy when there is no valid processed status.
    """
    app = Flask(__name__)
    CORS(app)

    @app.get("/api/status/<camera>")
    def get_status(camera):
        with status_lock:
            if camera not in camera_captures:
                return jsonify({"error": "Camera is not configured or active"}), 404
            current = latest_status.get(camera)

        if current is None:
            return jsonify({"error": "Parking status is not ready"}), 503
        if not current["spaces"]:
            return jsonify({"error": "No configured parking spaces available"}), 503

        return jsonify({
            "cars_detected": current["cars"],
            "vehicles_in_spaces": current["in_space_vehicles"],
            "vehicles_outside_spaces": current["outside_space_vehicles"],
            "parking_spaces": [
                {"id": space["id"], "occupied": not space["open"]}
                for space in current["spaces"]
            ],
        })

    return app
