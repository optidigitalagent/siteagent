"""Deterministic, evidence-backed composition and quality contracts.

Creative agents supply facts and copy.  This module turns those inputs into an
explicit page composition, makes its provenance inspectable, and evaluates
quality without self-ratings or network calls.
"""
from __future__ import annotations

import hashlib
import json
import re
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, model_validator

from site_agent.commercial_usefulness import (
    commercial_usefulness_report,
    language_fit_report,
    semantic_repetition_report,
)
from site_agent.models import ResearchBrief, SiteSpec, StrategyBrief
from site_agent.skill_lock import directory_checksum, load_fingerprint_history, record_fingerprint, validate_skill_lock

PIPELINE_SCHEMA_VERSION = 5
QUALITY_FLOORS = {
    "business": 82, "business_clarity": 85, "commercial_usefulness": 85,
    "ux": 80, "story": 78, "storytelling": 78, "copy": 82, "copy_quality": 80,
    "brand_fit": 80, "media_direction": 80, "design": 80, "responsive": 80,
    "accessibility": 80, "technical": 88, "anti_template": 80,
}


class EvidenceLevel(str, Enum):
    A = "A"
    B = "B"
    C = "C"


class PageScope(str, Enum):
    FULL = "full_site"
    MICRO = "micro_site"
    BLOCKED = "blocked"


class EvidenceAssessment(BaseModel):
    pipeline_schema_version: int = PIPELINE_SCHEMA_VERSION
    level: EvidenceLevel
    score: int = Field(ge=0, le=100)
    checks: dict[str, bool]
    page_scope: PageScope = PageScope.BLOCKED
    exact_product: str = ""
    content_theme_count: int = Field(default=0, ge=0)
    usable_media_count: int = Field(default=0, ge=0)
    required_concepts: int = Field(default=0, ge=0, le=3)
    reasons: list[str] = Field(default_factory=list)
    unresolved_questions: list[str] = Field(default_factory=list)

    @property
    def build_allowed(self) -> bool:
        return self.page_scope in {PageScope.FULL, PageScope.MICRO}


class MediaManifestItem(BaseModel):
    source: str
    local_path: str = ""
    checksum: str = ""
    dimensions: str = "unknown"
    orientation: str = "unknown"
    quality_score: int = Field(default=0, ge=0, le=100)
    use_cases: list[str] = Field(default_factory=list)
    crop_recommendations: str = ""
    focal_point: str = "center"
    alt_text: str = ""
    verified_description: str = ""
    selected: bool = False
    rejection_reason: str = ""


class BusinessBrief(BaseModel):
    pipeline_schema_version: int = PIPELINE_SCHEMA_VERSION
    business_name: str
    business_category: str
    location: str = ""
    verified_offerings: list[str] = Field(default_factory=list)
    audience: str
    main_user_intent: str
    business_goal: str
    page_goal: str
    primary_cta: str
    secondary_cta: str
    objections: list[str] = Field(default_factory=list)
    trust_opportunities: list[str] = Field(default_factory=list)
    differentiators: list[str] = Field(default_factory=list)
    unavailable_information: list[str] = Field(default_factory=list)
    prohibited_claims: list[str] = Field(default_factory=list)
    evidence_references: list[str] = Field(default_factory=list)


class UXArchitecture(BaseModel):
    pattern: str
    first_five_seconds: str
    user_goals: list[str]
    objection_map: list[str]
    information_architecture: list[str]
    cta_map: dict[str, str]
    mobile_interaction_logic: str


class NarrativeStrategy(BaseModel):
    thesis: str
    emotional_curve: list[str]
    section_storyboard: list[dict[str, str]]


class VisualDirection(BaseModel):
    name: str
    composition: str
    palette: dict[str, str]
    typography: dict[str, str]
    signature_element: str
    motion_profile: str
    rationale: str


class DesignSystem(BaseModel):
    selected_direction: str
    tokens: dict[str, str]
    responsive_notes: list[str]


class SectionPlan(BaseModel):
    id: str
    type: str
    purpose: str
    required_message: str
    content_source: str
    layout_family: str
    visual_role: str
    cta_relationship: str = "none"
    media_requirements: str = "optional"
    proof_requirements: str = "none"
    optional: bool = False
    mobile_order: int = Field(ge=0)
    accessibility_requirements: list[str] = Field(default_factory=lambda: ["semantic heading", "visible focus"])


class PageComposition(BaseModel):
    journey_pattern: str
    navigation_type: str
    hero_type: str
    ordered_sections: list[SectionPlan]
    cta_strategy: str
    proof_strategy: str
    closing_pattern: str
    responsive_behavior: str
    signature_element: str
    signature_element_placement: str

    @model_validator(mode="after")
    def valid_graph(self):
        ids = [section.id for section in self.ordered_sections]
        if len(ids) != len(set(ids)):
            raise ValueError("page composition section IDs must be unique")
        if not self.ordered_sections or not self.ordered_sections[0].type.endswith("hero"):
            raise ValueError("page composition must start with a hero section")
        if not any(section.type.endswith("closure") for section in self.ordered_sections):
            raise ValueError("page composition requires a closing section")
        return self


class BuilderContext(BaseModel):
    pipeline_schema_version: int = PIPELINE_SCHEMA_VERSION
    evidence: EvidenceAssessment
    business_brief: BusinessBrief
    ux_architecture: UXArchitecture
    narrative: NarrativeStrategy
    visual_directions: list[VisualDirection]
    selected_visual_direction: VisualDirection
    design_system: DesignSystem
    media_manifest: list[MediaManifestItem]
    page_composition: PageComposition
    prohibited_claims: list[str]
    anti_template_constraints: list[str]
    skill_executions: list[dict] = Field(default_factory=list)
    language_fit_approved: bool = True
    language_rationale: str = ""


class QualityIssue(BaseModel):
    category: str
    severity: str
    evidence: str
    violated_contract: str
    acceptance_condition: str


class ScoreBreakdown(BaseModel):
    status: str = "evaluated"
    base: int = 100
    passed_rules: list[str] = Field(default_factory=list)
    failed_rules: list[str] = Field(default_factory=list)
    deductions: list[dict[str, Any]] = Field(default_factory=list)
    evidence: list[str] = Field(default_factory=list)
    final_value: int = Field(ge=0, le=100)


class QualityReport(BaseModel):
    pipeline_schema_version: int = PIPELINE_SCHEMA_VERSION
    category_scores: dict[str, int]
    score_breakdown: dict[str, ScoreBreakdown]
    floors: dict[str, int] = Field(default_factory=lambda: QUALITY_FLOORS.copy())
    issues: list[QualityIssue] = Field(default_factory=list)
    fingerprint: str
    fingerprint_breakdown: dict[str, Any]
    approved: bool
    blocking_reasons: list[str] = Field(default_factory=list)


def clean_identity(value: str) -> str:
    return re.sub(r"\s*\([^)]*(?:unknown|inferred|likely|not verified)[^)]*\)", "", value or "", flags=re.I).strip()


def meaningful_identity(value: str) -> bool:
    return clean_identity(value).lower() not in {"", "unknown", "n/a", "none"}


_ABSTRACT_PRODUCT_TERMS = {
    "experience", "experiences", "premium", "unique", "unforgettable", "quality",
    "service", "services", "solution", "solutions", "approach", "lifestyle",
}


def _specific_product(research: ResearchBrief) -> str:
    identity = research.product_identity
    if identity is None or identity.confidence == "low" or not identity.evidence_sources:
        return ""
    value = clean_identity(identity.exact_product)
    # Keep this gate language-agnostic; ASCII-only tokenisation would reject a
    # fully evidenced Ukrainian (or any non-English) product by construction.
    words = set(re.findall(r"[^\W\d_]+", value.lower(), flags=re.UNICODE))
    if not value or (words and words <= _ABSTRACT_PRODUCT_TERMS):
        return ""
    # A phrase made solely of luxury/atmosphere adjectives is never a product.
    concrete = words - _ABSTRACT_PRODUCT_TERMS - {"private", "evening", "modern", "live", "online", "guided"}
    return value if concrete else ""


def _usable_media(research: ResearchBrief) -> list:
    unique = {}
    for item in research.best_media:
        url = item.url.strip()
        if not url or url in unique:
            continue
        # A source, descriptive alt, intended role and practical dimensions are
        # the minimum fixture-level proof that this is usable media, not a URL list.
        if not (url.startswith(("https://", "http://")) and item.alt.strip() and item.recommended_use.strip() and item.width >= 900 and item.height >= 700):
            continue
        unique[url] = item
    return list(unique.values())


def assess_studio_readiness(research: ResearchBrief) -> EvidenceAssessment:
    """Classify product evidence before strategy or creative work can begin.

    Full sites require enough independently sourced material to earn a long
    narrative. Sparse but identifiable businesses receive only a micro-site;
    ambiguity blocks generation rather than becoming atmospheric copy.
    """
    product = _specific_product(research)
    theme_keys = set()
    valid_themes = []
    for theme in research.content_themes:
        label = re.sub(r"\s+", " ", theme.label.strip().lower())
        if label and theme.evidence_sources and label not in theme_keys:
            theme_keys.add(label)
            valid_themes.append(theme)
    media = _usable_media(research)
    checks = {
        "business_identified": meaningful_identity(research.business_name),
        "business_type": meaningful_identity(research.niche),
        "product_identified": bool(product),
        "language_confirmed": bool(research.primary_language.strip()),
        "contact_path": bool(research.contacts) or bool(research.instagram_url),
        "content_sufficient_for_full_site": len(valid_themes) >= 3,
        "media_sufficient_for_full_site": 5 <= len(media) <= 8,
        "no_critical_contradiction": not any(token in " ".join(research.unknowns).lower() for token in ("contradict", "conflict", "different business")),
    }
    can_micro = all(checks[key] for key in ("business_identified", "business_type", "product_identified", "language_confirmed", "contact_path", "no_critical_contradiction")) and bool(valid_themes)
    can_full = can_micro and checks["content_sufficient_for_full_site"] and checks["media_sufficient_for_full_site"]
    scope = PageScope.FULL if can_full else (PageScope.MICRO if can_micro else PageScope.BLOCKED)
    level = EvidenceLevel.A if scope is PageScope.FULL else (EvidenceLevel.B if scope is PageScope.MICRO else EvidenceLevel.C)
    score = min(100, sum(checks.values()) * 12 + min(len(valid_themes), 3) * 2 + min(len(media), 8))
    reasons = [key.replace("_", " ") for key, value in checks.items() if not value]
    if scope is PageScope.MICRO:
        reasons.append("full site is not allowed; only an intentional micro-site may be generated")
    if scope is PageScope.BLOCKED:
        reasons.append("product identification, confirmed language, and at least one sourced content theme are mandatory before generation")
    return EvidenceAssessment(
        level=level, score=score, checks=checks, page_scope=scope, exact_product=product,
        content_theme_count=len(valid_themes), usable_media_count=len(media),
        required_concepts=3 if scope is PageScope.FULL else (1 if scope is PageScope.MICRO else 0),
        reasons=reasons, unresolved_questions=research.unknowns,
    )


def assess_evidence(research: ResearchBrief) -> EvidenceAssessment:
    return assess_studio_readiness(research)


def choose_pattern(category: str, offerings: list[str], level: EvidenceLevel) -> str:
    text = f"{category} {' '.join(offerings)}".lower()
    tokens = set(re.findall(r"[a-z]+", text))
    def has(*words: str) -> bool:
        return any(word in tokens for word in words)
    if level == EvidenceLevel.B:
        return "intentional sparse editorial"
    if has("restaurant", "cafe", "food", "hospitality", "event"):
        return "experience-led"
    if has("dental", "clinic", "health", "legal", "therapy"):
        return "trust/service decision"
    if has("portfolio", "decorator", "decor", "design", "architect", "studio"):
        return "portfolio discovery"
    if has("school", "course", "learning", "education"):
        return "learning/outcome"
    return "service decision"


def visual_directions(category: str, research: ResearchBrief, strategy: StrategyBrief, skill_executions: list[dict]) -> list[VisualDirection]:
    palettes = [("Harbour ledger", {"ink":"#18312d", "paper":"#f5f1e8", "accent":"#b75530", "accent_2":"#527465"}, "menu-ribbon"), ("Clinical margin", {"ink":"#142333", "paper":"#f2f7f8", "accent":"#276f8e", "accent_2":"#597d90"}, "confidence-line"), ("Material folio", {"ink":"#332821", "paper":"#f7f1e9", "accent":"#805331", "accent_2":"#72826a"}, "project-index")]
    seed = int(hashlib.sha256(f"{category}|{research.brand_atmosphere}|{strategy.tone}".encode()).hexdigest()[:2], 16) % len(palettes)
    recommendation = next((json.dumps(entry.get("output", {}).get("design_system", {}), ensure_ascii=False)[:220] for entry in skill_executions if entry.get("name") == "ui-ux-pro-max"), "local category strategy")
    result = []
    for index in range(3):
        name, palette, signature = palettes[(seed + index) % len(palettes)]
        result.append(VisualDirection(name=name, composition=["asymmetric evidence rail", "editorial full-bleed field", "indexed portfolio grid"][index], palette=palette, typography={"display":"Georgia, serif", "body":"Inter, system-ui"}, signature_element=signature, motion_profile="one purposeful reveal; reduced motion disables it", rationale=f"Direction for {category}, informed by {recommendation}."))
    return result


def _plan(id: str, type: str, purpose: str, source: str, layout: str, role: str, *, cta: str = "none", media: str = "optional", proof: str = "none", order: int = 0) -> SectionPlan:
    return SectionPlan(id=id, type=type, purpose=purpose, required_message=purpose, content_source=source, layout_family=layout, visual_role=role, cta_relationship=cta, media_requirements=media, proof_requirements=proof, mobile_order=order)


def compose_page(pattern: str, direction: VisualDirection, spec: SiteSpec) -> PageComposition:
    # Each journey deliberately has a distinct semantic and layout sequence.
    plans: dict[str, tuple[str, str, str, list[SectionPlan]]] = {
        "experience-led": ("compact booking nav", "experience hero", "booking closure", [
            _plan("hero", "experience_hero", "Make the visit feel tangible before asking for a table.", "SiteSpec.hero", "split-media", "thesis", cta="primary", media="hero", order=0),
            _plan("formats", "experience_formats", "Show the available visit formats.", "BusinessBrief.verified_offerings", "menu-ribbon", "decision", cta="secondary", order=1),
            _plan("atmosphere", "atmosphere_gallery", "Let the atmosphere support the choice.", "MediaManifest", "masonry-gallery", "immersion", media="gallery", order=2),
            _plan("occasion-proof", "case_proof", "Ground the visit with verified practical cues.", "SiteSpec.trust_points", "proof-strip", "confidence", proof="verified cues", order=3),
            _plan("book", "booking_closure", "Move a ready guest to a table request.", "SiteSpec.contact_lines", "booking-band", "action", cta="primary", order=4),
        ]),
        "trust/service decision": ("utility trust nav", "authority hero", "consultation closure", [
            _plan("hero", "authority_hero", "Answer the first care decision with calm authority.", "SiteSpec.hero", "authority-split", "thesis", cta="primary", order=0),
            _plan("concerns", "treatment_concerns", "Name the questions a new patient brings.", "StrategyBrief.objections", "question-columns", "reassurance", order=1),
            _plan("services", "service_matrix", "Make the verified service routes scannable.", "BusinessBrief.verified_offerings", "service-matrix", "decision", cta="secondary", order=2),
            _plan("journey", "process_timeline", "Explain what happens after contact.", "SiteSpec.process_steps", "numbered-timeline", "clarity", order=3),
            _plan("proof", "case_proof", "Show the evidence path without invented outcomes.", "SiteSpec.trust_points", "confidence-cards", "confidence", proof="verified cues", order=4),
            _plan("consult", "consultation_closure", "Invite a focused consultation request.", "SiteSpec.contact_lines", "consultation-panel", "action", cta="primary", order=5),
        ]),
        "portfolio discovery": ("folio index nav", "portfolio hero", "inquiry closure", [
            _plan("hero", "portfolio_hero", "Lead with the visual world and project question.", "SiteSpec.hero", "folio-canvas", "thesis", cta="primary", media="hero", order=0),
            _plan("projects", "portfolio_mosaic", "Let selected work lead discovery.", "SiteSpec.sections", "portfolio-mosaic", "evidence", media="gallery", order=1),
            _plan("occasions", "service_matrix", "Connect the work to an occasion or project need.", "BusinessBrief.verified_offerings", "editorial-list", "decision", cta="secondary", order=2),
            _plan("process", "process_timeline", "Make the creative conversation legible.", "SiteSpec.process_steps", "studio-steps", "clarity", order=3),
            _plan("voices", "testimonial_proof", "Use only the available proof language.", "SiteSpec.trust_points", "quote-wall", "confidence", proof="verified cues", order=4),
            _plan("inquire", "inquiry_closure", "Open a project inquiry with context.", "SiteSpec.contact_lines", "inquiry-sheet", "action", cta="primary", order=5),
        ]),
        "learning/outcome": ("learning path nav", "outcome hero", "enrollment closure", [
            _plan("hero", "outcome_hero", "Put the learner outcome before the course list.", "SiteSpec.hero", "outcome-rail", "thesis", cta="primary", order=0),
            _plan("benefits", "learning_benefits", "Explain what practice unlocks.", "SiteSpec.sections", "benefit-steps", "outcome", order=1),
            _plan("model", "learning_model", "Make the learning model clear.", "SiteSpec.process_steps", "model-diagram", "clarity", order=2),
            _plan("programs", "service_matrix", "Offer a route into the available programmes.", "BusinessBrief.verified_offerings", "program-stack", "decision", cta="secondary", order=3),
            _plan("platform", "platform_demonstration", "Show how learning continues between conversations.", "SiteSpec.trust_points", "platform-frame", "evidence", proof="verified cues", order=4),
            _plan("enroll", "enrollment_closure", "Turn readiness into the right course question.", "SiteSpec.contact_lines", "enrollment-band", "action", cta="primary", order=5),
        ]),
        "intentional sparse editorial": ("minimal direct nav", "editorial sparse hero", "direct editorial closure", [
            _plan("hero", "editorial_sparse_hero", "State only what is verified and point to Direct.", "SiteSpec.hero", "editorial-column", "thesis", cta="primary", order=0),
            _plan("offer", "focused_offer", "Keep one verified offer in focus.", "BusinessBrief.verified_offerings", "single-offer", "decision", order=1),
            _plan("direct", "direct_editorial_closure", "Give one honest route to current details.", "SiteSpec.contact_lines", "direct-note", "action", cta="primary", order=2),
        ]),
    }
    navigation, hero, closing, sections = plans.get(pattern, plans["trust/service decision"])
    return PageComposition(journey_pattern=pattern, navigation_type=navigation, hero_type=hero, ordered_sections=sections, cta_strategy="primary in hero and closing; supporting CTA only in decision module", proof_strategy="place proof where the journey asks for confidence", closing_pattern=closing, responsive_behavior="composition preserves semantic order, then prioritises action and readable media on mobile", signature_element=direction.signature_element, signature_element_placement="hero and the first decision module")


def build_context(research: ResearchBrief, strategy: StrategyBrief, spec: SiteSpec, skill_executions: list[dict] | None = None) -> BuilderContext:
    evidence = assess_evidence(research)
    offerings = research.sells or research.services_or_products
    name, category = clean_identity(research.business_name) or "Instagram business", clean_identity(research.niche) or "independent business"
    brief = BusinessBrief(business_name=name, business_category=category, location=research.city if meaningful_identity(research.city) else "", verified_offerings=offerings, audience=strategy.target_customer, main_user_intent="Understand the offer and choose the next contact step", business_goal=strategy.business_logic, page_goal="Turn informed interest into the approved primary action", primary_cta=strategy.primary_cta or spec.primary_cta, secondary_cta=strategy.secondary_cta or spec.secondary_cta, objections=strategy.customer_questions_or_fears, trust_opportunities=strategy.reason_to_choose, differentiators=strategy.reason_to_choose, unavailable_information=research.unknowns, prohibited_claims=research.forbidden_claims, evidence_references=[item.source for item in research.verified_facts])
    pattern = choose_pattern(category, offerings, evidence.level)
    directions = visual_directions(category, research, strategy, skill_executions or [])
    selected = directions[int(hashlib.sha256((category + strategy.primary_cta).encode()).hexdigest()[:2], 16) % len(directions)]
    composition = compose_page(pattern, selected, spec)
    ux = UXArchitecture(pattern=pattern, first_five_seconds=f"{name}: {category}. {brief.primary_cta}", user_goals=["Recognize the business", "Understand the relevant offer", "Choose the next step"], objection_map=brief.objections, information_architecture=[section.id for section in composition.ordered_sections], cta_map={"hero": spec.primary_cta, "closing": spec.primary_cta}, mobile_interaction_logic=composition.responsive_behavior)
    narrative = NarrativeStrategy(thesis=spec.h1, emotional_curve=[section.visual_role for section in composition.ordered_sections], section_storyboard=[{"id": section.id, "purpose": section.purpose, "message": section.required_message, "source": section.content_source} for section in composition.ordered_sections])
    tokens = {"ink": selected.palette["ink"], "paper": selected.palette["paper"], "accent": selected.palette["accent"], "accent_2": selected.palette["accent_2"], "display_font": selected.typography["display"], "body_font": selected.typography["body"], "radius": "0px" if "folio" in composition.navigation_type else ("18px" if pattern == "experience-led" else "8px")}
    media = [MediaManifestItem(source=m.url, quality_score=70 if m.url.startswith("http") else 0, use_cases=[m.recommended_use or "gallery"], alt_text=m.alt, verified_description=m.alt, selected=m.url.startswith("http")) for m in research.best_media]
    language = language_fit_report(spec, research)
    return BuilderContext(evidence=evidence, business_brief=brief, ux_architecture=ux, narrative=narrative, visual_directions=directions, selected_visual_direction=selected, design_system=DesignSystem(selected_direction=selected.name, tokens=tokens, responsive_notes=["390px primary CTA remains reachable", "No horizontal overflow", "Respect reduced motion"]), media_manifest=media, page_composition=composition, prohibited_claims=research.forbidden_claims, anti_template_constraints=["Do not reuse a full page composition across unrelated business decisions", "Reuse primitives but not an unchanged hero/CTA/closure sequence", "Every page needs its direction signature element"], skill_executions=skill_executions or [], language_fit_approved=language.approved, language_rationale=language.rationale)


def fingerprint_breakdown(spec: SiteSpec, context: BuilderContext) -> dict[str, Any]:
    c = context.page_composition
    return {"section_sequence": [section.type for section in c.ordered_sections], "section_type_multiset": sorted(section.type for section in c.ordered_sections), "hero_type": c.hero_type, "navigation_type": c.navigation_type, "cta_pattern": [section.id for section in c.ordered_sections if section.cta_relationship != "none"], "proof_pattern": [section.id for section in c.ordered_sections if section.proof_requirements != "none"], "closing_pattern": c.closing_pattern, "layout_family_sequence": [section.layout_family for section in c.ordered_sections], "card_usage_ratio": round(sum("card" in section.layout_family or "matrix" in section.layout_family or "stack" in section.layout_family for section in c.ordered_sections) / len(c.ordered_sections), 3), "gallery_media_pattern": [section.type for section in c.ordered_sections if section.media_requirements != "optional"], "palette_family": context.selected_visual_direction.name, "typography_category": context.selected_visual_direction.typography["display"], "radius_profile": context.design_system.tokens["radius"], "signature_element": c.signature_element, "journey_pattern": c.journey_pattern, "copy_phrase_fingerprint": meaningful_phrases(" ".join([spec.h1, spec.hero_subtitle, *[section.title for section in spec.sections]]))}


def fingerprint(spec: SiteSpec, context: BuilderContext) -> str:
    return hashlib.sha256(json.dumps(fingerprint_breakdown(spec, context), ensure_ascii=False, sort_keys=True).encode()).hexdigest()


def meaningful_phrases(text: str) -> list[str]:
    words = re.findall(r"[\w'-]+", text.lower(), flags=re.UNICODE)
    stop = {"the", "and", "for", "with", "your", "from", "this", "that", "about", "what", "how", "you", "our", "are", "use", "instagram", "direct", "a", "an", "to", "of", "in", "on"}
    words = [word for word in words if len(word) > 2 and word not in stop]
    return sorted({" ".join(words[i:i + size]) for size in (3, 4, 5) for i in range(max(0, len(words) - size + 1))})


def _ratio(left: list[str], right: list[str]) -> float:
    return round(len(set(left) & set(right)) / len(set(left) | set(right)), 3) if set(left) | set(right) else 0.0


def _lcs_ratio(left: list[str], right: list[str]) -> float:
    rows = [[0] * (len(right) + 1) for _ in range(len(left) + 1)]
    for i, a in enumerate(left, 1):
        for j, b in enumerate(right, 1):
            rows[i][j] = rows[i - 1][j - 1] + 1 if a == b else max(rows[i - 1][j], rows[i][j - 1])
    return round(rows[-1][-1] / max(len(left), len(right), 1), 3)


def composition_similarity(left: dict[str, Any], right: dict[str, Any], *, dom_similarity: float | None = None, css_similarity: float | None = None, copy_phrases: tuple[list[str], list[str]] | None = None) -> dict[str, float]:
    sequence = _lcs_ratio(left["section_sequence"], right["section_sequence"])
    groups = {"section_sequence_similarity": sequence, "section_type_overlap": _ratio(left["section_type_multiset"], right["section_type_multiset"]), "hero_similarity": float(left["hero_type"] == right["hero_type"]), "navigation_similarity": float(left["navigation_type"] == right["navigation_type"]), "cta_pattern_similarity": _ratio(left["cta_pattern"], right["cta_pattern"]), "proof_pattern_similarity": _ratio(left["proof_pattern"], right["proof_pattern"]), "closing_similarity": float(left["closing_pattern"] == right["closing_pattern"]), "component_usage_similarity": _ratio(left["layout_family_sequence"], right["layout_family_sequence"]), "visual_token_similarity": round(sum(left[key] == right[key] for key in ("palette_family", "typography_category", "radius_profile")) / 3, 3), "journey_similarity": float(left["journey_pattern"] == right["journey_pattern"]), "signature_similarity": float(left["signature_element"] == right["signature_element"])}
    groups["dom_tree_similarity"] = dom_similarity if dom_similarity is not None else sequence
    groups["css_structure_similarity"] = css_similarity if css_similarity is not None else groups["component_usage_similarity"]
    groups["copy_similarity"] = _ratio(*(copy_phrases or (left["copy_phrase_fingerprint"], right["copy_phrase_fingerprint"])))
    groups["narrative_similarity"] = round((sequence + groups["proof_pattern_similarity"] + groups["closing_similarity"]) / 3, 3)
    groups["complete_composition_similarity"] = round(sum(groups[key] for key in ("section_sequence_similarity", "section_type_overlap", "dom_tree_similarity", "hero_similarity", "navigation_similarity", "cta_pattern_similarity", "closing_similarity", "component_usage_similarity", "copy_similarity")) / 9, 3)
    return groups


def audit_quality(spec: SiteSpec, context: BuilderContext, *, technical_passed: bool, historical_fingerprints: list[str] | None = None, guideline_findings: list[dict] | None = None, category_score_overrides: dict[str, int] | None = None, comparison: dict[str, float] | None = None, html_text: str = "", hero_cta_present: bool | None = None, visual_signals: dict[str, bool] | None = None) -> QualityReport:
    text = " ".join([spec.h1, spec.hero_subtitle, *spec.trust_points, *[x for s in spec.sections for x in [s.title, *s.content]]]).lower()
    issues: list[QualityIssue] = []
    generic = ("high quality services", "individual approach", "lorem ipsum", "placeholder", "best service")
    if any(term in text for term in generic): issues.append(QualityIssue(category="copy", severity="high", evidence="generic/placeholder phrase", violated_contract="conversion copy", acceptance_condition="replace with evidence-grounded copy"))
    if context.evidence.level == EvidenceLevel.C: issues.append(QualityIssue(category="business", severity="critical", evidence="insufficient evidence", violated_contract="evidence gate", acceptance_condition="obtain sufficient verified facts"))
    if not spec.h1 or not spec.primary_cta or not spec.sections: issues.append(QualityIssue(category="story", severity="high", evidence="missing thesis, action, or content", violated_contract="storyboard", acceptance_condition="complete the approved narrative"))
    placeholder_like = spec.h1.strip().lower() in {"welcome", "hello", "instagram"} or ("generic" in text and len(spec.sections) < 2)
    if placeholder_like:
        issues.extend([
            QualityIssue(category="business", severity="high", evidence="placeholder-like business proposition", violated_contract="business clarity", acceptance_condition="state one verified offer and customer decision"),
            QualityIssue(category="design", severity="high", evidence="placeholder-like visual direction", violated_contract="visual direction", acceptance_condition="use a business-specific signature element"),
        ])
    if not context.page_composition.signature_element: issues.append(QualityIssue(category="design", severity="high", evidence="missing signature element", violated_contract="visual direction", acceptance_condition="select and render signature"))
    if any(claim.lower() in text for claim in context.prohibited_claims if len(claim) > 3): issues.append(QualityIssue(category="copy", severity="high", evidence="prohibited claim rendered", violated_contract="evidence research", acceptance_condition="remove unsupported claim"))
    fp = fingerprint(spec, context)
    if historical_fingerprints and fp in historical_fingerprints: issues.append(QualityIssue(category="anti_template", severity="high", evidence="identical layout fingerprint", violated_contract="anti-template", acceptance_condition="change page composition"))
    if comparison and comparison.get("complete_composition_similarity", 0) >= 0.82 and comparison.get("hero_similarity") and comparison.get("closing_similarity"):
        issues.append(QualityIssue(category="anti_template", severity="high", evidence="composition reuses sequence, hero, and closing pattern", violated_contract="anti-template", acceptance_condition="change purpose-driven composition"))
    for finding in guideline_findings or []:
        issues.append(QualityIssue(category="accessibility", severity=finding.get("severity", "medium"), evidence=f"{finding.get('file')}:{finding.get('selector')}: {finding.get('message')}", violated_contract="web-design-guidelines", acceptance_condition="resolve local guideline finding"))
    semantic = semantic_repetition_report(spec, context, html_text=html_text)
    commercial = commercial_usefulness_report(spec, context, semantic=semantic, html_text=html_text, hero_cta_present=hero_cta_present)
    if not commercial.approved:
        issues.append(QualityIssue(category="commercial_usefulness", severity="high", evidence=f"commercial usefulness score {commercial.score} below 85", violated_contract="commercial usefulness", acceptance_condition="make the offer, value, and primary action clear in the first meaningful viewport"))
    if semantic.items:
        evidence_text = "semantic duplicate sections: " + ", ".join(semantic.items[0].sections)
        for category in ("copy", "copy_quality", "story", "storytelling"):
            issues.append(QualityIssue(category=category, severity="high", evidence=evidence_text, violated_contract="semantic repetition", acceptance_condition="merge repeated sections and restore offer-desire-proof-action progression"))
    if not context.language_fit_approved:
        issues.append(QualityIssue(category="brand_fit", severity="high", evidence="unverified language choice", violated_contract="language fit", acceptance_condition="use evidence-backed language or record the input-contract fallback"))
    signals = visual_signals or {}
    if signals.get("media_blackout") or signals.get("dead_space") or signals.get("media_does_not_support_offer"):
        issues.append(QualityIssue(category="media_direction", severity="high", evidence="media blackout/dead-space issue", violated_contract="media direction", acceptance_condition="use media to clarify or make the offer desirable without consuming functional space"))
    evidence = fingerprint_breakdown(spec, context)
    score_breakdown: dict[str, ScoreBreakdown] = {}
    for category, floor in QUALITY_FLOORS.items():
        base = 100
        deductions: list[dict[str, Any]] = []
        passed = ["deterministic evidence evaluated"]
        if category == "technical":
            if technical_passed: deductions.append({"rule":"technical margin retained for visual checks", "points":6})
            else: deductions.append({"rule":"technical gate failed", "points":100})
        else:
            # Scores reflect composition evidence, not a blanket approved value.
            structural_margin = {"business": 4, "business_clarity": 4, "commercial_usefulness": 0, "ux": 7, "story": 8, "storytelling": 8, "copy": 6, "copy_quality": 6, "brand_fit": 9, "media_direction": 9, "design": 11, "responsive": 7, "accessibility": 5, "anti_template": 10}[category]
            deductions.append({"rule":"remaining evidence margin", "points":structural_margin})
            section_count = len(context.page_composition.ordered_sections)
            if category in {"ux", "story", "storytelling", "responsive"} and section_count < 5:
                deductions.append({"rule":"shorter journey has less decision coverage", "points": 2})
            requires_media = any(section.media_requirements in {"hero", "gallery"} for section in context.page_composition.ordered_sections)
            if category in {"brand_fit", "design", "media_direction"} and requires_media and not context.media_manifest:
                deductions.append({"rule":"required media composition uses verified text-led fallback", "points": 4})
            if category in {"business", "business_clarity"} and len(context.business_brief.verified_offerings) < 2:
                deductions.append({"rule":"single verified offering narrows decision evidence", "points": 2})
            if category in {"copy", "copy_quality"} and len(meaningful_phrases(text)) < 8:
                deductions.append({"rule":"limited meaningful copy evidence", "points": 4})
        for issue in issues:
            if issue.category == category:
                deductions.append({"rule":issue.evidence, "points":50 if issue.severity in {"high", "critical"} else 18})
        value = max(0, base - sum(item["points"] for item in deductions))
        score_breakdown[category] = ScoreBreakdown(base=base, passed_rules=passed, failed_rules=[issue.evidence for issue in issues if issue.category == category], deductions=deductions, evidence=[json.dumps(evidence, ensure_ascii=False)[:500]], final_value=value)
    # Score caps stop visual or technical strength from compensating for a commercial failure.
    caps: dict[str, tuple[int, str]] = {}
    if not commercial.checks["offer_clear_within_five_seconds"]:
        caps["business_clarity"] = (60, "offer is not identifiable in the first meaningful viewport")
    if semantic.items or not commercial.checks["missing_information_is_not_primary_narrative"] or "copy this question" in text:
        caps["copy_quality"] = (55, "missing information or one semantic instruction dominates the copy")
    if semantic.items:
        caps["storytelling"] = (55, "three sections repeat one meaning without offer-desire-proof-action progression")
    if not commercial.checks["primary_cta_in_first_meaningful_viewport"]:
        caps["ux"] = (60, "primary CTA is missing from the first meaningful viewport")
    if not context.language_fit_approved or not commercial.checks["reads_as_commercial_site"]:
        caps["brand_fit"] = (60, "language is unverified or the creative concept obscures the business")
    if signals.get("media_blackout") or signals.get("dead_space") or signals.get("media_does_not_support_offer"):
        caps["media_direction"] = (65, "media blackout or dead space weakens offer comprehension")
    for category, (maximum, rule) in caps.items():
        current = score_breakdown[category].final_value
        if current > maximum:
            score_breakdown[category].deductions.append({"rule": f"score cap: {rule}", "points": current - maximum})
            score_breakdown[category].final_value = maximum
    for category, value in (category_score_overrides or {}).items():
        if category in score_breakdown:
            score_breakdown[category].deductions.append({"rule":"controlled override", "points":max(0, score_breakdown[category].final_value - value)})
            score_breakdown[category].final_value = value
    scores = {key: data.final_value for key, data in score_breakdown.items()}
    blockers = [f"{key} score {scores[key]} below floor {floor}" for key, floor in QUALITY_FLOORS.items() if scores[key] < floor] + [issue.evidence for issue in issues if issue.severity in {"high", "critical"}]
    return QualityReport(category_scores=scores, score_breakdown=score_breakdown, issues=issues, fingerprint=fp, fingerprint_breakdown=evidence, approved=not blockers, blocking_reasons=list(dict.fromkeys(blockers)))
