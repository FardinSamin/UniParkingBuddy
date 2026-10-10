# Parking-space configuration

UniParkingBuddy has **two preconfigured test-video cameras**:

| Camera | File | Configured spaces |
| --- | --- | --- |
| `camera_1` | `configs/camera_1.json` | 7 |
| `camera_2` | `configs/camera_2.json` | 4 |

These JSON files preserve the polygons from the team's original, committed
`CarPos_camera_1` and `CarPos_camera_2` files. The original binary files are
kept only as reference. **The application does not load or execute pickles.**

## Format

```json
{
  "version": 1,
  "next_space_id": 3,
  "spaces": [
    { "id": 1, "points": [[10, 10], [30, 10], [30, 30], [10, 30]] },
    { "id": 2, "points": [[40, 10], [60, 10], [60, 30], [40, 30]] }
  ]
}
```

- Each space has an independent positive integer `id`, stable within its camera/lot.
- `next_space_id` increases when a new space is created; deleted IDs are never reused.
- The four `points` are ordered corners in **original source-video pixel
  coordinates**, not normalized percentages or browser coordinates.
- Spaces must have distinct nonnegative integer corners forming a convex
  quadrilateral. Configured polygons may touch but may not overlap with
  positive area, because that would make vehicle-to-space association ambiguous.
- The actual configured camera/lot identity is associated with the config
  filename. `id` is unique **within** that lot; persistent database keys should
  use the lot identifier **together with** the space ID.

## Editing regions in the OpenCV window

Run the backend from any working directory (paths now resolve from the
repository root). Press `m` to enter marking mode.

- **Left-click four corners** in order to define a new space. On success, its
  unique ID is allocated, saved to JSON, and displayed in the video window.
- **Right-click inside a space** to remove it. Remaining IDs do **not** change.
- Press `m` again to return to play mode.

Changes are validated and saved through a temporary file plus atomic replace.
If an overlapping/invalid polygon or write failure is detected, the saved file
and current in-memory configuration are left unchanged, and an error is printed
to the backend terminal. A failed four-click attempt can be retried.

### Avoid losing previous work

If you have **different local markings** in old `CarPos_*` pickle files,
**back them up before checking out this branch**. These files are not
automatically migrated or trusted. The committed JSON preserves the **committed
October 7** coordinates only. Additional local markings need to be reviewed
and recreated or safely converted separately.

Do not edit the JSON with Python `pickle.load`; pickle is not a safe interchange
format. Prefer the OpenCV marking controls or a reviewed manual JSON edit.

## Startup validation and verification

Missing, corrupt, unsupported-version, overlapping, or otherwise invalid
configuration causes startup to **fail with a clear error** rather than claim
that zero configured spaces are a valid empty lot. A valid JSON file with
`spaces: []` is structurally allowed for future configuration, but the
availability API will report current availability as **unavailable** until
at least one region is configured.

From the repository root:

```sh
python -m unittest discover -s backend/tests -p "test_parking_config.py"
python -m unittest discover -s backend/tests -p "test_space_matching.py"
```

The second command requires the OpenCV and NumPy backend dependencies.
Both video-based calibration/verification and controlled ground-truth occupancy
testing are still necessary. This configuration change does not establish a
measured detection-accuracy or refresh-time guarantee.
