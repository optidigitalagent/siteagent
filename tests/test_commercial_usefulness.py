from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from site_agent.commercial_usefulness import commercial_usefulness_report, semantic_repetition_report
from site_agent.design_quality import EvidenceLevel, assess_evidence, audit_quality, build_context
from site_agent.models import ContentTheme, ProductIdentity, ResearchBrief, SectionSpec, SiteSpec, StrategyBrief
from site_agent.studio import CodexStudioRunner


def research(**changes) -> ResearchBrief:
    values = dict(
        instagram_url="https://www.instagram.com/example/",
        business_name="Night Example",
        niche="private water experience",
        primary_language="en",
        sells=["private evening water experiences"],
        contacts=["Instagram Direct"],
        brand_atmosphere="reflective water at dusk",
        product_identity=ProductIdentity(exact_product="private yacht charter", evidence_sources=["fixture:product"], confidence="high"),
        content_themes=[ContentTheme(label="private charter request", decision_role="offer", evidence_sources=["fixture:product"])],
    )
    values.update(changes)
    return ResearchBrief(**values)


def strategy() -> StrategyBrief:
    return StrategyBrief(
        target_customer="people planning private time on the water",
        reason_to_choose=["private evening water experiences"],
        customer_questions_or_fears=["What is the experience?"],
        niche_specific_sections=["the experience"],
        primary_cta="Ask about an evening",
        secondary_cta="See the experience",
        tone="calm and direct",
        color_direction="derived from supplied water media",
        typography_direction="quiet editorial",
        business_logic="clarify the experience and start a Direct enquiry",
    )


def spec(**changes) -> SiteSpec:
    values = dict(
        language="en", title="Night Example", meta_description="Private evening water experiences.",
        h1="Private evening water experiences", hero_subtitle="For people planning private time on the water.",
        primary_cta="Ask about an evening", secondary_cta="See the experience",
        sections=[SectionSpec(id="experience", title="A private evening on the water", purpose="Clarify the offer.", content=["Private evening water experiences for a considered, unhurried occasion."])],
        trust_points=["Current availability and pricing are confirmed in Instagram Direct."],
        process_steps=["Send your preferred evening in Instagram Direct."], footer_note="Instagram Direct confirms current details.",
        no_fake_claims_checklist=[],
    )
    values.update(changes)
    return SiteSpec(**values)


class CommercialUsefulnessTests(unittest.TestCase):
    def test_missing_information_cannot_be_primary_narrative(self) -> None:
        current = spec(sections=[
            SectionSpec(id="one", title="Confirm details", purpose="x", content=["Confirm current details in Instagram Direct."]),
            SectionSpec(id="two", title="Ask in Direct", purpose="x", content=["Confirm current details in Instagram Direct."]),
            SectionSpec(id="three", title="Message us", purpose="x", content=["Confirm current details in Instagram Direct."]),
        ])
        context = build_context(research(), strategy(), current)
        report = audit_quality(current, context, technical_passed=True)
        self.assertFalse(report.approved)
        self.assertLessEqual(report.category_scores["copy_quality"], 55)

    def test_three_semantic_duplicates_block_story(self) -> None:
        current = spec(sections=[
            SectionSpec(id="one", title="Direct", purpose="x", content=["Confirm current details in Instagram Direct."]),
            SectionSpec(id="two", title="Direct", purpose="x", content=["Confirm current details in Instagram Direct."]),
            SectionSpec(id="three", title="Direct", purpose="x", content=["Confirm current details in Instagram Direct."]),
        ])
        context = build_context(research(), strategy(), current)
        semantic = semantic_repetition_report(current, context)
        report = audit_quality(current, context, technical_passed=True)
        self.assertFalse(semantic.approved)
        self.assertLessEqual(report.category_scores["storytelling"], 55)

    def test_hero_without_identifiable_offer_caps_business_clarity(self) -> None:
        current = spec(h1="Night, noted.", hero_subtitle="A quiet field study for the evening.")
        report = audit_quality(current, build_context(research(), strategy(), current), technical_passed=True)
        self.assertLessEqual(report.category_scores["business_clarity"], 60)

    def test_missing_first_viewport_cta_caps_ux(self) -> None:
        current = spec()
        report = audit_quality(current, build_context(research(), strategy(), current), technical_passed=True, hero_cta_present=False)
        self.assertLessEqual(report.category_scores["ux"], 60)

    def test_copy_question_is_not_meaningful_conversion(self) -> None:
        current = spec()
        report = audit_quality(current, build_context(research(), strategy(), current), technical_passed=True, html_text="<section>Copy this question</section>")
        self.assertFalse(report.approved)
        self.assertIn("commercial usefulness", " ".join(report.blocking_reasons).lower())

    def test_unverified_language_choice_blocks_brand_fit(self) -> None:
        current = spec(language="en")
        report = audit_quality(current, build_context(research(primary_language="ru"), strategy(), current), technical_passed=True)
        self.assertLessEqual(report.category_scores["brand_fit"], 60)

    def test_art_director_cannot_approve_when_commercial_gate_fails(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            studio = Path(temp)
            for name, payload in {
                "commercial_usefulness_report.json": {"score": 42, "checks": {"offer_clear_within_five_seconds": False, "primary_cta_in_first_meaningful_viewport": False}},
                "language_fit_report.json": {"approved": True},
                "semantic_repetition_report.json": {"approved": False, "items": [{}]},
            }.items():
                (studio / name).write_text(json.dumps(payload), encoding="utf-8")
            result = CodexStudioRunner._apply_art_director_calibration(studio, {"approved": True, "score": 90, "findings": [], "unresolved_issues": []})
            self.assertFalse(result["approved"])
            self.assertEqual(result["score"], 42)

    def test_desire_failure_cannot_receive_commercial_or_art_direction_approval(self) -> None:
        current = spec(h1="A clear offer", hero_subtitle="A factual request path.")
        context = build_context(research(), strategy(), current)
        commercial = commercial_usefulness_report(current, context, html_text="<main>Clear offer. Ask in Direct.</main>")
        self.assertFalse(commercial.checks["desire_created"])
        self.assertFalse(commercial.approved)
        with tempfile.TemporaryDirectory() as temp:
            studio = Path(temp)
            (studio / "commercial_usefulness_report.json").write_text(json.dumps(commercial.model_dump()), encoding="utf-8")
            (studio / "language_fit_report.json").write_text(json.dumps({"approved": True}), encoding="utf-8")
            (studio / "semantic_repetition_report.json").write_text(json.dumps({"approved": True}), encoding="utf-8")
            result = CodexStudioRunner._apply_art_director_calibration(studio, {"approved": True, "score": 90, "findings": [], "unresolved_issues": []})
            self.assertFalse(result["approved"])

    def test_technical_success_cannot_compensate_commercial_failure(self) -> None:
        current = spec(h1="Night, noted.", hero_subtitle="A field study.")
        report = audit_quality(current, build_context(research(), strategy(), current), technical_passed=True)
        self.assertGreaterEqual(report.category_scores["technical"], report.floors["technical"])
        self.assertFalse(report.approved)

    def test_media_blackout_and_dead_space_cap_media_direction(self) -> None:
        current = spec()
        report = audit_quality(current, build_context(research(), strategy(), current), technical_passed=True, visual_signals={"media_blackout": True, "dead_space": True})
        self.assertLessEqual(report.category_scores["media_direction"], 65)

    def test_level_b_remains_concise_and_level_c_does_not_build(self) -> None:
        level_b = assess_evidence(research(brand_atmosphere=""))
        level_c = assess_evidence(research(business_name="Unknown (inferred)", niche="Unknown", contacts=[], instagram_url=""))
        self.assertEqual(level_b.level, EvidenceLevel.B)
        self.assertTrue(level_b.build_allowed)
        self.assertEqual(level_c.level, EvidenceLevel.C)
        self.assertFalse(level_c.build_allowed)

    def test_original_night_yacht_rejection_is_recorded(self) -> None:
        record = Path("runs/creative-studio-e2e/night_yacht/calibration_v2/rejection.json")
        self.assertTrue(record.is_file())
        self.assertFalse(json.loads(record.read_text(encoding="utf-8"))["approved"])


if __name__ == "__main__":
    unittest.main()
