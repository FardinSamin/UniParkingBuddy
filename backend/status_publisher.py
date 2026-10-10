"""Publish valid computed space occupancy only after durable writes succeed.

This separates the live API publication decision from OpenCV GUI/YOLO startup
so it can be exercised against a real disposable PostgreSQL instance.
"""

from datetime import datetime, timezone

if __package__:
    from .occupancy_writer import CAMERA_LOTS, persist_processed_observation
    from .occupancy_contract import snapshot_from_cv
    from .status_api import invalidate_camera_status
else:
    from occupancy_writer import CAMERA_LOTS, persist_processed_observation
    from occupancy_contract import snapshot_from_cv
    from status_api import invalidate_camera_status


def publish_space_result(
    camera_name,
    space_status,
    vehicle_count,
    vehicles_in_spaces,
    vehicles_outside_spaces,
    *,
    repository,
    newly_inferred,
    latest_status,
    status_lock,
    observed_at=None,
):
    """Return True if a valid live result was published.

    In persistence mode: cache-reused frames are not published again.
    A failed/invalid database write invalidates the old live value, raises
    to the caller for safe error logging, and never publishes uncommitted data.
    """
    if repository is not None and not newly_inferred:
        return False

    if not space_status:
        invalidate_camera_status(camera_name, latest_status, status_lock)
        return False

    timestamp = observed_at if observed_at is not None else datetime.now(timezone.utc)
    try:
        if repository is None:
            # Even the no-database demo must reject malformed CV results.
            snapshot_from_cv(camera_name, space_status, timestamp, CAMERA_LOTS)
        else:
            persist_processed_observation(repository, camera_name, space_status, timestamp)
    except Exception:
        invalidate_camera_status(camera_name, latest_status, status_lock)
        raise

    with status_lock:
        latest_status[camera_name] = {
            "cars": vehicle_count,
            "in_space_vehicles": vehicles_in_spaces,
            "outside_space_vehicles": vehicles_outside_spaces,
            "spaces": space_status,
        }
    return True
