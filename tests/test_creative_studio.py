from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from site_agent.models import ContentTheme, MediaAsset, ProductIdentity, ResearchBrief, SectionSpec, SiteSpec, StrategyBrief, TechnicalGate
from site_agent.skill_lock import validate_studio_plugin_bundle
from site_agent.studio import CodexStudioRunner, StudioError


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
    def test_relative_accepts_a_workspace_relative_path_for_resume_prompts(self) -> None:
        runner = CodexStudioRunner(project_root=Path.cwd(), inspector=StubInspector())
        self.assertEqual(
            runner._relative(Path("runs") / "creative-studio-e2e" / "night_yacht" / "studio" / "art_director_report.json"),
            "runs/creative-studio-e2e/night_yacht/studio/art_director_report.json",
        )

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

    def test_creative_source_has_no_category_layout_map_or_jinja_renderer(self) -> None:
        source = (Path("site_agent") / "studio.py").read_text(encoding="utf-8").lower()
        self.assertNotIn("compose_page(", source)
        self.assertNotIn("sitebuilder", source)
        self.assertNotIn("category ==", source)


if __name__ == "__main__":
    unittest.main()
