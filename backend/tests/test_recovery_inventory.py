"""Guard against accidental loss of baseline project evidence.

This is an existence check, not a security boundary: branch protection and
review remain necessary to prevent someone from removing the check itself.
This inventory may be intentionally revised only by a reviewed change.
"""

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[2]

REQUIRED_DOCUMENTS = (
    "README.md",
    "backend/DATABASE_SETUP.md",
    "configs/README.md",
    "docs/ACCEPTANCE_TEST_RECORD.md",
    "docs/ACCESSIBILITY_REVIEW.md",
    "docs/ACCURACY_EVALUATION.md",
    "docs/API_CONTRACT.md",
    "docs/EXPERIMENT_AUTOMATIC_DISCOVERY.md",
    "docs/EXPERIMENT_ROW_CONTINUITY.md",
    "docs/EXPERIMENT_STALL_DISCOVERY_BENCHMARK.md",
    "docs/EXPERIMENT_STALL_GEOMETRY.md",
    "docs/EXPERIMENT_STALL_QUALITY_REVIEW.md",
    "docs/FASTAPI_MIGRATION.md",
    "docs/HISTORY.md",
    "docs/PARKING_SPACE_CALIBRATION.md",
    "docs/RESEARCH_ADAPTIVE_SPACE_DISCOVERY.md",
    "docs/VALIDATION.md",
    "docs/WORKSTATION_DEMO.md",
    "docs/RECOVERY_AUDIT_2026-11-10.md",
    "frontend/README.md",
)

REQUIRED_TEST_MODULES = (
    "test_accuracy_bundle_smoke.py",
    "test_accuracy_evaluation.py",
    "test_browser_react_fastapi.py",
    "test_calibrate_spaces.py",
    "test_configured_lots_api.py",
    "test_cv_db_api_integration.py",
    "test_discover_space_hypotheses.py",
    "test_discover_stall_geometry.py",
    "test_discovery_real_video_smoke.py",
    "test_ground_paint_evidence.py",
    "test_history_api.py",
    "test_media_smoke.py",
    "test_occupancy_contract.py",
    "test_occupancy_repository.py",
    "test_occupancy_writer.py",
    "test_parking_config.py",
    "test_preflight.py",
    "test_real_video_db_api.py",
    "test_real_yolo_inference.py",
    "test_review_stall_candidates.py",
    "test_review_stalls_real_video_smoke.py",
    "test_row_continuity_experiment.py",
    "test_row_continuity_real_video_smoke.py",
    "test_space_matching.py",
    "test_stall_discovery_benchmark.py",
    "test_stall_discovery_benchmark_real_video_smoke.py",
    "test_stall_geometry_real_video_smoke.py",
    "test_status_api.py",
    "test_status_publisher.py",
    "test_yolo_detection.py",
    "test_three_camera_recovery.py",
    "test_recovery_inventory.py",
)


class RecoveryInventoryTests(unittest.TestCase):
    def test_critical_documents_have_not_disappeared(self):
        for filename in REQUIRED_DOCUMENTS:
            with self.subTest(path=filename):
                path = ROOT / filename
                self.assertTrue(path.is_file(), f"Missing project evidence: {filename}")
                self.assertGreater(path.stat().st_size, 0, f"Empty project evidence: {filename}")

    def test_restored_tests_and_new_regressions_are_still_present(self):
        for name in REQUIRED_TEST_MODULES:
            with self.subTest(test=name):
                path = ROOT / "backend" / "tests" / name
                self.assertTrue(path.is_file(), f"Missing regression test: {name}")
                self.assertGreater(path.stat().st_size, 0)

    def test_root_ignore_rules_and_all_three_sources_remain_available(self):
        required = (
            ".gitignore",
            "configs/camera_1.json",
            "configs/camera_2.json",
            "configs/camera_3.json",
            "footage/stockvidsample2.mp4",
            "footage/parkinglotfootage1_1.mp4",
            "footage/parkinglot3.mp4",
            "backend/schema.sql",
            ".github/workflows/ci.yml",
        )
        for filename in required:
            with self.subTest(path=filename):
                self.assertTrue((ROOT / filename).is_file(), f"Missing: {filename}")


if __name__ == "__main__":
    unittest.main()
