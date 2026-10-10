# UniParkingBuddy Frontend

The React + TypeScript web interface is a **read-only** view of monitored
parking-space availability and descriptive historical observations. The design
and existing Lot 1/Lot 2 routes are retained.

## Local development

From the repository root, launch the Python/FastAPI backend according to
`docs/FASTAPI_MIGRATION.md`:

```sh
python backend/main.py
```

Then in a separate terminal:

```sh
cd frontend
npm ci
npm run dev
```

Open the URL that Vite prints. The page makes requests to **relative
`/api/...` paths**. The Vite development server proxies them to
`http://127.0.0.1:5000` (FastAPI) by default; it never relies on the
browser viewer's own `localhost`.

If FastAPI runs at a different address from the Vite process, set
`API_PROXY_TARGET` in the environment of the terminal **launching Vite**,
for example:

```powershell
$env:API_PROXY_TARGET = 'http://127.0.0.1:5000'
npm run dev
```

`API_PROXY_TARGET` is a local development server setting, not a user
credential and not a client-side browser URL.

## Authorized testing from a second device

On an authorized private test network, you may explicitly start Vite using
`npm run dev -- --host 0.0.0.0`, then visit
`http://<development-computer-LAN-IP>:5173` from another device. The
second device sends `/api` to that same Vite host, which proxies requests
to FastAPI on the development computer. Keep this on authorized networks,
follow campus DoIT rules, and do not expose the Vite development server or
camera processing service to the public internet.

## Production/demo hosting

A production build created by `npm run build` does **not** carry a Vite
development proxy. Whichever authorized web server serves `dist/` must
forward `/api/*` to the FastAPI backend, while serving React routes such
as `/parking-lot1` and `/history/lot1` via the application HTML entry
point. Without that routing, API requests fail safely as unavailable; do
not claim the static build alone is a deployed backend.

## Data behavior

- `GET /api/lots` is the authoritative inventory of actively monitored
  configured lots. The existing home cards for Lots 1/2 become interactive
  only when their matching camera/lot pair is active.
- The unsupported Lot 3 placeholder remains visible and disabled.
- A monitored lot with valid current data displays actual Open/Occupied
  counts. **Recorded zero open spots** means FULL.
- If current results have not been processed, the API has no current
  observation or the network fails, the UI shows **UNAVAILABLE**,
  not a fabricated zero count or FULL label.
- Lot detail pages still use the existing validated live-status endpoint.
  The separate history screen reads stored observations from PostgreSQL;
  replayed demonstration video must not be described as real campus traffic
  trends.
- The UNCP logo is loaded through Vite's static asset bundling so it works
  when built for distribution.

## Verification

```sh
npm test
npm run lint
npm run build
```

GitHub Actions runs these commands and includes actual Chromium/Vite/FastAPI
navigation, keyboard focus, mobile-width smoke checks and controlled
synthetic update-timing observations. **Physical camera setup, second-device
networking, full-system workstation acceptance, manually verified model
accuracy and complete WCAG review still need human execution.** See
`docs/VALIDATION.md` and `docs/WORKSTATION_DEMO.md`.

There are no user-facing actions to edit configured spaces, submit occupancy
updates, identify vehicles or people, or make parking reservations.
