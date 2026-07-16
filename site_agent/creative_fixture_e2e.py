"""Opt-in real-Codex fixture calibration; never claims Telegram jobs or publishes."""
from __future__ import annotations

import html
import json
import os
import shutil
import argparse
from pathlib import Path

from site_agent.models import ContentTheme, Evidence, MediaAsset, ProductIdentity, ResearchBrief, SectionSpec, SiteSpec, StrategyBrief
from site_agent.config import settings
from site_agent.studio import CodexStudioRunner, StudioError, _media_provenance_report


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
        "botanika_form": rich_floral_fixture(),
        "harbour_dental": rich_dental_fixture(),
    }


def rich_floral_fixture():
    """The controlled full-site calibration brief; every publishable detail is explicit."""
    source = "controlled_fixture:botanika_form:2026-07"
    media = [
        MediaAsset(url="https://images.unsplash.com/photo-1490750967868-88aa4486c946?auto=format&fit=crop&w=1600&q=85", asset_id="botanika-stock-01", source_kind="fixture_stock", source_url="https://unsplash.com/photos/1490750967868-88aa4486c946", provenance_note="Controlled calibration stock media; visual reference only, not Botanika Form portfolio.", alt="Жовті тюльпани крупним планом", recommended_use="hero: seasonal tulip study", width=1600, height=1067),
        MediaAsset(url="https://images.unsplash.com/photo-1507504031003-b417219a0fde?auto=format&fit=crop&w=1600&q=85", asset_id="botanika-stock-02", source_kind="fixture_stock", source_url="https://unsplash.com/photos/1507504031003-b417219a0fde", provenance_note="Controlled calibration stock media; visual reference only, not Botanika Form portfolio.", alt="Табличка Mr & Mrs серед весільних квітів", recommended_use="fixture-only ceremony reference", width=1600, height=1067),
        MediaAsset(url="https://images.unsplash.com/photo-1526047932273-341f2a7631f9?auto=format&fit=crop&w=1600&q=85", asset_id="botanika-stock-03", source_kind="fixture_stock", source_url="https://unsplash.com/photos/1526047932273-341f2a7631f9", provenance_note="Controlled calibration stock media; visual reference only, not Botanika Form portfolio.", alt="Букет польових квітів у руках", recommended_use="fixture-only floral detail", width=1600, height=1067),
        MediaAsset(url="https://images.unsplash.com/photo-1468327768560-75b778cbb551?auto=format&fit=crop&w=1600&q=85", asset_id="botanika-stock-04", source_kind="fixture_stock", source_url="https://unsplash.com/photos/1468327768560-75b778cbb551", provenance_note="Controlled calibration stock media; visual reference only, not Botanika Form portfolio.", alt="Тюльпани в садовому світлі", recommended_use="fixture-only botanical atmosphere", width=1600, height=1067),
        MediaAsset(url="https://images.unsplash.com/photo-1501004318641-b39e6451bec6?auto=format&fit=crop&w=1600&q=85", asset_id="botanika-stock-05", source_kind="fixture_stock", source_url="https://unsplash.com/photos/1501004318641-b39e6451bec6", provenance_note="Controlled calibration stock media; visual reference only, not Botanika Form portfolio.", alt="Зелена рослина у керамічному горщику", recommended_use="fixture-only botanical material", width=1600, height=1067),
        MediaAsset(url="https://images.unsplash.com/photo-1485955900006-10f4d324d411?auto=format&fit=crop&w=1600&q=85", asset_id="botanika-stock-06", source_kind="fixture_stock", source_url="https://unsplash.com/photos/1485955900006-10f4d324d411", provenance_note="Controlled calibration stock media; visual reference only, not Botanika Form portfolio.", alt="Сукулент у горщику крупним планом", recommended_use="fixture-only botanical detail", width=1600, height=1067),
    ]
    research = ResearchBrief(
        instagram_url="https://www.instagram.com/botanika_form_fixture/", business_name="Botanika Form",
        primary_language="uk", niche="флористична студія для подій",
        sells=["весільні квіткові інсталяції", "квіти для приватних вечерь", "флористичне оформлення брендових подій"],
        contacts=["Instagram Direct"], communication_style="спокійна, предметна українська", brand_atmosphere="жива ботаніка, м’яке світло, уважна ручна робота", visual_style="редакційна предметна зйомка", colors=["мох", "пудровий", "вершковий"], best_media=media,
        product_identity=ProductIdentity(exact_product="флористичні інсталяції та квіти для весіль, приватних вечерь і брендових подій", evidence_sources=[source + ":product"], confidence="high"),
        content_themes=[
            ContentTheme(label="весільні квіткові інсталяції", decision_role="offer", evidence_sources=[source + ":weddings"]),
            ContentTheme(label="квіти для приватних вечерь", decision_role="format", evidence_sources=[source + ":dinners"]),
            ContentTheme(label="флористичне оформлення брендових подій", decision_role="format", evidence_sources=[source + ":brands"]),
            ContentTheme(label="запит, референс і монтаж", decision_role="process", evidence_sources=[source + ":process"]),
        ],
        verified_facts=[
            Evidence(source=source + ":language", value="Підтверджена мова fixture — українська", confidence="high"),
            Evidence(source=source + ":product", value="Студія створює флористичні інсталяції та квіти для подій", confidence="high"),
            Evidence(source=source + ":formats", value="Підтверджені формати: весілля, приватні вечері, брендові події", confidence="high"),
            Evidence(source=source + ":process", value="Початок розмови — через Direct з датою, форматом та референсом", confidence="high"),
        ],
        unknowns=["Актуальну доступність, кошторис і локацію підтверджують у Direct."],
        forbidden_claims=["Не стверджувати ціни, доступність, кількість гостей, локації, нагороди, команду або відгуки без нових доказів."],
    )
    strategy = StrategyBrief(
        target_customer="людина або команда, що планує весілля, вечерю чи брендову подію", reason_to_choose=["одна студія для інсталяції, столу та деталей", "запит починається з формату події та референсу"],
        customer_questions_or_fears=["Чи підходить формат моїй події?", "Що надіслати в першому повідомленні?"],
        niche_specific_sections=["формати подій", "робочий ритм", "квіткові деталі"], primary_cta="Надіслати формат події", secondary_cta="Подивитися формати", tone="виразна, спокійна, конкретна", color_direction="мох, вершковий і пудровий із медіа", typography_direction="виразний serif для назв, нейтральний sans для рішень", business_logic="назвати точний формат, показати відмінні сценарії і відкрити змістовний Direct-запит",
    )
    spec = SiteSpec(
        language="uk", title="Botanika Form — флористика для подій", meta_description="Флористичні інсталяції та квіти для весіль, вечерь і брендових подій.",
        h1="Флористика, що збирає подію в один живий жест", hero_subtitle="Весільні інсталяції, квіти для приватних вечерь і брендових подій — починаємо з формату, дати та вашого референсу.",
        primary_cta="Надіслати формат події", secondary_cta="Подивитися формати",
        sections=[
            SectionSpec(id="weddings", title="Весілля", purpose="Показати інсталяції для церемонії та святкового простору.", content=["Весільні квіткові інсталяції."]),
            SectionSpec(id="dinners", title="Приватні вечері", purpose="Пояснити роль квітів у столі й атмосфері.", content=["Квіти для приватних вечерь."]),
            SectionSpec(id="brands", title="Брендові події", purpose="Назвати формат для запусків і зустрічей бренду.", content=["Флористичне оформлення брендових подій."]),
            SectionSpec(id="process", title="Від референсу до монтажу", purpose="Дати чесний перший крок до розмови.", content=["Надішліть у Direct формат події, дату й референс."]),
        ], trust_points=["Підтверджені формати: весілля, приватні вечері, брендові події."], process_steps=["Надішліть формат події, дату й референс у Direct.", "У Direct підтверджують доступність, кошторис і локацію."], gallery_assets=media,
        footer_note="Актуальні деталі підтверджують у Instagram Direct.", no_fake_claims_checklist=[],
    )
    return research, strategy, spec


def rich_dental_fixture():
    """A controlled full-site calibration brief, deliberately unlike Botanika Form.

    This is not a real clinic or a production candidate.  Its source-backed
    fixture facts let the studio exercise a high-information healthcare brief
    while every visual remains visibly classified calibration-only stock.
    """
    source = "controlled_fixture:harbour_dental:2026-07"
    stock = "Controlled calibration stock media; visual reference only, not Harbour Dental clinical work or portfolio proof."
    media = [
        MediaAsset(url="https://images.unsplash.com/photo-1606811971618-4486d14f3f99?auto=format&fit=crop&w=1600&q=85", asset_id="harbour-dental-stock-01", source_kind="fixture_stock", source_url="https://unsplash.com/photos/1606811971618-4486d14f3f99", provenance_note=stock, alt="Dental clinician in protective equipment preparing a treatment room", recommended_use="hero: calm clinical welcome", width=1600, height=1067),
        MediaAsset(url="https://images.unsplash.com/photo-1629909613654-28e377c37b09?auto=format&fit=crop&w=1600&q=85", asset_id="harbour-dental-stock-02", source_kind="fixture_stock", source_url="https://unsplash.com/photos/1629909613654-28e377c37b09", provenance_note=stock, alt="Dental chair and clinical light in a bright treatment room", recommended_use="fixture-only treatment-room context", width=1600, height=1067),
        MediaAsset(url="https://images.unsplash.com/photo-1511174511562-5f7f18b874f8?auto=format&fit=crop&w=1600&q=85", asset_id="harbour-dental-stock-03", source_kind="fixture_stock", source_url="https://unsplash.com/photos/1511174511562-5f7f18b874f8", provenance_note=stock, alt="Clinician speaking with a patient in a consultation setting", recommended_use="fixture-only consultation context", width=1600, height=1067),
        MediaAsset(url="https://images.unsplash.com/photo-1629909615184-74f495363b67?auto=format&fit=crop&w=1600&q=85", asset_id="harbour-dental-stock-04", source_kind="fixture_stock", source_url="https://unsplash.com/photos/1629909615184-74f495363b67", provenance_note=stock, alt="Dental tools arranged for a clinical procedure", recommended_use="fixture-only detail", width=1600, height=1067),
        MediaAsset(url="https://images.unsplash.com/photo-1588776814546-1ffcf47267a5?auto=format&fit=crop&w=1600&q=85", asset_id="harbour-dental-stock-05", source_kind="fixture_stock", source_url="https://unsplash.com/photos/1588776814546-1ffcf47267a5", provenance_note=stock, alt="Close view of a clinician wearing examination gloves", recommended_use="fixture-only care detail", width=1600, height=1067),
        MediaAsset(url="https://images.unsplash.com/photo-1609840114035-3c981b782dfe?auto=format&fit=crop&w=1600&q=85", asset_id="harbour-dental-stock-06", source_kind="fixture_stock", source_url="https://unsplash.com/photos/1609840114035-3c981b782dfe", provenance_note=stock, alt="Dental x-ray image displayed on a clinical screen", recommended_use="fixture-only diagnostic context", width=1600, height=1067),
    ]
    research = ResearchBrief(
        instagram_url="https://www.instagram.com/harbour_dental_fixture/", business_name="Harbour Dental",
        primary_language="en", niche="modern adult dental clinic",
        sells=["routine examinations and hygiene appointments", "restorative dentistry consultations", "urgent dental consultations"],
        contacts=["Instagram Direct"], communication_style="plain-English, calm, precise",
        brand_atmosphere="quietly capable, reassuring and clinically clear",
        visual_style="wayfinding-led clinical system: structured grids, diagnostic blue, graphite type, clear progression and compact data-like cues",
        colors=["cobalt blue", "graphite", "white", "cool grey"], best_media=media,
        product_identity=ProductIdentity(exact_product="consultation-led adult dental care covering routine hygiene, restorative treatment planning and urgent dental consultations", evidence_sources=[source + ":product"], confidence="high"),
        content_themes=[
            ContentTheme(label="routine examinations and hygiene appointments", decision_role="offer", evidence_sources=[source + ":routine-care"]),
            ContentTheme(label="restorative dentistry consultations", decision_role="offer", evidence_sources=[source + ":restorative-care"]),
            ContentTheme(label="urgent dental consultations", decision_role="offer", evidence_sources=[source + ":urgent-care"]),
            ContentTheme(label="consultation first: current concern, options and next step", decision_role="process", evidence_sources=[source + ":consultation-process"]),
            ContentTheme(label="clear explanation before a treatment decision", decision_role="proof", evidence_sources=[source + ":decision-support"]),
            ContentTheme(label="clinical imaging discussed as part of the consultation where relevant", decision_role="proof", evidence_sources=[source + ":imaging-context"]),
        ],
        verified_facts=[
            Evidence(source=source + ":language", value="Confirmed fixture language is English.", confidence="high"),
            Evidence(source=source + ":product", value="The clinic provides consultation-led adult dental care for routine hygiene, restorative planning and urgent concerns.", confidence="high"),
            Evidence(source=source + ":offers", value="Confirmed offer themes: routine examinations and hygiene; restorative dentistry consultations; urgent dental consultations.", confidence="high"),
            Evidence(source=source + ":trust", value="Confirmed decision-support themes: explain the concern, discuss relevant options, then agree the next step; imaging may be discussed where relevant.", confidence="high"),
            Evidence(source=source + ":cta", value="Confirmed conversion action: request a consultation in Instagram Direct.", confidence="high"),
        ],
        unknowns=["Current appointment availability, pricing, treatment suitability, clinician details and location require confirmation in Direct."],
        forbidden_claims=["Do not claim outcomes, pain-free treatment, same-day availability, insurance, prices, qualifications, reviews, awards, addresses, staff names or emergency response times.", "All supplied media is fixture stock for calibration only, never Harbour Dental patient work, clinic photography or portfolio proof.", "Do not use Botanika Form's floral/editorial composition, overlapping serif hero, cream/pink/dark-green palette, collage, CTA treatment, section rhythm or signature element."],
    )
    strategy = StrategyBrief(
        target_customer="an adult deciding whether to arrange routine care, discuss a restorative concern or ask for an urgent consultation",
        reason_to_choose=["the site separates the three reasons to get in touch", "the first conversation is framed around the concern, options and an agreed next step"],
        customer_questions_or_fears=["Which kind of appointment fits my concern?", "What happens before I decide on treatment?", "How do I ask about an urgent concern?"],
        niche_specific_sections=["care routes", "what a consultation clarifies", "decision support", "request pathway"],
        primary_cta="Request a consultation", secondary_cta="See the care routes", tone="calm, plain-English and exact",
        color_direction="cobalt blue, graphite, white and cool grey; never Botanika's cream/pink/dark-green palette",
        typography_direction="compact technical sans-serif hierarchy; no oversized or overlapping serif display type",
        business_logic="identify the visitor's reason for contact, show the three care routes, explain consultation-led decision support, then invite a Direct consultation request without promising availability",
    )
    spec = SiteSpec(
        language="en", title="Harbour Dental — consultation-led adult dental care",
        meta_description="Routine hygiene, restorative dentistry consultations and urgent dental consultations. Request a consultation in Direct.",
        h1="Dental care starts with the right next question.",
        hero_subtitle="Consultation-led adult dental care for routine hygiene, restorative planning and urgent concerns.",
        primary_cta="Request a consultation", secondary_cta="See the care routes",
        sections=[
            SectionSpec(id="care-routes", title="Choose the reason you are getting in touch", purpose="Let a visitor identify the relevant care route without diagnosing or promising treatment.", content=["Routine examinations and hygiene appointments.", "Restorative dentistry consultations.", "Urgent dental consultations."]),
            SectionSpec(id="consultation", title="A consultation clarifies the next step", purpose="Explain the verified decision-support process.", content=["Start with the concern you want to discuss.", "Discuss relevant options before deciding on a next step.", "Imaging may be discussed where relevant."]),
            SectionSpec(id="restorative", title="When a restorative concern needs a plan", purpose="Name restorative planning as a distinct offer without asserting an outcome.", content=["Bring the question you want to resolve to a restorative dentistry consultation."]),
            SectionSpec(id="urgent", title="When the concern feels urgent", purpose="Give an honest urgent-contact route without inventing availability or response promises.", content=["Request an urgent dental consultation in Direct; current availability is confirmed there."]),
            SectionSpec(id="request", title="Request a consultation", purpose="Set a clear conversion step.", content=["Send a brief description of the concern and whether it is routine, restorative or urgent."]),
        ],
        trust_points=["Three confirmed care routes: routine hygiene, restorative planning and urgent consultations.", "The consultation is framed around the concern, relevant options and an agreed next step.", "Current availability and treatment suitability are confirmed directly."],
        process_steps=["Choose the care route closest to your question.", "Send the concern in Instagram Direct.", "Confirm availability and the appropriate next step directly."],
        gallery_assets=media, footer_note="Controlled fixture only — all displayed media is stock reference material, not Harbour Dental clinical work. Current details are confirmed in Instagram Direct.", no_fake_claims_checklist=[],
    )
    return research, strategy, spec


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
    business_name = json.loads((studio / "input" / "business_brief.json").read_text(encoding="utf-8"))["research"]["business_name"]
    media_disclosure = (
        f"Every image below is controlled fixture stock for calibration only; it is not presented as "
        f"{business_name} portfolio, clinical work or business photography. Production promotion is blocked."
    )
    selected_data = json.loads((studio / "concept_reviews" / "selected_concept.json").read_text(encoding="utf-8"))
    comparison = json.loads((studio / "concept_reviews" / "comparison.json").read_text(encoding="utf-8"))
    media_report = _write_media_provenance_report(run_dir)
    media = media_report["assets"]
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
    media_rows = "".join(
        "<li><strong>{}</strong> — {}. <a href='{}'>source</a>; {}.</li>".format(
            html.escape(str(item.get("asset_id") or item.get("url", "media"))),
            html.escape(str(item.get("source_kind", "unknown"))),
            html.escape(str(item.get("source_url") or item.get("url", "#")), quote=True),
            html.escape("used {} time(s); {}".format(item.get("rendered_uses", 0), item.get("provenance_note", "No provenance note recorded"))),
        ) for item in media
    )
    before = f"../studio/concept_reviews/{selected}/desktop.png"
    fixer_before = studio / "fixer_history" / "iteration_1" / "before" / "desktop.png"
    fixer_after = studio / "fixer_history" / "iteration_1" / "after" / "desktop.png"
    fixer_block = ""
    if fixer_before.is_file() and fixer_after.is_file():
        fixer_block = "<h3>Creative fixer — before / after</h3><div class='pair'><img src='../studio/fixer_history/iteration_1/before/desktop.png' alt='Before fixer desktop'><img src='../studio/fixer_history/iteration_1/after/desktop.png' alt='After fixer desktop'></div><div class='pair'><img src='../studio/fixer_history/iteration_1/before/mobile.png' alt='Before fixer mobile'><img src='../studio/fixer_history/iteration_1/after/mobile.png' alt='After fixer mobile'></div>"
    page = """<!doctype html><html lang='en'><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>
<title>__BUSINESS__ — human calibration</title><style>*,*:before,*:after{box-sizing:border-box}body{margin:0;background:#111;color:#f3efe4;font:16px/1.5 system-ui}main{width:100%;max-width:1800px;margin:auto;padding:40px}h1{font-size:clamp(2rem,5vw,5rem);line-height:1;margin:0 0 16px}.pair{display:grid;grid-template-columns:3fr 1fr;gap:20px}.pair img,.final img{display:block;width:100%;max-width:100%;height:auto;border:1px solid #555;background:#222}section{border-top:1px solid #555;padding:32px 0}.final{display:grid;gap:20px}.note{color:#f98d5d}p,li,pre{overflow-wrap:anywhere}pre{white-space:pre-wrap}@media(max-width:760px){main{padding:18px}.pair{grid-template-columns:1fr}}</style><main>
<p class='note'>Human calibration required — no Telegram or Cloudflare action was run.</p><h1>__BUSINESS__<br>Creative Studio review</h1>
<section><h2>Concept stage</h2><p>Selected: <strong>__SELECTED__</strong></p><ul>__REASONS__</ul>__CONCEPTS__</section>
<section class='final'><h2>Final stage</h2><p>Selected concept before extension</p><img src='__BEFORE__' alt='Selected concept before full build'><h3>Native review captures</h3><p><a href='artifacts/desktop-1440x1100.png'>Desktop viewport — 1440×1100</a> · <a href='artifacts/desktop-full.png'>Desktop full page — 1440px wide</a> · <a href='artifacts/mobile-390x844.png'>Mobile viewport — 390×844</a> · <a href='artifacts/mobile-full.png'>Mobile full page — 390px wide</a></p><img src='artifacts/desktop-1440x1100.png' alt='Final desktop viewport at 1440 by 1100'><img src='artifacts/mobile-390x844.png' alt='Final mobile viewport at 390 by 844'>__FIXER__<h3>Art Director</h3><p>Score: __SCORE__. __SUMMARY__</p><ul>__FINDINGS__</ul><h3>Media provenance</h3><p>__MEDIA_DISCLOSURE__</p><ul>__MEDIA_ROWS__</ul><h3>Unresolved medium/low issues</h3><pre>__UNRESOLVED__</pre></section>
</main></html>""".replace("__BUSINESS__", html.escape(business_name)).replace("__SELECTED__", html.escape(selected)).replace("__REASONS__", reasons).replace("__CONCEPTS__", "".join(concepts)).replace("__BEFORE__", before).replace("__FIXER__", fixer_block).replace("__SCORE__", html.escape(str(report.get("score", "unscored")))).replace("__SUMMARY__", html.escape(str(report.get("summary", "")))).replace("__FINDINGS__", findings).replace("__UNRESOLVED__", html.escape(json.dumps(report.get("unresolved_issues", []), ensure_ascii=False, indent=2)))
    page = page.replace("__MEDIA_ROWS__", media_rows).replace("__MEDIA_DISCLOSURE__", html.escape(media_disclosure))
    index = calibration / "index.html"
    index.write_text(page, encoding="utf-8")
    from playwright.sync_api import sync_playwright
    artifacts = calibration / "artifacts"
    artifacts.mkdir(exist_ok=True)
    png = calibration / f"{run_dir.name}_calibration.png"
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        try:
            site = run_dir / "site" / "index.html"
            for filename, viewport, full_page in (
                ("desktop-1440x1100.png", {"width": 1440, "height": 1100}, False),
                ("desktop-full.png", {"width": 1440, "height": 1100}, True),
                ("mobile-390x844.png", {"width": 390, "height": 844}, False),
                ("mobile-full.png", {"width": 390, "height": 844}, True),
            ):
                capture = browser.new_page(viewport=viewport)
                capture.goto(site.resolve().as_uri(), wait_until="networkidle")
                capture.screenshot(path=artifacts / filename, full_page=full_page)
                capture.close()
            page_object = browser.new_page(viewport={"width": 1920, "height": 1200})
            page_object.goto(index.resolve().as_uri(), wait_until="networkidle")
            page_object.screenshot(path=png, full_page=True)
            page_object.close()
        finally:
            browser.close()
    return {"calibration_page": str(index), "calibration_png": str(png), "calibration_artifacts": {name: str(artifacts / name) for name in ("desktop-1440x1100.png", "desktop-full.png", "mobile-390x844.png", "mobile-full.png")}, "media_provenance_report": str(studio / "media_provenance_report.json"), "comparison_reviews": comparison.get("concept_reviews", {})}


def _write_media_provenance_report(run_dir: Path) -> dict:
    """Classify every fixture asset against the exact promoted HTML it supports."""
    studio = run_dir / "studio"
    report = _media_provenance_report(studio_dir=studio, site_dir=run_dir / "site")
    (studio / "media_provenance_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--resume", metavar="FIXTURE", help="Resume exactly one existing fixture run.")
    args = parser.parse_args()
    result = run_one(args.resume) if args.resume else run_all()
    print(json.dumps(result, ensure_ascii=False, indent=2))
