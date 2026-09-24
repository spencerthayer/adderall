#!/usr/bin/env python3
import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "fixtures"


class EvolveEndToEndTests(unittest.TestCase):
    def run_command(self, *args):
        return subprocess.run(
            [sys.executable, *args],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )

    def test_real_gepa_emits_bounded_proposal_and_passes_gate(self):
        cases = FIXTURES / "gepa-cases.jsonl"
        runner_template = json.loads((FIXTURES / "gepa-runners.json").read_text(encoding="utf-8"))
        source = ROOT / "skills" / "adderall" / "SKILL.md"
        source_hash = hashlib.sha256(source.read_bytes()).hexdigest()

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            runner_config = root / "runners.json"
            config = {}
            for name, runner in runner_template.items():
                config[name] = {
                    **runner,
                    "command": [sys.executable, str(FIXTURES / "fake_model.py"), name],
                }
            runner_config.write_text(json.dumps(config), encoding="utf-8")
            output_dir = root / "proposal"

            optimize = self.run_command(
                str(ROOT / "scripts" / "evolve.py"),
                "optimize",
                "--cases",
                str(cases),
                "--rubric",
                str(ROOT / "evals" / "rubric.md"),
                "--runner-config",
                str(runner_config),
                "--runner",
                "task",
                "--judge-runner",
                "judge",
                "--reflection-runner",
                "reflection",
                "--output-dir",
                str(output_dir),
                "--max-metric-calls",
                "4",
                "--budget-usd",
                "1",
                "--allow-unmetered",
            )
            self.assertEqual(optimize.returncode, 0, optimize.stderr)
            self.assertTrue((output_dir / "SKILL.md").is_file())
            self.assertEqual(hashlib.sha256(source.read_bytes()).hexdigest(), source_hash)

            proposal = (output_dir / "SKILL.md").read_text(encoding="utf-8")
            self.assertIn("Lead with the fix.", proposal)
            self.assertNotEqual(proposal, source.read_text(encoding="utf-8"))

            manifest = json.loads((output_dir / "manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["gepa_version"], "0.1.4")
            self.assertEqual(manifest["source_sha256"], source_hash)
            self.assertNotIn("api_key", json.dumps(manifest).lower())
            next_commands = json.loads(
                (output_dir / "next-commands.json").read_text(encoding="utf-8")
            )
            self.assertTrue(all("--cases" in command for command in next_commands[:3]))
            self.assertIn("--rubric", next_commands[2])
            for name in ("optimization-responses.jsonl", "optimization-feedback.jsonl"):
                rows = [
                    json.loads(line)
                    for line in (output_dir / name).read_text(encoding="utf-8").splitlines()
                    if line.strip()
                ]
                self.assertTrue(rows)

            responses = root / "responses.jsonl"
            scores = root / "scores.jsonl"
            common = [
                "--cases",
                str(cases),
                "--runner-config",
                str(runner_config),
                "--runner",
                "task",
                "--trials",
                "1",
                "--budget-usd",
                "1",
                "--allow-unmetered",
                "--output",
                str(responses),
            ]
            baseline = self.run_command(
                str(ROOT / "scripts" / "run_evals.py"), "run", "--condition", "baseline", *common
            )
            candidate = self.run_command(
                str(ROOT / "scripts" / "run_evals.py"),
                "run",
                "--condition",
                "candidate",
                "--condition-skill",
                str(output_dir / "SKILL.md"),
                *common,
            )
            judged = self.run_command(
                str(ROOT / "scripts" / "judge.py"),
                "--cases",
                str(cases),
                "--runner-config",
                str(runner_config),
                "--runner",
                "judge",
                "--responses",
                str(responses),
                "--output",
                str(scores),
            )
            self.assertEqual(baseline.returncode, 0, baseline.stderr)
            self.assertEqual(candidate.returncode, 0, candidate.stderr)
            self.assertEqual(judged.returncode, 0, judged.stderr)

            scored = self.run_command(str(ROOT / "scripts" / "run_evals.py"), "score", str(scores))
            self.assertEqual(scored.returncode, 0, scored.stderr)
            summary = json.loads(scored.stdout)
            self.assertTrue(summary["release_gate"]["passed"], scored.stdout)


if __name__ == "__main__":
    unittest.main()
