"""Read-only FastAPI status/history endpoints independent of YOLO and OpenCV.

Keep existing HTTP paths, JSON success/error shapes, and status codes stable
while replacing the temporary Flask implementation.
"""

import logging
from typing import Literal

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel

if __package__:
    from .occupancy_writer import CAMERA_LOTS
else:
    from occupancy_writer import CAMERA_LOTS

logger = logging.getLogger(__name__)


class ConfiguredLotResponse(BaseModel):
    lot_id: str
    display_label: str
    camera: str
    space_ids: list[int]
    total_spaces: int
    has_current_data: bool
    available_spaces: int | None
    occupied_spaces: int | None


class ConfiguredLotsResponse(BaseModel):
    lots: list[ConfiguredLotResponse]


class ConfiguredSpaceResponse(BaseModel):
    id: int
    occupied: bool | None


class ConfiguredSpacesResponse(BaseModel):
    lot_id: str
    display_label: str
    camera: str
    has_current_data: bool
    spaces: list[ConfiguredSpaceResponse]


class ParkingSpaceResponse(BaseModel):
    id: int
    occupied: bool


class CurrentStatusResponse(BaseModel):
    cars_detected: int
    vehicles_in_spaces: int
    vehicles_outside_spaces: int
    parking_spaces: list[ParkingSpaceResponse]


class HourlyTrendResponse(BaseModel):
    hour_utc: int
    observations: int
    occupied_observations: int
    occupied_percent: float


class TrendsResponse(BaseModel):
    lot_id: str
    days: int
    timezone: Literal["UTC"]
    space_ids: list[str]
    has_history: bool
    hourly: list[HourlyTrendResponse]
    basis: str


class HistoryRecordResponse(BaseModel):
    status: Literal["AVAILABLE", "OCCUPIED"]
    observed_at: str


class SpaceHistoryResponse(BaseModel):
    lot_id: str
    space_id: str
    has_history: bool
    records: list[HistoryRecordResponse]


def _error(message: str, status_code: int) -> JSONResponse:
    """Preserve the JSON error contract expected by existing React clients."""
    return JSONResponse(status_code=status_code, content={"error": message})


def invalidate_camera_status(camera_name, latest_status, status_lock):
    """Discard a previously published result when frames stop being valid."""
    with status_lock:
        latest_status.pop(camera_name, None)


def create_status_app(camera_captures, latest_status, status_lock, persistence=None):
    """Construct the FastAPI app without opening video windows or a database."""
    app = FastAPI(
        title="UniParkingBuddy API",
        description="Read-only current occupancy and historical observations.",
        version="1.0.0",
    )
    # The public browser interface performs reads only. No credentialed
    # cross-origin endpoint is exposed in this milestone.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["GET"],
        allow_headers=["*"],
    )

    def configured_lots():
        """Read only active, validated configured regions and fresh live data."""
        summaries = []
        for camera, (lot_id, label) in CAMERA_LOTS.items():
            capture = camera_captures.get(camera)
            if not isinstance(capture, dict) or not isinstance(capture.get("config"), dict):
                continue
            configured = capture["config"].get("spaces")
            if not isinstance(configured, list):
                continue

            ids = [space["id"] for space in configured]
            with status_lock:
                live = latest_status.get(camera)
            observed = None
            if live is not None:
                live_spaces = live.get("spaces")
                if (
                    isinstance(live_spaces, list)
                    and len(live_spaces) == len(ids)
                    and {space["id"] for space in live_spaces} == set(ids)
                    and all(type(space["open"]) is bool for space in live_spaces)
                    and len(ids) > 0
                ):
                    observed = {space["id"]: not space["open"] for space in live_spaces}
            summaries.append((lot_id, label, camera, ids, observed))
        return summaries

    @app.get("/api/lots", response_model=ConfiguredLotsResponse)
    def get_configured_lots():
        """Configured monitored lots only (no unsupported Lot 3 entry)."""
        lots = []
        for lot_id, label, camera, ids, states in configured_lots():
            lots.append({
                "lot_id": lot_id,
                "display_label": label,
                "camera": camera,
                "space_ids": ids,
                "total_spaces": len(ids),
                "has_current_data": states is not None,
                "available_spaces": None if states is None else sum(not v for v in states.values()),
                "occupied_spaces": None if states is None else sum(states.values()),
            })
        return {"lots": lots}

    @app.get("/api/lots/{lot_id}/spaces", response_model=ConfiguredSpacesResponse)
    def get_configured_spaces(lot_id: str):
        """Return IDs even when status is unavailable; null means unknown."""
        for known_lot, label, camera, ids, states in configured_lots():
            if known_lot == lot_id:
                return {
                    "lot_id": lot_id,
                    "display_label": label,
                    "camera": camera,
                    "has_current_data": states is not None,
                    "spaces": [
                        {"id": space_id, "occupied": None if states is None else states[space_id]}
                        for space_id in ids
                    ],
                }
        return _error("Monitored lot not found", 404)

    @app.get("/api/status/{camera}", response_model=CurrentStatusResponse)
    def get_status(camera: str):
        with status_lock:
            if camera not in camera_captures:
                return _error("Camera is not configured or active", 404)
            current = latest_status.get(camera)

        if current is None:
            return _error("Parking status is not ready", 503)
        if not current["spaces"]:
            return _error("No configured parking spaces available", 503)

        return {
            "cars_detected": current["cars"],
            "vehicles_in_spaces": current["in_space_vehicles"],
            "vehicles_outside_spaces": current["outside_space_vehicles"],
            "parking_spaces": [
                {"id": space["id"], "occupied": not space["open"]}
                for space in current["spaces"]
            ],
        }

    @app.get("/api/trends/{lot_id}", response_model=TrendsResponse)
    def get_trends(lot_id: str, days: str = "7"):
        """Read-only historical observation summary; never a forecast."""
        if persistence is None:
            return _error("Historical data is not configured", 503)

        if not days.isascii() or not days.isdecimal():
            return _error("days must be an integer from 1 through 31", 400)
        requested_days = int(days)
        if not 1 <= requested_days <= 31:
            return _error("days must be an integer from 1 through 31", 400)

        try:
            spaces = persistence.lot_spaces(lot_id)
            if spaces is None:
                return _error("Monitored lot not found", 404)
            hourly = persistence.hourly_occupancy_trends(lot_id, requested_days)
        except (ValueError, TypeError):
            return _error("Invalid lot identifier", 400)
        except Exception:
            logger.exception("Unable to retrieve historical trends")
            return _error("Historical data is temporarily unavailable", 503)

        return {
            "lot_id": lot_id,
            "days": requested_days,
            "timezone": "UTC",
            "space_ids": spaces,
            "has_history": bool(hourly),
            "hourly": hourly,
            "basis": "observed occupancy samples; not parked duration or prediction",
        }

    @app.get("/api/history/{lot_id}/{space_id}", response_model=SpaceHistoryResponse)
    def get_space_history(lot_id: str, space_id: str):
        """Return at most 100 recent anonymous occupancy observations."""
        if persistence is None:
            return _error("Historical data is not configured", 503)

        try:
            spaces = persistence.lot_spaces(lot_id)
            if spaces is None or space_id not in spaces:
                return _error("Configured lot or space not found", 404)
            entries = persistence.space_history(lot_id, space_id, limit=100)
        except (ValueError, TypeError):
            return _error("Invalid lot or space identifier", 400)
        except Exception:
            logger.exception("Unable to retrieve space history")
            return _error("Historical data is temporarily unavailable", 503)

        return {
            "lot_id": lot_id,
            "space_id": space_id,
            "has_history": bool(entries),
            "records": [
                {"status": entry["status"], "observed_at": entry["observed_at"].isoformat()}
                for entry in entries
            ],
        }

    return app
