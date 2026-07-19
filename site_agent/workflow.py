"""Durable contracts for the separated strategy and implementation planes."""
from __future__ import annotations

import hashlib
import json
from urllib.parse import urlparse
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from site_agent.config import Settings, settings


class WorkflowConfigurationError(RuntimeError):
    pass


def checksum(value: Any) -> str:
    """Stable digest for a JSON-like artifact without ever serialising secrets."""
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def role_provenance(*, role: str, provider: str, model: str, prompt_version: str, prompt: dict, inputs: dict, output: dict, used: bool = True) -> dict:
    """Audit a model role without retaining prompts that could contain secrets."""
    return {"role": role, "provider": provider, "model": model, "prompt_version": prompt_version, "prompt_checksum": checksum(prompt), "input_checksum": checksum(inputs), "output_checksum": checksum(output), "timestamp": datetime.now(timezone.utc).isoformat(), "used": used}


def validate_role_providers(config: Settings = settings) -> None:
    expected = {
        "RESEARCH_STRATEGIST_PROVIDER": (config.research_strategist_provider, {"openai"}),
        "REFERENCE_ANALYST_PROVIDER": (config.reference_analyst_provider, {"openai"}),
        "DESIGN_DIRECTOR_PROVIDER": (config.design_director_provider, {"openai"}),
        "SITE_BUILDER_PROVIDER": (config.site_builder_provider, {"codex"}),
    }
    for variable, (value, allowed) in expected.items():
        if value.strip().lower() not in allowed:
            raise WorkflowConfigurationError(f"{variable} must be one of {', '.join(sorted(allowed))}; got {value!r}.")


def _tokens(value: Any) -> set[str]:
    if isinstance(value, list):
        return {token for item in value for token in _tokens(item)}
    return {item for item in re.findall(r"[\w-]{3,}", str(value).lower()) if item not in {"site", "business", "design", "reference"}}


def reference_query(business_research: dict | None = None, design_brief: dict | None = None) -> dict[str, Any]:
    research = (business_research or {}).get("research", business_research or {})
    return {
        "business": [research.get("niche", ""), research.get("product_identity", {}).get("exact_product", "")],
        "audience": [business_research.get("target_audience", "") if business_research else ""],
        "level": [business_research.get("business_level", "") if business_research else ""],
        "atmosphere": [research.get("brand_atmosphere", ""), *(research.get("colors", []) or [])],
        "conversion": [design_brief.get("cta_logic", "") if design_brief else "", *(research.get("contacts", []) or [])],
        "media": [design_brief.get("media_treatment", "") if design_brief else "", *(business_research.get("brand_media_signals", []) if business_research else [])],
        "emotion": [design_brief.get("central_idea", "") if design_brief else ""],
        "structure": [design_brief.get("narrative", "") if design_brief else "", *(design_brief.get("page_structure", []) if design_brief else [])],
    }


def _reference_score(reference: dict, query: dict[str, Any]) -> tuple[int, list[str]]:
    corpus = _tokens([reference.get("traits", []), reference.get("search_text", ""), reference.get("business_context", ""), reference.get("audience", ""), reference.get("conversion_goal", ""), reference.get("reusable_cross_category_traits", []), reference.get("composition", {}), reference.get("narrative", "")])
    score, reasons = 0, []
    weights = {"business": 1, "audience": 2, "level": 2, "atmosphere": 3, "conversion": 3, "media": 2, "emotion": 2, "structure": 3}
    for dimension, values in query.items():
        hits = corpus & _tokens(values)
        if hits:
            score += weights[dimension] * min(3, len(hits))
            reasons.append(f"{dimension}: {', '.join(sorted(hits)[:3])}")
    # Category coincidence can inform relevance, never decide it alone.
    non_business = [reason for reason in reasons if not reason.startswith("business:")]
    if not non_business:
        score = min(score, 1)
        reasons.append("category-only similarity is intentionally capped")
    return score, reasons


def selected_references(
    root: Path = Path("references/site_designs"),
    limit: int = 6,
    *,
    business_research: dict | None = None,
    design_brief: dict | None = None,
) -> list[dict]:
    catalog = root / "catalog.json"
    if not catalog.is_file():
        raise WorkflowConfigurationError("reference-input checkpoint blocked: references/site_designs/catalog.json is missing; run python -m site_agent.reference_import first.")
    data = json.loads(catalog.read_text(encoding="utf-8"))
    captured_count = sum(1 for item in data.get("references", []) if item.get("capture_status") == "captured" and item.get("analysis_status") == "completed")
    if captured_count < 3:
        raise WorkflowConfigurationError("reference-input checkpoint blocked: at least three fully analysed captured trait references are required.")
    decisions_path = root / str(data.get("decision_artifact", "reference_decisions.json"))
    if not decisions_path.is_file():
        raise WorkflowConfigurationError("reference-input checkpoint blocked: autonomous reference decisions are missing; run python -m site_agent.reference_import.")
    decisions = json.loads(decisions_path.read_text(encoding="utf-8"))
    active = {
        str(item.get("reference_id")): item for item in decisions.get("decisions", [])
        if item.get("decision") == "active" and int(item.get("confidence", 0)) >= 90
    }
    def _site_identity(value: object) -> str:
        """Compare owned sites by host/path, not an incidental http/https variant."""
        parsed = urlparse(str(value or "").strip().lower())
        host = parsed.netloc.removeprefix("www.")
        path = parsed.path.rstrip("/")
        return f"{host}{path}" if host else ""

    research_url = _site_identity(((business_research or {}).get("research", business_research or {}).get("instagram_url", "")))
    usable = []
    for item in data.get("references", []):
        item_id = str(item.get("id", ""))
        # A business's existing public site can establish media provenance or
        # facts, but it must never influence the new site's design, copy, or
        # layout. Exclude that exact canonical site from reference selection.
        record_urls = {
            _site_identity(item.get(key, ""))
            for key in ("source_url", "normalized_url", "url")
        }
        if research_url and research_url in record_urls:
            continue
        if item_id not in active or item.get("capture_status") != "captured" or item.get("analysis_status") != "completed":
            continue
        paths = item.get("screenshot_paths", [])
        if set(paths) != {"desktop.png", "mobile.png"}:
            continue
        try:
            expected = item.get("capture", {}).get("screenshots", {})
            if not all((root / item_id / name).is_file() and hashlib.sha256((root / item_id / name).read_bytes()).hexdigest() == expected.get(name) for name in paths):
                continue
        except OSError:
            continue
        copy = dict(item)
        copy["scope_of_learning"] = active[item_id].get("scope_of_learning")
        copy["autonomous_decision_confidence"] = active[item_id].get("confidence")
        usable.append(copy)
    if len(usable) < 3:
        raise WorkflowConfigurationError("reference-input checkpoint blocked: at least three fully analysed captured trait references are required.")
    query = reference_query(business_research, design_brief)
    ranked = []
    for record in usable:
        score, rationale = _reference_score(record, query)
        copy = dict(record)
        copy["selection_score"] = score
        copy["selection_rationale"] = rationale or ["broad cross-category visual reference; selected only with stronger trait matches"]
        ranked.append(copy)
    ranked.sort(key=lambda item: (-item["selection_score"], item.get("id", "")))
    selected = ranked[: max(3, min(6, limit))]
    if not selected:
        raise WorkflowConfigurationError("reference-input checkpoint blocked: no analysed reference could be ranked.")
    return selected


def _bullets(lines: list[str]) -> list[str]:
    return [f"- {line}" for line in lines if str(line).strip()] or ["- Not evidenced in the current source material."]


def write_markdown(path: Path, title: str, payload: dict) -> None:
    """Write a readable handoff document, with structured JSON retained separately."""
    if title == "Business research":
        research = payload.get("research", {})
        lines = [f"# {title}", "", "## Business identity", "", f"- **Business:** {research.get('business_name') or 'Not confirmed'}", f"- **Exact offer:** {(research.get('product_identity') or {}).get('exact_product') or 'Not confirmed'}", f"- **Language / location:** {research.get('primary_language') or 'Not confirmed'} / {research.get('city') or 'Not confirmed'}", "", "## Customer and commercial context", "", f"{payload.get('target_audience') or 'Audience is not yet evidenced.'}", "", f"{payload.get('buying_context') or 'Buying context is not yet evidenced.'}", "", "## Positioning and evidence", "", *_bullets(payload.get("positioning", []) + payload.get("differentiators", [])), "", "## Trust, media and customer questions", "", *_bullets(payload.get("trust_signals", []) + payload.get("brand_media_signals", []) + payload.get("customer_questions", [])), "", "## Scope decision", "", f"**Recommended scope:** `{payload.get('recommended_scope', 'blocked')}`", "", "## Unknowns and prohibited claims", "", *_bullets(research.get("unknowns", []) + research.get("forbidden_claims", [])), "", "## Sources", "", *_bullets([f"{item.get('source', 'source')}: {item.get('value', '')}" for item in payload.get("citations", []) + research.get("verified_facts", [])])]
    elif title == "Design implementation brief":
        lines = [f"# {title}", "", "## Central creative idea", "", payload.get("central_idea", "Not generated."), "", "## First viewport", "", payload.get("first_viewport", "Not generated."), "", "## Page narrative and sections", "", payload.get("narrative", "Not generated."), "", *_bullets(payload.get("page_structure", []) + payload.get("section_requirements", [])), "", "## Visual system", "", f"- **Typography:** {payload.get('typography', '')}", f"- **Palette and contrast:** {payload.get('palette', '')}", f"- **Grid and rhythm:** {payload.get('spacing_grid', '')}", f"- **Media:** {payload.get('media_treatment', '')}", f"- **Motion:** {payload.get('motion', '')}", "", "## Conversion and responsiveness", "", f"- **CTA logic:** {payload.get('cta_logic', '')}", f"- **Responsive behavior:** {payload.get('responsive_behavior', '')}", f"- **Copy direction:** {payload.get('copy_direction', '')}", "", "## Reference rationale", "", payload.get("reference_rationale", "No reference is a template."), "", "## Explicit anti-patterns", "", *_bullets(payload.get("anti_patterns", []) + payload.get("do_not_copy", []))]
    else:
        lines = [f"# {title}", "", "This is a readable workflow artifact. The adjacent JSON file is the machine-readable source of truth."]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def implementation_package(*, business_research: dict, media_manifest: dict, design_brief: dict, references: list[dict], target: str = "production") -> dict:
    research = business_research.get("research", {})
    required_research = (
        "product_identity", "primary_language", "content_themes", "verified_facts",
        "unknowns", "forbidden_claims", "requested_product_type",
    )
    required_design = (
        "central_idea", "narrative", "first_viewport", "page_structure",
        "section_requirements", "cta_logic", "responsive_behavior", "media_treatment", "do_not_copy",
    )
    missing = [f"research.{key}" for key in required_research if key not in research]
    missing.extend(f"design.{key}" for key in required_design if key not in design_brief)
    package = {
        "schema_version": 3,
        "requested_product_type": research.get("requested_product_type", "full_commercial_site"),
        "delivery_target": target,
        "business_research": business_research,
        "authorised_media_manifest": media_manifest,
        "design_implementation_brief": design_brief,
        "selected_references": references,
        "commercial_completeness_contract": {
            "required_capabilities": [
                "identity_value", "offer_services", "proof", "brand_about", "trust_process",
                "commercial_decision", "objection_handling", "final_conversion",
            ],
            "full_site_minimum_semantic_sections": 7,
            "redirect_only_is_rejected": True,
            "technical_pass_cannot_override_product_failure": True,
        },
        "implementation_package_information_loss": not missing,
        "missing_required_handoff_fields": missing,
        "input_checksums": {
            "business_research": checksum(business_research),
            "media_manifest": checksum(media_manifest),
            "design_implementation_brief": checksum(design_brief),
            "selected_references": checksum(references),
        },
        "acceptance_contract": {
            "use_only_authorised_cloudinary_business_media": True,
            "isolated_preview_business_social_media_allowed": target == "isolated_preview",
            "preview_media_never_implies_production_rights": True,
            "no_reference_copying": True,
            "first_viewport_requires_offer_and_cta": True,
            "persistent_navigation_required_on_scrollable_pages": True,
            "semantic_footer_requires_navigation_and_conversion": True,
            "footer_social_and_contact_routes_must_be_verified": True,
            "primary_cta_text_geometry_must_remain_intact": True,
            "site_shell_must_pass_every_declared_page_and_viewport": True,
            "functional_shell_does_not_prescribe_visual_composition": True,
            "independent_screenshot_review_required": True,
            "independent_product_director_required": True,
            "human_calibration_remains_blocking": True,
        },
    }
    package["sha256"] = checksum(package)
    return package
