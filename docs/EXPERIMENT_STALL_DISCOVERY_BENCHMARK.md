# Independent benchmark for automatic parking-stall discovery

**Status:** A research **measurement workflow**, not a new SRS requirement
or working automatic stall-layout model. It does not alter approved
`configs/` polygons, FastAPI, PostgreSQL, React or the application history.

## Why this exists

The October 10 Windows evidence showed:
- Phase 3 (pre-line-joining): 39 unverified geometries; zero shortlisted; 31
  suspected vehicle-surface artifacts
- Phase 4: **raw** 31 proposed shapes / zero shortlisted;
  **ground-contrast-supported** 6 shapes / one shortlisted

That evidence does **not** tell us precision, recall or IoU, because no
independent complete set of verified parking stalls exists for comparison.
And a clean-looking preview is not a substitute for reference labels.

This benchmark measures **discovered stall geometry**, separately from
the existing
[configured-space occupancy accuracy evaluation](ACCURACY_EVALUATION.md).
It uses human-marked *visible parking-stall quadrilaterals* as reference
geometry in a chosen fixed-camera view. These human labels are evaluation
data, **not configuration** and not a method used by the live detector.

## Step 1 — Blindly mark a small, bounded region of true stalls

Choose a part of the original video where painted stalls are actually
visible, ideally **including empty spaces**. The region must be small
enough to mark **all verifiable stalls inside it**, not an arbitrary sample.
This is required for meaningful precision: unlabeled real stalls inside
the evaluation area would otherwise be counted as model false positives.

From Windows **CMD**, after updating to the merged implementation:

```cmd
cd /d C:\Users\Fardin\UniParkingBuddy
git pull --ff-only
.venv\Scripts\python.exe -m backend.stall_discovery_benchmark annotate --video footage/stockvidsample2.mp4 --frame 0 --output evaluation_runs/stall_benchmark_camera1
```

The GUI deliberately shows a **clean original video frame**, with no
model predictions, stall proposals or occupancy labels.

- Press **R**, then click **two opposite corners** of a region containing
  only unambiguous, verifiable stalls. A blue outline identifies this
  evaluation region. Choose it **before** drawing any stall.
- For **every** genuine, visually verifiable marked stall in that
  region, left-click its **four physical boundary corners in order**
  around the perimeter. A green polygon and temporary ID appear.
- Include empty, marked stalls in the selected region. Do **not**
  invent hidden corners beneath cars. If a stall is too occluded to
  verify, choose a region that excludes it rather than silently counting
  unknown geometry.
- Press **U** to undo an unfinished corner or the last completed stall.
  Press **S** to save locally once **all** verifiable marked stalls in
  the evaluation region have been drawn. Press **Q** to exit without
  saving.
- The tool validates geometry and overlapping truth polygons, records
  the original video SHA-256 checksum, original frame dimensions and
  the selected ROI. It refuses to overwrite an existing annotation folder.

Output: `evaluation_runs/stall_benchmark_camera1/ground_truth.json`.
Your local `evaluation_runs/` folder is Git-ignored. Keep reference
annotations private; do not commit raw video frames, plates/faces,
or private parking activity to GitHub.

**Research independence:** We already saw the model's results on Camera 1,
so these new annotations can no longer be described as fully
experimenter-blind evaluation. The UI hides model proposals to reduce
additional bias, but an independent reviewer or truly held-out camera
view is necessary for stronger claims.

## Step 2 — Score actual geometry candidates

You already generated Phase 4 comparison results. Run:

```cmd
.venv\Scripts\python.exe -m backend.stall_discovery_benchmark score --truth evaluation_runs/stall_benchmark_camera1/ground_truth.json --proposals evaluation_runs/row_continuity_camera1/row_comparison.json --output evaluation_runs/stall_benchmark_camera1/phase4_scores.json
```

The report evaluates **both** raw and ground-filtered line-joining
variants, and compares their **full unverified candidate sets separately
from their shortlists**. Predictions outside the explicitly marked
evaluation rectangle are excluded. Ambiguous candidates crossing that
border are also excluded; the report records how many were excluded.

The procedure uses one-to-one matching of the **actual projected
quadrilaterals**, with intersection-over-union (IoU) in source-image
pixels. For **experimental reporting only**, it calculates precision,
recall, F1, TP, FP and FN at IoU 0.25, 0.50 and 0.75; the CLI prints
IoU 0.50 and the JSON includes all three. **These thresholds are
benchmark choices, not pass/fail commitments in the submitted SRS**.

- **TP:** one proposed shape uniquely matched to a human-verified stall
  at the selected IoU threshold.
- **FP:** a proposed shape inside the evaluation region which does not
  uniquely match a verified stall (including duplicate proposals).
- **FN:** a verifiable human-marked stall without a matching proposal.
- **Precision:** TP / (TP + FP), with zero when no proposals are made.
- **Recall:** TP / (TP + FN).
- **F1:** harmonic mean of precision and recall.

The program refuses to score incompatible source video hashes,
invalid/nonconvex/out-of-bounds quadrilaterals, invalid/overlapping
human labels, or an empty set of reference stalls. It will not overwrite
a previous report.

For Phase 2, substitute its `stall_candidates.json` in
`--proposals`. For Phase 3, use `review.json`. Both formats are
supported and can be scored under **new report filenames**, allowing
a direct comparison of algorithms on the **same frozen human labels**.

## Step 3 — Make decisions from measurements, not screenshots

The first annotation can be a narrow, easy-to-inspect region of the
present demo video. This is for debugging/algorithm development, not
a final generalization claim. Then repeat **on a separate, authorized,
held-out camera view** without adjusting thresholds on that view.

Keep a written record of camera geometry, selected scene, source
hashes, visible/occluded stall conditions, annotation reviewer, date,
and algorithm Git SHA. Maintain separate development and test views.

Improvements should prioritize both:
- **True marked-stall recall**, especially empty stalls and distant rows
- **Low false-proposal rate** from cars, windows, curbs and driving lanes

A method that reduces 39 incorrect-looking proposals to one candidate
may increase apparent precision while destroying recall. This benchmark
makes that tradeoff visible.

**Do not interpret polygon IoU as occupied/available classification
accuracy.** Continue SRS NFR-P01 / AT-05 / AT-06 using the existing
separate human-verified configured-space occupancy evaluation. No
unverified discovered polygon may flow to approved stable-ID configs,
FastAPI current availability or PostgreSQL occupancy history.
