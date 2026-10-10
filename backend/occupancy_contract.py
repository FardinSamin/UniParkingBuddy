"""Trusted CV -> backend occupancy contract (SRS FR-05/06/11, SR-06/07).

This is an internal structured interface, not an unauthenticated public HTTP
write route. The React application remains read-only.
"""

from datetime import datetime
from typing import Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, field_validator, model_validator


class SpaceObservation(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    space_id: str = Field(min_length=1, max_length=64)
    status: Literal["AVAILABLE", "OCCUPIED"]

    @field_validator("space_id")
    @classmethod
    def configured_identifier(cls, value):
        # The project's committed JSON region IDs are positive integers.
        # Reject alternate spellings such as "+1", "01" and whitespace.
        if not value.isascii() or not value.isdecimal() or value.startswith("0"):
            raise ValueError("space_id must be a canonical positive configured ID")
        return value


class OccupancyUpdate(BaseModel):
    """One timestamped, anonymous snapshot for one configured monitored lot."""

    model_config = ConfigDict(extra="forbid", strict=True)

    lot_id: str = Field(min_length=1, max_length=64)
    observed_at: AwareDatetime
    spaces: list[SpaceObservation] = Field(min_length=1)

    @field_validator("lot_id")
    @classmethod
    def nonblank_lot(cls, value):
        if not value.strip():
            raise ValueError("lot_id must not be blank")
        return value

    @model_validator(mode="after")
    def unique_space_ids(self):
        ids = [space.space_id for space in self.spaces]
        if len(ids) != len(set(ids)):
            raise ValueError("Duplicate configured-space identifier in update")
        return self


def accept_occupancy_update(repository, update):
    """Validate before calling the repository's atomic current/history update.

    Unknown lot/space IDs are rejected by the repository against configured
    PostgreSQL rows; any such error rolls the whole transaction back.
    """
    validated = OccupancyUpdate.model_validate(update)
    repository.record_observations(
        validated.lot_id,
        [space.model_dump() for space in validated.spaces],
        validated.observed_at,
    )
    return validated


def snapshot_from_cv(camera, spaces, observed_at, camera_lots):
    """Convert fresh CV boolean states to the same validated domain contract."""
    if camera not in camera_lots:
        raise ValueError("Unknown monitored camera")
    if not isinstance(spaces, list) or not spaces:
        raise ValueError("No configured-space observations")
    observations = []
    for space in spaces:
        if not isinstance(space, dict) or set(space) != {"id", "open"}:
            raise ValueError("Unexpected processed space status")
        if type(space["id"]) is not int or space["id"] <= 0 or type(space["open"]) is not bool:
            raise ValueError("Invalid configured-space ID or occupancy boolean")
        observations.append({
            "space_id": str(space["id"]),
            "status": "AVAILABLE" if space["open"] else "OCCUPIED",
        })
    return OccupancyUpdate.model_validate({
        "lot_id": camera_lots[camera][0],
        "observed_at": observed_at,
        "spaces": observations,
    })
