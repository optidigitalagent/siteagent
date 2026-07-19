from __future__ import annotations

import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class ProjectBrainContractTests(unittest.TestCase):
    def test_required_project_brain_files_exist(self) -> None:
        required = [
            "AGENTS.md",
            ".codex/project_brain/INDEX.md",
            ".codex/project_brain/VISION.md",
            ".codex/project_brain/QUALITY_BAR.md",
            ".codex/project_brain/HUMAN_FEEDBACK.md",
            ".codex/project_brain/DIRECTOR_PROTOCOL.md",
            ".codex/project_brain/REFERENCE_LIBRARY.md",
            ".agents/skills/siteagent-project-director/SKILL.md",
            ".agents/skills/siteagent-web-studio/SKILL.md",
            "references/site_designs/reference.schema.json",
        ]
        missing = [path for path in required if not (ROOT / path).is_file()]
        self.assertEqual([], missing)

    def test_root_contract_loads_director_and_current_builder(self) -> None:
        agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8-sig")
        self.assertIn("$siteagent-project-director", agents)
        self.assertIn("SITE_BUILDER=codex_studio", agents)
        self.assertNotIn("Uses a deterministic renderer", agents)

    def test_global_goal_does_not_describe_legacy_pipeline_as_current(self) -> None:
        goal = (ROOT / ".codex/workflow/GLOBAL_GOAL.md").read_text(encoding="utf-8-sig")
        normalized_goal = " ".join(goal.split())
        self.assertIn("Codex Creative Studio", normalized_goal)
        self.assertNotIn("deterministic build", normalized_goal)

    def test_reference_schema_is_valid_json(self) -> None:
        data = json.loads(
            (ROOT / "references/site_designs/reference.schema.json").read_text(encoding="utf-8")
        )
        self.assertEqual("object", data["type"])
        self.assertIn("learn", data["required"])
        self.assertIn("do_not_copy", data["required"])

    def test_functional_site_shell_is_a_durable_non_template_contract(self) -> None:
        quality = (ROOT / ".codex/project_brain/QUALITY_BAR.md").read_text(encoding="utf-8-sig")
        skill = (ROOT / ".agents/skills/siteagent-web-studio/SKILL.md").read_text(encoding="utf-8-sig")
        self.assertIn("Functional site shell", quality)
        self.assertIn("primary navigation remains available", quality)
        self.assertIn("semantic footer", skill)
        self.assertIn("not a visual template", skill)

    def test_preview_notification_is_separate_from_production_delivery(self) -> None:
        feedback = (ROOT / ".codex/project_brain/HUMAN_FEEDBACK.md").read_text(
            encoding="utf-8-sig"
        )
        director = (ROOT / ".agents/skills/siteagent-project-director/SKILL.md").read_text(
            encoding="utf-8-sig"
        )
        normalized_director = " ".join(director.split())
        self.assertIn("Telegram preview delivery contract", feedback)
        self.assertIn("at-most-once", feedback)
        self.assertIn("keep the job `preview_ready`", normalized_director)
        self.assertIn("never reuse production notifier", normalized_director)


if __name__ == "__main__":
    unittest.main()
