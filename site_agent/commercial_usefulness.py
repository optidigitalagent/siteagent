"""Commercial, language, and semantic-repetition gates for creative builds.

The checks are deliberately conservative: they evaluate whether a visitor can
recognise the offer and act on it, without asking a sparse-evidence site to
invent unavailable operational detail.
"""
from __future__ import annotations

import re
from collections import Counter
from typing import Any

from pydantic import BaseModel, Field


class CommercialIssue(BaseModel):
    severity: str
    rule: str
    evidence: str
    impact: str
    recommendation: str


class CommercialUsefulnessReport(BaseModel):
    score: int = Field(ge=0, le=100)
    minimum_score: int = 85
    approved: bool
    page_scope: str = "unspecified"
    checks: dict[str, bool]
    issues: list[CommercialIssue] = Field(default_factory=list)
    rationale: str


class LanguageFitReport(BaseModel):
    selected_language: str
    evidence_language: str = ""
    source: str
    rationale: str
    approved: bool


class SemanticRepetitionItem(BaseModel):
    repeated_idea: str
    sections: list[str]
    closeness: float
    storytelling_impact: str
    recommendation: str


class SemanticRepetitionReport(BaseModel):
    approved: bool
    page_scope: str = "unspecified"
    items: list[SemanticRepetitionItem] = Field(default_factory=list)
    section_intents: dict[str, str] = Field(default_factory=dict)
    section_roles: dict[str, str] = Field(default_factory=dict)
    missing_information_ratio: float = Field(default=0.0, ge=0, le=1)


def _plain_text(value: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", value or "")).strip()


def _sections_from_html(html_text: str) -> list[tuple[str, str, str]]:
    sections: list[tuple[str, str, str]] = []
    for index, match in enumerate(re.finditer(r"<section\b(?P<attrs>[^>]*)>(?P<body>.*?)</section>", html_text or "", re.I | re.S), 1):
        attrs, body = match.group("attrs"), match.group("body")
        id_match = re.search(r"\bid\s*=\s*['\"]([^'\"]+)['\"]", attrs, re.I)
        role_match = re.search(r"\bdata-decision-role\s*=\s*['\"]([^'\"]+)['\"]", attrs, re.I)
        sections.append((id_match.group(1) if id_match else f"section-{index}", _plain_text(body), role_match.group(1).strip().lower() if role_match else ""))
    return sections


def _intent(text: str, offerings: list[str], *, declared_role: str = "", section_id: str = "") -> str:
    if declared_role in {"offer", "proof", "process", "conversion"}:
        return declared_role
    if section_id.lower() in {"contact", "contacts", "book", "booking", "close", "closure", "direct"}:
        return "conversion"
    value = text.lower()
    offer_terms = [term.lower() for term in offerings if len(term.strip()) > 4]
    for term in offer_terms:
        if term in value or term.rstrip("s") in value:
            return f"verified offer: {term.rstrip('s')}"
    contact_hits = sum(token in value for token in ("instagram direct", "confirm", "current details", "ask in direct", "message us", "message on instagram"))
    if contact_hits >= 2:
        return "ask for missing current details"
    if any(token in value for token in ("how it works", "next step", "enquiry", "inquiry", "contact")):
        return "conversion guidance"
    if any(token in value for token in ("atmosphere", "quiet", "water", "evening")):
        return "experience atmosphere"
    return "other"


def semantic_repetition_report(
    spec: Any, context: Any, *, html_text: str = "", page_scope: str | None = None
) -> SemanticRepetitionReport:
    """Check narrative repetition against the approved evidence scope.

    A Level B page has room for only offer, proof/process, and conversion.  It
    must not be penalised for not carrying the longer Level A journey, but it
    must still give each of those scarce sections a different job.
    """
    scope = (page_scope or "unspecified").strip().lower()
    sections = _sections_from_html(html_text)
    if not sections:
        sections = [(section.id, " ".join([section.title, *section.content]), "") for section in spec.sections]
    intents = {
        section_id: _intent(text, context.business_brief.verified_offerings, declared_role=role, section_id=section_id)
        for section_id, text, role in sections
    }
    roles = {section_id: role or intents[section_id] for section_id, _, role in sections}
    total_words = sum(len(text.split()) for _, text, _ in sections)
    missing_words = sum(len(text.split()) for section_id, text, _ in sections if intents[section_id] == "ask for missing current details")
    missing_ratio = round(missing_words / max(total_words, 1), 3)
    duplicates = []
    for idea, count in Counter(intents.values()).items():
        ids = [section_id for section_id, value in intents.items() if value == idea]
        # Three repeated meanings are always a failure.  For Level B we also
        # reject a two-section duplicate because that consumes its entire
        # decision budget; a repeated offer in a labelled conversion close is
        # deliberately represented as conversion rather than duplicated offer.
        repeated_limit = 2 if scope == "micro_site" else 3
        if count >= repeated_limit and idea != "other":
            duplicates.append(
                SemanticRepetitionItem(
                    repeated_idea=idea,
                    sections=ids,
                    closeness=0.92,
                    storytelling_impact="Three sections repeat one decision instead of moving from offer to desire to action.",
                    recommendation="Merge these sections into one concise note and use the recovered space for a distinct customer question.",
                )
            )
    if missing_ratio > 0.25:
        contact_sections = [section_id for section_id, intent in intents.items() if intent == "ask for missing current details"]
        duplicates.append(
            SemanticRepetitionItem(
                repeated_idea="missing information dominates page content",
                sections=contact_sections,
                closeness=1.0,
                storytelling_impact="More than a quarter of section text asks the visitor to obtain missing details instead of explaining the offer.",
                recommendation="Reduce this to one short factual caveat and restore offer, desire, proof, and action content.",
            )
        )
    if scope == "micro_site":
        required_roles = {"offer", "proof", "conversion"}
        absent = sorted(required_roles - set(roles.values()))
        if absent:
            duplicates.append(
                SemanticRepetitionItem(
                    repeated_idea="incomplete micro-site decision path",
                    sections=list(intents),
                    closeness=1.0,
                    storytelling_impact="A concise Level B page still needs offer, evidence-backed proof or process, and a conversion close.",
                    recommendation="Use the existing three-section budget for distinct offer, proof/process, and booking roles; do not add filler sections.",
                )
            )
    elif scope == "blocked":
        duplicates.append(
            SemanticRepetitionItem(
                repeated_idea="blocked evidence scope rendered",
                sections=list(intents),
                closeness=1.0,
                storytelling_impact="Insufficient evidence must block creative output before commercial review.",
                recommendation="Obtain a confirmed product, language, and sourced content theme before building.",
            )
        )
    return SemanticRepetitionReport(approved=not duplicates, page_scope=scope, items=duplicates, section_intents=intents, section_roles=roles, missing_information_ratio=missing_ratio)


def language_fit_report(spec: Any, research: Any) -> LanguageFitReport:
    selected = (spec.language or "").strip().lower()
    evidence_language = (research.primary_language or "").strip().lower()
    language_codes = {
        "ukrainian": "uk", "українська": "uk", "український": "uk",
        "english": "en", "англійська": "en",
        "polish": "pl", "polski": "pl", "польська": "pl",
        "russian": "ru", "русский": "ru", "російська": "ru",
    }
    selected_primary = language_codes.get(selected) or (re.match(r"[a-z]{2,3}", selected) or [""])[0]
    evidence_primary = language_codes.get(evidence_language) or (re.match(r"[a-z]{2,3}", evidence_language) or [""])[0]
    if evidence_language:
        approved = bool(selected_primary) and selected_primary == evidence_primary
        return LanguageFitReport(
            selected_language=selected,
            evidence_language=evidence_language,
            source="research evidence",
            rationale="The site language must match the language recorded in the research evidence.",
            approved=approved,
        )
    return LanguageFitReport(
        selected_language=selected,
        source="input contract fallback",
        rationale="No language is verified in bio, captions, audience, geography, or brand material; the explicit fixture/input language is retained rather than chosen for aesthetics.",
        approved=bool(selected),
    )


def commercial_usefulness_report(
    spec: Any,
    context: Any,
    *,
    semantic: SemanticRepetitionReport | None = None,
    html_text: str = "",
    hero_cta_present: bool | None = None,
    page_scope: str | None = None,
) -> CommercialUsefulnessReport:
    scope = (page_scope or "unspecified").strip().lower()
    semantic = semantic or semantic_repetition_report(spec, context, html_text=html_text, page_scope=scope)
    rendered_sections = _sections_from_html(html_text)
    # When runnable HTML exists, judge the copy the visitor actually sees.
    # Falling back to the planning spec would let a stale or untranslated spec
    # approve a vague rendered first viewport.
    hero = (rendered_sections[0][1] if rendered_sections else " ".join([spec.h1, spec.hero_subtitle])).lower()
    all_text = _plain_text(html_text) or " ".join([
        spec.h1, spec.hero_subtitle, *spec.trust_points,
        *[" ".join([section.title, *section.content]) for section in spec.sections],
    ])
    offer_terms = [item.lower() for item in context.business_brief.verified_offerings if item.strip()]
    if context.business_brief.exact_product.strip():
        offer_terms.append(context.business_brief.exact_product.strip().lower())
    category_terms = [term for term in re.findall(r"[a-z]{4,}", context.business_brief.business_category.lower()) if term not in {"private", "independent"}]
    localized_category_terms: tuple[str, ...] = ()
    category = context.business_brief.business_category.lower()
    if any(token in category for token in ("dent", "стомат", "стомато")):
        localized_category_terms = (
            "стоматолог", "коронк", "імплант", "имплант", "вінір", "винир", "брекет",
            "dentysta", "stomatolog", "implant", "liców", "licow", "aparat ortodont",
        )
    offer_visible = any(
        term in hero or term.rstrip("s") in hero
        for term in [*offer_terms, *category_terms]
    ) or sum(term in hero for term in localized_category_terms) >= 2
    primary_action = bool(spec.primary_cta.strip())
    hero_action = primary_action if hero_cta_present is None else hero_cta_present
    audience = (context.business_brief.audience or "").strip().lower()
    audience_clear = audience not in {"", "a prospective customer", "prospective customer", "visitor"} or any(term in hero for term in category_terms)
    value_clear = offer_visible and (len(hero.split()) >= 8 if rendered_sections else bool(spec.hero_subtitle.strip()))
    conversion_path = primary_action and ("instagram" in all_text.lower() or "direct" in all_text.lower() or bool(context.business_brief.primary_cta))
    business_information = bool(offer_terms)
    # This is a commercial gate, so it must work for the verified site language
    # rather than silently favouring an English fixture vocabulary. The terms are
    # deliberately broad sensory/product stems, not unsupported superlatives.
    desire_terms = (
        "private", "evening", "experience", "time on the water", "occasion",
        "посміш", "турбот", "довір", "досвід", "естетик", "відновлен", "професійн",
        "квіт", "простір", "світл", "жив", "момент", "атмосфер", "церемон",
        "kwiat", "przestrze", "światł", "swiatl", "kolor", "materia wydarzenia",
        "scenograf", "instalacj", "atmosfer", "ceremoni",
    )
    evidence_backed_value = any(
        phrase.strip().lower() in all_text.lower()
        or phrase.strip().lower().rstrip("s") in all_text.lower()
        for phrase in context.business_brief.differentiators
        if len(phrase.strip()) >= 4
    )
    evidence_numbers = {
        value
        for phrase in context.business_brief.differentiators
        for value in re.findall(r"\b\d+(?:[.,]\d+)?\b", phrase)
    }
    evidence_backed_value = evidence_backed_value or any(
        re.search(rf"\b{re.escape(value)}\b", all_text) for value in evidence_numbers
    )
    value_clear = value_clear or (offer_visible and evidence_backed_value)
    desire = any(word in all_text.lower() for word in desire_terms) or evidence_backed_value
    recitable = offer_visible and primary_action
    editorial_only = any(token in all_text.lower() for token in ("field notes", "dossier", "copy this question", "editorial exercise"))
    checks = {
        "offer_clear_within_five_seconds": offer_visible,
        "audience_clear": audience_clear,
        "primary_action_clear": primary_action,
        "reason_to_choose_present": value_clear,
        "conversion_path_present": conversion_path,
        "useful_business_information_present": business_information,
        "missing_information_is_not_primary_narrative": semantic.approved,
        "desire_created": desire,
        "offer_is_recitable_after_first_screen": recitable,
        "reads_as_commercial_site": not editorial_only,
        "primary_cta_in_first_meaningful_viewport": hero_action,
    }
    if scope == "micro_site":
        checks["micro_site_has_offer_proof_conversion_path"] = semantic.approved
    elif scope == "full_site":
        # A full commercial product has a complete decision journey, not just
        # four visually separated blocks. Roles are intentionally explicit so
        # a repeated CTA or decorative band cannot satisfy the contract.
        sections = _sections_from_html(html_text)
        roles = {role.replace("-", "_") for _, _, role in sections if role}
        aliases = {
            "identity": "identity_value", "hero": "identity_value", "offer": "offer_services", "services": "offer_services",
            "portfolio": "proof", "gallery": "proof", "about": "brand_about", "brand": "brand_about",
            "process": "trust_process", "trust": "trust_process", "pricing": "commercial_decision",
            "consultation": "commercial_decision", "faq": "objection_handling", "objections": "objection_handling",
            "contact": "final_conversion", "conversion": "final_conversion",
        }
        normalized = {aliases.get(role, role) for role in roles}
        required = {"identity_value", "offer_services", "proof", "brand_about", "trust_process", "commercial_decision", "objection_handling", "final_conversion"}
        checks["full_site_has_complete_commercial_path"] = len(sections) >= 7 and required <= normalized
    elif scope == "blocked":
        checks["scope_allows_generation"] = False
    deductions = {
        "offer_clear_within_five_seconds": 40,
        "audience_clear": 8,
        "primary_action_clear": 20,
        "reason_to_choose_present": 18,
        "conversion_path_present": 18,
        "useful_business_information_present": 18,
        "missing_information_is_not_primary_narrative": 28,
        "desire_created": 5,
        "offer_is_recitable_after_first_screen": 20,
        "reads_as_commercial_site": 18,
        "primary_cta_in_first_meaningful_viewport": 20,
        "micro_site_has_offer_proof_conversion_path": 28,
        "full_site_has_complete_commercial_path": 28,
        "scope_allows_generation": 100,
    }
    evidence_margin = 0
    if len(context.business_brief.verified_offerings) <= 1:
        evidence_margin += 5
    if not context.business_brief.evidence_references:
        evidence_margin += 4
    score = max(0, 100 - evidence_margin - sum(deductions[key] for key, passed in checks.items() if not passed))
    issues = [
        CommercialIssue(
            severity="high" if key in {"offer_clear_within_five_seconds", "primary_cta_in_first_meaningful_viewport", "missing_information_is_not_primary_narrative"} else "medium",
            rule=key,
            evidence="failed deterministic commercial contract",
            impact="The visitor cannot confidently understand or act on the offer.",
            recommendation="Resolve this before visual approval or promotion.",
        )
        for key, passed in checks.items() if not passed
    ]
    return CommercialUsefulnessReport(
        score=score,
        approved=score >= 85 and all(checks[key] for key in ("offer_clear_within_five_seconds", "primary_action_clear", "primary_cta_in_first_meaningful_viewport", "missing_information_is_not_primary_narrative", "desire_created", "reads_as_commercial_site")) and (scope != "micro_site" or checks["micro_site_has_offer_proof_conversion_path"]) and (scope != "full_site" or checks["full_site_has_complete_commercial_path"]) and scope != "blocked",
        page_scope=scope,
        checks=checks,
        issues=issues,
        rationale="Commercial usefulness is a hard gate: clear offer, value, action, and a concise evidence boundary must survive the first meaningful viewport. Sparse verified evidence retains a visible score margin rather than becoming the page narrative.",
    )
