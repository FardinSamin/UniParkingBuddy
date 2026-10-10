# Prototype accessibility review record (SRS AT-08 / NFR-U01–U05)

**Purpose:** Track tested keyboard, accessible naming, text cues, contrast,
reflow and assistive-technology findings for UniParkingBuddy's existing
React user interface. The SRS requests review against relevant WCAG 2.2
Level A/AA criteria; it does **not** authorize claiming full formal
conformance without checking all applicable criteria.

**Scope and constraints:** Read-only homepage, Lot 1/2 current status,
Lot 1/2 historical trends and missing-data states. Not a native mobile
app, reservation workflow or vehicle/person identification tool.

## Test environment

- Commit: _enter_
- Browser/version: _enter_
- OS / screen / zoom: _enter_
- Keyboard / screen-reader tools: _enter_
- Tester and review date: _enter_
- Attached screenshots, keyboard-video evidence or issue IDs: _enter_

## Existing automated coverage (partial evidence only)

The actual Playwright/Chromium + Vite + FastAPI job checks:

- Desktop and mobile-size browser rendering without obvious horizontal
  document overflow in the existing smoke test.
- Lot-card textual OPEN/FULL/COMING SOON indicators and disabled
  unsupported Lot 3; text status does not rely on color alone.
- Keyboard Tab focus on the monitored lot cards, Enter to open the
  detail view, keyboard Enter to navigate into history, keyboard
  ArrowDown to switch configured space, and keyboard return to index.
- Programmatically confirmed visible CSS focus outlines on primary
  lot and history selection controls.
- Selected space has an associated "Parking space" label; historical
  observations display text for Occupied/Available and distinguish
  recorded 0% from missing data.
- Backend error / unavailable state uses visible explanatory text
  rather than inventing occupancy.

Automation is **supporting evidence** and not comprehensive WCAG 2.2
testing; human review of the applicable criteria is still required.

## WCAG 2.2 A / AA candidate checklist

Test applicable criteria on the actual workstation and browser/device
configuration. Mark each as **Pass**, **Fail**, **Not applicable** (with
reason) or **Not tested**; don't assume a pass from the existence of a
single automated check. The list below is **not exhaustive**.

| Criterion (when applicable) | What to inspect | Result | Evidence/issue |
| --- | --- | --- | --- |
| 1.1.1 Non-text Content (A) | UNCP image alternative text and nondecorative icons | **Not tested fully** | _enter_ |
| 1.3.1 Info and Relationships (A) | Landmarks/headings/space selector label/chart information | **Not tested fully** | _enter_ |
| 1.4.1 Use of Color (A) | OPEN/OCCUPIED/FULL/UNAVAILABLE text independent of colors | **Partly automated** | _enter_ |
| 1.4.3 Contrast (Minimum) (AA) | All ordinary text against its actual background, including badges and muted text | **Not tested** | _enter measured ratios_ |
| 1.4.10 Reflow (AA) | Content at narrow width / zoom without loss of functionality | **Partly automated** | _enter viewports and zoom_ |
| 1.4.11 Non-text Contrast (AA) | Interactive focus indicators/borders and meaningful graphical elements | **Not tested** | _enter_ |
| 2.1.1 Keyboard (A) | No mouse needed for each user-facing primary route/control | **Partly automated** | _enter full keyboard pass_ |
| 2.1.2 No Keyboard Trap (A) | Tab/Shift+Tab through all views and selects | **Not tested fully** | _enter_ |
| 2.4.3 Focus Order (A) | Focus movement follows reading/navigation order | **Partly automated** | _enter_ |
| 2.4.6 Headings and Labels (AA) | Meaningful page/section labels and select names | **Partly automated** | _enter_ |
| 2.4.7 Focus Visible (AA) | Focus appearance on all keyboard-reachable controls | **Partly automated** | _enter_ |
| 2.4.11 Focus Not Obscured (Minimum) (AA) | Sticky/overlay elements do not fully hide focus | **Not tested** | _enter_ |
| 3.3.1 Error Identification (A) | Clear unavailable/loading text and recovery | **Partly automated** | _enter_ |
| 4.1.2 Name, Role, Value (A) | Buttons/selects/chart names and accessible semantics | **Not tested fully** | _enter_ |
| 4.1.3 Status Messages (AA) | Loading/unavailable changes correctly announced via assistive technology | **Not tested** | _enter screen-reader results_ |

Before describing a criterion as Passed, record the actual procedure,
view(s), expected and observed behaviors. Use a browser accessibility
inspector and keyboard-only check, and perform assistive technology
checks where relevant. Use WCAG's **actual** published thresholds for
contrast and zoom; do not invent substitute project thresholds.

## Privacy and scope checks (AT-08)

- [ ] Inspect PostgreSQL tables for any face, plate, identity or raw
      video field; none should be collected by the application schema
- [ ] Inspect UI for unauthorized editing, reservations, payments,
      enforcement or identity tracking
- [ ] Confirm all testing uses approved camera/media sources; don't
      publicly share identifying frames or screenshots
- [ ] Verify public FastAPI routes are read-only
- [ ] Document any deviations, mitigations or formally reviewed changes

## Defect and sign-off

| Finding | Steps to reproduce | Severity | GitHub issue / fix | Retest |
| --- | --- | --- | --- | --- |
| _enter_ | _enter_ | _enter_ | _enter_ | _pending_ |

**Final accessibility review status: NOT COMPLETE.** The team must
execute, record and approve the relevant manual checks before claiming
AT-08 fully satisfied. This review worksheet does not modify the
original submitted SRS, SOW or SDD.
