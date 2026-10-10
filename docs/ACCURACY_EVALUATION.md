# Controlled configured-space accuracy evaluation

This is the **independently verified ground-truth evaluation** for the
approved UniParkingBuddy SRS NFR-P01. This workflow evaluates only the
configured-space `AVAILABLE` / `OCCUPIED` states. It does not invent a
required accuracy threshold, forecast parking, or classify vehicles as
stationary/moving.

No actual accuracy score is available until a human reviewer completes
the ground-truth annotations. Synthetic unit-test fixtures are **not**
real performance results.

## 1. Prepare a fixed, blind evaluation set

From a clone containing the latest committed source videos, configurations,
and `yolo26n.pt`:

```sh
python -m pip install -r requirements.txt
python -m backend.evaluate_accuracy prepare --output evaluation_runs/round1
```

This creates:
- `evaluation_runs/round1/manifest.json`: both source videos, deterministic
  sampled frame indices, configured-space IDs, and SHA-256 checksums of video,
  region configs and exact model weights.
- `evaluation_runs/round1/frames/camera_1/*.png` and similarly camera 2:
  previews with **configured polygon outlines and space IDs only**. No
  model detections or proposed Occupied/Available labels are shown.
- `evaluation_runs/round1/ground_truth.csv`: **blank** ground-truth
  labels for every chosen (camera, frame index, configured space ID) pair.

The default is eight frames per camera, chosen systematically across frames
the actual backend would infer (its 30-frame cadence). This is an evaluation
sampling **choice**, not an approved performance threshold. It can be changed
for an appropriate controlled protocol using `--frames-per-camera`.
Do not select only easy images; record the sampling procedure in your report.

The program refuses to overwrite an existing evaluation folder. To rerun,
use a **new** `evaluation_runs/round2` directory so you don't erase evidence.

## 2. Independently verify each space state

An authorized human reviewer examines the preview images and fills in
ONLY `ground_truth` (optionally `reviewer_notes`) in the CSV, leaving
`camera`, `frame_index` and `space_id` unchanged.

The only allowed human labels are:
- **AVAILABLE** — the configured space is visibly available.
- **OCCUPIED** — the configured space is visibly occupied.
- **UNVERIFIABLE** — the image genuinely doesn't allow a reliable human
  determination (for example, obstruction). **This is an annotation-only
  exclusion, not a third UniParkingBuddy occupancy state.**

Every row must receive one of these labels. Do not use model output as a
substitute for human verification. Prefer performing and freezing this step
**before running model predictions**, to prevent confirmation bias. Record
the annotator(s), review date and uncertainty/occlusion reasoning separately.

## 3. Run exactly the project's configured detection pipeline

```sh
python -m backend.evaluate_accuracy predict --output evaluation_runs/round1
```

This loads the committed model weights locally and uses the same:
- YOLO vehicle classes 2/3/7 (car/motorcycle/truck)
- confidence and input image size
- every-30-frame inference cadence
- center-point-in-configured-polygon rule
- persistent configured-space identifiers

Predictions are stored separately in `predictions.csv` and contain only
space-level `AVAILABLE`/`OCCUPIED` values. No faces, plates, specific
vehicle identities, or video data are written to PostgreSQL.

Model or source changes invalidate the sample evidence: checksums must
match. Start a new round for a different model, video or polygon layout.

## 4. Score only completed, manually verified annotations

```sh
python -m backend.evaluate_accuracy report --output evaluation_runs/round1
```

The program will refuse to compute a metric when:
- any human label remains blank,
- all entries are unverifiable,
- a prediction or annotation is missing, duplicated, malformed or unexpected,
- a third application occupancy state appears,
- source video, model or region configuration no longer matches the manifest.

On complete evidence, `accuracy_report.json` contains:
- number of sampled space/frame pairs,
- number excluded as humanly unverifiable,
- the evaluated denominator, number correct, and computed accuracy,
- occupied-positive TP, TN, FP, FN counts,
- separate summaries for each configured camera and parking space.

**Formula:**

`configured-space accuracy = correct human-verified comparisons / all human-verifiable comparisons × 100`

A passing vehicle whose detection center enters a polygon could still cause
false occupancy; this is an explicit known limitation. Keep such error cases
in your review rather than hiding them.

## 5. How to report results responsibly

Report the actual Git commit, annotation protocol, frame indices, dates
of evaluation, number of manually verified observations and exclusions,
per-camera performance, common error cases, and any uncertainty. The default
eight frames per camera are a **small sampled demonstration set**; do not
generalize their results to the entire campus without representative data.

Keep model correctness and display-update timing as distinct measurements.
For timing, follow `docs/VALIDATION.md`: observe the delay from processed
occupancy results to React display under documented system-test conditions.
The SRS baseline contains **no numeric mandated threshold**.

The `evaluation_runs/` directory is ignored by Git to protect local video
preview images, truth annotations and evidence. Do not commit images or
potentially sensitive observations to the public repository. Share summaries
only after confirming they contain no personal data.
