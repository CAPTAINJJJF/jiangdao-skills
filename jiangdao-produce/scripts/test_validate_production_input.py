#!/usr/bin/env python3

from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).with_name("validate-production-input.py")


def source(source_id: str, function: str = "问题与场景") -> dict:
    return {
        "id": source_id,
        "kind": "external_source",
        "full_text": True,
        "traceable": True,
        "relevant": True,
        "function": function,
    }


def user_original(valid: bool = True) -> dict:
    return {
        "present": valid,
        "concrete_start": valid,
        "confirmed_judgment": valid,
        "source_ref": "用户口述记录.md" if valid else "",
    }


def base(mode: str) -> dict:
    return {
        "schema_version": "production-input-gate-v1",
        "production_mode": mode,
        "topic_confirmed": True,
        "production_decision_confirmed": True,
        "high_fidelity_instruction_explicit": False,
        "target_source_id": None,
        "market_calibration_status": "available",
        "sources": [],
        "user_original_content": user_original(False),
    }


class ProductionInputValidatorTest(unittest.TestCase):
    def run_case(self, payload: dict) -> subprocess.CompletedProcess[str]:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "audit.json"
            path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
            return subprocess.run(
                ["python3", str(SCRIPT), str(path)],
                text=True,
                capture_output=True,
                check=False,
            )

    def test_high_fidelity_single_source_passes(self) -> None:
        payload = base("high_fidelity")
        payload["high_fidelity_instruction_explicit"] = True
        payload["target_source_id"] = "S001"
        payload["sources"] = [source("S001")]
        result = self.run_case(payload)
        self.assertEqual(result.returncode, 0, result.stdout)

    def test_high_fidelity_incomplete_source_fails(self) -> None:
        payload = base("high_fidelity")
        payload["high_fidelity_instruction_explicit"] = True
        payload["target_source_id"] = "S001"
        broken = source("S001")
        broken["full_text"] = False
        payload["sources"] = [broken]
        result = self.run_case(payload)
        self.assertIn("HIGH_FIDELITY_SOURCE_INCOMPLETE", result.stdout)

    def test_mixed_two_sources_pass(self) -> None:
        payload = base("mixed_creation")
        payload["sources"] = [source("S001", "问题与场景"), source("S002", "方法与边界")]
        result = self.run_case(payload)
        self.assertEqual(result.returncode, 0, result.stdout)

    def test_mixed_one_source_without_user_material_fails(self) -> None:
        payload = base("mixed_creation")
        payload["sources"] = [source("S001")]
        result = self.run_case(payload)
        self.assertIn("MIXED_INPUT_INSUFFICIENT", result.stdout)

    def test_mixed_one_source_plus_user_material_passes(self) -> None:
        payload = base("mixed_creation")
        payload["sources"] = [source("S001")]
        payload["user_original_content"] = user_original(True)
        result = self.run_case(payload)
        self.assertEqual(result.returncode, 0, result.stdout)

    def test_mixed_one_source_plus_confirmed_judgment_passes(self) -> None:
        payload = base("mixed_creation")
        payload["sources"] = [source("S001")]
        payload["user_original_content"] = {
            "present": True,
            "concrete_start": False,
            "confirmed_judgment": True,
            "source_ref": "用户确认观点.md",
        }
        result = self.run_case(payload)
        self.assertEqual(result.returncode, 0, result.stdout)

    def test_soul_creation_without_market_source_passes_with_status(self) -> None:
        payload = base("soul_creation")
        payload["market_calibration_status"] = "unavailable"
        payload["user_original_content"] = user_original(True)
        result = self.run_case(payload)
        self.assertEqual(result.returncode, 0, result.stdout)

    def test_soul_creation_without_confirmed_core_fails(self) -> None:
        payload = base("soul_creation")
        payload["market_calibration_status"] = "unavailable"
        result = self.run_case(payload)
        self.assertIn("SOUL_CORE_MISSING", result.stdout)


if __name__ == "__main__":
    unittest.main()
