from __future__ import annotations

import unittest

from site_agent.design_quality import audit_quality, build_context
from site_agent.models import ResearchBrief, SectionSpec, SiteSpec, StrategyBrief


FIXTURES = {
    "restaurant": ("Harbor Lunch", "restaurant", ["daily menu"], "Reserve a table"),
    "dental": ("North Dental", "dental clinic", ["consultations"], "Request an appointment"),
    "decorator": ("Atelier Moss", "decorator portfolio", ["interior projects"], "Discuss a project"),
    "school": ("Language Room", "online school", ["live classes"], "Ask about a course"),
    "sparse": ("Studio Onda", "independent studio", [], "Message on Instagram"),
}


def make_fixture(name: str):
    business, category, offers, cta = FIXTURES[name]
    research = ResearchBrief(instagram_url=f"https://www.instagram.com/{name}/", business_name=business, niche=category, sells=offers, contacts=["Instagram"], brand_atmosphere="quiet and tactile" if name != "sparse" else "", colors=["blue"] if name != "sparse" else [])
    strategy = StrategyBrief(target_customer="prospective customer", reason_to_choose=offers or ["a direct conversation"], customer_questions_or_fears=["What is the right next step?"], niche_specific_sections=["decision"], primary_cta=cta, secondary_cta="Learn what to ask", tone="clear", color_direction="contextual", typography_direction="distinctive", business_logic="clarify and convert")
    spec = SiteSpec(language="en", title=business, meta_description=f"{business}: {category}", h1=f"{business} — {category}", hero_subtitle=f"A clear next step for {category} visitors.", primary_cta=cta, secondary_cta="Learn what to ask", sections=[SectionSpec(id=f"{name}-decision", title="Choose your next step", purpose="Answer the key question before contact.", content=[f"Ask about {offers[0] if offers else 'the current details'}."])], trust_points=["Current information is confirmed directly."], process_steps=["Start the conversation."], footer_note="Use the approved contact path.", no_fake_claims_checklist=[])
    return research, strategy, spec


class DesignQualityFixtureTests(unittest.TestCase):
    def test_business_fixtures_have_distinct_journeys_and_fingerprints(self) -> None:
        patterns, fingerprints, ctas = set(), set(), set()
        for name in FIXTURES:
            research, strategy, spec = make_fixture(name)
            context = build_context(research, strategy, spec)
            report = audit_quality(spec, context, technical_passed=True)
            patterns.add(context.ux_architecture.pattern)
            fingerprints.add(report.fingerprint)
            ctas.add(spec.primary_cta)
            self.assertTrue(report.approved, name)
        self.assertGreaterEqual(len(patterns), 5)
        self.assertEqual(len(fingerprints), len(FIXTURES))
        self.assertEqual(len(ctas), len(FIXTURES))

    def test_technical_yacht_placeholder_is_blocked(self) -> None:
        research, strategy, spec = make_fixture("decorator")
        spec.h1 = "Welcome"
        spec.hero_subtitle = "High quality services with an individual approach."
        spec.sections = []
        report = audit_quality(spec, build_context(research, strategy, spec), technical_passed=True)
        self.assertFalse(report.approved)
        self.assertGreaterEqual(report.category_scores["technical"], report.floors["technical"])
        self.assertTrue(any("generic" in reason or "missing" in reason for reason in report.blocking_reasons))


if __name__ == "__main__":
    unittest.main()
