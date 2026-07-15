"""Opt-in real-Codex fixture calibration; never claims Telegram jobs or publishes."""
from __future__ import annotations

import html
import json
import os
import shutil
from pathlib import Path

from site_agent.models import MediaAsset, ResearchBrief, SectionSpec, SiteSpec, StrategyBrief
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


def _write_comparison_page(root: Path, results: dict) -> None:
    cards = []
    for name, result in results.items():
        base = Path("..") / name / "studio"
        selected = result.get("selected_concept", "not selected")
        images = "".join(f'<img src="{html.escape(str(base / "concept_reviews" / concept / "desktop.png"))}" alt="{concept} desktop">' for concept in ("concept_a", "concept_b", "concept_c"))
        cards.append(f"<article><h2>{html.escape(name)}</h2><p>Status: {html.escape(result['status'])}; selected: {html.escape(selected)}</p><div class='grid'>{images}</div><p><a href='{html.escape(str(base / "full_build_visuals" / "desktop.png"))}'>Final desktop</a> · <a href='{html.escape(str(base / "full_build_visuals" / "mobile.png"))}'>Final mobile</a> · <a href='{html.escape(str(base / "art_director_report.json"))}'>Art Director report</a></p></article>")
    page = "<!doctype html><html lang='en'><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'><title>Creative Studio calibration</title><style>body{font:16px/1.5 system-ui;margin:0;background:#141414;color:#f7f4ee}main{max-width:1500px;margin:auto;padding:32px}.grid{display:grid;grid-template-columns:repeat(3,1fr);gap:12px}img{width:100%;border:1px solid #555}article{border-top:1px solid #555;padding:28px 0}a{color:#ffd27a}@media(max-width:760px){.grid{grid-template-columns:1fr}}</style><main><h1>Creative Studio calibration — human review required</h1><p>These are local, opt-in Codex fixture artifacts. No Telegram or Cloudflare operation has run.</p>" + "".join(cards) + "</main></html>"
    (root / "comparison" / "index.html").write_text(page, encoding="utf-8")


if __name__ == "__main__":
    print(json.dumps(run_all(), ensure_ascii=False, indent=2))
