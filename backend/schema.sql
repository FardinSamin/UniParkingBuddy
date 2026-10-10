-- UniParkingBuddy PostgreSQL physical schema.
-- Matches the approved SDD Part 2 (September 21, 2026), Section 12.
-- Apply once to an empty UniParkingBuddy database.
-- Deliberately contains no raw video, identity, permit, or prediction data.

CREATE TYPE occupancy_status AS ENUM ('AVAILABLE', 'OCCUPIED');

CREATE TABLE parking_lot (
    lot_id VARCHAR(64) PRIMARY KEY,
    display_label VARCHAR(120)
);

CREATE TABLE parking_space (
    lot_id VARCHAR(64) NOT NULL,
    space_id VARCHAR(64) NOT NULL,
    current_status occupancy_status,
    current_status_at TIMESTAMPTZ,
    PRIMARY KEY (lot_id, space_id),
    FOREIGN KEY (lot_id) REFERENCES parking_lot (lot_id),
    CHECK (
        (current_status IS NULL AND current_status_at IS NULL)
        OR
        (current_status IS NOT NULL AND current_status_at IS NOT NULL)
    )
);

CREATE TABLE parking_space_region (
    lot_id VARCHAR(64) NOT NULL,
    space_id VARCHAR(64) NOT NULL,
    region_definition JSONB NOT NULL,
    PRIMARY KEY (lot_id, space_id),
    FOREIGN KEY (lot_id, space_id)
        REFERENCES parking_space (lot_id, space_id),
    CHECK (jsonb_typeof(region_definition) IN ('object', 'array'))
);

CREATE TABLE occupancy_record (
    record_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    lot_id VARCHAR(64) NOT NULL,
    space_id VARCHAR(64) NOT NULL,
    status occupancy_status NOT NULL,
    observed_at TIMESTAMPTZ NOT NULL,
    FOREIGN KEY (lot_id, space_id)
        REFERENCES parking_space (lot_id, space_id)
);

CREATE INDEX idx_occupancy_space_time
    ON occupancy_record (lot_id, space_id, observed_at DESC);

CREATE INDEX idx_occupancy_lot_time
    ON occupancy_record (lot_id, observed_at DESC);
