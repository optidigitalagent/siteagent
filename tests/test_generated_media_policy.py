from __future__ import annotations

import base64
import io
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from PIL import Image

from site_agent.design_quality import PageScope, assess_studio_readiness
from site_agent.generated_media import (
    GeneratedMediaManager,
    MediaPlan,
    MediaPlanItem,
    OpenAIImageGenerator,
    merge_user_provided_business_assets,
)
from site_agent.media import MediaInputBlocked, MediaPreparer, authorised_media_assets
from site_agent.media_policy import (
    MediaProvenanceType,
    manifest_policy_issues,
    rendered_media_policy_issues,
)
from site_agent.models import ContentTheme, ProductIdentity, ResearchBrief
from site_agent.workflow import checksum


def _safe_items() -> list[MediaPlanItem]:
    roles = (
        ("Hero", "atmosphere"),
        ("Services", "service_visualization"),
        ("About", "abstract_brand"),
        ("Process", "object_scene"),
        ("Closing", "decorative_texture"),
    )
    return [
        MediaPlanItem(
            section=section,
            required_visual=f"Original {section.lower()} visual",
            source_strategy="ai_generated_original",
            truthfulness_constraint="Do not present this as documentary business evidence.",
            claim_role=role,
            prompt=f"Create a refined generic {section.lower()} composition with no text or logo.",
            alt=f"Conceptual {section.lower()} visual",
        )
        for section, role in roles
    ]


class StaticPlanner:
    def __init__(self, *, omitted: list[str] | None = None) -> None:
        self.omitted = omitted or []
        self.calls = 0

    def run(self, *, business_research, existing_manifest, real_business_media_only):
        self.calls += 1
        payload = {
            "business_research": business_research,
            "existing_media": [
                {
                    key: item.get(key)
                    for key in (
                        "asset_id", "provenance_type", "source_role", "recommended_use",
                        "alt", "width", "height",
                    )
                }
                for item in existing_manifest.get("media", [])
            ],
            "real_business_media_only": real_business_media_only,
        }
        return MediaPlan(
            input_checksum=checksum(payload),
            items=_safe_items(),
            omitted_evidence_sections=self.omitted,
            summary="Five original non-documentary visuals complete the preview media set.",
        )


class FakeGenerator:
    def __init__(self) -> None:
        self.calls = 0

    def generate(self, item: MediaPlanItem, output_path: Path):
        self.calls += 1
        output_path.parent.mkdir(parents=True, exist_ok=True)
        Image.new("RGB", (1024, 768), (20 + self.calls, 40, 60)).save(output_path, format="PNG")
        return {
            "prompt": item.prompt,
            "prompt_checksum": checksum(item.prompt),
            "generation_model": "test-image-model",
            "width": 1024,
            "height": 768,
        }


class FakeUploader:
    def __init__(self) -> None:
        self.upload_calls = 0

    def upload(self, path: Path, *, public_id: str, resource_type: str = "image"):
        self.upload_calls += 1
        leaf = public_id.replace("/", "-")
        return {
            "url": f"https://res.cloudinary.com/siteagent-test/image/upload/{leaf}.png",
            "cloudinary_public_id": public_id,
            "cloudinary_asset_id": leaf,
            "cloudinary_version": "1",
        }

    @staticmethod
    def _is_own_cloudinary_url(url: str) -> bool:
        return url.startswith("https://res.cloudinary.com/siteagent-test/image/upload/")


def _manager(*, omitted: list[str] | None = None):
    planner = StaticPlanner(omitted=omitted)
    generator = FakeGenerator()
    manager = GeneratedMediaManager(planner=planner, generator=generator, uploader=FakeUploader())
    return manager, planner, generator


def _base_manifest() -> dict:
    return {
        "schema_version": 2,
        "purpose": "isolated_preview",
        "media": [],
        "media_count": 0,
        "image_count": 0,
        "composition_mode": "generated_media_required",
    }


def _business_research() -> dict:
    return {
        "research": {
            "business_name": "Example Studio",
            "category": "specialist service",
            "offerings": ["consultation", "planning", "delivery"],
        }
    }


class GeneratedMediaPolicyTests(unittest.TestCase):
    def test_image_generation_omits_model_incompatible_response_format(self) -> None:
        class FakeImages:
            def __init__(self) -> None:
                self.kwargs = {}

            def generate(self, **kwargs):
                self.kwargs = kwargs
                buffer = io.BytesIO()
                Image.new("RGB", (8, 8), (20, 40, 60)).save(buffer, format="PNG")
                encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
                return SimpleNamespace(data=[SimpleNamespace(b64_json=encoded, url=None)])

        images = FakeImages()
        client = SimpleNamespace(images=images)
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / "generated.png"
            result = OpenAIImageGenerator(client=client, model="gpt-image-1").generate(
                _safe_items()[0], output
            )

            self.assertNotIn("response_format", images.kwargs)
            self.assertEqual(images.kwargs["output_format"], "png")
            with Image.open(output) as image:
                self.assertEqual(image.size, (8, 8))
            self.assertEqual(result["generation_model"], "gpt-image-1")

    def test_1_logo_only_project_generates_media_and_becomes_design_ready(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            run_dir = Path(temp)
            logo_dir = run_dir / "media_input" / "user_provided"
            logo_dir.mkdir(parents=True)
            Image.new("RGBA", (600, 240), (12, 32, 42, 255)).save(logo_dir / "logo.png")
            manifest = merge_user_provided_business_assets(run_dir, _base_manifest())
            manager, planner, generator = _manager()

            merged, plan = manager.prepare(
                run_dir=run_dir,
                business_research=_business_research(),
                existing_manifest=manifest,
                real_business_media_only=False,
                job_id="same-run",
            )

            self.assertEqual(planner.calls, 1)
            self.assertEqual(generator.calls, 5)
            self.assertEqual(merged["generated_media_count"], 5)
            self.assertTrue(merged["full_preview_media_sufficient"])
            self.assertEqual(plan["items"][0]["source_strategy"], "ai_generated_original")
            self.assertEqual(
                merged["media"][0]["provenance_type"],
                MediaProvenanceType.USER_PROVIDED_BUSINESS_ASSET.value,
            )

            research = ResearchBrief(
                instagram_url="https://instagram.com/example",
                business_name="Example Studio",
                primary_language="en",
                niche="specialist service studio",
                sells=["consultation and delivery"],
                contacts=["Instagram Direct"],
                product_identity=ProductIdentity(
                    exact_product="specialist consultation and delivery",
                    evidence_sources=["official:profile"],
                    confidence="high",
                ),
                content_themes=[
                    ContentTheme(label=f"Verified theme {index}", decision_role="offer", evidence_sources=[f"official:{index}"])
                    for index in range(3)
                ],
                best_media=authorised_media_assets(merged, preview=True),
            )
            self.assertEqual(assess_studio_readiness(research).page_scope, PageScope.FULL)

    def test_2_no_owned_photos_is_a_warning_not_a_terminal_blocker(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            manager, _, _ = _manager()
            merged, _ = manager.prepare(
                run_dir=Path(temp),
                business_research=_business_research(),
                existing_manifest=_base_manifest(),
                real_business_media_only=False,
                job_id="warning-run",
            )
            self.assertEqual(merged["real_business_photo_count"], 0)
            self.assertTrue(any("No real business photos" in item for item in merged["production_warnings"]))

    def test_3_reference_only_image_cannot_enter_output(self) -> None:
        url = "https://images.example/unlicensed-reference.jpg"
        manifest = {
            "media": [{
                "asset_id": "reference",
                "url": url,
                "provenance_type": "reference_only",
                "source_kind": "reference_only",
            }]
        }
        self.assertTrue(manifest_policy_issues(manifest, target="isolated_preview"))
        self.assertTrue(rendered_media_policy_issues(manifest, f'<img src="{url}">'))
        contradictory = {
            "media": [{
                "asset_id": "laundered-fixture",
                "url": "https://res.cloudinary.com/siteagent-test/image/upload/fixture.jpg",
                "source_kind": "fixture_stock",
                "provenance_type": "verified_official_business_asset",
                "user_authorized_for_preview": True,
            }]
        }
        self.assertTrue(manifest_policy_issues(contradictory, target="isolated_preview"))

    def test_4_generated_hero_is_allowed_with_traceable_safe_role(self) -> None:
        url = "https://res.cloudinary.com/siteagent-test/image/upload/hero.png"
        manifest = {
            "media": [{
                "asset_id": "generated-hero",
                "url": url,
                "source_kind": "ai_generated",
                "provenance_type": "ai_generated_original",
                "generation_model": "test-image-model",
                "prompt_checksum": "prompt-sha",
                "original_checksum": "image-sha",
                "claim_role": "atmosphere",
                "portfolio_claim": False,
                "user_authorized_for_preview": True,
                "allowed_for_customer_production": True,
            }]
        }
        html = (
            f'<img src="{url}" data-media-provenance="ai_generated_original" '
            'data-media-claim-role="atmosphere" alt="Conceptual atmosphere">'
        )
        self.assertEqual(manifest_policy_issues(manifest, target="isolated_preview"), [])
        self.assertEqual(rendered_media_policy_issues(manifest, html), [])
        repeated = html + f'<img src="{url}" alt="Untraceable repeated use">'
        self.assertTrue(any("use 2" in issue for issue in rendered_media_policy_issues(manifest, repeated)))

    def test_5_generated_fake_team_is_prohibited(self) -> None:
        with self.assertRaisesRegex(ValueError, "forbidden documentary role|not safe"):
            MediaPlanItem(
                section="Team",
                required_visual="Portrait",
                source_strategy="ai_generated_original",
                truthfulness_constraint="Pretend this is a real employee.",
                claim_role="real_employee",
                prompt="Portrait of the business team member.",
            )

    def test_6_generated_fake_case_is_prohibited(self) -> None:
        with self.assertRaisesRegex(ValueError, "forbidden documentary role|not safe"):
            MediaPlanItem(
                section="Cases",
                required_visual="Before and after",
                source_strategy="ai_generated_original",
                truthfulness_constraint="Present as a real client result.",
                claim_role="before_after",
                prompt="A before and after result.",
            )

    def test_7_missing_evidence_sections_are_omitted_without_blocking_preview(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            manager, _, _ = _manager(omitted=["cases", "reviews"])
            merged, plan = manager.prepare(
                run_dir=Path(temp),
                business_research=_business_research(),
                existing_manifest=_base_manifest(),
                real_business_media_only=False,
                job_id="omission-run",
            )
            self.assertEqual(plan["omitted_evidence_sections"], ["cases", "reviews"])
            self.assertEqual(merged["omitted_evidence_sections"], ["cases", "reviews"])
            self.assertTrue(merged["full_preview_media_sufficient"])

    def test_8_real_business_media_only_blocks_without_real_photos(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            manager, planner, generator = _manager()
            with self.assertRaisesRegex(MediaInputBlocked, "real_business_media_only=true"):
                manager.prepare(
                    run_dir=Path(temp),
                    business_research=_business_research(),
                    existing_manifest=_base_manifest(),
                    real_business_media_only=True,
                    job_id="real-only-run",
                )
            self.assertEqual(planner.calls, 0)
            self.assertEqual(generator.calls, 0)

    def test_9_same_run_reuses_media_plan_and_generated_assets(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            run_dir = Path(temp)
            manager, planner, generator = _manager()
            first, first_plan = manager.prepare(
                run_dir=run_dir,
                business_research=_business_research(),
                existing_manifest=_base_manifest(),
                real_business_media_only=False,
                job_id="recoverable-run",
            )
            second, second_plan = manager.prepare(
                run_dir=run_dir,
                business_research=_business_research(),
                existing_manifest=_base_manifest(),
                real_business_media_only=False,
                job_id="recoverable-run",
            )
            self.assertEqual(planner.calls, 1)
            self.assertEqual(generator.calls, 5)
            self.assertEqual(first_plan, second_plan)
            self.assertEqual(
                [item["original_checksum"] for item in first["media"]],
                [item["original_checksum"] for item in second["media"]],
            )

    def test_partial_generation_checkpoint_reuses_uploaded_assets_after_failure(self) -> None:
        class FailOnceGenerator(FakeGenerator):
            def generate(self, item: MediaPlanItem, output_path: Path):
                if self.calls == 2:
                    self.calls += 1
                    raise MediaInputBlocked("simulated generation interruption")
                return super().generate(item, output_path)

        with tempfile.TemporaryDirectory() as temp:
            run_dir = Path(temp)
            planner = StaticPlanner()
            generator = FailOnceGenerator()
            manager = GeneratedMediaManager(
                planner=planner,
                generator=generator,
                uploader=FakeUploader(),
            )
            with self.assertRaisesRegex(MediaInputBlocked, "simulated generation interruption"):
                manager.prepare(
                    run_dir=run_dir,
                    business_research=_business_research(),
                    existing_manifest=_base_manifest(),
                    real_business_media_only=False,
                    job_id="interrupted-run",
                )
            checkpoint = __import__("json").loads(
                (run_dir / "generated_media" / "manifest.json").read_text(encoding="utf-8")
            )
            self.assertEqual(checkpoint["status"], "in_progress")
            self.assertEqual(checkpoint["generated_count"], 2)
            completed, _ = manager.prepare(
                run_dir=run_dir,
                business_research=_business_research(),
                existing_manifest=_base_manifest(),
                real_business_media_only=False,
                job_id="interrupted-run",
            )
            self.assertEqual(planner.calls, 1)
            self.assertEqual(generator.calls, 6)
            self.assertEqual(completed["generated_media_count"], 5)

    def test_user_provided_business_visuals_are_uploaded_before_readiness_count(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            run_dir = Path(temp)
            source_dir = run_dir / "media_input" / "user_provided"
            source_dir.mkdir(parents=True)
            for index in range(5):
                Image.new("RGB", (800, 600), (index * 20, 80, 100)).save(source_dir / f"photo-{index}.png")
            manifest = merge_user_provided_business_assets(run_dir, _base_manifest())
            planner = StaticPlanner()
            generator = FakeGenerator()
            uploader = FakeUploader()
            manager = GeneratedMediaManager(planner=planner, generator=generator, uploader=uploader)
            merged, _ = manager.prepare(
                run_dir=run_dir,
                business_research=_business_research(),
                existing_manifest=manifest,
                real_business_media_only=False,
                job_id="user-photos-run",
            )
            self.assertEqual(uploader.upload_calls, 5)
            self.assertEqual(generator.calls, 0)
            self.assertEqual(planner.calls, 0)
            self.assertEqual(len(authorised_media_assets(merged, preview=True)), 5)

    def test_generation_is_bounded_to_the_missing_visual_count(self) -> None:
        existing = _base_manifest()
        existing["media"] = [
            {
                "asset_id": f"official-{index}",
                "kind": "image",
                "url": f"https://res.cloudinary.com/siteagent-test/image/upload/official-{index}.png",
                "source_kind": "business_social",
                "provenance_type": "verified_official_business_asset",
                "source_role": "post_or_reel_cover",
                "user_authorized_for_preview": True,
                "allowed_for_customer_production": False,
                "width": 1024,
                "height": 768,
            }
            for index in range(4)
        ]
        with tempfile.TemporaryDirectory() as temp:
            manager, _, generator = _manager()
            merged, plan = manager.prepare(
                run_dir=Path(temp),
                business_research=_business_research(),
                existing_manifest=existing,
                real_business_media_only=False,
                job_id="bounded-generation-run",
            )
            self.assertEqual(generator.calls, 1)
            self.assertEqual(merged["generated_media_count"], 1)
            self.assertEqual(sum(item["output_required"] for item in plan["items"]), 1)

    def test_lone_business_photo_is_not_inferred_to_be_a_logo_and_duplicates_are_removed(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            run_dir = Path(temp)
            source_dir = run_dir / "media_input" / "user_provided"
            source_dir.mkdir(parents=True)
            image = Image.new("RGB", (800, 600), (40, 80, 120))
            image.save(source_dir / "photo.png")
            image.save(source_dir / "photo-copy.png")
            manifest = merge_user_provided_business_assets(run_dir, _base_manifest())
            self.assertEqual(len(manifest["media"]), 1)
            self.assertEqual(manifest["media"][0]["source_role"], "user_provided_business_visual")

    def test_canonical_generated_media_passes_production_manifest_validation(self) -> None:
        generated = {
            "asset_id": "generated-production",
            "url": "https://res.cloudinary.com/siteagent-test/image/upload/generated-production.png",
            "source_kind": "ai_generated",
            "provenance_type": "ai_generated_original",
            "generation_model": "test-image-model",
            "prompt_checksum": "prompt-sha",
            "original_checksum": "image-sha",
            "claim_role": "atmosphere",
            "portfolio_claim": False,
            "user_authorized": True,
            "allowed_for_public_site": True,
            "allowed_for_customer_production": True,
        }
        logo = {
            "asset_id": "logo",
            "url": "",
            "source_kind": "business",
            "provenance_type": "user_provided_business_asset",
            "source_role": "user_provided_logo",
            "user_authorized": True,
            "allowed_for_public_site": True,
        }
        MediaPreparer(uploader=FakeUploader()).validate_manifest({"media": [logo, generated]})


if __name__ == "__main__":
    unittest.main()
