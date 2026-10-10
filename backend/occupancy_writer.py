"""Map newly processed CV space observations to the approved database model.

Only anonymous per-space AVAILABLE/OCCUPIED states are persisted; vehicle
detection boxes, people, plates and video frames are never passed to the DB.
"""

from datetime import datetime


CAMERA_LOTS = {
    "camera_1": ("lot1", "Lot 1"),
    "camera_2": ("lot2", "Lot 2"),
}


def initialize_lots(repository, camera_captures):
    """Register each configured lot before processing or publishing updates."""
    for camera, (lot_id, label) in CAMERA_LOTS.items():
        if camera not in camera_captures:
            continue
        configuration = camera_captures[camera]["config"]
        repository.register_lot_configuration(lot_id, label, configuration)


def persist_processed_observation(repository, camera, space_status, observed_at):
    """Write one fresh CV inference result, not repeated cached-frame results."""
    if camera not in CAMERA_LOTS:
        raise ValueError("Unknown monitored camera")
    if not isinstance(space_status, list) or not space_status:
        raise ValueError("No configured space observations to persist")
    if not isinstance(observed_at, datetime):
        raise ValueError("A timestamp is required")

    seen = set()
    observations = []
    for space in space_status:
        if not isinstance(space, dict) or set(space) != {"id", "open"}:
            raise ValueError("Unexpected processed space status")
        space_id = space["id"]
        if type(space_id) is not int or space_id <= 0 or type(space["open"]) is not bool:
            raise ValueError("Invalid processed space ID or state")
        if space_id in seen:
            raise ValueError("Duplicate processed space ID")
        seen.add(space_id)
        observations.append({
            "space_id": str(space_id),
            "status": "AVAILABLE" if space["open"] else "OCCUPIED",
        })

    lot_id, _ = CAMERA_LOTS[camera]
    repository.record_observations(lot_id, observations, observed_at)
