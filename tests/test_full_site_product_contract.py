from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from site_agent.design_quality import PageScope, assess_studio_readiness
from site_agent.models import ContentTheme, MediaAsset, ProductIdentity, ResearchBrief
from site_agent.orchestrator import SiteAgentOrchestrator
from site_agent.product_director import ProductDirectorAuditor
from site_agent.workflow import implementation_package


def research(**overrides) -> ResearchBrief:
    values = dict(
        instagram_url="https://www.instagram.com/example/",
        business_name="Example Studio",
        niche="event design studio",
        primary_language="pl",
        contacts=["contact form"],
        product_identity=ProductIdentity(exact_product="event scenography and floral installations", evidence_sources=["fixture:offer"], confidence="high"),
        content_themes=[
            ContentTheme(label="wedding scenography", decision_role="offer", evidence_sources=["fixture:weddings"]),
            ContentTheme(label="corporate events", decision_role="format", evidence_sources=["fixture:corporate"]),
            ContentTheme(label="consultation and installation", decision_role="process", evidence_sources=["fixture:process"]),
        ],
        best_media=[MediaAsset(url=f"https://media.example/{i}.jpg", alt=f"Event work {i}", recommended_use="portfolio", width=1200, height=900) for i in range(6)],
    )
    values.update(overrides)
    return ResearchBrief(**values)


class FullSiteProductContractTests(unittest.TestCase):
    def test_saved_critic_is_reused_only_for_the_exact_site_bytes(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            site = root / "index.html"
            provenance = root / "critique.provenance.json"
            site.write_text("first build", encoding="utf-8")
            self.assertFalse(SiteAgentOrchestrator._critique_matches_site(provenance, site))
            provenance.write_text(json.dumps({
                "site_sha256": SiteAgentOrchestrator._site_checksum(root),
            }), encoding="utf-8")
            self.assertTrue(SiteAgentOrchestrator._critique_matches_site(provenance, site))
            (root / "styles.css").write_text("body { color: red; }", encoding="utf-8")
            self.assertFalse(SiteAgentOrchestrator._critique_matches_site(provenance, site))

    def test_normal_business_defaults_to_full_and_sparse_input_blocks(self) -> None:
        item = research(content_themes=research().content_themes[:1], best_media=research().best_media[:1])
        assessment = assess_studio_readiness(item)
        self.assertEqual(item.requested_product_type, "full_commercial_site")
        self.assertEqual(assessment.page_scope, PageScope.BLOCKED)
        self.assertIn("content_sufficient_for_full_site", assessment.missing_content_manifest)

    def test_explicit_campaign_can_use_micro_scope(self) -> None:
        item = research(requested_product_type="campaign_landing", content_themes=research().content_themes[:1], best_media=research().best_media[:1])
        self.assertEqual(assess_studio_readiness(item).page_scope, PageScope.MICRO)

    def test_product_director_caps_three_section_redirect_even_with_clean_technical_inputs(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); site = root / "site"; shots = root / "shots"; site.mkdir(); shots.mkdir()
            (site / "index.html").write_text("""<main>
              <section data-decision-role='identity_value'>Studio</section>
              <section data-decision-role='offer_services'>Services <a href='https://official.example'>Official site</a></section>
              <section data-decision-role='final_conversion'>Continue</section>
            </main>""", encoding="utf-8")
            for name in ("desktop.png", "tablet.png", "mobile.png"):
                (shots / name).write_bytes(b"png")
            report = ProductDirectorAuditor().audit(
                requested_product_type="full_commercial_site", site_dir=site, screenshots_dir=shots,
                business_research={"research": {"product_identity": {"exact_product": "event design"}}},
                media_manifest={"media": [{"url": "https://res.cloudinary.com/example/a.jpg"}]},
            )
            self.assertFalse(report["product_accepted"])
            self.assertLessEqual(report["score"], 40)
            self.assertTrue(report["redirect_only"])
            self.assertNotIn("internal_critic_scores", report["blind_input_contract"]["included"])

    def test_multi_page_request_fails_closed_when_secondary_pages_are_missing(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); site = root / "site"; shots = root / "shots"; site.mkdir(); shots.mkdir()
            sections = "".join(
                f"<section data-decision-role='{role}'>{role}</section>"
                for role in sorted({
                    "identity_value", "offer_services", "proof", "brand_about",
                    "trust_process", "commercial_decision", "objection_handling",
                })
            )
            (site / "index.html").write_text(
                f"<main>{sections}<section data-decision-role='final_conversion'><form></form></section></main>",
                encoding="utf-8",
            )
            for name in ("desktop.png", "tablet.png", "mobile.png"):
                (shots / name).write_bytes(b"png")
            report = ProductDirectorAuditor().audit(
                requested_product_type="multi_page_commercial_site", site_dir=site, screenshots_dir=shots,
                business_research={"research": {"product_identity": {"exact_product": "event design"}}},
                media_manifest={"media": [{"url": "https://media.example/work.jpg"}]},
            )
            self.assertFalse(report["product_accepted"])
            self.assertEqual(
                report["multi_page_contract"]["missing_pages"],
                ["services.html", "portfolio.html", "about.html", "contact.html"],
            )
            self.assertLessEqual(report["score"], 45)

    def test_package_fails_closed_when_rich_handoff_fields_are_missing(self) -> None:
        package = implementation_package(
            business_research={"research": {"business_name": "Example"}}, media_manifest={"media": []},
            design_brief={"central_idea": "x"}, references=[],
        )
        self.assertFalse(package["implementation_package_information_loss"])
        self.assertIn("research.requested_product_type", package["missing_required_handoff_fields"])


if __name__ == "__main__":
    unittest.main()
