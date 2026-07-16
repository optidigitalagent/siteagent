"""Durable contracts for the separated strategy and implementation planes."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from site_agent.config import Settings, settings


class WorkflowConfigurationError(RuntimeError):
    pass


def validate_role_providers(config: Settings = settings) -> None:
    expected = {
        "RESEARCH_STRATEGIST_PROVIDER": (config.research_strategist_provider, {"openai"}),
        "DESIGN_DIRECTOR_PROVIDER": (config.design_director_provider, {"openai"}),
        "SITE_BUILDER_PROVIDER": (config.site_builder_provider, {"codex"}),
    }
    for variable, (value, allowed) in expected.items():
        if value.strip().lower() not in allowed:
            raise WorkflowConfigurationError(f"{variable} must be one of {', '.join(sorted(allowed))}; got {value!r}.")


def selected_references(root: Path = Path("references/site_designs"), limit: int = 6) -> list[dict]:
    catalog = root / "catalog.json"
    if not catalog.is_file():
        raise WorkflowConfigurationError("reference-input checkpoint blocked: references/site_designs/catalog.json is missing; run python -m site_agent.reference_import first.")
    data = json.loads(catalog.read_text(encoding="utf-8"))
    usable = [item for item in data.get("references", []) if item.get("capture_status") == "captured"]
    if len(usable) < 3:
        raise WorkflowConfigurationError("reference-input checkpoint blocked: at least three captured trait references are required.")
    return usable[:limit]


def write_markdown(path: Path, title: str, payload: dict) -> None:
    lines = [f"# {title}", "", "```json", json.dumps(payload, ensure_ascii=False, indent=2), "```", ""]
    path.write_text("\n".join(lines), encoding="utf-8")


def implementation_package(*, business_research: dict, media_manifest: dict, design_brief: dict, references: list[dict]) -> dict:
    package = {
        "schema_version": 1,
        "business_research": business_research,
        "authorised_media_manifest": media_manifest,
        "design_implementation_brief": design_brief,
        "selected_references": references,
        "acceptance_contract": {
            "use_only_authorised_cloudinary_business_media": True,
            "no_reference_copying": True,
            "first_viewport_requires_offer_and_cta": True,
            "independent_screenshot_review_required": True,
            "human_calibration_remains_blocking": True,
        },
    }
    canonical = json.dumps(package, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    package["sha256"] = hashlib.sha256(canonical).hexdigest()
    return package
