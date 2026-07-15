"""Opt-in real-Codex fixture calibration; never claims Telegram jobs or publishes."""
from __future__ import annotations

import html
import json
import os
import shutil
import argparse
from pathlib import Path

from site_agent.models import MediaAsset, ResearchBrief, SectionSpec, SiteSpec, StrategyBrief
from site_agent.config import settings
from site_agent.studio import CodexStudioRunner, StudioError


def _fixture(name: str, niche: str, offer: str, atmosphere: str, cta: str, media: list[str]):
    research = ResearchBrief(
        instagram_url=f"https://www.instagram.com/{name}/",
        business_name=name.replace("_", " ").title(), niche=niche, sells=[offer], contacts=["Instagram Direct"],
        brand_atmosphere=atmosphere, best_media=[MediaAsset(url=url, alt=f"Verified {name} visual", recommended_use="hero or narrative media") for url in media],
        verified_facts=[], unknowns=["Current availability, prices and exact location require confirmation in Direct."],
        forbidden_claims=["Do not claim awards, capacity, results, pricing or availability not present in this fixture."],
    )
    strategy = StrategyBrief(
        target_customer="a prospective customer", reason_to_choose=[offer], customer_questions_or_fears=["What is the right next step?"],
        niche_specific_sections=["decision support"], primary_cta=cta, secondary_cta="See the approach", tone="specific and grounded",
        color_direction="derive from verified media", typography_direction="derive from the creative idea", business_logic="clarify the offer and start a Direct conversation",
    )
    spec = SiteSpec(
        language="en", title=research.business_name, meta_description=f"{offer}. Confirm current details in Direct.",
        h1=research.business_name, hero_subtitle=f"{offer}. Ask for current details in Direct.", primary_cta=cta,
        secondary_cta="See the approach", sections=[SectionSpec(id="offer", title="What to ask about", purpose="Give a visitor a grounded next step.", content=[offer])],
        trust_points=["Current details are confirmed directly."], process_steps=["Start a Direct conversation."],
        gallery_assets=research.best_media, footer_note="Use Instagram Direct for current details.", no_fake_claims_checklist=[],
    )
    return research, strategy, spec


def fixture_data():
    return {
        "night_yacht": _fixture("night_yacht", "night yacht experience", "Private evening water experiences", "nocturnal, reflective, cinematic", "Ask about an evening", ["https://images.unsplash.com/photo-1567899378494-47b22a2ae96a?auto=format&fit=crop&w=1600&q=80"]),
        "modern_dental": _fixture("modern_dental", "modern dentistry", "Consultation-led dental care", "precise, calm, clinical", "Request a consultation", ["https://images.unsplash.com/photo-1606811971618-4486d14f3f99?auto=format&fit=crop&w=1600&q=80"]),
        "event_decorator": _fixture("event_decorator", "event decoration portfolio", "Spatial event decoration projects", "expressive, layered, tactile", "Discuss a project", ["https://images.unsplash.com/photo-1519167758481-83f550bb49b3?auto=format&fit=crop&w=1600&q=80"]),
        "online_school": _fixture("online_school", "online learning platform", "Live learning with a practical platform", "clear, focused, encouraging", "Ask about a course", ["https://images.unsplash.com/photo-1522202176988-66273c2fd55f?auto=format&fit=crop&w=1600&q=80"]),
    }


def run_all(root: Path = Path("runs/creative-studio-e2e"), *, clean: bool = False) -> dict:
    if os.getenv("CODEX_CREATIVE_E2E") != "1":
        return {"status": "skipped", "reason": "Set CODEX_CREATIVE_E2E=1 to use the local Codex creative runner."}
    if clean and root.exists():
        shutil.rmtree(root)
    root.mkdir(parents=True, exist_ok=True)
    runner = CodexStudioRunner()
    results = {}
    for name, (research, strategy, spec) in fixture_data().items():
        run_dir = root / name
        reports = run_dir / "generation_reports"
        reports.mkdir(parents=True, exist_ok=True)
        checkpoints = {}
        try:
            result = runner.build(
                run_dir=run_dir, site_dir=run_dir / "site", job_id=name, research=research, strategy=strategy,
                spec=spec, evidence={"level": "A", "fixture": True}, checkpoints=lambda *names: checkpoints.update({item: "fixture" for item in names}),
            )
            (reports / "checkpoints.json").write_text(json.dumps(checkpoints, indent=2), encoding="utf-8")
            results[name] = {"status": "completed", "selected_concept": result.selected_concept, "studio": str(result.studio_dir), "final": str(result.index_path)}
        except StudioError as exc:
            (reports / "checkpoints.json").write_text(json.dumps(checkpoints, indent=2), encoding="utf-8")
            results[name] = {"status": "failed_retryable", "reason": str(exc)}
    comparison = {"calibration_required": True, "runs": results}
    (root / "comparison").mkdir(exist_ok=True)
    (root / "comparison" / "comparison.json").write_text(json.dumps(comparison, ensure_ascii=False, indent=2), encoding="utf-8")
    _write_comparison_page(root, results)
    return comparison


def run_one(name: str, root: Path = Path("runs/creative-studio-e2e")) -> dict:
    """Resume exactly one existing fixture workspace; never create peer fixtures."""
    if os.getenv("CODEX_CREATIVE_E2E") != "1":
        return {"status": "skipped", "reason": "Set CODEX_CREATIVE_E2E=1 to use the local Codex creative runner."}
    fixtures = fixture_data()
    if name not in fixtures:
        raise ValueError(f"Unknown fixture: {name}")
    run_dir = root / name
    if not run_dir.is_dir():
        raise ValueError(f"Existing fixture run not found: {run_dir}")
    reports = run_dir / "generation_reports"
    reports.mkdir(parents=True, exist_ok=True)
    checkpoints_path = reports / "checkpoints.json"
    try:
        checkpoints = json.loads(checkpoints_path.read_text(encoding="utf-8")) if checkpoints_path.is_file() else {}
    except ValueError:
        checkpoints = {}

    def checkpoint(*names: str) -> None:
        checkpoints.update({item: "fixture_resume" for item in names})
        checkpoints_path.write_text(json.dumps(checkpoints, ensure_ascii=False, indent=2), encoding="utf-8")

    research, strategy, spec = fixtures[name]
    runner = CodexStudioRunner()
    try:
        result = runner.build(
            run_dir=run_dir, site_dir=run_dir / "site", job_id=name, research=research, strategy=strategy,
            spec=spec, evidence={"level": "A", "fixture": True}, checkpoints=checkpoint,
        )
    except StudioError as exc:
        return {"status": "failed_retryable", "fixture": name, "reason": str(exc), "run": str(run_dir)}
    report_path = run_dir / "studio" / "art_director_report.json"
    report = json.loads(report_path.read_text(encoding="utf-8"))
    blocking = (not report["approved"]) or any(
        item.get("severity") in {"critical", "high"} for item in report["findings"]
    )
    task_state_path = run_dir / "studio" / "task_state.json"
    task_state = json.loads(task_state_path.read_text(encoding="utf-8")) if task_state_path.is_file() else {}
    # A completed-looking review cannot close an interrupted or no-op fixer.
    if task_state.get("creative_fixer", {}).get("status") != "completed" and (run_dir / "studio" / "fixer_history").exists():
        blocking = True
    fixer_iterations: list[int] = []
    for iteration in range(1, settings.max_fix_iterations + 1):
        if not blocking:
            break
        history = run_dir / "studio" / "fixer_history" / f"iteration_{iteration}"
        before = history / "before"
        before.mkdir(parents=True, exist_ok=True)
        for artifact in ("desktop.png", "tablet.png", "mobile.png", "technical_gate.json", "observations.json"):
            source = run_dir / "studio" / "final_reviews" / artifact
            if source.is_file():
                shutil.copy2(source, before / artifact)
        shutil.copy2(report_path, before / "art_director_report.json")
        runner.revise(
            run_dir=run_dir, site_dir=run_dir / "site", critique_path=report_path,
            checkpoints=checkpoint, iteration=iteration,
        )
        report = runner.review_art_director(run_dir=run_dir, checkpoints=checkpoint)
        report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        final_after = history / "after"
        final_after.mkdir(parents=True, exist_ok=True)
        for artifact in ("desktop.png", "tablet.png", "mobile.png", "technical_gate.json", "observations.json"):
            source = run_dir / "studio" / "final_reviews" / artifact
            if source.is_file():
                shutil.copy2(source, final_after / artifact)
        fixer_iterations.append(iteration)
        blocking = (not report["approved"]) or any(item.get("severity") in {"critical", "high"} for item in report["findings"])
    if blocking:
        return {"status": "failed_creative_quality", "fixture": name, "selected_concept": result.selected_concept, "run": str(run_dir), "art_director_report": str(report_path), "fixer_iterations": fixer_iterations}
    calibration = _write_calibration_package(run_dir, result.selected_concept, report)
    return {
        "status": "completed_human_calibration_required",
        "fixture": name,
        "selected_concept": result.selected_concept,
        "run": str(run_dir),
        "site": str(result.index_path),
        "fixer_iterations": fixer_iterations,
        **calibration,
    }


def _write_comparison_page(root: Path, results: dict) -> None:
    cards = []
    for name, result in results.items():
        base = Path("..") / name / "studio"
        selected = result.get("selected_concept", "not selected")
        images = "".join(f'<img src="{html.escape(str(base / "concept_reviews" / concept / "desktop.png"))}" alt="{concept} desktop">' for concept in ("concept_a", "concept_b", "concept_c"))
        cards.append(f"<article><h2>{html.escape(name)}</h2><p>Status: {html.escape(result['status'])}; selected: {html.escape(selected)}</p><div class='grid'>{images}</div><p><a href='{html.escape(str(base / "full_build_visuals" / "desktop.png"))}'>Final desktop</a> · <a href='{html.escape(str(base / "full_build_visuals" / "mobile.png"))}'>Final mobile</a> · <a href='{html.escape(str(base / "art_director_report.json"))}'>Art Director report</a></p></article>")
    page = "<!doctype html><html lang='en'><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'><title>Creative Studio calibration</title><style>body{font:16px/1.5 system-ui;margin:0;background:#141414;color:#f7f4ee}main{max-width:1500px;margin:auto;padding:32px}.grid{display:grid;grid-template-columns:repeat(3,1fr);gap:12px}img{width:100%;border:1px solid #555}article{border-top:1px solid #555;padding:28px 0}a{color:#ffd27a}@media(max-width:760px){.grid{grid-template-columns:1fr}}</style><main><h1>Creative Studio calibration — human review required</h1><p>These are local, opt-in Codex fixture artifacts. No Telegram or Cloudflare operation has run.</p>" + "".join(cards) + "</main></html>"
    (root / "comparison" / "index.html").write_text(page, encoding="utf-8")


def _write_calibration_package(run_dir: Path, selected: str, report: dict) -> dict:
    """Build a local, evidence-only board for the required human calibration stop."""
    calibration = run_dir / "calibration"
    calibration.mkdir(parents=True, exist_ok=True)
    studio = run_dir / "studio"
    selected_data = json.loads((studio / "concept_reviews" / "selected_concept.json").read_text(encoding="utf-8"))
    comparison = json.loads((studio / "concept_reviews" / "comparison.json").read_text(encoding="utf-8"))
    concepts = []
    for concept in ("concept_a", "concept_b", "concept_c"):
        idea = (studio / "concepts" / concept / "concept.md").read_text(encoding="utf-8")
        concepts.append(
            "<section><h2>{}</h2><p>{}</p><div class='pair'><img src='../studio/concept_reviews/{}/desktop.png' alt='{} desktop'><img src='../studio/concept_reviews/{}/mobile.png' alt='{} mobile'></div></section>".format(
                html.escape(concept.replace("_", " ").upper()), html.escape(idea), concept, concept, concept, concept
            )
        )
    reasons = "".join(f"<li>{html.escape(str(item))}</li>" for item in selected_data.get("reasons", []))
    findings = "".join(
        "<li><strong>{}</strong> — {} ({}, {})</li>".format(
            html.escape(str(item.get("severity", "unknown"))), html.escape(str(item.get("description", item.get("reason", "")))),
            html.escape(str(item.get("screenshot", ""))), html.escape(str(item.get("screenshot_region", ""))),
        ) for item in report.get("findings", [])
    ) or "<li>No Art Director findings recorded.</li>"
    before = f"../studio/concept_reviews/{selected}/desktop.png"
    fixer_before = studio / "fixer_history" / "iteration_1" / "before" / "desktop.png"
    fixer_after = studio / "fixer_history" / "iteration_1" / "after" / "desktop.png"
    fixer_block = ""
    if fixer_before.is_file() and fixer_after.is_file():
        fixer_block = "<h3>Creative fixer — before / after</h3><div class='pair'><img src='../studio/fixer_history/iteration_1/before/desktop.png' alt='Before fixer desktop'><img src='../studio/fixer_history/iteration_1/after/desktop.png' alt='After fixer desktop'></div><div class='pair'><img src='../studio/fixer_history/iteration_1/before/mobile.png' alt='Before fixer mobile'><img src='../studio/fixer_history/iteration_1/after/mobile.png' alt='After fixer mobile'></div>"
    page = """<!doctype html><html lang='en'><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>
<title>Night Yacht — human calibration</title><style>body{margin:0;background:#111;color:#f3efe4;font:16px/1.5 system-ui}main{max-width:1600px;margin:auto;padding:32px}h1{font-size:clamp(2rem,5vw,5rem);line-height:1;margin:0 0 16px}.pair{display:grid;grid-template-columns:3fr 1fr;gap:16px}.pair img,.final img{width:100%;height:auto;border:1px solid #555;background:#222}section{border-top:1px solid #555;padding:28px 0}.final{display:grid;gap:16px}.note{color:#f98d5d}@media(max-width:760px){main{padding:18px}.pair{grid-template-columns:1fr}}</style><main>
<p class='note'>Human calibration required — no Telegram or Cloudflare action was run.</p><h1>Night Yacht<br>Creative Studio review</h1>
<section><h2>Concept stage</h2><p>Selected: <strong>__SELECTED__</strong></p><ul>__REASONS__</ul>__CONCEPTS__</section>
<section class='final'><h2>Final stage</h2><p>Selected concept before extension</p><img src='__BEFORE__' alt='Selected concept before full build'><p>Full build — desktop</p><img src='../studio/final_reviews/desktop.png' alt='Final desktop'><p>Full build — mobile</p><img src='../studio/final_reviews/mobile.png' alt='Final mobile'>__FIXER__<h3>Art Director</h3><p>Score: __SCORE__. __SUMMARY__</p><ul>__FINDINGS__</ul><h3>Unresolved medium/low issues</h3><pre>__UNRESOLVED__</pre></section>
</main></html>""".replace("__SELECTED__", html.escape(selected)).replace("__REASONS__", reasons).replace("__CONCEPTS__", "".join(concepts)).replace("__BEFORE__", before).replace("__FIXER__", fixer_block).replace("__SCORE__", html.escape(str(report.get("score", "unscored")))).replace("__SUMMARY__", html.escape(str(report.get("summary", "")))).replace("__FINDINGS__", findings).replace("__UNRESOLVED__", html.escape(json.dumps(report.get("unresolved_issues", []), ensure_ascii=False, indent=2)))
    index = calibration / "index.html"
    index.write_text(page, encoding="utf-8")
    from playwright.sync_api import sync_playwright
    png = calibration / "night_yacht_calibration.png"
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        try:
            page_object = browser.new_page(viewport={"width": 1600, "height": 1200})
            page_object.goto(index.resolve().as_uri(), wait_until="networkidle")
            page_object.screenshot(path=png, full_page=True)
        finally:
            browser.close()
    return {"calibration_page": str(index), "calibration_png": str(png), "comparison_reviews": comparison.get("concept_reviews", {})}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--resume", metavar="FIXTURE", help="Resume exactly one existing fixture run.")
    args = parser.parse_args()
    result = run_one(args.resume) if args.resume else run_all()
    print(json.dumps(result, ensure_ascii=False, indent=2))
