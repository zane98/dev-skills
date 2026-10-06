#!/usr/bin/env python3
"""Regression checks for skill suite validation, with isolated fixtures."""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import validate_skill_suite as suite


class SuiteValidationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.skill = self.root / "demo"
        (self.skill / "references").mkdir(parents=True)
        (self.skill / "SKILL.md").write_text("---\nname: demo\ndescription: Demonstrate a scoped workflow.\n---\n[Guide](references/guide.md)\n")
        (self.skill / "references/guide.md").write_text("A guide.\n")

    def check_cases(self, cases, names=None):
        path = self.root / "cases.json"
        path.write_text(json.dumps(cases))
        errors = []
        suite.validate_cases(path, names or {"demo"}, errors)
        return errors

    def test_valid_case_with_behavior_constraints(self):
        self.assertEqual([], self.check_cases([{"id": "ok", "prompt": "Review this.", "expected_skills": ["demo"], "required_decisions": ["scoped-review"], "forbidden_actions": ["write"]}]))

    def test_invalid_lists_and_ids_return_errors(self):
        for patch in [{"id": []}, {"expected_skills": "demo"}, {"required_decisions": [1]}, {"forbidden_actions": {}}, {"expected_skills": []}]:
            with self.subTest(patch=patch):
                case = {"id": "case", "prompt": "Review.", "expected_skills": ["demo"], **patch}
                self.assertTrue(self.check_cases([case]))

    def test_contradictory_actions_and_skills_are_rejected(self):
        for patch in [{"forbidden_skills": ["demo"]}, {"required_actions": ["write"], "forbidden_actions": ["write"]}]:
            with self.subTest(patch=patch):
                self.assertTrue(self.check_cases([{"id": "case", "prompt": "Review.", "expected_skills": ["demo"], **patch}]))

    def test_duplicate_cases_and_values_are_rejected(self):
        case = {"id": "same", "prompt": "Review.", "expected_skills": ["demo"]}
        self.assertTrue(self.check_cases([case, case]))
        self.assertTrue(self.check_cases([{**case, "required_decisions": ["a", "a"]}]))

    def test_unknown_skill_requires_supplied_catalog(self):
        case = [{"id": "peer", "prompt": "Review.", "expected_skills": ["peer"]}]
        self.assertTrue(self.check_cases(case))
        self.assertEqual([], self.check_cases(case, {"demo", "peer"}))

    def test_nested_reference_links_are_checked(self):
        guide = self.skill / "references/guide.md"
        guide.write_text("[Missing](missing.md)\n")
        errors = []
        suite.validate_skill(self.skill / "SKILL.md", errors)
        self.assertTrue(any("missing.md" in error for error in errors))
        (guide.parent / "missing.md").write_text("Available.\n")
        errors = []
        suite.validate_skill(self.skill / "SKILL.md", errors)
        self.assertEqual([], errors)

    def test_metadata_and_http_anchor_links(self):
        (self.skill / "references/guide.md").write_text("[Web](https://example.com) [Local](#heading)\n")
        (self.skill / "agents").mkdir()
        (self.skill / "agents/openai.yaml").write_text('interface:\n  default_prompt: "Use $wrong."\n')
        errors = []
        suite.validate_skill(self.skill / "SKILL.md", errors)
        self.assertEqual(1, len(errors))
        self.assertIn("default_prompt", errors[0])


if __name__ == "__main__":
    unittest.main()
