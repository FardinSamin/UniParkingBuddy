# Parking-space calibration (space-first workflow)

Use this **before** tuning YOLO matching. The sample videos contain many
visible parked cars that are not inside the currently configured stall
polygons. "Outside configured spaces" does not mean "outside the lot."

The current committed baseline intentionally monitors only:
- `camera_1`: seven polygons in `configs/camera_1.json`
- `camera_2`: four polygons in `configs/camera_2.json`

Those are **not** complete maps of every parking stall visible in either video.
Do not mark an unmapped vehicle as an occupancy error until it has a
verified, configured stall to match.

## Calibrate one camera at a time on Windows (CMD)

1. **Stop the running demo first**: focus an OpenCV window and press `q`.
   Also stop the React server if desired. Do not edit polygons while a
   live pipeline or controlled accuracy evaluation is running. If you
   have opted into PostgreSQL, stop the app before editing and plan an
   explicit configuration/database synchronization before restarting;
   newly added or removed IDs will not silently sync to PostgreSQL.
2. In CMD, from the repository root:

   ```cmd
   cd /d C:\Users\Fardin\UniParkingBuddy
   git pull --ff-only
   .venv\Scripts\python.exe -m backend.calibrate_spaces --camera camera_1 --frame 0
   ```

   For the second source:

   ```cmd
   .venv\Scripts\python.exe -m backend.calibrate_spaces --camera camera_2 --frame 0
   ```

   To examine a different paused frame, exit and rerun with a different
   nonnegative `--frame` index. For a smaller window, use `--width 960`.
   **All coordinates are saved in the original source-video resolution,**
   not resized-window pixels.

3. On the paused frame, draw **one actual parking stall at a time**:
   - **Left-click four corners** of the physical stall, in order around
     its perimeter. Add a polygon only where painted lines / known stall
     boundaries are sufficiently clear; don't guess through occluded areas.
   - Each successful polygon gets a **new stable ID**. Existing polygons
     and IDs are displayed in green and are not renumbered.
   - **Right-click within an existing polygon** to remove it from the
     unsaved working copy if it is incorrectly mapped. Removed IDs are
     **not** reused.
   - **U** undoes the last unfinished corner. An invalid, crossing,
     degenerate or overlapping polygon is rejected by existing config
     validation.
   - **S** saves changes after validating the entire configuration.
     The previous JSON is automatically backed up to the
     git-ignored `evaluation_runs/calibration_backups/` folder.
   - **Q** or Escape exits. Changes not explicitly saved are discarded.

   This is a **manual geometry editor**; it does not run YOLO, invent
   boundaries, or automatically classify any car as parked. The tool
   operates on the two existing sample videos and never writes to the
   application database.

4. After saving, verify configuration and restart the app:

   ```cmd
   .venv\Scripts\python.exe -m backend.preflight --require-gui
   .venv\Scripts\python.exe -m backend.main
   ```

   Confirm that every *configured* stall is labeled, no polygons
   overlap, and IDs match the on-screen physical stalls. Use manual
   review of the source video; passing preflight does **not** prove
   the polygons are geometrically correct.

## After space calibration

Only then evaluate the detection-to-space association. The current
matching algorithm still uses vehicle **bounding-box centers**, which
can misclassify angled parked cars and passing vehicles. Improved
ground-contact / occupancy logic is a separate, testable follow-up;
calibration alone is not an accuracy claim.

Before any scored evaluation, freeze both configuration JSON files,
record their Git commit SHA, and start a **new** `evaluation_runs/`
accuracy round (the previous manifest checksum becomes invalid after
any region change). Independently label ground truth as described in
[ACCURACY_EVALUATION.md](ACCURACY_EVALUATION.md).

Real campus camera frames will require **new, separately approved
calibration** for the fixed physical view, rather than reusing polygons
from these prerecorded sample videos. No campus recording is authorized
by this tool.
