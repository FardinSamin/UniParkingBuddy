"""Testable Flask status API, independent of video windows and YOLO loading."""

from flask import Flask, jsonify, request
from flask_cors import CORS


def invalidate_camera_status(camera_name, latest_status, status_lock):
    """Discard a previously published result when frames stop being valid."""
    with status_lock:
        latest_status.pop(camera_name, None)


def create_status_app(camera_captures, latest_status, status_lock, persistence=None):
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


    @app.get("/api/trends/<lot_id>")
    def get_trends(lot_id):
        """Read-only historical observation summary; never a forecast."""
        if persistence is None:
            return jsonify({"error": "Historical data is not configured"}), 503

        days_raw = request.args.get("days", "7")
        if not days_raw.isascii() or not days_raw.isdecimal():
            return jsonify({"error": "days must be an integer from 1 through 31"}), 400
        days = int(days_raw)
        if not 1 <= days <= 31:
            return jsonify({"error": "days must be an integer from 1 through 31"}), 400

        try:
            spaces = persistence.lot_spaces(lot_id)
            if spaces is None:
                return jsonify({"error": "Monitored lot not found"}), 404
            hourly = persistence.hourly_occupancy_trends(lot_id, days)
        except (ValueError, TypeError):
            return jsonify({"error": "Invalid lot identifier"}), 400
        except Exception:
            app.logger.exception("Unable to retrieve historical trends")
            return jsonify({"error": "Historical data is temporarily unavailable"}), 503

        return jsonify({
            "lot_id": lot_id,
            "days": days,
            "timezone": "UTC",
            "space_ids": spaces,
            "has_history": bool(hourly),
            "hourly": hourly,
            "basis": "observed occupancy samples; not parked duration or prediction",
        })

    @app.get("/api/history/<lot_id>/<space_id>")
    def get_space_history(lot_id, space_id):
        """Return at most 100 recent anonymous occupancy observations."""
        if persistence is None:
            return jsonify({"error": "Historical data is not configured"}), 503

        try:
            spaces = persistence.lot_spaces(lot_id)
            if spaces is None or space_id not in spaces:
                return jsonify({"error": "Configured lot or space not found"}), 404
            entries = persistence.space_history(lot_id, space_id, limit=100)
        except (ValueError, TypeError):
            return jsonify({"error": "Invalid lot or space identifier"}), 400
        except Exception:
            app.logger.exception("Unable to retrieve space history")
            return jsonify({"error": "Historical data is temporarily unavailable"}), 503

        return jsonify({
            "lot_id": lot_id,
            "space_id": space_id,
            "has_history": bool(entries),
            "records": [
                {"status": entry["status"], "observed_at": entry["observed_at"].isoformat()}
                for entry in entries
            ],
        })

    return app
