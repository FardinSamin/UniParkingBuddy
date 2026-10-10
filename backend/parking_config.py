"""Validated, versioned parking-space configuration with persistent IDs.

Configurations are JSON files stored under configs/. Legacy CarPos_* pickle
files are retained for archival reference but are never executed or loaded.
"""

import json
import os
from pathlib import Path
import tempfile


class ParkingConfigError(ValueError):
    """A parking-space configuration is missing or invalid."""


def _positive_int(value):
    return type(value) is int and value > 0


def _cross(a, b, c):
    return (b[0] - a[0]) * (c[1] - b[1]) - (b[1] - a[1]) * (c[0] - b[0])


def _validate_polygon(points, space_id):
    if not isinstance(points, list) or len(points) != 4:
        raise ParkingConfigError(f"Space {space_id}: expected exactly four corners")

    if any(
        not isinstance(point, list)
        or len(point) != 2
        or any(type(coordinate) is not int or coordinate < 0 for coordinate in point)
        for point in points
    ):
        raise ParkingConfigError(f"Space {space_id}: coordinates must be nonnegative integers")

    if len({tuple(point) for point in points}) != 4:
        raise ParkingConfigError(f"Space {space_id}: polygon corners must be distinct")

    # Four consecutive turns must be nonzero and point in the same direction.
    # This rules out zero-area, self-crossing and concave quadrilaterals.
    turns = [_cross(points[i], points[(i + 1) % 4], points[(i + 2) % 4])
             for i in range(4)]
    if any(turn == 0 for turn in turns) or any((turn > 0) != (turns[0] > 0) for turn in turns):
        raise ParkingConfigError(f"Space {space_id}: corners must form a convex quadrilateral")


def _polygons_overlap(a, b):
    """True when two convex polygons share positive area (touching is allowed)."""
    for polygon in (a, b):
        for i in range(len(polygon)):
            p = polygon[i]
            q = polygon[(i + 1) % len(polygon)]
            axis = (p[1] - q[1], q[0] - p[0])
            a_values = [point[0] * axis[0] + point[1] * axis[1] for point in a]
            b_values = [point[0] * axis[0] + point[1] * axis[1] for point in b]
            if max(a_values) <= min(b_values) or max(b_values) <= min(a_values):
                return False
    return True


def validate_config(config):
    """Validate complete config without silently modifying or discarding spaces."""
    if not isinstance(config, dict) or set(config) != {"version", "next_space_id", "spaces"}:
        raise ParkingConfigError("Expected version, next_space_id, and spaces")
    if type(config["version"]) is not int or config["version"] != 1:
        raise ParkingConfigError("Unsupported configuration version")
    if not _positive_int(config["next_space_id"]):
        raise ParkingConfigError("next_space_id must be a positive integer")

    spaces = config["spaces"]
    if not isinstance(spaces, list):
        raise ParkingConfigError("spaces must be a list")

    identifiers = set()
    for space in spaces:
        if not isinstance(space, dict) or set(space) != {"id", "points"}:
            raise ParkingConfigError("Each space requires id and points")
        identifier = space["id"]
        if not _positive_int(identifier) or identifier in identifiers:
            raise ParkingConfigError("Space IDs must be unique positive integers")
        identifiers.add(identifier)
        _validate_polygon(space["points"], identifier)

    if identifiers and config["next_space_id"] <= max(identifiers):
        raise ParkingConfigError("next_space_id must exceed every existing space ID")

    for index, first in enumerate(spaces):
        for second in spaces[index + 1:]:
            if _polygons_overlap(first["points"], second["points"]):
                raise ParkingConfigError(
                    f"Spaces {first['id']} and {second['id']} overlap"
                )
    return config


def load_config(path):
    """Load only validated JSON. A missing/corrupt config is not an empty lot."""
    try:
        with open(path, "r", encoding="utf-8") as handle:
            config = json.load(handle)
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise ParkingConfigError(f"Cannot read parking configuration {path}: {error}") from error
    return validate_config(config)


def add_space(config, points):
    """Return a new config; existing IDs never change or get recycled."""
    space_id = config["next_space_id"]
    candidate = {
        "version": 1,
        "next_space_id": space_id + 1,
        "spaces": [
            *config["spaces"],
            {"id": space_id, "points": [list(point) for point in points]},
        ],
    }
    return validate_config(candidate)


def remove_space(config, space_id):
    """Remove the selected space without renumbering other IDs."""
    if not any(space["id"] == space_id for space in config["spaces"]):
        raise ParkingConfigError(f"Space {space_id} does not exist")
    candidate = {
        "version": 1,
        "next_space_id": config["next_space_id"],
        "spaces": [space for space in config["spaces"] if space["id"] != space_id],
    }
    return validate_config(candidate)


def save_config(path, config):
    """Atomically replace a validated config; never leave a partial JSON file."""
    validate_config(config)
    destination = Path(path)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=destination.parent,
            prefix=f".{destination.name}.", suffix=".tmp", delete=False,
        ) as handle:
            temporary = Path(handle.name)
            json.dump(config, handle, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, destination)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
