# First experiment: video-driven, unverified parking-location hypotheses

**Status:** Research prototype for the adaptive-space-discovery architecture
([research plan](RESEARCH_ADAPTIVE_SPACE_DISCOVERY.md)); **not** a finished
automatic parking-stall detector and not an approved parking configuration.

## What works in this iteration

For any **authorized, fixed-view** prerecorded parking-lot video supported by
OpenCV, the offline command:

1. Selects evenly distributed, model-compatible sample frames.
2. Applies the repository's local YOLO model to cars, trucks and motorcycles.
3. Uses each anonymous detection's bottom-center as an **approximate**
   ground-contact anchor (not a calibrated physical-world point).
4. Groups closely repeated anchors using widths/heights of the associated
   vehicle boxes as local geometric scales. A hypothesis receives **at most
   one supporting observation per sampled frame**.
5. Rejects groups with too few distinct frames or too little sample support.
6. Saves a local JSON report and a video-frame preview with numbered magenta
   **vehicle-location proxy boxes** labeled `UNVERIFIED`.

**Crucial:** These proxy rectangles are *not* parking-stall quadrilaterals;
the tool does **not** inspect painted parking lines or infer empty stalls.
A vehicle sitting in a driving lane may still create a false hypothesis.
Frame support is **not** calibrated confidence or a true probability.
We are testing the vehicle-location branch of the proposed multi-signal
algorithm before adding line detection, perspective calibration, and review.

The live occupancy app, `configs/camera_1.json`,
`configs/camera_2.json`, PostgreSQL tables, and public dashboard remain
**unchanged**.

## Run on Windows CMD (after merging and pulling the PR)

Stop any backend/video demo you are using for baseline accuracy testing,
then from your project folder:

```cmd
cd /d C:\Users\Fardin\UniParkingBuddy
git pull --ff-only
.venv\Scripts\python.exe -m backend.discover_space_hypotheses --video footage/stockvidsample2.mp4 --output evaluation_runs/discovery_camera1
```

For the second test video:

```cmd
.venv\Scripts\python.exe -m backend.discover_space_hypotheses --video footage/parkinglotfootage1_1.mp4 --output evaluation_runs/discovery_camera2
```

For a third, independently authorized fixed-view video (in any path you
control), replace the `--video` value and use a *new* `--output` directory.
The tool is **not** specific to these two filenames. For quick exploratory
runs, `--frames 8 --min-frames 3 --min-support 0.3` is accepted. These
default values are engineering experiments, **not** requirements or validated
thresholds. Processing runs on CPU, and many sampled frames can take time.

Each output directory contains:

- `hypotheses.json`: sampled frame indices, input/model SHA-256 hashes,
  numbered unverified location proxies, their supporting sampled frame
  counts, and explicit limitations.
- `preview.png`: one **local** sample frame annotated with proposed vehicle
  positions. The preview may contain visible faces/plates: review/privacy-
  screen it before sharing; never commit it to the public repository.

The program **refuses to overwrite** an existing results folder. Choose a
new folder for a rerun. `evaluation_runs/` is Git-ignored.

If it prints zero proposals, that does not mean the parking lot has zero
spaces or that it is empty. It may mean sampled observations failed to
provide repeatable vehicle evidence. If the source video moves/zooms,
contains moving traffic, or obscures stalls, proposals may be wrong.

## How to judge the output

Compare each magenta proposal against visible painted stalls in the original
source image; mark **true stall / lane or illegal parking / ambiguous** in
your private experiment notes. Also count **visible real stalls for which no
proposal appeared**. A correct-looking proposal isn't a verified four-corner
parking space. Avoid guessing boundaries that are obscured by vehicles.

Do not copy `proxy_vehicle_box_xyxy` into any live parking-space JSON.
That field is deliberately incompatible with the validated `points`-based
configuration format.

### Known gaps to address next

- Detect painted marking line segments, junctions, row alignment and
  possible stall boundaries; corroborate or reject vehicle-location
  hypotheses.
- Estimate scene homography only when verifiable reference geometry exists;
  fixed-camera perspective means a box anchor is not automatically a
  stall-center point.
- Reject traffic-lane patterns, single permanently parked vehicles,
  uncalibrated camera movement, and repeated-observation dependence.
- Add an independent review-and-approval workflow to convert **verified**
  stall polygons into stable IDs without erasing earlier configurations.
- Evaluate stall-geometry extraction on **unseen** videos and independently
  verified boundaries, separately from occupancy accuracy and latency.

These steps are **research work**, beyond the working SRS-mandated manual
configured-space capability. No measurable real-world accuracy, number
of discoverable stalls, or universal compatibility is claimed.
