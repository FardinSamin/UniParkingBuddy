"""Real Chromium + Vite + FastAPI read-only interface smoke tests.

Uses the production FastAPI route handlers and actual React components with
controlled *synthetic* occupancy fixtures. The real YOLO/PostgreSQL pipeline
is tested in test_real_video_db_api.py; this test does not assert CV accuracy.
No physical camera, raw video or public write endpoint is involved.
"""

from datetime import datetime, timezone
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

    def lot_spaces(self, lot_id):
        for camera, (configured_lot, _) in CAMERA_LOTS.items():
            if lot_id == configured_lot:
                return [
                    str(space["id"])
                    for space in self.camera_captures[camera]["config"]["spaces"]
                ]
        return None

    def hourly_occupancy_trends(self, lot_id, days):
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
        from playwright.sync_api import sync_playwright
        import uvicorn

        cls.cameras = {
            camera: {"config": load_config(ROOT / "configs" / f"{camera}.json")}
            for camera in CAMERA_LOTS
        }
        cls.lock = threading.Lock()
        cls.live = {}
        cls.restore_live_status()
        app = create_status_app(
            cls.cameras, cls.live, cls.lock,
            ReadOnlyHistoryFixture(cls.cameras),
        )

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
        cls.expect = staticmethod(__import__(
            "playwright.sync_api", fromlist=["expect"]
        ).expect)

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
        self.expect(cards.nth(0)).to_contain_text("6 of 7 open", timeout=15000)
        self.expect(cards.nth(1)).to_contain_text("0 of 4 open")
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
        self.expect(page.locator(".dashboard-space")).to_have_count(7)
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
        self.expect(cards.nth(0)).to_contain_text("6 of 7 open")

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
            7, timeout=12000
        )
        self.expect(page.get_by_role("alert")).to_have_count(0)

        page.set_viewport_size({"width": 390, "height": 844})
        self.assertLessEqual(
            page.evaluate("document.documentElement.scrollWidth"),
            392,  # permit fractional pixel rounding on a narrow viewport
        )

    def test_history_without_database_does_not_invent_trends(self):
        # The production router must return 503 when persistence is
        # unconfigured, and React must show an error instead of 0%.
        from backend.status_api import create_status_app
        from fastapi.testclient import TestClient

        app = create_status_app(self.cameras, self.live, self.lock, None)
        client = TestClient(app)
        self.assertEqual(client.get("/api/trends/lot1").status_code, 503)
        self.assertEqual(client.get("/api/history/lot1/1").status_code, 503)


if __name__ == "__main__":
    unittest.main()
