"""Space-first manual calibration on a paused frame of an existing test video.

This tool does not run YOLO, infer parking lines, or write application history.
Changes remain in memory until the operator presses S to save. The original
configuration is backed up under the git-ignored evaluation_runs/ directory.
"""

import argparse
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
import shutil
import sys

import cv2
import numpy as np

from .accuracy_evaluation import CAMERA_VIDEOS, PROJECT_ROOT
from .parking_config import (
    ParkingConfigError, add_space, load_config, remove_space, save_config,
)


def display_to_source(x, y, source_width, source_height, display_width, display_height):
    """Convert a click on the resized preview into original-video coordinates."""
    if not (0 <= x < display_width and 0 <= y < display_height):
        raise ValueError("Click is outside the video preview")
    return [
        min(source_width - 1, max(0, round(x * source_width / display_width))),
        min(source_height - 1, max(0, round(y * source_height / display_height))),
    ]


def source_to_display(point, source_width, source_height, display_width, display_height):
    return (
        round(point[0] * display_width / source_width),
        round(point[1] * display_height / source_height),
    )


class CalibrationSession:
    """Edit a copy of the config so an accidental exit cannot corrupt it."""

    def __init__(self, config_path, source_width, source_height, display_width):
        self.config_path = Path(config_path)
        self.config = deepcopy(load_config(self.config_path))
        self.original = deepcopy(self.config)
        self.source_width = source_width
        self.source_height = source_height
        self.display_width = display_width
        self.display_height = max(1, round(source_height * display_width / source_width))
        self.pending = []
        self.message = "Left-click FOUR corners around one physical parking stall."
    
    @property
    def dirty(self):
        return self.config != self.original

    def to_source(self, x, y):
        return display_to_source(
            x, y, self.source_width, self.source_height,
            self.display_width, self.display_height,
        )

    def add_corner(self, x, y):
        point = self.to_source(x, y)
        self.pending.append(point)
        if len(self.pending) < 4:
            self.message = f"Corner {len(self.pending)}/4 set; continue around the stall."
            return
        corners = self.pending
        self.pending = []
        try:
            candidate = add_space(self.config, corners)
        except ParkingConfigError as error:
            self.message = f"Invalid stall: {error}"
            return
        self.config = candidate
        self.message = f"Added space {self.config['next_space_id'] - 1} (not yet saved)."

    def remove_at(self, x, y):
        point = self.to_source(x, y)
        for space in reversed(self.config["spaces"]):
            contour = np.asarray(space["points"], dtype=np.int32).reshape((-1, 1, 2))
            if cv2.pointPolygonTest(contour, tuple(map(float, point)), False) >= 0:
                self.config = remove_space(self.config, space["id"])
                self.pending = []
                self.message = f"Removed space {space['id']} (not yet saved)."
                return
        self.message = "No configured space at this point."

    def undo_corner(self):
        if self.pending:
            self.pending.pop()
            self.message = f"Pending corners: {len(self.pending)}/4."
        else:
            self.message = "No unfinished corner to undo. Press Q to discard unsaved edits."

    def save(self, root=PROJECT_ROOT):
        if self.pending:
            raise ValueError("Finish or undo pending corners before saving")
        if not self.dirty:
            self.message = "No changes to save."
            return None
        backup_dir = Path(root) / "evaluation_runs" / "calibration_backups"
        backup_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        backup = backup_dir / f"{self.config_path.stem}_{stamp}.json"
        shutil.copy2(self.config_path, backup)
        save_config(self.config_path, self.config)
        self.original = deepcopy(self.config)
        self.message = f"Saved {len(self.config['spaces'])} spaces. Backup: {backup}"
        return backup


def draw_preview(frame, session, frame_index):
    width = session.display_width
    height = session.display_height
    resized = cv2.resize(frame, (width, height))
    canvas = np.zeros((height + 90, width, 3), dtype=np.uint8)
    canvas[:height] = resized
    for space in session.config["spaces"]:
        pts = np.array([
            source_to_display(p, session.source_width, session.source_height, width, height)
            for p in space["points"]
        ], dtype=np.int32).reshape((-1, 1, 2))
        cv2.polylines(canvas, [pts], True, (0, 225, 80), 2)
        centroid = np.mean(pts[:, 0], axis=0).astype(int)
        cv2.putText(
            canvas, str(space["id"]), tuple(centroid),
            cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2,
        )
    scaled = [
        source_to_display(p, session.source_width, session.source_height, width, height)
        for p in session.pending
    ]
    for point in scaled:
        cv2.circle(canvas, point, 5, (0, 225, 255), -1)
    if len(scaled) > 1:
        cv2.polylines(canvas, [np.array(scaled, dtype=np.int32)], False, (0, 225, 255), 2)

    instructions = [
        f"Frame {frame_index} | Configured spaces: {len(session.config['spaces'])} | Unsaved: {session.dirty}",
        "LEFT: add 4 corners in order | RIGHT: remove space | U: undo corner | S: save | Q: exit",
        session.message[:min(145, max(15, width // 8))],
    ]
    for i, line in enumerate(instructions):
        cv2.putText(
            canvas, line, (10, height + 23 + 27 * i),
            cv2.FONT_HERSHEY_SIMPLEX, 0.53, (230, 230, 230), 1,
        )
    return canvas


def read_frame(video_path, frame_index):
    capture = cv2.VideoCapture(str(video_path))
    try:
        if not capture.isOpened():
            raise ValueError(f"Cannot open video: {video_path}")
        if not capture.set(cv2.CAP_PROP_POS_FRAMES, frame_index):
            raise ValueError(f"Cannot seek to frame {frame_index} of {video_path}")
        success, frame = capture.read()
        if not success or frame is None:
            raise ValueError(f"Cannot read frame {frame_index} of {video_path}")
        return frame
    finally:
        capture.release()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--camera", required=True, choices=sorted(CAMERA_VIDEOS))
    parser.add_argument("--frame", type=int, default=0, help="Paused source-video frame index")
    parser.add_argument("--width", type=int, default=1280, help="Display width in pixels")
    args = parser.parse_args(argv)
    if args.frame < 0 or not 320 <= args.width <= 1920:
        parser.error("--frame must be nonnegative and --width must be 320..1920")

    video_path = PROJECT_ROOT / CAMERA_VIDEOS[args.camera]
    config_path = PROJECT_ROOT / "configs" / f"{args.camera}.json"
    try:
        frame = read_frame(video_path, args.frame)
        source_height, source_width = frame.shape[:2]
        session = CalibrationSession(config_path, source_width, source_height, args.width)
    except (OSError, ValueError) as error:
        print(f"Calibration unavailable: {error}", file=sys.stderr)
        return 1

    window = f"Calibrate {args.camera} | frame {args.frame}"
    print("Click four corners of each stall in perimeter order. Existing IDs are preserved.")
    print("Nothing is saved unless you press S. Q discards unsaved changes.")
    try:
        cv2.namedWindow(window, cv2.WINDOW_AUTOSIZE)

        def on_mouse(event, x, y, _flags, _param):
            if y >= session.display_height:
                return
            try:
                if event == cv2.EVENT_LBUTTONDOWN:
                    session.add_corner(x, y)
                elif event == cv2.EVENT_RBUTTONDOWN:
                    session.remove_at(x, y)
            except (ValueError, ParkingConfigError) as error:
                session.message = str(error)

        cv2.setMouseCallback(window, on_mouse)
        while True:
            cv2.imshow(window, draw_preview(frame, session, args.frame))
            key = cv2.waitKey(40) & 0xFF
            if key in (ord("q"), 27):
                if session.dirty:
                    print("Discarded unsaved configuration edits.")
                break
            if key == ord("u"):
                session.undo_corner()
            if key == ord("s"):
                try:
                    backup = session.save()
                    print(session.message)
                    if backup:
                        print(f"Previous config preserved at {backup}")
                except (ValueError, OSError, ParkingConfigError) as error:
                    session.message = f"Save failed: {error}"
                    print(session.message, file=sys.stderr)
    finally:
        cv2.destroyWindow(window)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
