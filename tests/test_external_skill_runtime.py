from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from site_agent.design_quality import audit_quality, build_context
from site_agent.external_skills import LocalSkillRuntime, project_root
from site_agent.fixture_e2e import fixture_data, run_all


class ExternalSkillRuntimeTests(unittest.TestCase):
    def test_project_skill_discovery_never_resolves_sibling_directory(self) -> None:
        root = project_root()
        self.assertEqual(root, Path.cwd().resolve())
        self.assertTrue((root / ".agents" / "skills" / "frontend-design" / "SKILL.md").is_file())
        self.assertFalse((root.parent / f"{root.name}.agents" / "skills").exists())

    def test_pinned_search_and_guidelines_are_actually_executed(self) -> None:
        research, strategy, spec = fixture_data()["restaurant"]
        runtime = LocalSkillRuntime()
        frontend = runtime.frontend_design_brief(category=research.niche, audience=strategy.target_customer, goal=strategy.business_logic, atmosphere=research.brand_atmosphere)
        system = runtime.design_system(category=research.niche, audience=strategy.target_customer, offer=" ".join(research.sells), atmosphere=research.brand_atmosphere, project_name=research.business_name)
        self.assertIn("Frontend Design", frontend.output["prompt_guidance"])
        self.assertIn("restaurant", system.input["query"])
        self.assertTrue(system.output["design_system"])
        with tempfile.TemporaryDirectory() as temp:
            index = Path(temp) / "index.html"
            index.write_text("<html><head></head><body><main></main></body></html>", encoding="utf-8")
            guideline = runtime.web_guidelines(index)
        self.assertTrue(any(item["selector"] == "head meta[name=viewport]" for item in guideline.output["findings"]))

    def test_category_floor_and_high_issue_cannot_be_compensated(self) -> None:
        research, strategy, spec = fixture_data()["restaurant"]
        context = build_context(research, strategy, spec)
        for category in ("business", "story", "accessibility", "anti_template"):
            report = audit_quality(spec, context, technical_passed=True, category_score_overrides={category: 40})
            self.assertFalse(report.approved, category)
        report = audit_quality(spec, context, technical_passed=True, guideline_findings=[{"file":"site/index.html", "selector":"main", "severity":"high", "message":"controlled high issue"}])
        self.assertFalse(report.approved)

    def test_fixture_resume_reuses_completed_run_and_level_c_skips_builder(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "runs"
            first = run_all(root)
            index = root / "restaurant" / "site" / "index.html"
            stamp = index.stat().st_mtime_ns
            second = run_all(root, clean=False)
            self.assertEqual(stamp, index.stat().st_mtime_ns)
            self.assertEqual(first["runs"]["restaurant"]["fingerprint"], second["runs"]["restaurant"]["fingerprint"])
            self.assertFalse(second["runs"]["level_c"]["builder_started"])


if __name__ == "__main__":
    unittest.main()
