from __future__ import annotations

import unittest

from site_agent.media import authorised_media_assets
from site_agent.orchestrator import SiteAgentOrchestrator


SOURCE = "https://instagram.com/amidental_kiev"


class OneLinkPreviewContractTests(unittest.TestCase):
    def test_exact_twenty_year_source_is_not_upgraded_to_plus_claim(self) -> None:
        business = {
            "research": {
                "business_name": "Ami Dental",
                "verified_facts": [{
                    "source": SOURCE,
                    "value": "Dental clinic with over 20 years of experience.",
                    "confidence": "high",
                }],
                "content_provenance": [{
                    "field": "years_experience",
                    "value": "20+ years",
                    "status": "verified_fact",
                    "sources": [SOURCE],
                }],
            }
        }
        intake = {
            "title": "Ami Dental",
            "description": "20 років досвіду",
            "public_text": "Стоматологія Київ",
        }

        result = SiteAgentOrchestrator._apply_provisional_preview_contract(business, intake, SOURCE)
        serialized = str({
            "verified_facts": result["research"]["verified_facts"],
            "content_provenance": result["research"]["content_provenance"],
        })

        self.assertNotIn("over 20", serialized.lower())
        self.assertNotIn("20+", serialized)
        self.assertIn("20 years", serialized)
        self.assertTrue(any("exact duration" in item for item in result["research"]["forbidden_claims"]))

    def test_missing_phone_email_and_public_price_do_not_shrink_or_block_preview_brief(self) -> None:
        business = {"research": {}, "recommended_scope": "blocked"}
        intake = {
            "title": "СТОМАТОЛОГІЯ КИЇВ | КОРОНКИ | ІМПЛАНТИ | ВІНІРИ | БРЕКЕТИ",
            "description": "Твоя усмішка — наша гордість",
            "public_text": "Стоматологія Київ коронки імпланти вініри брекети",
            "business_name": "Ami Dental",
        }

        result = SiteAgentOrchestrator._apply_provisional_preview_contract(business, intake, SOURCE)
        research = result["research"]

        self.assertEqual(research["requested_product_type"], "full_commercial_site")
        self.assertEqual(result["recommended_scope"], "full_site")
        self.assertGreaterEqual(len(research["content_themes"]), 3)
        self.assertEqual(research["contacts"], [f"Instagram: {SOURCE}"])
        blockers = " ".join(result["missing_content_manifest"])
        self.assertIn("phone", blockers)
        self.assertIn("email", blockers)
        self.assertIn("public_price_numbers", blockers)
        statuses = {item["status"] for item in research["content_provenance"]}
        self.assertTrue({"verified_fact", "inferred_brand_copy", "generated_demo_content", "missing_required_fact"} <= statuses)

    def test_preview_social_media_is_usable_for_preview_but_never_production_authorised(self) -> None:
        manifest = {
            "media": [{
                "asset_id": "asset-1",
                "url": "https://res.cloudinary.com/siteagent/image/upload/v1/asset.jpg",
                "kind": "image",
                "width": 900,
                "height": 700,
                "source_kind": "business_social",
                "source_url": SOURCE,
                "user_authorized_for_preview": True,
                "allowed_for_customer_production": False,
                "user_authorized": False,
                "allowed_for_public_site": False,
            }]
        }

        self.assertEqual(authorised_media_assets(manifest), [])
        preview_assets = authorised_media_assets(manifest, preview=True)
        self.assertEqual(len(preview_assets), 1)
        self.assertEqual(preview_assets[0].source_kind, "business_social")
        self.assertFalse(preview_assets[0].portfolio_claim)


if __name__ == "__main__":
    unittest.main()
