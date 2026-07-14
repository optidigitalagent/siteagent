from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from site_agent.builder import SiteBuilder
from site_agent.models import ResearchBrief, SiteSpec, StrategyBrief
from site_agent.orchestrator import SiteAgentOrchestrator


class SparseContactBridgeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.research = ResearchBrief(
            instagram_url="https://www.instagram.com/example_handle?igsh=abc",
            business_name="Example (inferred from Instagram handle)",
            niche="Unknown service (inferred from handle only)",
            city="Unknown",
            country="Unknown",
            unknowns=["Services and contact details are unknown."],
        )
        self.spec = SiteSpec(
            language="ru",
            title="placeholder",
            meta_description="placeholder",
            h1="placeholder",
            hero_subtitle="placeholder",
            primary_cta="placeholder",
            secondary_cta="placeholder",
            sections=[],
            trust_points=[],
            process_steps=[],
            footer_note="placeholder",
            no_fake_claims_checklist=[],
        )

    def test_sparse_research_becomes_neutral_instagram_contact_bridge(self) -> None:
        orchestrator = SiteAgentOrchestrator.__new__(SiteAgentOrchestrator)
        result = orchestrator._normalize_sparse_instagram_spec(self.research, self.spec)

        self.assertEqual(result.language, "uk")
        self.assertIn("Direct", result.h1)
        self.assertIn("@example_handle", result.hero_subtitle)
        self.assertNotIn("?igsh", result.hero_subtitle)
        self.assertEqual(result.gallery_assets, [])
        self.assertTrue(all("Unknown" not in line for line in result.contact_lines))

    def test_renderer_uses_clean_handle_and_customer_facing_profile_note(self) -> None:
        orchestrator = SiteAgentOrchestrator.__new__(SiteAgentOrchestrator)
        spec = orchestrator._normalize_sparse_instagram_spec(self.research, self.spec)
        strategy = StrategyBrief(
            target_customer="Instagram visitor",
            reason_to_choose=[],
            customer_questions_or_fears=[],
            niche_specific_sections=[],
            primary_cta="Open Instagram",
            secondary_cta="What to send in Direct",
            tone="neutral",
            color_direction="neutral",
            typography_direction="clear",
            business_logic="Direct contact",
        )
        with TemporaryDirectory() as temp_dir:
            index_path = SiteBuilder().build(
                site_dir=Path(temp_dir), research=self.research, strategy=strategy, spec=spec
            )
            html = index_path.read_text(encoding="utf-8")

        self.assertIn("@example_handle</p>", html)
        self.assertNotIn("@example_handle?igsh", html)
        self.assertIn("Instagram", html)
        self.assertIn("Direct", html)
        self.assertNotIn("unverified photos as work samples", html)


if __name__ == "__main__":
    unittest.main()
