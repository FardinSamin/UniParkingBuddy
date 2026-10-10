"""Map newly processed CV space observations to the approved database model.

Only anonymous per-space AVAILABLE/OCCUPIED states are persisted; vehicle
detection boxes, people, plates and video frames are never passed to the DB.
"""

if __package__:
    from .occupancy_contract import accept_occupancy_update, snapshot_from_cv
else:
    from occupancy_contract import accept_occupancy_update, snapshot_from_cv


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
    """Accept a fresh CV result only after strict domain-contract validation."""
    snapshot = snapshot_from_cv(camera, space_status, observed_at, CAMERA_LOTS)
    accept_occupancy_update(repository, snapshot)
