from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from playwright.sync_api import sync_playwright

from site_agent.creative_fixture_e2e import _write_media_provenance_report, rich_dental_fixture, rich_floral_fixture
from site_agent.design_quality import EvidenceAssessment, EvidenceLevel, PageScope, assess_studio_readiness
from site_agent.models import ContentTheme, MediaAsset, ProductIdentity, ResearchBrief, SectionSpec, SiteSpec, StrategyBrief, TechnicalGate
from site_agent.skill_lock import validate_studio_plugin_bundle
from site_agent.studio import (
    CodexStudioRunner,
    StudioError,
    _media_provenance_report,
    assert_production_promotion_allowed,
)


def fixtures() -> tuple[ResearchBrief, StrategyBrief, SiteSpec]:
    research = ResearchBrief(
        instagram_url="https://www.instagram.com/fixture/",
        business_name="Fixture Studio",
        primary_language="en",
        niche="independent experience business",
        sells=["evening experiences"],
        contacts=["Instagram Direct"],
        brand_atmosphere="night-time and cinematic",
        product_identity=ProductIdentity(exact_product="guided evening harbour walk", evidence_sources=["fixture:product"], confidence="high"),
        content_themes=[
            ContentTheme(label="guided harbour walk", decision_role="offer", evidence_sources=["fixture:product"]),
            ContentTheme(label="meeting preparation", decision_role="process", evidence_sources=["fixture:process"]),
            ContentTheme(label="waterfront route studies", decision_role="proof", evidence_sources=["fixture:media"]),
        ],
        best_media=[MediaAsset(url=f"https://media.example/{index}.jpg", alt=f"Fixture scene {index}", recommended_use="narrative media", width=1600, height=1067) for index in range(6)],
        forbidden_claims=["best in town"],
    )
    strategy = StrategyBrief(
        target_customer="curious guests", reason_to_choose=["evening experience"],
        customer_questions_or_fears=["What happens after I enquire?"], niche_specific_sections=["experience"],
        primary_cta="Message on Instagram", secondary_cta="See the approach", tone="direct",
        color_direction="contextual", typography_direction="distinctive", business_logic="start a Direct conversation",
    )
    spec = SiteSpec(
        language="en", title="Fixture Studio", meta_description="Fixture experience", h1="Fixture Studio",
        hero_subtitle="Ask about the next evening experience.", primary_cta="Message on Instagram",
        secondary_cta="See the approach", sections=[SectionSpec(id="offer", title="The experience", purpose="Clarify the offer.", content=["Current details are confirmed in Direct."])],
        trust_points=["Use Direct for current details."], process_steps=["Start a conversation."],
        footer_note="Instagram Direct", no_fake_claims_checklist=[],
    )
    return research, strategy, spec


class StubInspector:
    def inspect(self, index_path: Path, artifacts_dir: Path):
        artifacts_dir.mkdir(parents=True, exist_ok=True)
        for name in ("desktop.png", "tablet.png", "mobile.png"):
            (artifacts_dir / name).write_bytes(b"png")
        return TechnicalGate(passed=True), {"desktop": "{}", "tablet": "{}", "mobile": "{}"}


class CreativeStudioTests(unittest.TestCase):
    def _write_provenance_workspace(
        self, root: Path, *, source_kind: str, body: str, url: str = "https://res.cloudinary.com/siteagent/image/upload/v1/image.jpg"
    ) -> tuple[Path, Path]:
        studio = root / "studio"
        site = root / "site"
        (studio / "input").mkdir(parents=True)
        site.mkdir()
        (studio / "input" / "media_manifest.json").write_text(
            json.dumps({"media": [{"asset_id": "selected-media", "url": url, "source_kind": source_kind,
                                   "user_authorized": source_kind == "business", "allowed_for_public_site": source_kind == "business"}]}),
            encoding="utf-8",
        )
        (site / "index.html").write_text(body, encoding="utf-8")
        report = _media_provenance_report(studio_dir=studio, site_dir=site)
        (studio / "media_provenance_report.json").write_text(json.dumps(report), encoding="utf-8")
        return studio, site

    def test_fixture_or_stock_media_blocks_production_promotion(self) -> None:
        for source_kind in ("fixture_stock", "stock"):
            with self.subTest(source_kind=source_kind), tempfile.TemporaryDirectory() as temp:
                studio, site = self._write_provenance_workspace(
                    Path(temp), source_kind=source_kind, body='<img src="https://res.cloudinary.com/siteagent/image/upload/v1/image.jpg">'
                )
                with self.assertRaisesRegex(StudioError, "selected fixture/stock/unverified media"):
                    assert_production_promotion_allowed(studio_dir=studio, site_dir=site)

    def test_verified_business_media_permits_production_promotion(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            studio, site = self._write_provenance_workspace(
                Path(temp), source_kind="business", body='<img src="https://res.cloudinary.com/siteagent/image/upload/v1/image.jpg">'
            )
            assert_production_promotion_allowed(studio_dir=studio, site_dir=site)

    def test_fixture_media_cannot_be_promoted_by_removing_its_provenance_warning(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            studio, site = self._write_provenance_workspace(
                Path(temp),
                source_kind="fixture_stock",
                body='<main><img src="https://res.cloudinary.com/siteagent/image/upload/v1/image.jpg"><p>Customer-facing copy only.</p></main>',
            )
            with self.assertRaisesRegex(StudioError, "selected fixture/stock/unverified media"):
                assert_production_promotion_allowed(studio_dir=studio, site_dir=site)

    def test_production_promotion_rejects_calibration_only_footer_text(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            studio, site = self._write_provenance_workspace(
                Path(temp),
                source_kind="business",
                body='<footer>Fixture-only calibration artifact; do not publish.</footer><img src="https://res.cloudinary.com/siteagent/image/upload/v1/image.jpg">',
            )
            with self.assertRaisesRegex(StudioError, "calibration-only disclosure leaked"):
                assert_production_promotion_allowed(studio_dir=studio, site_dir=site)

    def test_static_build_rejects_local_media_when_manifest_requires_cloudinary(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            studio, site = self._write_provenance_workspace(
                root, source_kind="business", body='<img src="media/local-photo.jpg">'
            )
            with self.assertRaisesRegex(StudioError, "outside the authorised Cloudinary manifest"):
                CodexStudioRunner._validate_authorised_media_rendering(studio, site)

    def test_intermediate_responsive_hero_keeps_type_clear_of_media_and_next_band(self) -> None:
        """A 960px breakpoint must stack the care-map hero without collisions."""
        with tempfile.TemporaryDirectory() as temp:
            page_path = Path(temp) / "index.html"
            page_path.write_text("""<!doctype html><style>
              *{box-sizing:border-box}body{margin:0;font:16px Arial}.hero{padding:32px;background:#101b27;color:#fff}
              .grid{display:grid;grid-template-columns:1fr 1fr;gap:48px}.hero h1{margin:0;font-size:76px;line-height:.9;max-width:9ch}.media{height:420px;background:#1649e8}.next{margin-top:48px;padding-top:24px;border-top:1px solid #789}
              @media(max-width:960px){.grid{grid-template-columns:1fr;gap:42px}.hero h1{font-size:clamp(43px,6.1vw,70px);max-width:12ch}.media{height:330px}}
            </style><main class="hero"><div class="grid"><h1>Dental care starts with the right next question.</h1><div class="media"></div></div><p class="next">Your question comes first.</p></main>""", encoding="utf-8")
            with sync_playwright() as playwright:
                browser = playwright.chromium.launch()
                try:
                    page = browser.new_page(viewport={"width": 960, "height": 1024})
                    page.goto(page_path.resolve().as_uri())
                    heading = page.locator("h1").bounding_box()
                    media = page.locator(".media").bounding_box()
                    next_band = page.locator(".next").bounding_box()
                    self.assertIsNotNone(heading)
                    self.assertIsNotNone(media)
                    self.assertIsNotNone(next_band)
                    self.assertLessEqual(heading["y"] + heading["height"], media["y"])
                    self.assertLessEqual(media["y"] + media["height"], next_band["y"])
                    self.assertFalse(page.evaluate("document.documentElement.scrollWidth > innerWidth + 1"))
                finally:
                    browser.close()

    def test_relative_accepts_a_workspace_relative_path_for_resume_prompts(self) -> None:
        runner = CodexStudioRunner(project_root=Path.cwd(), inspector=StubInspector())
        self.assertEqual(
            runner._relative(Path("runs") / "creative-studio-e2e" / "night_yacht" / "studio" / "art_director_report.json"),
            "runs/creative-studio-e2e/night_yacht/studio/art_director_report.json",
        )

    def test_micro_site_selection_accepts_named_viewport_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            studio = Path(temp) / "studio"
            (studio / "input").mkdir(parents=True)
            (studio / "concept_reviews").mkdir()
            (studio / "concepts" / "concept_a").mkdir(parents=True)
            source = studio / "concepts" / "concept_a" / "index.html"
            source.write_text("<main>micro concept" + "x" * 200 + "</main>", encoding="utf-8")
            (studio / "input" / "concept_contract.json").write_text(json.dumps({"required_concepts": ["concept_a"]}), encoding="utf-8")
            checksum = __import__("hashlib").sha256(source.read_bytes()).hexdigest()
            required = {key: [] for key in ("strengths", "weaknesses", "technical_risks", "visual_risks", "business_risks", "desktop_observations", "mobile_observations", "anti_template_observations")}
            (studio / "concept_reviews" / "comparison.json").write_text(json.dumps({"concept_reviews": {"concept_a": required}}), encoding="utf-8")
            (studio / "concept_reviews" / "selected_concept.json").write_text(json.dumps({
                "selected_concept": "concept_a", "reasons": ["bounded micro scope"], "selected_weaknesses": ["one"],
                "mandatory_improvements": ["one"], "elements_to_preserve": ["one"], "source_concept_checksum": checksum,
                "desktop_screenshot_reference": "concept_a/desktop.png", "mobile_screenshot_reference": "concept_a/mobile.png",
            }), encoding="utf-8")
            self.assertTrue(CodexStudioRunner(project_root=Path.cwd(), inspector=StubInspector())._selection_is_valid(studio))

    def test_effective_micro_scope_is_preserved_when_research_would_allow_full_site(self) -> None:
        research, strategy, spec = fixtures()
        self.assertEqual(assess_studio_readiness(research).page_scope, PageScope.FULL)
        effective = EvidenceAssessment(
            level=EvidenceLevel.B,
            score=100,
            checks={"product_identified": True},
            page_scope=PageScope.MICRO,
            exact_product=research.product_identity.exact_product,
            content_theme_count=3,
            usable_media_count=6,
            required_concepts=1,
        )
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            runner = CodexStudioRunner(project_root=Path.cwd(), inspector=StubInspector())
            studio = root / "studio"
            runner._prepare_input(studio, "scope-test", research, strategy, spec, effective)
            self.assertEqual(runner._stored_readiness(studio).page_scope, PageScope.MICRO)
            folder = root / "site"
            folder.mkdir()
            (folder / "index.html").write_text(
                "<main><section>Offer</section><section>Real proof</section><section>Contact</section></main>",
                encoding="utf-8",
            )
            runner._validate_scope_compliance(studio, folder, effective)
            report = json.loads((studio / "scope_compliance_report.json").read_text(encoding="utf-8"))
            self.assertEqual(report["scope"], "micro_site")
            self.assertTrue(report["approved"])

    def test_fixer_rejects_a_noop_source_change(self) -> None:
        research, strategy, spec = fixtures()
        with tempfile.TemporaryDirectory() as temp:
            run_dir = Path(temp) / "run"
            source = run_dir / "studio" / "selected" / "source"
            source.mkdir(parents=True)
            (source / "index.html").write_text("<html><body>" + "x" * 200 + "</body></html>", encoding="utf-8")
            runner = CodexStudioRunner(project_root=Path.cwd(), command_runner=lambda *args, **kwargs: SimpleNamespace(returncode=0, stdout="", stderr=""), inspector=StubInspector())
            with self.assertRaisesRegex(StudioError, "without changing"):
                runner.revise(run_dir=run_dir, site_dir=run_dir / "site", critique_path=Path("runs/report.json"), checkpoints=lambda *names: None, iteration=1)

    def test_fixed_source_is_not_replaced_by_staging_on_resume(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            runner = CodexStudioRunner(project_root=Path.cwd(), inspector=StubInspector())
            studio = root / "studio"
            source = studio / "selected" / "source"
            staging = studio / "selected" / "staging"
            for folder, label in ((source, "fixed"), (staging, "staging")):
                folder.mkdir(parents=True)
                (folder / "index.html").write_text(f"<html><body>{label}" + "x" * 200 + "</body></html>", encoding="utf-8")
            runner._mark_task(studio, "creative_fixer", "completed")
            self.assertTrue(runner._task_completed(studio, "creative_fixer"))
            self.assertIn("fixed", (source / "index.html").read_text(encoding="utf-8"))

    def test_workspace_has_concepts_screenshots_selection_and_atomic_site_promotion(self) -> None:
        calls = []

        def fake_codex(command, **kwargs):
            calls.append(kwargs["input"])
            prompt = kwargs["input"]
            root = Path.cwd()
            # The bounded prompt always names paths relative to project root.
            if "Create the missing" in prompt:
                run = next(Path("runs").glob("studio-test"), None)
                self.assertIsNotNone(run)
                for name, marker, shape in (("concept_a", "waterline", "<section><p>Different</p></section>"), ("concept_b", "case-file", "<article><blockquote>Different</blockquote></article>"), ("concept_c", "night-index", "<nav><ol><li>Different</li></ol></nav>")):
                    folder = run / "studio" / "concepts" / name
                    folder.mkdir(parents=True, exist_ok=True)
                    (folder / "index.html").write_text(f"<html><body><main class='{marker}'><h1>{marker}</h1>{shape}<a href='https://instagram.com'>Message</a></main></body></html>", encoding="utf-8")
                    (folder / "concept.md").write_text(marker, encoding="utf-8")
            elif "Art Director" in prompt:
                run = next(Path("runs").glob("studio-test"))
                report = run / "studio" / "art_director_report.json"
                report.write_text(json.dumps({"approved": True, "score": 90, "summary": "reviewed screenshots", "unresolved_issues": [], "findings": []}), encoding="utf-8")
            elif "act as Creative Director" in prompt:
                run = next(Path("runs").glob("studio-test"))
                selected = run / "studio" / "concept_reviews" / "selected_concept.json"
                selected.parent.mkdir(parents=True, exist_ok=True)
                checksum = __import__("hashlib").sha256((run / "studio" / "concepts" / "concept_b" / "index.html").read_bytes()).hexdigest()
                selected.write_text(json.dumps({"selected_concept": "concept_b", "reasons": ["strong hierarchy"], "rejected_concepts": ["concept_a", "concept_c"], "screenshot_evidence": ["concept_b/desktop.png"], "selected_weaknesses": ["one"], "mandatory_improvements": ["one"], "elements_to_preserve": ["one"], "source_concept_checksum": checksum}), encoding="utf-8")
                comparison = run / "studio" / "concept_reviews" / "comparison.json"
                structural = json.loads(comparison.read_text(encoding="utf-8"))
                structural["concept_reviews"] = {name: {key: [] for key in ("strengths", "weaknesses", "technical_risks", "visual_risks", "business_risks", "desktop_observations", "mobile_observations", "anti_template_observations")} for name in ("concept_a", "concept_b", "concept_c")}
                comparison.write_text(json.dumps(structural), encoding="utf-8")
            else:
                run = next(Path("runs").glob("studio-test"))
                source = run / "studio" / "selected" / "staging"
                source.mkdir(parents=True, exist_ok=True)
                (source / "index.html").write_text("<html><body><main class='case-file'><h1>Selected</h1><a href='https://instagram.com'>Message</a><section>Offer</section><section>Process</section><section>Proof</section><section>Contact</section></main></body></html>" + " " * 160, encoding="utf-8")
            return SimpleNamespace(returncode=0, stdout="", stderr="")

        research, strategy, spec = fixtures()
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            # Studio's skills are project-owned; point at the real repository while artifacts are isolated.
            runner = CodexStudioRunner(project_root=Path.cwd(), command_runner=fake_codex, inspector=StubInspector())
            run_dir = Path.cwd() / "runs" / "studio-test"
            if run_dir.exists():
                import shutil
                shutil.rmtree(run_dir)
            checkpoints: list[str] = []
            try:
                result = runner.build(run_dir=run_dir, site_dir=run_dir / "site", job_id="studio-test", research=research, strategy=strategy, spec=spec, evidence={"level": "A"}, checkpoints=lambda *names: checkpoints.extend(names))
                self.assertEqual(result.selected_concept, "concept_b")
                self.assertTrue((run_dir / "site" / "index.html").is_file())
                self.assertTrue((run_dir / "studio" / "concept_reviews" / "concept_a" / "desktop.png").is_file())
                self.assertTrue((run_dir / "studio" / "concept_reviews" / "concept_c" / "mobile.png").is_file())
                self.assertIn("concept_selected", checkpoints)
                self.assertTrue(any("$siteagent-web-studio" in prompt for prompt in calls))
            finally:
                import shutil
                shutil.rmtree(run_dir, ignore_errors=True)

    def test_similarity_gate_rejects_palette_or_text_only_variants(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            studio = Path(temp) / "studio"
            for name in ("concept_a", "concept_b", "concept_c"):
                folder = studio / "concepts" / name
                folder.mkdir(parents=True)
                (folder / "index.html").write_text("<html><body><main><h1>Same layout</h1></main></body></html>", encoding="utf-8")
            comparison = CodexStudioRunner(project_root=Path.cwd(), inspector=StubInspector())._compare_concepts(studio)
            self.assertFalse(comparison["materially_different"])
            self.assertIn("palette/text-only", " ".join(comparison["reasons"]))

    def test_plugin_bundle_is_identical_to_repository_skills(self) -> None:
        self.assertEqual(validate_studio_plugin_bundle(Path.cwd()), [])

    def test_botanika_fixture_media_is_explicit_stock_not_portfolio_proof(self) -> None:
        floral_research, _, _ = rich_floral_fixture()
        self.assertEqual(len(floral_research.best_media), 6)
        for media in floral_research.best_media:
            self.assertEqual(media.source_kind, "fixture_stock")
            self.assertTrue(media.asset_id)
            self.assertTrue(media.source_url.startswith("https://unsplash.com/photos/"))
            self.assertIn("not Botanika Form portfolio", media.provenance_note)
            self.assertFalse(media.portfolio_claim)

    def test_harbour_dental_is_a_rich_english_fixture_not_a_production_media_candidate(self) -> None:
        research, strategy, spec = rich_dental_fixture()
        readiness = assess_studio_readiness(research)
        self.assertEqual(readiness.page_scope, PageScope.FULL)
        self.assertEqual(research.primary_language, "en")
        self.assertIn("routine hygiene", research.product_identity.exact_product)
        self.assertGreaterEqual(len(research.content_themes), 5)
        self.assertEqual(len(research.best_media), 6)
        self.assertEqual(spec.primary_cta, "Request a consultation")
        self.assertNotIn("Botanika Form", spec.h1)
        self.assertTrue(all(item.source_kind == "fixture_stock" for item in research.best_media))
        self.assertTrue(all(not item.portfolio_claim for item in research.best_media))
        self.assertTrue(all("not Harbour Dental clinical work" in item.provenance_note for item in research.best_media))
        self.assertIn("Controlled fixture only", spec.footer_note)

    def test_media_provenance_report_tracks_used_fixture_assets_by_final_hash(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            run_dir = Path(temp) / "fixture"
            studio = run_dir / "studio"
            (studio / "input").mkdir(parents=True)
            (run_dir / "site").mkdir()
            used = "https://images.example/used.jpg"
            (studio / "input" / "media_manifest.json").write_text(json.dumps({"media": [
                {"asset_id": "used", "url": used, "source_kind": "fixture_stock", "portfolio_claim": False},
                {"asset_id": "unused", "url": "https://images.example/unused.jpg", "source_kind": "fixture_stock", "portfolio_claim": False},
            ]}), encoding="utf-8")
            (run_dir / "site" / "index.html").write_text(f'<img src="{used}">', encoding="utf-8")
            report = _write_media_provenance_report(run_dir)
            self.assertEqual(report["used_asset_count"], 1)
            self.assertTrue(report["production_media_blocked"])
            self.assertEqual([item["status"] for item in report["assets"]], ["used", "not_used"])
            self.assertTrue((studio / "media_provenance_report.json").is_file())

    def test_creative_source_has_no_category_layout_map_or_jinja_renderer(self) -> None:
        source = (Path("site_agent") / "studio.py").read_text(encoding="utf-8").lower()
        self.assertNotIn("compose_page(", source)
        self.assertNotIn("sitebuilder", source)
        self.assertNotIn("category ==", source)


if __name__ == "__main__":
    unittest.main()
