"""PostgreSQL occupancy repository following UniParkingBuddy SDD Part 2.

The camera loop is deliberately not connected in this migration: this module
provides validated, atomic database operations without silently changing the
existing live API. No identified vehicles or raw camera frames are stored.
"""

from datetime import datetime
from pathlib import Path

import psycopg
from psycopg.types.json import Jsonb

from .parking_config import validate_config

SCHEMA_PATH = Path(__file__).with_name("schema.sql")


def _identifier(value, name):
    if not isinstance(value, str) or not 1 <= len(value) <= 64 or not value.strip():
        raise ValueError(f"{name} must be a nonempty string of at most 64 characters")
    return value


def _timestamp(value):
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("observed_at must be a timezone-aware datetime")
    return value


def _status(value):
    if value not in ("AVAILABLE", "OCCUPIED") or not isinstance(value, str):
        raise ValueError("status must be AVAILABLE or OCCUPIED")
    return value


class OccupancyRepository:
    """Open a transaction for each operation; commit only fully valid batches."""

    def __init__(self, dsn):
        if not isinstance(dsn, str) or not dsn.strip():
            raise ValueError("A PostgreSQL connection string is required")
        self.dsn = dsn

    def register_lot_configuration(self, lot_id, display_label, config):
        """Persist the validated configured spaces/regions without erasing history.

        Existing DB spaces absent from JSON cause an explicit error. Deletion
        requires an intentional history-preserving maintenance procedure and
        cannot happen implicitly during startup or configuration synchronization.
        """
        lot_id = _identifier(lot_id, "lot_id")
        if display_label is not None and (
            not isinstance(display_label, str) or len(display_label) > 120
        ):
            raise ValueError("display_label must be null or at most 120 characters")
        validate_config(config)
        configured = {str(space["id"]) for space in config["spaces"]}

        with psycopg.connect(self.dsn) as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    "SELECT space_id FROM parking_space WHERE lot_id = %s FOR UPDATE",
                    (lot_id,),
                )
                existing = {row[0] for row in cursor.fetchall()}
                if existing - configured:
                    raise ValueError(
                        "Database contains spaces removed from the JSON configuration; "
                        "review historical records and reconcile manually"
                    )
                cursor.execute(
                    """
                    INSERT INTO parking_lot (lot_id, display_label)
                    VALUES (%s, %s)
                    ON CONFLICT (lot_id) DO UPDATE
                    SET display_label = EXCLUDED.display_label
                    """,
                    (lot_id, display_label),
                )
                for space in config["spaces"]:
                    space_id = str(space["id"])
                    cursor.execute(
                        """
                        INSERT INTO parking_space (lot_id, space_id)
                        VALUES (%s, %s)
                        ON CONFLICT (lot_id, space_id) DO NOTHING
                        """,
                        (lot_id, space_id),
                    )
                    cursor.execute(
                        """
                        INSERT INTO parking_space_region
                            (lot_id, space_id, region_definition)
                        VALUES (%s, %s, %s)
                        ON CONFLICT (lot_id, space_id) DO UPDATE
                        SET region_definition = EXCLUDED.region_definition
                        """,
                        (lot_id, space_id, Jsonb({"points": space["points"]})),
                    )

    def record_observations(self, lot_id, observations, observed_at):
        """Append a validated snapshot and update latest valid states atomically.

        All observations share the supplied timestamp; older updates are still
        retained in history, but cannot overwrite newer current states.
        Invalid input or an unknown space fails the entire transaction.
        """
        lot_id = _identifier(lot_id, "lot_id")
        observed_at = _timestamp(observed_at)
        if not isinstance(observations, list) or not observations:
            raise ValueError("observations must be a nonempty list")
        prepared = []
        used = set()
        for observation in observations:
            if not isinstance(observation, dict) or set(observation) != {"space_id", "status"}:
                raise ValueError("Each observation must contain space_id and status")
            space_id = _identifier(observation["space_id"], "space_id")
            status = _status(observation["status"])
            if space_id in used:
                raise ValueError("A space may appear only once in a snapshot")
            used.add(space_id)
            prepared.append((space_id, status))

        with psycopg.connect(self.dsn) as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT space_id FROM parking_space
                    WHERE lot_id = %s AND space_id = ANY(%s)
                    FOR UPDATE
                    """,
                    (lot_id, list(used)),
                )
                found = {row[0] for row in cursor.fetchall()}
                if found != used:
                    raise ValueError("Unknown configured space in occupancy update")

                for space_id, status in prepared:
                    cursor.execute(
                        """
                        INSERT INTO occupancy_record (lot_id, space_id, status, observed_at)
                        VALUES (%s, %s, %s::occupancy_status, %s)
                        """,
                        (lot_id, space_id, status, observed_at),
                    )
                    cursor.execute(
                        """
                        UPDATE parking_space
                        SET current_status = %s::occupancy_status,
                            current_status_at = %s
                        WHERE lot_id = %s AND space_id = %s
                          AND (current_status_at IS NULL OR %s >= current_status_at)
                        """,
                        (status, observed_at, lot_id, space_id, observed_at),
                    )

    def lot_summary(self, lot_id):
        """Return counts and an explicit completeness flag, never fake availability."""
        lot_id = _identifier(lot_id, "lot_id")
        with psycopg.connect(self.dsn) as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT COUNT(*),
                           COUNT(current_status),
                           COUNT(*) FILTER (WHERE current_status = 'AVAILABLE'),
                           COUNT(*) FILTER (WHERE current_status = 'OCCUPIED')
                    FROM parking_space WHERE lot_id = %s
                    """,
                    (lot_id,),
                )
                total, measured, available, occupied = cursor.fetchone()
                return {
                    "lot_id": lot_id,
                    "total_spaces": total,
                    "spaces_with_current_state": measured,
                    "available_spaces": available,
                    "occupied_spaces": occupied,
                    "complete": total > 0 and measured == total,
                }

    def space_history(self, lot_id, space_id):
        """Return timestamped history for one configured space, newest first."""
        lot_id = _identifier(lot_id, "lot_id")
        space_id = _identifier(space_id, "space_id")
        with psycopg.connect(self.dsn) as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT status, observed_at
                    FROM occupancy_record
                    WHERE lot_id = %s AND space_id = %s
                    ORDER BY observed_at DESC, record_id DESC
                    """,
                    (lot_id, space_id),
                )
                return [
                    {"status": status, "observed_at": time}
                    for status, time in cursor.fetchall()
                ]
