"""Read-only workstation preflight for UniParkingBuddy.

Run from the repository root:
    python -m backend.preflight
    python -m backend.preflight --check-db --require-gui

No inference, database migrations/writes, process startup, or raw-frame
exports occur. The optional database check never prints credentials.
"""

import argparse
from dataclasses import dataclass
from importlib import metadata
import os
from pathlib import Path
import shutil
import sys


ROOT = Path(__file__).resolve().parent.parent
SOURCES = {
    "camera_1": "footage/stockvidsample2.mp4",
    "camera_2": "footage/parkinglotfootage1_1.mp4",
}
PACKAGES = ("numpy", "ultralytics", "fastapi", "uvicorn", "psycopg")


@dataclass(frozen=True)
class Check:
    level: str
    topic: str
    message: str


def check_project_files(root, capture_factory=None):
    """Check committed assets, camera regions and readable first video frames."""
    from .parking_config import ParkingConfigError, load_config

    findings = []
    for relative in (
        "yolo26n.pt", "requirements.txt", "backend/schema.sql",
        "frontend/package.json", "frontend/package-lock.json",
    ):
        path = root / relative
        if not path.is_file() or path.stat().st_size == 0:
            findings.append(Check("FAIL", relative, "Required file missing or empty"))
        else:
            findings.append(Check("PASS", relative, "File present"))

    try:
        import cv2
    except ImportError:
        cv2 = None

    if capture_factory is None and cv2 is not None:
        capture_factory = cv2.VideoCapture

    for camera, relative in SOURCES.items():
        cfg = None
        config_file = root / "configs" / f"{camera}.json"
        try:
            cfg = load_config(config_file)
        except ParkingConfigError as exc:
            findings.append(Check("FAIL", camera + " configuration", str(exc)))
        else:
            count = len(cfg["spaces"])
            if count == 0:
                findings.append(Check(
                    "WARN", camera + " configuration",
                    "Valid configuration, but no spaces are outlined",
                ))
            else:
                findings.append(Check(
                    "PASS", camera + " configuration",
                    f"{count} persistent configured-space IDs",
                ))

        video = root / relative
        if not video.is_file() or video.stat().st_size == 0:
            findings.append(Check("FAIL", relative, "Input video missing or empty"))
            continue
        if capture_factory is None:
            findings.append(Check(
                "FAIL", relative,
                "Cannot decode input: install OpenCV and its Python dependencies",
            ))
            continue

        cap = None
        try:
            cap = capture_factory(str(video))
            if not cap.isOpened():
                raise ValueError("Video cannot be opened")
            ok, frame = cap.read()
            if not ok or frame is None or len(frame.shape) < 2:
                raise ValueError("First frame cannot be decoded")
            height, width = frame.shape[:2]
            if width <= 0 or height <= 0:
                raise ValueError("Invalid decoded frame dimensions")
            if cfg is not None:
                invalid_ids = [
                    str(space["id"]) for space in cfg["spaces"]
                    if any(
                        x >= width or y >= height
                        for x, y in space["points"]
                    )
                ]
                if invalid_ids:
                    raise ValueError(
                        "Configured polygon corners exceed the frame "
                        f"({width}x{height}) for space IDs: {', '.join(invalid_ids)}"
                    )
            findings.append(Check(
                "PASS", relative,
                f"First frame decoded ({width}x{height}); space bounds checked",
            ))
        except (OSError, ValueError, AttributeError, TypeError) as exc:
            findings.append(Check("FAIL", relative, str(exc)))
        finally:
            if cap is not None:
                cap.release()
    return findings


def check_dependencies(require_gui=False, check_node=True):
    findings = []
    if sys.version_info[:2] != (3, 11):
        findings.append(Check(
            "WARN", "Python version",
            f"{sys.version_info.major}.{sys.version_info.minor} detected; "
            "GitHub Actions tests Python 3.11",
        ))
    else:
        findings.append(Check("PASS", "Python version", "Python 3.11"))

    for name in PACKAGES:
        try:
            version = metadata.version(name)
        except metadata.PackageNotFoundError:
            findings.append(Check("FAIL", name, "Python package not installed"))
        else:
            findings.append(Check("PASS", name, f"Installed version {version}"))

    installed_cv = []
    for dist in ("opencv-python", "opencv-python-headless"):
        try:
            installed_cv.append(f"{dist} {metadata.version(dist)}")
        except metadata.PackageNotFoundError:
            pass
    if not installed_cv:
        findings.append(Check("FAIL", "OpenCV", "opencv-python is not installed"))
    else:
        findings.append(Check("PASS", "OpenCV", ", ".join(installed_cv)))

    if require_gui:
        try:
            import cv2
            info = cv2.getBuildInformation()
            gui_line = next(
                (line.strip() for line in info.splitlines()
                 if line.strip().startswith("GUI:")), "",
            )
            if not gui_line or gui_line.split(":", 1)[1].strip().upper() in (
                "NONE", "NO",
            ):
                findings.append(Check(
                    "FAIL", "OpenCV display",
                    "No graphical window backend; install opencv-python on "
                    "a graphical workstation and remove conflicting "
                    "opencv-python-headless if necessary",
                ))
            else:
                findings.append(Check("PASS", "OpenCV display", gui_line))
        except (ImportError, AttributeError):
            findings.append(Check(
                "FAIL", "OpenCV display", "OpenCV GUI support cannot be verified",
            ))
    if check_node:
        npm = shutil.which("npm")
        if npm is None:
            findings.append(Check(
                "FAIL", "npm", "Node/npm not found; React cannot be launched",
            ))
        else:
            findings.append(Check("PASS", "npm", "npm launcher found"))
    return findings


def check_database():
    """Opt-in, SELECT-only verification. Never print DSN or exception text."""
    dsn = os.getenv("DATABASE_URL")
    if not dsn:
        return [Check(
            "WARN", "PostgreSQL",
            "DATABASE_URL is unset; current status works but history is unavailable",
        )]
    try:
        import psycopg
        with psycopg.connect(dsn, connect_timeout=5) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT to_regclass('parking_lot'), "
                    "to_regclass('parking_space'), "
                    "to_regclass('parking_space_region'), "
                    "to_regclass('occupancy_record')"
                )
                present = cursor.fetchone()
        if not all(present):
            return [Check(
                "FAIL", "PostgreSQL",
                "Connected, but required tables are missing; apply backend/schema.sql",
            )]
    except Exception as exc:
        return [Check(
            "FAIL", "PostgreSQL",
            f"Read-only connection/schema check failed ({type(exc).__name__}); "
            "verify private DATABASE_URL and schema",
        )]
    return [Check("PASS", "PostgreSQL", "Connected; required tables exist (read-only)")]


def run_preflight(root=ROOT, *, dependencies=True, node=True,
                  database=False, require_gui=False, capture_factory=None):
    findings = []
    if dependencies:
        findings.extend(check_dependencies(
            require_gui=require_gui, check_node=node,
        ))
    findings.extend(check_project_files(Path(root), capture_factory))
    if database:
        findings.extend(check_database())
    elif os.getenv("DATABASE_URL"):
        findings.append(Check(
            "WARN", "PostgreSQL",
            "DATABASE_URL is set but connectivity was not tested "
            "(add --check-db)",
        ))
    else:
        findings.append(Check(
            "WARN", "PostgreSQL",
            "DATABASE_URL unset; run without history or configure the approved schema",
        ))
    return findings


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check-db", action="store_true",
        help="Opt in to read-only PostgreSQL connection and schema checks",
    )
    parser.add_argument(
        "--require-gui", action="store_true",
        help="Require graphical OpenCV support for the local demo windows",
    )
    parser.add_argument(
        "--skip-node", action="store_true",
        help="Skip npm existence check for backend-only/CI environments",
    )
    args = parser.parse_args(argv)

    findings = run_preflight(
        database=args.check_db, require_gui=args.require_gui,
        node=not args.skip_node,
    )
    for check in findings:
        print(f"[{check.level}] {check.topic}: {check.message}")
    failed = sum(check.level == "FAIL" for check in findings)
    print(f"Preflight: {failed} failed; "
          f"{sum(check.level == 'WARN' for check in findings)} warning(s)")
    if failed:
        print("Fix failed checks before starting the demonstration.")
    else:
        print("Required checks passed. This does not replace live GUI/camera "
              "or human acceptance testing.")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
