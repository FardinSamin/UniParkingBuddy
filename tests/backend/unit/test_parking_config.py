import pytest
import tempfile
import os
from backend.parking_config import (
    validate_config, ParkingConfigError, add_space, remove_space, load_config, save_config
)


def make_valid_config():
    return {
        "version": 1,
        "next_space_id": 3,
        "spaces": [
            {"id": 1, "points": [[0,0],[10,0],[10,10],[0,10]]},
            {"id": 2, "points": [[20,0],[30,0],[30,10],[20,10]]}
        ]
    }


def test_validate_config_valid():
    cfg = make_valid_config()
    assert validate_config(cfg) == cfg


def test_validate_config_nonconvex():
    cfg = make_valid_config()
    cfg['spaces'][0]['points'] = [[0,0],[10,0],[5,5],[0,10]]  # concave / crossing
    with pytest.raises(ParkingConfigError):
        validate_config(cfg)


def test_validate_config_overlap():
    cfg = make_valid_config()
    cfg['spaces'][1]['points'] = [[5,0],[15,0],[15,10],[5,10]]  # overlaps with first
    with pytest.raises(ParkingConfigError):
        validate_config(cfg)


def test_add_and_remove_space():
    cfg = make_valid_config()
    new_cfg = add_space(cfg, [(40,0),(50,0),(50,10),(40,10)])
    assert new_cfg['next_space_id'] == cfg['next_space_id'] + 1
    # remove the added space
    removed = remove_space(new_cfg, new_cfg['next_space_id'] - 1)
    assert len(removed['spaces']) == len(cfg['spaces'])


def test_load_and_save_config(tmp_path):
    cfg = make_valid_config()
    path = tmp_path / "test_config.json"
    save_config(str(path), cfg)
    loaded = load_config(str(path))
    assert loaded == cfg

