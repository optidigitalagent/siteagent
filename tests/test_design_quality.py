from __future__ import annotations

import unittest
from pathlib import Path

from site_agent.design_quality import (
    EvidenceLevel,
    assess_evidence,
    audit_quality,
    build_context,
    validate_skill_lock,
)
from site_agent.models import ContentTheme, MediaAsset, ProductIdentity, ResearchBrief, SectionSpec, SiteSpec, StrategyBrief


def complete_research(**changes) -> ResearchBrief:
    values = dict(
        instagram_url="https://www.instagram.com/example/",
        business_name="Example Kitchen",
        primary_language="en",
        niche="restaurant",
        sells=["seasonal lunch"],
        contacts=["Instagram Direct"],
        brand_atmosphere="warm, ingredient-led",
        colors=["olive"],
        product_identity=ProductIdentity(exact_product="seasonal lunch at a neighbourhood restaurant", evidence_sources=["fixture:product"], confidence="high"),
        content_themes=[
            ContentTheme(label="seasonal lunch menu", decision_role="offer", evidence_sources=["fixture:menu"]),
            ContentTheme(label="table requests", decision_role="process", evidence_sources=["fixture:booking"]),
            ContentTheme(label="ingredient-led kitchen", decision_role="proof", evidence_sources=["fixture:story"]),
        ],
        best_media=[MediaAsset(url=f"https://media.example/{index}.jpg", alt=f"Kitchen fixture {index}", recommended_use="editorial media", width=1600, height=1067) for index in range(6)],
    )
    values.update(changes)
    return ResearchBrief(**values)


def spec() -> SiteSpec:
    return SiteSpec(language="en", title="Example Kitchen", meta_description="Seasonal lunch via Direct", h1="Seasonal lunch at Example Kitchen", hero_subtitle="See the current menu and make an enquiry.", primary_cta="Message on Instagram", secondary_cta="View current menu", sections=[SectionSpec(id="menu", title="Today's menu", purpose="Choose a lunch direction.", content=["Ask about today's seasonal dishes."])], trust_points=["Current options are confirmed in Direct."], process_steps=["Message the kitchen."], footer_note="Instagram is the current contact path.", no_fake_claims_checklist=[])


class EvidenceTests(unittest.TestCase):
    def test_sufficient_evidence_is_level_a(self) -> None:
        assessment = assess_evidence(complete_research())
        self.assertEqual(assessment.level, EvidenceLevel.A)
        self.assertTrue(assessment.build_allowed)

    def test_sparse_but_identified_business_is_level_b(self) -> None:
        assessment = assess_evidence(complete_research(content_themes=[ContentTheme(label="seasonal lunch menu", decision_role="offer", evidence_sources=["fixture:menu"])], best_media=[MediaAsset(url="https://media.example/one.jpg", alt="Kitchen fixture", recommended_use="hero", width=1600, height=1067)]))
        self.assertEqual(assessment.level, EvidenceLevel.B)
        self.assertTrue(assessment.build_allowed)

    def test_missing_identity_blocks_as_level_c(self) -> None:
        assessment = assess_evidence(complete_research(business_name="Unknown (inferred)", niche="Unknown"))
        self.assertEqual(assessment.level, EvidenceLevel.C)
        self.assertFalse(assessment.build_allowed)

    def test_generic_unproven_night_yacht_is_blocked_before_scope(self) -> None:
        assessment = assess_evidence(ResearchBrief(
            instagram_url="https://instagram.com/night_yacht", business_name="Night Yacht", niche="night yacht experience",
            sells=["Private evening water experiences"], contacts=["Instagram Direct"], brand_atmosphere="cinematic",
        ))
        self.assertEqual(assessment.level, EvidenceLevel.C)
        self.assertEqual(assessment.page_scope.value, "blocked")
        self.assertFalse(assessment.checks["product_identified"])

    def test_duplicate_themes_and_media_cannot_unlock_full_scope(self) -> None:
        repeated = MediaAsset(url="https://media.example/repeated.jpg", alt="Repeated kitchen fixture", recommended_use="hero", width=1600, height=1067)
        assessment = assess_evidence(complete_research(
            content_themes=[ContentTheme(label="seasonal lunch", decision_role="offer", evidence_sources=["fixture:menu"])] * 3,
            best_media=[repeated] * 6,
        ))
        self.assertEqual(assessment.level, EvidenceLevel.B)
        self.assertEqual(assessment.content_theme_count, 1)
        self.assertEqual(assessment.usable_media_count, 1)
        self.assertEqual(assessment.page_scope.value, "micro_site")


class QualityGateTests(unittest.TestCase):
    def test_technical_score_cannot_compensate_generic_copy(self) -> None:
        current = spec()
        current.hero_subtitle = "High quality services with an individual approach."
        context = build_context(complete_research(), strategy(), current)
        report = audit_quality(current, context, technical_passed=True)
        self.assertFalse(report.approved)
        self.assertLess(report.category_scores["copy"], report.floors["copy"])
        self.assertGreaterEqual(report.category_scores["technical"], report.floors["technical"])

    def test_same_input_has_stable_fingerprint_and_duplicate_is_blocked(self) -> None:
        current = spec()
        context = build_context(complete_research(), strategy(), current)
        first = audit_quality(current, context, technical_passed=True)
        duplicate = audit_quality(current, context, technical_passed=True, historical_fingerprints=[first.fingerprint])
        self.assertEqual(first.fingerprint, audit_quality(current, context, technical_passed=True).fingerprint)
        self.assertFalse(duplicate.approved)
        self.assertIn("identical layout fingerprint", duplicate.blocking_reasons)

    def test_vendored_skill_lock_is_pinned_and_present(self) -> None:
        errors = validate_skill_lock(Path(".agents/skills/skills.lock.json"))
        self.assertEqual(errors, [])


def strategy() -> StrategyBrief:
    return StrategyBrief(target_customer="local lunch guest", reason_to_choose=["seasonal menu"], customer_questions_or_fears=["What is available today?"], niche_specific_sections=["menu"], primary_cta="Message on Instagram", secondary_cta="View current menu", tone="warm", color_direction="olive", typography_direction="editorial", business_logic="Direct enquiries")


if __name__ == "__main__":
    unittest.main()
