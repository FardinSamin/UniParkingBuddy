"""Register committed configured spaces in an initialized PostgreSQL database.

Run once after applying schema.sql, or again after non-destructive additions
to a JSON configuration. Do not expose DATABASE_URL in terminal output.
"""

import os
from pathlib import Path

from .occupancy_repository import OccupancyRepository
from .parking_config import load_config


ROOT = Path(__file__).resolve().parent.parent

# Mappings correspond to the existing React "Lot 1"/"Lot 2" UI cards.
CAMERA_LOTS = (
    ("camera_1", "lot1", "Lot 1"),
    ("camera_2", "lot2", "Lot 2"),
)


def main():
    dsn = os.environ.get("DATABASE_URL")
    if not dsn:
        raise SystemExit("Set DATABASE_URL to a PostgreSQL connection string first.")

    repository = OccupancyRepository(dsn)
    for camera, lot_id, label in CAMERA_LOTS:
        config = load_config(ROOT / "configs" / f"{camera}.json")
        repository.register_lot_configuration(lot_id, label, config)
        print(f"Registered {lot_id}: {len(config['spaces'])} configured spaces")


if __name__ == "__main__":
    main()
