"""Real Chromium + Vite + FastAPI read-only interface smoke tests.

Uses the production FastAPI route handlers and actual React components with
controlled *synthetic* occupancy fixtures. The real YOLO/PostgreSQL pipeline
is tested in test_real_video_db_api.py; this test does not assert CV accuracy.
No physical camera, raw video or public write endpoint is involved.
"""

from datetime import datetime, timezone
import json
import platform
import statistics
from pathlib import Path
import os
import re
import shutil
import socket
import subprocess
import threading
import time
import unittest
from urllib.error import URLError
from urllib.request import urlopen

from backend.occupancy_writer import CAMERA_LOTS
from backend.parking_config import load_config
from backend.status_api import create_status_app, invalidate_camera_status


ROOT = Path(__file__).resolve().parents[2]


def unused_local_port():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def wait_for_http(url, process=None):
    deadline = time.monotonic() + 35
    while time.monotonic() < deadline:
        if process is not None and process.poll() is not None:
            raise RuntimeError(f"Development server exited ({process.returncode})")
        try:
            with urlopen(url, timeout=1) as response:
                if response.status == 200:
                    return
        except (URLError, OSError, TimeoutError):
            pass
        time.sleep(0.2)
    raise RuntimeError(f"Service did not become ready at {url}")


class ReadOnlyHistoryFixture:
    """An explicitly synthetic test-only history provider, not PostgreSQL."""

    def __init__(self, camera_captures):
        self.camera_captures = camera_captures
        self.unavailable = False

    def lot_spaces(self, lot_id):
        for camera, (configured_lot, _) in CAMERA_LOTS.items():
            if lot_id == configured_lot:
                return [
                    str(space["id"])
                    for space in self.camera_captures[camera]["config"]["spaces"]
                ]
        return None

    def hourly_occupancy_trends(self, lot_id, days):
        if self.unavailable:
            raise RuntimeError("Simulated history storage outage for browser test")
        if self.lot_spaces(lot_id) is None:
            raise ValueError("Unknown lot")
        return [{
            "hour_utc": 12,
            "observations": 4,
            "occupied_observations": 2,
            "occupied_percent": 50.0,
        }]

    def space_history(self, lot_id, space_id, limit):
        if space_id not in self.lot_spaces(lot_id):
            raise ValueError("Unknown configured space")
        return [{
            "status": "OCCUPIED" if space_id == "1" else "AVAILABLE",
            "observed_at": datetime(2026, 10, 10, 12, tzinfo=timezone.utc),
        }]


@unittest.skipUnless(
    os.getenv("RUN_BROWSER_E2E") == "1",
    "Chromium/Vite integration is exercised in its dedicated CI job",
)
class ReactFastAPIBrowserTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from playwright.sync_api import sync_playwright, expect
        import uvicorn

        cls.cameras = {
            camera: {"config": load_config(ROOT / "configs" / f"{camera}.json")}
            for camera in CAMERA_LOTS
        }
        cls.lock = threading.Lock()
        cls.live = {}
        cls.restore_live_status()
        cls.history = ReadOnlyHistoryFixture(cls.cameras)
        app = create_status_app(cls.cameras, cls.live, cls.lock, cls.history)

        cls.api_port = unused_local_port()
        cls.frontend_port = unused_local_port()
        config = uvicorn.Config(
            app, host="127.0.0.1", port=cls.api_port,
            log_level="error", access_log=False,
        )
        cls.server = uvicorn.Server(config)
        cls.api_thread = threading.Thread(
            target=cls.server.run, daemon=True, name="browser-fixture-api"
        )
        cls.api_thread.start()

        def stop_backend():
            cls.server.should_exit = True
            cls.api_thread.join(timeout=10)
        cls.addClassCleanup(stop_backend)

        wait_for_http(f"http://127.0.0.1:{cls.api_port}/openapi.json")
        npm = shutil.which("npm")
        if npm is None:
            raise RuntimeError("Node/npm is required for Vite browser tests")

        env = os.environ.copy()
        env["API_PROXY_TARGET"] = f"http://127.0.0.1:{cls.api_port}"
        cls.vite = subprocess.Popen(
            [
                npm, "run", "dev", "--", "--host", "127.0.0.1",
                "--port", str(cls.frontend_port), "--strictPort",
            ],
            cwd=ROOT / "frontend", env=env,
            stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT,
        )

        def stop_vite():
            if cls.vite.poll() is None:
                cls.vite.terminate()
                try:
                    cls.vite.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    cls.vite.kill()
                    cls.vite.wait(timeout=5)
        cls.addClassCleanup(stop_vite)

        cls.base_url = f"http://127.0.0.1:{cls.frontend_port}"
        wait_for_http(cls.base_url, cls.vite)
        cls.playwright = sync_playwright().start()
        cls.addClassCleanup(cls.playwright.stop)
        cls.browser = cls.playwright.chromium.launch(headless=True)
        cls.addClassCleanup(cls.browser.close)
        cls.expect = staticmethod(expect)

    @classmethod
    def restore_live_status(cls):
        first_config = cls.cameras["camera_1"]["config"]["spaces"]
        second_config = cls.cameras["camera_2"]["config"]["spaces"]
        with cls.lock:
            cls.live["camera_1"] = {
                "cars": 2,
                "in_space_vehicles": 1,
                "outside_space_vehicles": 1,
                "spaces": [
                    {"id": space["id"], "open": space["id"] != first_config[0]["id"]}
                    for space in first_config
                ],
            }
            cls.live["camera_2"] = {
                "cars": len(second_config),
                "in_space_vehicles": len(second_config),
                "outside_space_vehicles": 0,
                "spaces": [
                    {"id": space["id"], "open": False}
                    for space in second_config
                ],
            }

    def test_browser_renders_lots_details_history_and_recovery(self):
        self.restore_live_status()
        page = self.browser.new_page(viewport={"width": 1200, "height": 800})
        self.addCleanup(page.close)

        # A real Chromium browser fetches the API THROUGH Vite's /api proxy
        # and the actual FastAPI endpoint, not via a mocked browser response.
        response = page.request.get(self.base_url + "/api/lots")
        self.assertEqual(response.status, 200)
        self.assertEqual(
            [lot["lot_id"] for lot in response.json()["lots"]],
            ["lot1", "lot2"],
        )

        page.goto(self.base_url, wait_until="domcontentloaded")
        cards = page.locator(".lot-card")
        self.expect(cards).to_have_count(3)
        configured_one = len(self.cameras["camera_1"]["config"]["spaces"])
        configured_two = len(self.cameras["camera_2"]["config"]["spaces"])
        self.expect(cards.nth(0)).to_contain_text(
            f"{configured_one - 1} of {configured_one} open", timeout=15000
        )
        self.expect(cards.nth(1)).to_contain_text(f"0 of {configured_two} open")
        self.expect(cards.nth(1)).to_contain_text("FULL")
        self.expect(cards.nth(2)).to_contain_text("COMING SOON")
        self.expect(cards.nth(2)).to_be_disabled()
        self.expect(cards.nth(0)).to_be_enabled()
        self.expect(page.locator(".welcome-logo")).to_be_visible()
        self.assertTrue(page.locator(".welcome-logo").evaluate(
            "(img) => img.complete && img.naturalWidth > 0"
        ))

        cards.nth(0).click()
        self.expect(page).to_have_url(re.compile(r"/parking-lot1$"))
        self.expect(page.locator(".dashboard-space")).to_have_count(configured_one)
        self.expect(page.locator(".dashboard-space.occupied")).to_have_count(1)
        self.expect(page.get_by_text("Outside marked spaces")).to_be_visible()
        self.expect(page.locator(".dashboard-space.occupied .dashboard-space-status")).to_have_text(
            "Occupied"
        )

        page.get_by_role("button", name="Historical trends").click()
        self.expect(page).to_have_url(re.compile(r"/history/lot1$"))
        self.expect(page.get_by_text("Observed occupancy by hour (UTC)")).to_be_visible()
        self.expect(page.locator(".history-hour")).to_have_count(24)
        self.expect(page.locator(".history-bar")).to_have_count(1)
        self.expect(page.locator(".history-record")).to_have_count(1)
        self.expect(page.locator(".history-record")).to_contain_text("Occupied")

        page.get_by_role("button", name=re.compile("All lots")).click()
        self.expect(page).to_have_url(re.compile(r"/$"))
        self.expect(cards.nth(0)).to_contain_text(
            f"{configured_one - 1} of {configured_one} open"
        )

        invalidate_camera_status("camera_1", self.live, self.lock)
        self.expect(cards.nth(0)).to_contain_text(
            "Current status unavailable", timeout=12000
        )
        self.expect(cards.nth(0)).to_contain_text("UNAVAILABLE")
        self.assertNotIn("FULL", cards.nth(0).inner_text())
        self.expect(cards.nth(1)).to_contain_text("FULL")

        # Confirm a real frontend detail page responds to FastAPI's 503,
        # then returns to a valid result when the source recovers.
        cards.nth(0).click()
        self.expect(page.get_by_role("alert")).to_contain_text(
            "Current parking status is unavailable", timeout=12000
        )
        self.restore_live_status()
        self.expect(page.locator(".dashboard-space")).to_have_count(
            configured_one, timeout=12000
        )
        self.expect(page.get_by_role("alert")).to_have_count(0)

        page.set_viewport_size({"width": 390, "height": 844})
        self.assertLessEqual(
            page.evaluate("document.documentElement.scrollWidth"),
            392,  # permit fractional pixel rounding on a narrow viewport
        )

    def test_record_observed_synthetic_backend_to_browser_update_times(self):
        """Actual measured intervals on controlled FastAPI fixture/Chromium.

        Timing starts immediately before publishing a synthetic server state
        and stops once Chromium visibly renders it. It includes polling,
        Vite proxy, FastAPI and React, but not YOLO, camera, or PostgreSQL.
        No numerical acceptance threshold is inferred from the SRS.
        """
        self.restore_live_status()
        page = self.browser.new_page(viewport={"width": 1200, "height": 800})
        self.addCleanup(page.close)
        page.goto(self.base_url, wait_until="domcontentloaded")
        cards = page.locator(".lot-card")
        total = len(self.cameras["camera_1"]["config"]["spaces"])
        self.expect(cards.nth(0)).to_contain_text(
            f"{total - 1} of {total} open", timeout=15000
        )

        observations = []

        def publish_fixture(open_all):
            with self.lock:
                current = self.live["camera_1"]
                current["spaces"] = [
                    {"id": item["id"], "open": open_all}
                    for item in self.cameras["camera_1"]["config"]["spaces"]
                ]
                current["in_space_vehicles"] = 0 if open_all else total
                current["outside_space_vehicles"] = 0
                current["cars"] = current["in_space_vehicles"]

        def measure(view, trial, open_all):
            # Python time.perf_counter_ns() uses the same local monotonic
            # clock before the mutation and after browser confirmation.
            # Thus no cross-machine/client clock synchronization is assumed.
            started_utc = datetime.now(timezone.utc).isoformat()
            start = time.perf_counter_ns()
            publish_fixture(open_all)
            if view == "home":
                expected = f"{total if open_all else 0} of {total} open"
                page.wait_for_function(
                    """expected => {
                        const el = document.querySelector(
                          '.lot-card .lot-card-count'
                        )
                        return el?.textContent?.trim() === expected
                    }""",
                    arg=expected, polling=25, timeout=15000,
                )
            else:
                expected_occupied = 0 if open_all else total
                page.wait_for_function(
                    """expected => {
                        const spaces = document.querySelectorAll(
                          '.dashboard-space'
                        )
                        const occupied = document.querySelectorAll(
                          '.dashboard-space.occupied'
                        )
                        return spaces.length === expected.total &&
                          occupied.length === expected.occupied
                    }""",
                    arg={"total": total, "occupied": expected_occupied},
                    polling=25, timeout=15000,
                )
            elapsed_ms = round((time.perf_counter_ns() - start) / 1_000_000, 3)
            observations.append({
                "surface": view,
                "trial": trial,
                "published_state": "AVAILABLE" if open_all else "OCCUPIED",
                "expected_visible_open_count": total if open_all else 0,
                "started_utc": started_utc,
                "observed_elapsed_ms": elapsed_ms,
            })

        # Repeat actual distinct state transitions to avoid accidentally
        # measuring an already rendered value.
        for i, open_all in enumerate((False, True, False), start=1):
            measure("home", i, open_all)

        cards.nth(0).click()
        self.expect(page).to_have_url(re.compile(r"/parking-lot1$"))
        self.expect(page.locator(".dashboard-space.occupied")).to_have_count(
            total, timeout=12000
        )
        for i, open_all in enumerate((True, False, True), start=1):
            measure("detail", i, open_all)

        report = {
            "schema_version": 1,
            "measurement_type": "synthetic_backend_state_to_browser_display",
            "git_sha": os.environ.get("GITHUB_SHA"),
            "github_run_id": os.environ.get("GITHUB_RUN_ID"),
            "observed_at_utc": datetime.now(timezone.utc).isoformat(),
            "environment": {
                "platform": platform.platform(),
                "python": platform.python_version(),
                "browser": "Chromium",
                "browser_version": self.browser.version,
                "frontend": "Vite development server with /api proxy",
                "backend": "Uvicorn/FastAPI with controlled in-memory fixtures",
                "configured_spaces_camera_1": total,
            },
            "description": (
                "Elapsed time from publishing a controlled synthetic live "
                "backend occupancy change to the matching React DOM render. "
                "Includes UI polling, Vite proxy and FastAPI delivery; excludes "
                "YOLO inference, camera acquisition and PostgreSQL transactions."
            ),
            "srs_performance_threshold_ms": None,
            "observations": observations,
            "summary_by_surface": {
                view: {
                    "samples": len(values),
                    "min_ms": min(values),
                    "median_ms": round(statistics.median(values), 3),
                    "max_ms": max(values),
                }
                for view in ("home", "detail")
                for values in [[
                    item["observed_elapsed_ms"] for item in observations
                    if item["surface"] == view
                ]]
            },
            "not_ground_truth_or_production_evidence": True,
        }
        print("CONTROLLED_UI_TIMING_JSON " + json.dumps(report, sort_keys=True))
        if os.getenv("UPDATE_TIMING_REPORT"):
            output = Path(os.environ["UPDATE_TIMING_REPORT"])
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(
                json.dumps(report, indent=2) + "\\n", encoding="utf-8"
            )

    def test_keyboard_primary_navigation_and_noncolor_status_cues(self):
        """Cover primary keyboard route and visible text; not full WCAG audit."""
        self.restore_live_status()
        page = self.browser.new_page(viewport={"width": 1200, "height": 800})
        self.addCleanup(page.close)
        page.goto(self.base_url, wait_until="domcontentloaded")
        cards = page.locator(".lot-card")
        self.expect(cards).to_have_count(3)
        self.expect(cards.nth(0)).to_contain_text("OPEN", timeout=15000)
        self.expect(cards.nth(1)).to_contain_text("FULL")
        self.expect(cards.nth(2)).to_contain_text("COMING SOON")
        self.expect(cards.nth(2)).to_be_disabled()

        # No pointer/mouse. Keyboard Tab reaches the monitored lot cards.
        page.keyboard.press("Tab")
        self.expect(cards.nth(0)).to_be_focused()
        self.assertTrue(cards.nth(0).evaluate(
            "(el) => parseFloat(getComputedStyle(el).outlineWidth) > 0"
        ), "The primary keyboard target must show visible focus")
        page.keyboard.press("Tab")
        self.expect(cards.nth(1)).to_be_focused()
        page.keyboard.press("Enter")
        self.expect(page).to_have_url(re.compile(r"/parking-lot2$"))

        statuses = page.locator(".dashboard-space-status")
        expected_spaces = len(self.cameras["camera_2"]["config"]["spaces"])
        self.expect(statuses).to_have_count(expected_spaces, timeout=12000)
        self.assertEqual(statuses.all_text_contents(), ["Occupied"] * expected_spaces)
        self.expect(page.get_by_text("Open now")).to_be_visible()
        self.expect(page.get_by_text("Occupied", exact=True).first).to_be_visible()

        # Test keyboard activation of the historical trends control.
        history_button = page.get_by_role("button", name="Historical trends")
        history_button.focus()
        self.expect(history_button).to_be_focused()
        page.keyboard.press("Enter")
        self.expect(page).to_have_url(re.compile(r"/history/lot2$"))
        self.expect(page.get_by_role(
            "heading", name="Observed occupancy by hour (UTC)"
        )).to_be_visible(timeout=12000)

        self.expect(page.get_by_text(
            "No data", exact=True
        )).to_have_count(23)
        self.expect(page.get_by_role(
            "group", name="Recorded occupancy shares by UTC hour"
        )).to_be_visible()
        select = page.get_by_role("combobox", name="Parking space")
        self.expect(select).to_be_visible()
        self.expect(select.locator("option")).to_have_count(expected_spaces)
        option_ids = select.locator("option").evaluate_all(
            "(options) => options.map(el => el.value)"
        )
        self.assertGreaterEqual(len(option_ids), 2)

        # Change a configured space using the keyboard-only select.
        select.focus()
        self.expect(select).to_be_focused()
        self.assertTrue(select.evaluate(
            "(el) => parseFloat(getComputedStyle(el).outlineWidth) > 0"
        ))
        page.keyboard.press("ArrowDown")
        self.expect(select).to_have_value(option_ids[1], timeout=12000)
        self.expect(page.locator(".history-record")).to_have_count(
            1, timeout=12000
        )
        self.assertTrue(
            any(
                state in page.locator(".history-record").inner_text()
                for state in ("Occupied", "Available")
            ),
            "History must convey the observed state as readable text",
        )

        # Return to the lot index via keyboard, without a pointer.
        back_button = page.get_by_role("button", name=re.compile("All lots"))
        back_button.focus()
        self.expect(back_button).to_be_focused()
        page.keyboard.press("Enter")
        self.expect(page).to_have_url(re.compile(r"/$"))
        self.expect(cards.nth(2)).to_be_disabled()

    def test_browser_does_not_invent_trends_during_storage_outage(self):
        # Test-only history provider raises like failed PostgreSQL; the
        # actual FastAPI error handler must return a sanitized HTTP 503.
        self.history.unavailable = True
        self.addCleanup(setattr, self.history, "unavailable", False)
        page = self.browser.new_page()
        self.addCleanup(page.close)
        page.goto(self.base_url + "/history/lot1", wait_until="domcontentloaded")
        self.expect(page.get_by_role("alert")).to_contain_text(
            "Historical records are unavailable", timeout=12000
        )
        self.expect(page.locator(".history-bar")).to_have_count(0)
        self.assertEqual(
            page.request.get(self.base_url + "/api/trends/lot1").status,
            503,
        )


if __name__ == "__main__":
    unittest.main()
