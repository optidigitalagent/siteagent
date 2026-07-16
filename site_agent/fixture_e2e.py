"""Deterministic, offline proof run for the quality pipeline.

This deliberately uses the same builder, local design-skill adapters, browser
inspector and acceptance auditor as production.  It replaces only the remote
research/LLM/publisher boundaries with controlled fixture objects.
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
from difflib import SequenceMatcher
from html.parser import HTMLParser
from pathlib import Path

from site_agent.acceptance import AcceptanceAuditor
from site_agent.builder import SiteBuilder
from site_agent.critic import TechnicalInspector
from site_agent.design_quality import EvidenceLevel, assess_evidence, audit_quality, build_context, composition_similarity, meaningful_phrases
from site_agent.external_skills import LocalSkillRuntime
from site_agent.json_io import write_json
from site_agent.models import ContentTheme, CritiqueReport, MediaAsset, ProductIdentity, ResearchBrief, SectionSpec, SiteSpec, StrategyBrief, TechnicalGate


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
        research = ResearchBrief(instagram_url=f"https://instagram.com/{key}", business_name=name, primary_language="en", niche=niche, sells=offers, contacts=["Instagram Direct"], brand_atmosphere=atmosphere, visual_style="documentary", colors=["ink", "paper"], verified_facts=[], product_identity=ProductIdentity(exact_product=offers[0], evidence_sources=[f"fixture:{key}:product"], confidence="high"), content_themes=[ContentTheme(label=section_id, decision_role=role, evidence_sources=[f"fixture:{key}:{section_id}"]) for section_id, role in zip(ids, ("offer", "process", "proof"))], best_media=[MediaAsset(url=f"https://media.example/{key}/{index}.jpg", alt=f"{name} controlled media {index}", recommended_use="narrative media", width=1600, height=1067) for index in range(6)])
        if key == "sparse_level_b":
            research.brand_atmosphere = ""
            research.visual_style = ""
            research.colors = []
            research.content_themes = [ContentTheme(label="editorial art prints", decision_role="offer", evidence_sources=["fixture:onda:prints"])]
            research.best_media = [MediaAsset(url="https://media.example/onda-feed.jpg", alt="verified monochrome feed", recommended_use="visual reference", width=1200, height=900)]
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
    design_dir = run_dir / "design"; design_dir.mkdir(exist_ok=True)
    write_json(design_dir / "page_composition.json", context.page_composition)
    index = SiteBuilder().build(site_dir=site, research=research, strategy=strategy, spec=spec, design_context=context)
    gate, observations = TechnicalInspector().inspect(index, critiques / "iteration_1")
    critique = CritiqueReport(score=(94 - (len(context.page_composition.ordered_sections) % 4)) if gate.passed else 0, technical_gate=gate, visual_director_approved=gate.passed, business_approved=gate.passed, issues=[], summary="deterministic fixture technical and visual inspection")
    write_json(critiques / "critique_iteration_1.json", critique)
    guidelines = runtime.web_guidelines(index); write_json(reports / "web_guidelines_iteration_1.json", guidelines.as_dict())
    quality = audit_quality(spec, context, technical_passed=gate.passed, guideline_findings=guidelines.output["findings"])
    write_json(reports / "quality_report_iteration_1.json", quality)
    write_json(reports / "quality_score_breakdown.json", {key: value.model_dump() for key, value in quality.score_breakdown.items()})
    acceptance = AcceptanceAuditor().audit(critique=critique, site_dir=site, quality_report=quality)
    write_json(reports / "acceptance_audit.json", acceptance)
    checkpoints.update({"strategy_completed":"fixture", "external_skills_completed":"fixture", "generation_completed":"fixture", "builder_context_completed":"fixture", "technical_gate_completed":"fixture", "critics_completed":"fixture", "acceptance_completed":"fixture" if acceptance.approved else "blocked"})
    write_json(reports / "checkpoints.json", checkpoints)
    result = {"fixture":name, "status":"approved" if acceptance.approved else "blocked", "category_scores":quality.category_scores, "fingerprint":quality.fingerprint, "fingerprint_breakdown":quality.fingerprint_breakdown, "page_composition":context.page_composition.model_dump(), "blocking_reasons":quality.blocking_reasons, "builder_started":True, "selected_direction":context.selected_visual_direction.name, "observations":observations}
    write_json(prior, result)
    return result


class _DOMAudit(HTMLParser):
    def __init__(self) -> None:
        super().__init__(); self.sections=[]; self.depth=0; self.max_depth=0; self.classes=[]; self.headings=[]; self.ctas=[]; self.tags=[]; self.texts=[]; self._ignored=0
    def handle_starttag(self, tag, attrs):
        self.depth += 1; self.max_depth=max(self.max_depth,self.depth); data=dict(attrs)
        if tag in {"style", "script"}: self._ignored += 1
        self.tags.append(f"{tag}:{data.get('data-section-type', '')}")
        self.classes.extend((data.get("class") or "").split())
        if tag == "section": self.sections.append({"id":data.get("id", ""), "type":data.get("data-section-type", ""), "layout":data.get("data-layout-family", "")})
        if tag == "a": self.ctas.append(data.get("href", ""))
    def handle_endtag(self, tag):
        if tag in {"style", "script"}: self._ignored=max(0,self._ignored-1)
        self.depth=max(0,self.depth-1)
    def handle_data(self, data):
        if data.strip() and not self._ignored:
            self.headings.append(data.strip()); self.texts.append(data.strip())


def _audit_site(path: Path) -> dict:
    parser=_DOMAudit(); html=path.read_text(encoding="utf-8"); parser.feed(html)
    section_types=[section["type"] for section in parser.sections]
    return {"sections":parser.sections,"section_sequence":section_types,"hero_type":section_types[0] if section_types else "","navigation_type":re.search(r'aria-label="([^"]+)"', html).group(1) if 'aria-label="' in html else "","primary_cta_placements":[section["id"] for section in parser.sections if "closure" in section["type"] or section["type"].endswith("hero")],"cta_count":len(parser.ctas),"proof_blocks":[section["type"] for section in parser.sections if "proof" in section["type"]],"cards":[section["layout"] for section in parser.sections if any(token in section["layout"] for token in ("card","matrix","stack"))],"gallery_media":[section["type"] for section in parser.sections if "gallery" in section["type"] or "mosaic" in section["type"]],"timeline":[section["type"] for section in parser.sections if "timeline" in section["type"]],"closing_pattern":section_types[-1] if section_types else "","dom_tree_depth":parser.max_depth,"dom_signature":parser.tags,"repeated_css_classes":{key:parser.classes.count(key) for key in sorted(set(parser.classes)) if parser.classes.count(key)>1},"repeated_layout_containers":{key:html.count(key) for key in ("inner","content-list","btn","section")},"heading_text":parser.headings[:40],"visible_text":" ".join(parser.texts),"journey_pattern":re.search(r'data-journey="([^"]+)"', html).group(1) if 'data-journey="' in html else "","signature_element":re.search(r'data-signature="([^"]+)"', html).group(1) if 'data-signature="' in html else ""}


def structural_audit(root: Path) -> dict:
    names=["restaurant","dental","decorator","school","sparse_level_b","yacht_placeholder"]
    sites={name:_audit_site(root/name/"site"/"index.html") for name in names if (root/name/"site"/"index.html").is_file()}
    sequences={name:value["section_sequence"] for name,value in sites.items()}
    duplicates=[]
    for name, sequence in sequences.items():
        for other, candidate in sequences.items():
            if name < other and sequence == candidate: duplicates.append([name,other])
    return {"scope":"real rendered fixture HTML", "sites":sites, "identical_section_sequences":duplicates, "finding":"Identical sequences are a structural defect; shared buttons, reset and shell are intentionally not treated as composition reuse."}


def _comparison_page(root: Path, reports: dict) -> None:
    folder=root/"comparison"; folder.mkdir(exist_ok=True)
    cards=[]
    for name in ("restaurant","dental","decorator","school"):
        result=reports[name]; comp=result["page_composition"]
        cards.append(f"<article><h2>{name}</h2><p><b>{comp['journey_pattern']}</b> · {comp['hero_type']} · {comp['closing_pattern']}</p><p>{' → '.join(section['type'] for section in comp['ordered_sections'])}</p><p>{result['category_scores']}</p><img src='../{name}/critique_reports/iteration_1/desktop.png'><img src='../{name}/critique_reports/iteration_1/mobile.png'></article>")
    (folder/"index.html").write_text("<!doctype html><meta charset=utf-8><title>Fixture composition comparison</title><style>body{font:16px system-ui;margin:24px;background:#f6f4ef;color:#1d2522}main{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:20px}article{background:white;padding:18px;border:1px solid #ddd}img{width:49%;vertical-align:top;border:1px solid #ccc}@media(max-width:800px){main{grid-template-columns:1fr}}</style><h1>Fixture composition comparison</h1><main>"+"".join(cards)+"</main>",encoding="utf-8")
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as playwright:
            browser=playwright.chromium.launch(); page=browser.new_page(viewport={"width":1440,"height":1100}); page.goto((folder/"index.html").resolve().as_uri()); page.screenshot(path=str(folder/"fixture_comparison.png"),full_page=True); browser.close()
    except Exception as exc:
        (folder/"screenshot_error.txt").write_text(str(exc),encoding="utf-8")


def run_all(root: Path, *, clean: bool = True) -> dict:
    before = structural_audit(root) if root.exists() else {"sites":{},"finding":"No prior fixture output found."}
    before["historical_renderer_root_cause"] = {
        "evidence": "The pre-remediation template always rendered hero → spec.sections → gallery → trust → process → details → final CTA.",
        "shared_structure": ["hero", "site_spec_sections", "gallery", "trust", "process", "details", "cta_band"],
        "conclusion": "Journey CSS classes and briefing asides changed appearance, not content architecture.",
    }
    if clean and root.exists(): shutil.rmtree(root)
    root.mkdir(parents=True, exist_ok=True)
    reports = {name: run_fixture(name, item, root) for name, item in fixture_data().items()}
    reports["level_c"] = run_fixture("level_c", level_c_fixture(), root)
    reports["yacht_placeholder"] = run_fixture("yacht_placeholder", yacht_fixture(), root)
    approved = [r for r in reports.values() if r["status"] == "approved"]
    comparison = {}
    for a in approved:
        comparison[a["fixture"]] = {}
        for b in approved:
            a_audit,b_audit=_audit_site(root/a["fixture"]/'site'/'index.html'),_audit_site(root/b["fixture"]/'site'/'index.html')
            a_phrases,b_phrases=meaningful_phrases(a_audit["visible_text"]),meaningful_phrases(b_audit["visible_text"])
            shared=sorted(set(a_phrases)&set(b_phrases))
            # The normalized DOM compares content architecture separately from
            # legitimate document-shell reuse. Section type and layout shape
            # carry most of the weight; shared semantic utilities carry less.
            section_dom=SequenceMatcher(a=[f"section:{item['type']}:{item['layout']}" for item in a_audit["sections"]],b=[f"section:{item['type']}:{item['layout']}" for item in b_audit["sections"]]).ratio()
            shell_dom=SequenceMatcher(a=a_audit["dom_signature"],b=b_audit["dom_signature"]).ratio()
            dom=round(section_dom * .7 + shell_dom * .3,3)
            css=round(SequenceMatcher(a=[item["layout"] for item in a_audit["sections"]],b=[item["layout"] for item in b_audit["sections"]]).ratio(),3)
            details=composition_similarity(a["fingerprint_breakdown"],b["fingerprint_breakdown"],dom_similarity=dom,css_similarity=css,copy_phrases=(a_phrases,b_phrases))
            comparison[a["fixture"]][b["fixture"]] = {
                **details, "matched_meaningful_phrases":shared[:25], "fingerprint_equal":a["fingerprint"]==b["fingerprint"],
            }
    audit={"pre_remediation":before,"post_remediation":structural_audit(root)}
    (root/"structural_audit.json").write_text(json.dumps(audit,ensure_ascii=False,indent=2),encoding="utf-8")
    _comparison_page(root,reports)
    index = {"runs": reports, "similarity_matrix": comparison, "copy_overlap":"Meaningful 3-5 word phrases exclude technical boilerplate and common stopwords.","structural_audit":"structural_audit.json","comparison":"comparison/index.html"}
    (root / "e2e_evidence.json").write_text(json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8")
    return index


if __name__ == "__main__":
    parser = argparse.ArgumentParser(); parser.add_argument("--root", type=Path, default=Path("runs/fixture-e2e")); args = parser.parse_args()
    print(json.dumps(run_all(args.root), ensure_ascii=False, indent=2))
