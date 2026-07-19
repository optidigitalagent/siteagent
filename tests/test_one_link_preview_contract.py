from __future__ import annotations

import tempfile
import unittest
import json
from pathlib import Path

from site_agent.media import authorised_media_assets
from site_agent.models import ResearchBrief
from site_agent.orchestrator import SiteAgentOrchestrator


SOURCE = "https://instagram.com/amidental_kiev"


class OneLinkPreviewContractTests(unittest.TestCase):
    def test_cached_preview_intake_is_sanitized_without_reupload(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            workspace = Path(temp)
            run_dir = workspace / "current"
            originals = run_dir / "media_input" / "originals"
            originals.mkdir(parents=True)
            media = []
            for index in range(4):
                filename = f"asset-{index}.jpg"
                (originals / filename).write_bytes(b"business-owned")
                media.append({
                    "asset_id": f"asset-{index}",
                    "asset_url": (
                        "https://scontent.cdninstagram.com/t51.82787-19/logo.jpg"
                        if index == 0
                        else f"https://scontent.cdninstagram.com/t51.82787-15/post-{index}.jpg"
                    ),
                    "url": f"https://res.cloudinary.com/example/image/upload/asset-{index}.jpg",
                    "original_file": f"originals/{filename}",
                    "original_checksum": f"checksum-{index}",
                    "source_url": SOURCE,
                })
            media.append({
                "asset_id": "meta-decoration",
                "asset_url": "https://lookaside.fbsbx.com/elementpath/media/?media_id=1",
                "url": "https://res.cloudinary.com/example/image/upload/meta.jpg",
                "original_file": "originals/meta.jpg",
            })
            intake = {
                "pipeline_version": "one-link-preview-v1",
                "research": {
                    "normalized_url": SOURCE,
                    "image_urls": [media[1]["asset_url"], media[-1]["asset_url"]],
                    "official_site_urls": ["https://www.meta.com/about/"],
                    "media_candidates": [
                        {"asset_url": media[1]["asset_url"]},
                        {"asset_url": media[-1]["asset_url"]},
                    ],
                    "sources": [{"url": SOURCE}, {"url": "https://www.meta.com/about/"}],
                    "source_ledger": [{"url": SOURCE}, {"url": "https://www.meta.com/about/"}],
                },
                "media_manifest": {"media": media},
            }
            prior = workspace / "prior"
            prior_reports = prior / "generation_reports"
            prior_reports.mkdir(parents=True)
            (prior / "preview_deployment.json").write_text("{}", encoding="utf-8")
            (prior_reports / "acceptance_audit.json").write_text(
                json.dumps({"approved": True}), encoding="utf-8"
            )
            (prior_reports / "00_one_link_intake.json").write_text(
                json.dumps({"research": {"normalized_url": SOURCE}}), encoding="utf-8"
            )
            (prior_reports / "02_authorised_media_manifest.json").write_text(
                json.dumps({"media": media[:4]}), encoding="utf-8"
            )

            upgraded, changed = SiteAgentOrchestrator._upgrade_cached_preview_intake(
                intake=intake,
                normalized_url=SOURCE,
                run_dir=run_dir,
            )

            self.assertTrue(changed)
            self.assertEqual(len(upgraded["media_manifest"]["media"]), 4)
            self.assertEqual(upgraded["media_manifest"]["media"][0]["source_role"], "official_profile_avatar")
            self.assertEqual(upgraded["research"]["official_site_urls"], [])
            self.assertEqual(intake["pipeline_version"], "one-link-preview-v1")

    def test_recovery_compares_normalized_business_source_not_tracking_query(self) -> None:
        self.assertTrue(SiteAgentOrchestrator._same_business_source(
            "https://www.instagram.com/amidental_kiev/?igsh=tracking",
            "https://instagram.com/amidental_kiev",
        ))

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

    def test_final_customer_copy_cannot_reintroduce_plus_duration(self) -> None:
        research = ResearchBrief(
            instagram_url=SOURCE,
            business_name="Ami Dental",
            niche="dental clinic",
            forbidden_claims=[
                "Do not upgrade the verified exact duration of 20 years to over 20 years or 20+."
            ],
        )
        with tempfile.TemporaryDirectory() as temp:
            index = Path(temp) / "index.html"
            index.write_text("<main>Trusted for 20+ years.</main>", encoding="utf-8")
            self.assertFalse(
                SiteAgentOrchestrator._exact_duration_contract_passes(research, index)
            )
            index.write_text("<main>20 years of experience.</main>", encoding="utf-8")
            self.assertTrue(
                SiteAgentOrchestrator._exact_duration_contract_passes(research, index)
            )

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
