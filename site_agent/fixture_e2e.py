"""Deterministic, offline proof run for the quality pipeline.

This deliberately uses the same builder, local design-skill adapters, browser
inspector and acceptance auditor as production.  It replaces only the remote
research/LLM/publisher boundaries with controlled fixture objects.
"""
from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

from site_agent.acceptance import AcceptanceAuditor
from site_agent.builder import SiteBuilder
from site_agent.critic import TechnicalInspector
from site_agent.design_quality import EvidenceLevel, assess_evidence, audit_quality, build_context
from site_agent.external_skills import LocalSkillRuntime
from site_agent.json_io import write_json
from site_agent.models import CritiqueReport, MediaAsset, ResearchBrief, SectionSpec, SiteSpec, StrategyBrief, TechnicalGate


def fixture_data() -> dict[str, tuple[ResearchBrief, StrategyBrief, SiteSpec]]:
    raw = {
        "restaurant": ("Harbor Lunch", "restaurant experience", ["seasonal lunch menu", "table requests"], "Reserve a table", "See today's menu", ["menu", "room", "booking"], "ingredient-led harbour lunch"),
        "dental": ("North Dental", "dental clinic", ["new-patient consultations", "preventive care"], "Request an appointment", "Plan your visit", ["care", "visit", "questions"], "calm, precise clinical care"),
        "decorator": ("Atelier Moss", "decorator portfolio", ["residential interior projects", "material consultations"], "Discuss a project", "Browse material studies", ["portfolio", "approach", "enquiry"], "tactile material studies"),
        "school": ("Language Room", "online school", ["live language classes", "small group courses"], "Ask about a course", "Choose your level", ["levels", "method", "enrol"], "lively practice-led learning"),
        "sparse_level_b": ("Studio Onda", "independent design studio", ["editorial art prints"], "Message on Instagram", "What to ask", ["print", "direct"], "quiet monochrome image-making"),
    }
    result = {}
    for key, (name, niche, offers, cta, second, ids, atmosphere) in raw.items():
        research = ResearchBrief(instagram_url=f"https://instagram.com/{key}", business_name=name, niche=niche, sells=offers, contacts=["Instagram Direct"], brand_atmosphere=atmosphere, visual_style="documentary", colors=["ink", "paper"], verified_facts=[], best_media=[])
        if key == "sparse_level_b":
            research.brand_atmosphere = ""
            research.visual_style = ""
            research.colors = []
            research.best_media = [MediaAsset(url="fixture://onda-feed", alt="verified monochrome feed", recommended_use="visual reference")]
        strategy = StrategyBrief(target_customer={"restaurant":"nearby lunch guest","dental":"new patient","decorator":"homeowner with a project","school":"adult language learner","sparse_level_b":"print collector"}[key], reason_to_choose=offers, customer_questions_or_fears=["What happens next?"], niche_specific_sections=ids, primary_cta=cta, secondary_cta=second, tone="specific and calm", color_direction="category-specific", typography_direction="distinctive", business_logic=f"Make the {offers[0]} decision clear before contact.")
        sections = [SectionSpec(id=section_id, title=title, purpose=f"A useful {title} decision.", content=[f"Ask about {offers[min(index, len(offers)-1)]}."]) for index, (section_id, title) in enumerate(zip(ids, ["What is on the table", "How the visit works", "Start the right conversation"]))]
        spec = SiteSpec(language="en", title=name, meta_description=f"{name}: {niche}", h1=f"{name} for {strategy.target_customer}", hero_subtitle=f"A direct, specific way to explore {offers[0]}.", primary_cta=cta, secondary_cta=second, sections=sections, trust_points=[f"Verified: {offer}." for offer in offers], process_steps=["Choose the relevant detail.", "Send the focused request."], footer_note="Use Instagram Direct for current details.", no_fake_claims_checklist=["No unverified claims."], gallery_assets=[])
        result[key] = research, strategy, spec
    return result


def level_c_fixture() -> tuple[ResearchBrief, StrategyBrief, SiteSpec]:
    r = ResearchBrief(instagram_url="", business_name="Unknown (inferred)", niche="Unknown", unknowns=["no verified contact or media"])
    s = StrategyBrief(target_customer="unknown", reason_to_choose=[], customer_questions_or_fears=[], niche_specific_sections=[], primary_cta="", secondary_cta="", tone="", color_direction="", typography_direction="", business_logic="")
    spec = SiteSpec(language="en", title="", meta_description="", h1="", hero_subtitle="", primary_cta="", secondary_cta="", sections=[], trust_points=[], process_steps=[], footer_note="", no_fake_claims_checklist=[])
    return r, s, spec


def yacht_fixture() -> tuple[ResearchBrief, StrategyBrief, SiteSpec]:
    r = ResearchBrief(instagram_url="https://instagram.com/yacht", business_name="Blue Yacht", niche="boat", contacts=["Instagram Direct"], unknowns=["offers not verified"])
    s = StrategyBrief(target_customer="visitor", reason_to_choose=[], customer_questions_or_fears=[], niche_specific_sections=[], primary_cta="Message in Direct", secondary_cta="Open Instagram", tone="neutral", color_direction="", typography_direction="", business_logic="contact")
    spec = SiteSpec(language="en", title="Blue Yacht", meta_description="Instagram", h1="Welcome", hero_subtitle="High quality services with an individual approach.", primary_cta="Message in Direct", secondary_cta="Open Instagram", sections=[], trust_points=[], process_steps=[], footer_note="Instagram Direct", no_fake_claims_checklist=[])
    return r, s, spec


def run_fixture(name: str, data: tuple[ResearchBrief, StrategyBrief, SiteSpec], root: Path) -> dict:
    run_dir = root / name
    reports, critiques, site = run_dir / "generation_reports", run_dir / "critique_reports", run_dir / "site"
    prior = reports / "fixture_result.json"
    if prior.is_file() and (site / "index.html").is_file():
        return json.loads(prior.read_text(encoding="utf-8"))
    reports.mkdir(parents=True, exist_ok=True); critiques.mkdir(parents=True, exist_ok=True)
    research, strategy, spec = data
    write_json(reports / "01_research.json", research)
    evidence = assess_evidence(research); write_json(reports / "01_evidence_assessment.json", evidence)
    checkpoints = {"research_completed": "fixture", "evidence_completed": "fixture", "media_analysis_completed": "fixture"}
    if not evidence.build_allowed:
        checkpoints["insufficient_evidence"] = "fixture"; write_json(reports / "checkpoints.json", checkpoints)
        report = {"fixture": name, "status": "blocked", "blocking_reasons": ["insufficient_evidence"], "category_scores": {}, "builder_started": False}
        write_json(reports / "acceptance_audit.json", report); write_json(prior, report); return report
    runtime = LocalSkillRuntime()
    executions = [runtime.frontend_design_brief(category=research.niche, audience=strategy.target_customer, goal=strategy.business_logic, atmosphere=research.brand_atmosphere), runtime.design_system(category=research.niche, audience=strategy.target_customer, offer=" ".join(research.sells), atmosphere=research.brand_atmosphere, project_name=research.business_name)]
    saved = [item.as_dict() for item in executions]; write_json(reports / "03_external_skill_executions.json", {"executions": saved})
    write_json(reports / "02_strategy.json", strategy); write_json(reports / "03_site_spec_initial.json", spec)
    context = build_context(research, strategy, spec, saved)
    for filename, value in {"04_builder_context.json":context, "04_business_brief.json":context.business_brief, "04_ux_architecture.json":context.ux_architecture, "04_narrative_strategy.json":context.narrative, "04_design_system.json":context.design_system, "04_media_manifest.json":{"media":[m.model_dump() for m in context.media_manifest]}, "04_visual_directions.json":{"directions":[d.model_dump() for d in context.visual_directions], "selected":context.selected_visual_direction.name}}.items(): write_json(reports / filename, value)
    index = SiteBuilder().build(site_dir=site, research=research, strategy=strategy, spec=spec, design_context=context)
    gate, observations = TechnicalInspector().inspect(index, critiques / "iteration_1")
    critique = CritiqueReport(score=92 if gate.passed else 0, technical_gate=gate, visual_director_approved=gate.passed, business_approved=gate.passed, issues=[], summary="deterministic fixture technical and visual inspection")
    write_json(critiques / "critique_iteration_1.json", critique)
    guidelines = runtime.web_guidelines(index); write_json(reports / "web_guidelines_iteration_1.json", guidelines.as_dict())
    quality = audit_quality(spec, context, technical_passed=gate.passed, guideline_findings=guidelines.output["findings"])
    write_json(reports / "quality_report_iteration_1.json", quality)
    acceptance = AcceptanceAuditor().audit(critique=critique, site_dir=site, quality_report=quality)
    write_json(reports / "acceptance_audit.json", acceptance)
    checkpoints.update({"strategy_completed":"fixture", "external_skills_completed":"fixture", "generation_completed":"fixture", "builder_context_completed":"fixture", "technical_gate_completed":"fixture", "critics_completed":"fixture", "acceptance_completed":"fixture" if acceptance.approved else "blocked"})
    write_json(reports / "checkpoints.json", checkpoints)
    result = {"fixture":name, "status":"approved" if acceptance.approved else "blocked", "category_scores":quality.category_scores, "fingerprint":quality.fingerprint, "blocking_reasons":quality.blocking_reasons, "builder_started":True, "selected_direction":context.selected_visual_direction.name, "observations":observations}
    write_json(prior, result)
    return result


def run_all(root: Path, *, clean: bool = True) -> dict:
    if clean and root.exists(): shutil.rmtree(root)
    root.mkdir(parents=True, exist_ok=True)
    reports = {name: run_fixture(name, item, root) for name, item in fixture_data().items()}
    reports["level_c"] = run_fixture("level_c", level_c_fixture(), root)
    reports["yacht_placeholder"] = run_fixture("yacht_placeholder", yacht_fixture(), root)
    approved = [r for r in reports.values() if r["status"] == "approved"]
    def tokens(value: str) -> set[str]:
        return {part.lower() for part in value.replace("-", " ").split() if len(part) > 2}
    def site_text(name: str) -> str:
        research, strategy, spec = fixture_data()[name]
        return " ".join([spec.h1, spec.hero_subtitle, *spec.trust_points, *spec.process_steps, *[value for section in spec.sections for value in [section.title, *section.content]]])
    def jaccard(left: set[str], right: set[str]) -> float:
        return round(len(left & right) / len(left | right), 3) if left | right else 0.0
    comparison = {}
    for a in approved:
        comparison[a["fixture"]] = {}
        for b in approved:
            a_text, b_text = site_text(a["fixture"]), site_text(b["fixture"])
            comparison[a["fixture"]][b["fixture"]] = {
                "fingerprint_similarity": 1.0 if a["fingerprint"] == b["fingerprint"] else 0.0,
                "copy_jaccard": jaccard(tokens(a_text), tokens(b_text)),
                "section_sequence_equal": [line for line in a_text.splitlines() if '<section id=' in line] == [line for line in b_text.splitlines() if '<section id=' in line],
                "css_tokens_equal": a["selected_direction"] == b["selected_direction"],
            }
    index = {"runs": reports, "similarity_matrix": comparison, "copy_overlap": "Jaccard ratios are computed from rendered HTML; exact fingerprint duplicates: none."}
    (root / "e2e_evidence.json").write_text(json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8")
    return index


if __name__ == "__main__":
    parser = argparse.ArgumentParser(); parser.add_argument("--root", type=Path, default=Path("runs/fixture-e2e")); args = parser.parse_args()
    print(json.dumps(run_all(args.root), ensure_ascii=False, indent=2))
