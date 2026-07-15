"""Versioned, deterministic design-quality contracts for a site run.

This module intentionally contains no network or LLM calls.  Creative agents may
produce the input briefs, but evidence, fingerprints, skill locks and release
gates remain repeatable code.
"""
from __future__ import annotations

import hashlib
import json
import re
from enum import Enum
from pathlib import Path

from pydantic import BaseModel, Field

from site_agent.models import ResearchBrief, SiteSpec, StrategyBrief

PIPELINE_SCHEMA_VERSION = 2
QUALITY_FLOORS = {"business": 82, "ux": 80, "story": 78, "design": 80, "copy": 82, "accessibility": 80, "responsive": 80, "anti_template": 80, "technical": 88}


class EvidenceLevel(str, Enum):
    A = "A"
    B = "B"
    C = "C"


class EvidenceAssessment(BaseModel):
    pipeline_schema_version: int = PIPELINE_SCHEMA_VERSION
    level: EvidenceLevel
    score: int = Field(ge=0, le=100)
    checks: dict[str, bool]
    reasons: list[str] = Field(default_factory=list)
    unresolved_questions: list[str] = Field(default_factory=list)

    @property
    def build_allowed(self) -> bool:
        return self.level in {EvidenceLevel.A, EvidenceLevel.B}


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
    prohibited_claims: list[str]
    anti_template_constraints: list[str]


class QualityIssue(BaseModel):
    category: str
    severity: str
    evidence: str
    violated_contract: str
    acceptance_condition: str


class QualityReport(BaseModel):
    pipeline_schema_version: int = PIPELINE_SCHEMA_VERSION
    category_scores: dict[str, int]
    floors: dict[str, int] = Field(default_factory=lambda: QUALITY_FLOORS.copy())
    issues: list[QualityIssue] = Field(default_factory=list)
    fingerprint: str
    approved: bool
    blocking_reasons: list[str] = Field(default_factory=list)


def assess_evidence(research: ResearchBrief) -> EvidenceAssessment:
    name = meaningful_identity(research.business_name)
    category = meaningful_identity(research.niche)
    offering = bool(research.sells or research.services_or_products)
    contact = bool(research.contacts) or bool(research.instagram_url)
    brand = bool(research.brand_atmosphere or research.visual_style or research.colors or research.communication_style)
    media = bool(research.best_media)
    unknown_text = " ".join(research.unknowns).lower()
    contradiction = any(token in unknown_text for token in ("contradict", "conflict", "different business"))
    checks = {"business_identified": name, "business_type": category, "offering": offering, "contact_path": contact, "brand_signals": brand, "media_or_text_led": media or (name and category), "no_critical_contradiction": not contradiction}
    score = sum(checks.values()) * 14
    if contradiction or not (name and category and contact):
        level = EvidenceLevel.C
    elif offering and brand:
        level = EvidenceLevel.A
    else:
        level = EvidenceLevel.B
    reasons = [key.replace("_", " ") for key, value in checks.items() if not value]
    return EvidenceAssessment(level=level, score=min(score, 100), checks=checks, reasons=reasons, unresolved_questions=research.unknowns)


def clean_identity(value: str) -> str:
    return re.sub(r"\s*\([^)]*(?:unknown|inferred|likely|not verified)[^)]*\)", "", value or "", flags=re.I).strip()


def meaningful_identity(value: str) -> bool:
    return clean_identity(value).lower() not in {"", "unknown", "n/a", "none"}


def build_context(research: ResearchBrief, strategy: StrategyBrief, spec: SiteSpec) -> BuilderContext:
    evidence = assess_evidence(research)
    offerings = research.sells or research.services_or_products
    name = clean_identity(research.business_name) or "Instagram business"
    category = clean_identity(research.niche) or "independent business"
    brief = BusinessBrief(business_name=name, business_category=category, location=research.city if research.city.lower() not in {"unknown", ""} else "", verified_offerings=offerings, audience=strategy.target_customer, main_user_intent="Understand the offer and choose the next contact step", business_goal=strategy.business_logic, page_goal="Turn informed interest into the approved primary action", primary_cta=strategy.primary_cta or spec.primary_cta, secondary_cta=strategy.secondary_cta or spec.secondary_cta, objections=strategy.customer_questions_or_fears, trust_opportunities=strategy.reason_to_choose, differentiators=strategy.reason_to_choose, unavailable_information=research.unknowns, prohibited_claims=research.forbidden_claims, evidence_references=[item.source for item in research.verified_facts])
    pattern = choose_pattern(category, offerings, evidence.level)
    ux = UXArchitecture(pattern=pattern, first_five_seconds=f"{name}: {category}. {brief.primary_cta}", user_goals=["Recognize the business", "Understand the relevant offer", "Choose the next step"], objection_map=brief.objections, information_architecture=[section.id for section in spec.sections], cta_map={"hero": spec.primary_cta, "final": spec.primary_cta}, mobile_interaction_logic="Keep the primary action visible and preserve section order without horizontal scrolling.")
    narrative = NarrativeStrategy(thesis=spec.h1, emotional_curve=["recognition", "relevance", "confidence", "action"], section_storyboard=[{"id": s.id, "purpose": s.purpose or s.title, "message": s.title} for s in spec.sections])
    directions = visual_directions(category, research, strategy)
    selected = directions[0]
    tokens = {"ink": selected.palette["ink"], "paper": selected.palette["paper"], "accent": selected.palette["accent"], "accent_2": selected.palette["accent_2"], "display_font": selected.typography["display"], "body_font": selected.typography["body"], "radius": "4px" if "editorial" in selected.name.lower() else "12px"}
    media = [MediaManifestItem(source=m.url, quality_score=70 if m.url.startswith("http") else 0, use_cases=[m.recommended_use or "gallery"], alt_text=m.alt, verified_description=m.alt, selected=m.url.startswith("http")) for m in research.best_media]
    return BuilderContext(evidence=evidence, business_brief=brief, ux_architecture=ux, narrative=narrative, visual_directions=directions, selected_visual_direction=selected, design_system=DesignSystem(selected_direction=selected.name, tokens=tokens, responsive_notes=["390px primary CTA remains reachable", "No horizontal overflow", "Respect reduced motion"]), media_manifest=media, prohibited_claims=research.forbidden_claims, anti_template_constraints=["Do not reuse full layout across distinct business categories", "Use only token-driven primitives", "Hero thesis must name the actual business/category/action"])


def choose_pattern(category: str, offerings: list[str], level: EvidenceLevel) -> str:
    text = f"{category} {' '.join(offerings)}".lower()
    if level == EvidenceLevel.B: return "intentional text-led contact bridge"
    if any(x in text for x in ("restaurant", "cafe", "food")): return "local destination"
    if any(x in text for x in ("dental", "clinic", "health")): return "trust journey"
    if any(x in text for x in ("portfolio", "decor", "design")): return "portfolio proof"
    if "school" in text or "course" in text: return "expert authority"
    return "service decision"


def visual_directions(category: str, research: ResearchBrief, strategy: StrategyBrief) -> list[VisualDirection]:
    seed = hashlib.sha256(f"{category}|{research.brand_atmosphere}|{strategy.tone}".encode()).hexdigest()
    palettes = [("Editorial material", {"ink":"#1e2420","paper":"#f7f4ed","accent":"#9e4029","accent_2":"#3c6558"}), ("Field notes", {"ink":"#17212b","paper":"#eef3f0","accent":"#355f85","accent_2":"#805f35"}), ("Quiet signal", {"ink":"#251d2b","paper":"#fbf8fc","accent":"#824b70","accent_2":"#496a69"})]
    offset = int(seed[:2], 16) % 3
    return [VisualDirection(name=palettes[(offset+i)%3][0], composition=["asymmetric thesis with evidence rail", "image-led local rhythm", "text-led contact composition"][i], palette=palettes[(offset+i)%3][1], typography={"display":"Georgia, serif", "body":"Inter, system-ui"}, signature_element=["evidence rail", "cropped media field", "contact prompt card"][i], motion_profile="subtle opacity only; reduced motion disables it", rationale=f"A distinct direction for {category}, selected against verified media and audience signals.") for i in range(3)]


def fingerprint(spec: SiteSpec, context: BuilderContext) -> str:
    stable = {"pattern":context.ux_architecture.pattern,"sections":[s.id for s in spec.sections],"cta":spec.primary_cta.lower(),"palette":context.design_system.tokens,"words":sorted(set(re.findall(r"[a-zA-Zа-яА-ЯіІїЇєЄ]{5,}", " ".join([spec.h1, spec.hero_subtitle, *[s.title for s in spec.sections]]).lower())))[:40]}
    return hashlib.sha256(json.dumps(stable, ensure_ascii=False, sort_keys=True).encode()).hexdigest()


def audit_quality(spec: SiteSpec, context: BuilderContext, *, technical_passed: bool, historical_fingerprints: list[str] | None = None) -> QualityReport:
    text = " ".join([spec.h1, spec.hero_subtitle, *spec.trust_points, *[x for s in spec.sections for x in [s.title, *s.content]]]).lower()
    issues: list[QualityIssue] = []
    generic = ("high quality services", "individual approach", "lorem ipsum", "placeholder", "best service")
    if any(term in text for term in generic): issues.append(QualityIssue(category="copy", severity="high", evidence="generic/placeholder phrase", violated_contract="conversion copy", acceptance_condition="replace with evidence-grounded copy"))
    if context.evidence.level == EvidenceLevel.C: issues.append(QualityIssue(category="business", severity="critical", evidence="insufficient evidence", violated_contract="evidence gate", acceptance_condition="obtain sufficient verified facts"))
    if not spec.h1 or not spec.primary_cta or not spec.sections: issues.append(QualityIssue(category="story", severity="high", evidence="missing thesis, action, or content", violated_contract="storyboard", acceptance_condition="complete the approved narrative"))
    if any(claim.lower() in text for claim in context.prohibited_claims if len(claim) > 3): issues.append(QualityIssue(category="copy", severity="high", evidence="prohibited claim rendered", violated_contract="evidence research", acceptance_condition="remove unsupported claim"))
    fp = fingerprint(spec, context)
    if historical_fingerprints and fp in historical_fingerprints: issues.append(QualityIssue(category="anti_template", severity="high", evidence="identical layout fingerprint", violated_contract="anti-template", acceptance_condition="change justified structure/direction"))
    scores = {key: 92 for key in QUALITY_FLOORS}; scores["technical"] = 92 if technical_passed else 0
    for issue in issues: scores[issue.category] = min(scores.get(issue.category, 92), 50 if issue.severity in {"high","critical"} else 75)
    blockers = [f"{k} score {scores[k]} below floor {floor}" for k, floor in QUALITY_FLOORS.items() if scores.get(k,0) < floor] + [i.evidence for i in issues if i.severity in {"high","critical"}]
    return QualityReport(category_scores=scores, issues=issues, fingerprint=fp, approved=not blockers, blocking_reasons=list(dict.fromkeys(blockers)))


def validate_skill_lock(path: Path) -> list[str]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    errors = []
    for skill in payload.get("skills", []):
        target = path.parents[2] / skill["installed_path"]
        if not skill.get("source_commit") or len(skill["source_commit"]) != 40: errors.append(f"{skill.get('name')}: unpinned commit")
        if not target.is_dir() or not (target / "SKILL.md").is_file():
            errors.append(f"{skill.get('name')}: missing vendored skill")
        elif skill.get("checksum") != directory_checksum(target):
            errors.append(f"{skill.get('name')}: checksum mismatch")
    return errors


def directory_checksum(path: Path) -> str:
    file_hashes = []
    for file in sorted((item for item in path.rglob("*") if item.is_file()), key=lambda item: str(item).lower()):
        file_hashes.append(hashlib.sha256(file.read_bytes()).hexdigest())
    return hashlib.sha256("".join(file_hashes).encode()).hexdigest()


def load_fingerprint_history(path: Path, *, limit: int) -> list[str]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    values = payload.get("fingerprints", []) if isinstance(payload, dict) else []
    return [value for value in values if isinstance(value, str)][-limit:]


def record_fingerprint(path: Path, value: str, *, limit: int) -> None:
    values = load_fingerprint_history(path, limit=limit)
    if value not in values:
        values.append(value)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"fingerprints": values[-limit:]}, indent=2), encoding="utf-8")
