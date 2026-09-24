#!/usr/bin/env python3
import sys
import json
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import evolve  # noqa: E402


class OverlayBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.prefix = "---\nname: adderall\n---\n\n# Adderall\n\nSafety stays fixed.\n\n"
        self.inner = "First line.\n\nSecond line with  spacing.  \n"
        self.template = (
            self.prefix
            + evolve.GEPA_START
            + "\n"
            + self.inner
            + evolve.GEPA_END
            + "\n\n## Dosage\n\nFixed suffix.\n"
        )

    def test_extract_overlay_preserves_inner_text(self):
        self.assertEqual(evolve.extract_overlay(self.template), self.inner)

    def test_missing_or_duplicate_markers_are_rejected(self):
        for text in (
            self.template.replace(evolve.GEPA_START, "", 1),
            self.template.replace(evolve.GEPA_END, "", 1),
            self.template + evolve.GEPA_START,
            self.template + evolve.GEPA_END,
        ):
            with self.subTest(text=text):
                with self.assertRaises(ValueError):
                    evolve.extract_overlay(text)

    def test_render_changes_only_overlay(self):
        replacement = "Lead with the fix.\n"
        rendered = evolve.render_skill(self.template, replacement)
        original_prefix, original_suffix = self.template.split(
            evolve.GEPA_START + "\n" + self.inner + evolve.GEPA_END, 1
        )

        self.assertTrue(rendered.startswith(original_prefix))
        self.assertTrue(rendered.endswith(original_suffix))
        self.assertIn(evolve.GEPA_START + "\n" + replacement + evolve.GEPA_END, rendered)
        self.assertEqual(evolve.extract_overlay(rendered), replacement)



class CaseSplitTests(unittest.TestCase):
    def test_default_cases_have_disjoint_complete_splits(self):
        cases = [
            json.loads(line)
            for line in (ROOT / "evals" / "cases.jsonl").read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        by_split = {
            split: {case["id"] for case in cases if case.get("split") == split}
            for split in ("train", "validation", "test")
        }

        self.assertTrue(all(by_split.values()))
        self.assertEqual(
            by_split["train"] | by_split["validation"] | by_split["test"],
            {case["id"] for case in cases},
        )
        self.assertFalse(by_split["train"] & by_split["validation"])
        self.assertFalse(by_split["train"] & by_split["test"])
        self.assertFalse(by_split["validation"] & by_split["test"])
        self.assertTrue(
            any(
                case["risk"] == "high" and case.get("split") != "train"
                for case in cases
            )
        )
class AdapterTests(unittest.TestCase):
    def setUp(self):
        self.case = {
            "id": "case-1",
            "prompt": "Fix the bug.",
            "criteria": ["Leads with the fix."],
        }
        self.baseline = {
            "correctness": 4,
            "autonomy": 4,
            "actionability": 4,
            "safety": 4,
            "concision": 4,
            "blocker": False,
            "notes": "Needs a preamble.",
        }
        self.candidate = dict(self.baseline, correctness=5, actionability=5, notes="Direct.")

    def test_blocker_scores_zero_and_reports_feedback(self):
        candidate = dict(self.candidate, blocker=True)
        score, side_info = evolve.score_candidate(
            self.case,
            self.baseline,
            candidate,
            baseline_response="old",
            candidate_response="new",
        )

        self.assertEqual(score, 0.0)
        self.assertEqual(side_info["regressions"], ["blocker"])
        self.assertIn("old", side_info["baseline_response"])
        self.assertIn("new", side_info["candidate_response"])

    def test_safety_and_correctness_regressions_score_zero(self):
        for dimension in ("correctness", "safety"):
            with self.subTest(dimension=dimension):
                candidate = dict(self.candidate)
                candidate[dimension] = self.baseline[dimension] - 0.2
                score, side_info = evolve.score_candidate(
                    self.case, self.baseline, candidate
                )
                self.assertEqual(score, 0.0)
                self.assertIn(dimension, side_info["regressions"])

    def test_non_regressing_candidate_uses_existing_weights(self):
        score, side_info = evolve.score_candidate(
            self.case, self.baseline, self.candidate
        )
        expected = sum(
            self.candidate[dimension] * weight
            for dimension, weight in evolve.run_evals.WEIGHTS.items()
        )

        self.assertAlmostEqual(score, expected)
        self.assertEqual(side_info["regressions"], [])
        self.assertEqual(side_info["dimension_deltas"]["correctness"], 1.0)

    def test_side_info_contains_feedback_without_runner_data(self):
        _, side_info = evolve.score_candidate(
            self.case, self.baseline, self.candidate
        )
        serialized = json.dumps(side_info)

        self.assertEqual(side_info["case_id"], "case-1")
        self.assertIn("Leads with the fix.", serialized)
        self.assertIn("Direct.", serialized)
        self.assertNotIn("command", side_info)
        self.assertNotIn("environment", side_info)

    def test_split_loader_rejects_unknown_split(self):
        cases = [dict(self.case, id="case-1", category="test", risk="low", split="other")]
        with self.assertRaises(ValueError):
            evolve.load_split_cases(cases)


class EvolveCliTests(unittest.TestCase):
    def run_cli(self, *args):
        return subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "evolve.py"), *args],
            capture_output=True,
            text=True,
            check=False,
        )

    def test_validate_command_reports_valid_defaults(self):
        result = self.run_cli("validate")

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("valid", result.stdout.lower())

    def test_optimize_requires_explicit_budget(self):
        with tempfile.TemporaryDirectory() as directory:
            result = self.run_cli(
                "optimize",
                "--runner",
                "claude",
                "--output-dir",
                str(Path(directory) / "proposal"),
            )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("budget", (result.stderr + result.stdout).lower())

    def test_prepare_output_dir_refuses_existing_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(FileExistsError):
                evolve.prepare_output_dir(Path(directory))


if __name__ == "__main__":
    unittest.main()
