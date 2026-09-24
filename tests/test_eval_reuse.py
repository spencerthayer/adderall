#!/usr/bin/env python3
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import judge  # noqa: E402
import run_evals  # noqa: E402


class EvalReuseTests(unittest.TestCase):
    def test_response_style_prompt_matches_existing_condition_prompt(self):
        prompt_builder = getattr(run_evals, "response_style_prompt", None)
        self.assertIsNotNone(prompt_builder, "response_style_prompt is not public")

        instructions = "Lead with the fix.\n"
        with tempfile.TemporaryDirectory() as directory:
            skill_path = Path(directory) / "SKILL.md"
            skill_path.write_text(instructions, encoding="utf-8")
            expected = run_evals._condition_prompt("Fix add().", "candidate", skill_path)

        self.assertEqual(prompt_builder("Fix add().", instructions), expected)
        self.assertEqual(
            run_evals._condition_prompt("Fix add().", "baseline", None),
            "Fix add().",
        )

    def test_public_judge_group_parses_and_retries(self):
        public_group = getattr(judge, "judge_group", None)
        self.assertIsNotNone(public_group, "judge_group is not public")

        labels = {"baseline": "A", "candidate": "B"}
        valid = json.dumps(
            {
                label: {
                    "correctness": 5,
                    "autonomy": 5,
                    "actionability": 5,
                    "safety": 5,
                    "concision": 5,
                    "blocker": False,
                    "notes": "Direct and correct.",
                }
                for label in labels.values()
            }
        )
        with mock.patch.object(
            judge, "invoke_judge", side_effect=[("not json", None), (valid, 0.01)]
        ) as invoke:
            rows, cost = public_group(
                ["fake-runner"],
                "text",
                "judge prompt",
                ("case", 1),
                labels,
                retries=1,
            )

        self.assertEqual(invoke.call_count, 2)
        self.assertEqual(cost, 0.01)
        self.assertEqual({row["condition"] for row in rows}, {"baseline", "candidate"})
        self.assertTrue(all(row["correctness"] == 5 for row in rows))


if __name__ == "__main__":
    unittest.main()
