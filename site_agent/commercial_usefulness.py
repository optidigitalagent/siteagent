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
    items: list[SemanticRepetitionItem] = Field(default_factory=list)
    section_intents: dict[str, str] = Field(default_factory=dict)
    missing_information_ratio: float = Field(default=0.0, ge=0, le=1)


def _plain_text(value: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", value or "")).strip()


def _sections_from_html(html_text: str) -> list[tuple[str, str]]:
    sections: list[tuple[str, str]] = []
    for index, match in enumerate(re.finditer(r"<section\b(?P<attrs>[^>]*)>(?P<body>.*?)</section>", html_text or "", re.I | re.S), 1):
        attrs, body = match.group("attrs"), match.group("body")
        id_match = re.search(r"\bid\s*=\s*['\"]([^'\"]+)['\"]", attrs, re.I)
        sections.append((id_match.group(1) if id_match else f"section-{index}", _plain_text(body)))
    return sections


def _intent(text: str, offerings: list[str]) -> str:
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


def semantic_repetition_report(spec: Any, context: Any, *, html_text: str = "") -> SemanticRepetitionReport:
    sections = _sections_from_html(html_text)
    if not sections:
        sections = [(section.id, " ".join([section.title, *section.content])) for section in spec.sections]
    intents = {section_id: _intent(text, context.business_brief.verified_offerings) for section_id, text in sections}
    total_words = sum(len(text.split()) for _, text in sections)
    missing_words = sum(len(text.split()) for section_id, text in sections if intents[section_id] == "ask for missing current details")
    missing_ratio = round(missing_words / max(total_words, 1), 3)
    duplicates = []
    for idea, count in Counter(intents.values()).items():
        ids = [section_id for section_id, value in intents.items() if value == idea]
        if count >= 3 and idea != "other":
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
    return SemanticRepetitionReport(approved=not duplicates, items=duplicates, section_intents=intents, missing_information_ratio=missing_ratio)


def language_fit_report(spec: Any, research: Any) -> LanguageFitReport:
    selected = (spec.language or "").strip().lower()
    evidence_language = (research.primary_language or "").strip().lower()
    if evidence_language:
        approved = selected == evidence_language or selected.startswith(evidence_language + "-")
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
) -> CommercialUsefulnessReport:
    semantic = semantic or semantic_repetition_report(spec, context, html_text=html_text)
    hero = " ".join([spec.h1, spec.hero_subtitle]).lower()
    all_text = _plain_text(html_text) or " ".join([
        spec.h1, spec.hero_subtitle, *spec.trust_points,
        *[" ".join([section.title, *section.content]) for section in spec.sections],
    ])
    offer_terms = [item.lower() for item in context.business_brief.verified_offerings if item.strip()]
    category_terms = [term for term in re.findall(r"[a-z]{4,}", context.business_brief.business_category.lower()) if term not in {"private", "independent"}]
    offer_visible = any(
        term in hero or term.rstrip("s") in hero
        for term in [*offer_terms, *category_terms]
    )
    primary_action = bool(spec.primary_cta.strip())
    hero_action = primary_action if hero_cta_present is None else hero_cta_present
    audience = (context.business_brief.audience or "").strip().lower()
    audience_clear = audience not in {"", "a prospective customer", "prospective customer", "visitor"} or any(term in hero for term in category_terms)
    value_clear = offer_visible and bool(spec.hero_subtitle.strip())
    conversion_path = primary_action and ("instagram" in all_text.lower() or "direct" in all_text.lower() or bool(context.business_brief.primary_cta))
    business_information = bool(offer_terms)
    # This is a commercial gate, so it must work for the verified site language
    # rather than silently favouring an English fixture vocabulary. The terms are
    # deliberately broad sensory/product stems, not unsupported superlatives.
    desire_terms = (
        "private", "evening", "experience", "time on the water", "occasion",
        "квіт", "простір", "світл", "жив", "момент", "атмосфер", "церемон",
    )
    evidence_backed_value = any(
        phrase.strip().lower() in all_text.lower()
        for phrase in context.business_brief.differentiators
        if len(phrase.strip()) >= 4
    )
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
        approved=score >= 85 and all(checks[key] for key in ("offer_clear_within_five_seconds", "primary_action_clear", "primary_cta_in_first_meaningful_viewport", "missing_information_is_not_primary_narrative", "desire_created", "reads_as_commercial_site")),
        checks=checks,
        issues=issues,
        rationale="Commercial usefulness is a hard gate: clear offer, value, action, and a concise evidence boundary must survive the first meaningful viewport. Sparse verified evidence retains a visible score margin rather than becoming the page narrative.",
    )
