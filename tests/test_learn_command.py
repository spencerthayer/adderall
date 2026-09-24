#!/usr/bin/env python3
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class LearnCommandTests(unittest.TestCase):
    def read(self, relative_path):
        return (ROOT / relative_path).read_text(encoding="utf-8")

    def test_host_commands_require_budget_and_create_proposals(self):
        for relative_path in (
            "commands/adderall-learn.toml",
            ".opencode/command/adderall-learn.md",
        ):
            with self.subTest(relative_path=relative_path):
                command = self.read(relative_path)
                self.assertIn("/adderall-learn", command)
                self.assertIn("budget", command.lower())
                self.assertIn("evolve.py", command)
                self.assertIn("proposal", command.lower())
                self.assertIn("do not overwrite", command.lower())

    def test_skill_routes_explicit_learning_without_hijacking_response_improvement(self):
        skill = self.read("skills/adderall/SKILL.md")
        self.assertIn("## Explicit learning trigger", skill)
        self.assertIn("/adderall-learn", skill)
        self.assertIn("improve this response", skill.lower())
        self.assertIn("budget", skill.lower())
        self.assertIn("proposal", skill.lower())

    def test_help_and_pi_expose_learning_command(self):
        help_card = self.read("skills/adderall-help/SKILL.md")
        pi_extension = self.read("pi-extension/index.js")
        self.assertIn("/adderall-learn", help_card)
        self.assertIn('registerCommand("adderall-learn"', pi_extension)
        self.assertIn("pi.sendUserMessage", pi_extension)


if __name__ == "__main__":
    unittest.main()
