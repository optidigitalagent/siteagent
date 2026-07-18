"""Independent, product-level acceptance for commercial SiteAgent builds.

This deliberately reads neither internal critic scores nor their rationale. It
checks the requested product against the final DOM, final screenshots and
evidence package so a technically clean concept cannot pass as a business site.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import Path
from typing import Any


FULL_ROLES = {
    "identity_value", "offer_services", "proof", "brand_about", "trust_process",
    "commercial_decision", "objection_handling", "final_conversion",
}
ROLE_ALIASES = {
    "identity": "identity_value", "hero": "identity_value", "identity_value": "identity_value",
    "offer": "offer_services", "services": "offer_services", "offer_services": "offer_services",
    "portfolio": "proof", "gallery": "proof", "proof": "proof", "case_study": "proof",
    "about": "brand_about", "brand": "brand_about", "brand_about": "brand_about",
    "process": "trust_process", "trust": "trust_process", "trust_process": "trust_process",
    "pricing": "commercial_decision", "consultation": "commercial_decision", "commercial_decision": "commercial_decision",
    "faq": "objection_handling", "objections": "objection_handling", "objection_handling": "objection_handling",
    "contact": "final_conversion", "conversion": "final_conversion", "final_conversion": "final_conversion",
}


class _PageParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.roles: set[str] = set()
        self.sections = 0
        self.anchors: list[str] = []
        self.has_form = False
        self.meta_redirect = False
        self.script_redirect = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        data = {key.lower(): value or "" for key, value in attrs}
        if tag == "section":
            self.sections += 1
        role = data.get("data-decision-role", "").strip().lower().replace("-", "_")
        if role in ROLE_ALIASES:
            self.roles.add(ROLE_ALIASES[role])
        section_id = data.get("id", "").strip().lower().replace("-", "_")
        if tag == "section" and section_id in ROLE_ALIASES:
            self.roles.add(ROLE_ALIASES[section_id])
        if tag == "a" and data.get("href"):
            self.anchors.append(data["href"])
        if tag == "form":
            self.has_form = True
        if tag == "meta" and data.get("http-equiv", "").lower() == "refresh":
            self.meta_redirect = True

    def handle_data(self, data: str) -> None:
        lowered = data.lower()
        if "window.location" in lowered or "location.href" in lowered:
            self.script_redirect = True


@dataclass(frozen=True)
class ProductDirectorAuditor:
    """A blind final-product auditor for static commercial builds."""

    def audit(
        self,
        *,
        requested_product_type: str,
        site_dir: Path,
        screenshots_dir: Path,
        business_research: dict[str, Any],
        media_manifest: dict[str, Any],
    ) -> dict[str, Any]:
        index = site_dir / "index.html"
        html = index.read_text(encoding="utf-8") if index.is_file() else ""
        parser = _PageParser()
        parser.feed(html)
        roles = set(parser.roles)
        # A real final form is conversion evidence even when a design system
        # uses a non-standard section id.
        if parser.has_form:
            roles.add("final_conversion")
        screenshots = {name: (screenshots_dir / name).is_file() for name in ("desktop.png", "tablet.png", "mobile.png")}
        full_request = requested_product_type not in {"campaign_landing", "micro_site"}
        missing = sorted(FULL_ROLES - roles) if full_request else []
        external = [href for href in parser.anchors if href.startswith(("http://", "https://"))]
        redirect_only = bool(html) and (
            parser.meta_redirect or parser.script_redirect or
            (not parser.has_form and bool(external) and len(roles - {"identity_value", "final_conversion"}) < 2)
        )
        media_count = len([item for item in media_manifest.get("media", []) if item.get("url")])
        score = 100
        caps: list[dict[str, Any]] = []
        if "offer_services" not in roles:
            caps.append({"reason": "missing offer/services coverage", "maximum_score": 40})
        if "proof" not in roles:
            caps.append({"reason": "missing proof/portfolio/trust coverage", "maximum_score": 50})
        if full_request and parser.sections <= 3:
            caps.append({"reason": "three semantic sections cannot satisfy a normal business-site request", "maximum_score": 45})
        if redirect_only:
            caps.append({"reason": "redirect-only output is not a commercial website", "maximum_score": 0})
        for cap in caps:
            score = min(score, cap["maximum_score"])
        complete = not missing and parser.sections >= 7 and not redirect_only if full_request else bool(roles & {"offer_services", "final_conversion"}) and not redirect_only
        screenshot_complete = all(screenshots.values())
        reasons = []
        if not index.is_file():
            reasons.append("final site/index.html is missing")
        if missing:
            reasons.append("missing commercial coverage: " + ", ".join(missing))
        if full_request and parser.sections < 7:
            reasons.append(f"only {parser.sections} semantic sections; full commercial site requires at least 7")
        if redirect_only:
            reasons.append("redirect-only output is forbidden")
        if not screenshot_complete:
            reasons.append("final desktop/tablet/mobile screenshots are required")
        if not business_research.get("research", {}).get("product_identity"):
            reasons.append("business research lacks a sourced product identity")
        if media_count == 0:
            reasons.append("media manifest is empty")
        accepted = complete and screenshot_complete and not reasons
        return {
            "schema_version": 1,
            "auditor": "ProductDirectorAuditor",
            "requested_product_type": requested_product_type,
            "product_accepted": accepted,
            "score": score,
            "semantic_section_count": parser.sections,
            "coverage_roles": sorted(roles),
            "missing_coverage_roles": missing,
            "redirect_only": redirect_only,
            "screenshots": screenshots,
            "media_manifest_count": media_count,
            "score_caps": caps,
            "reasons": reasons,
            "blind_input_contract": {
                "included": ["business_request", "business_research", "requested_product_type", "final_site", "final_screenshots", "media_provenance"],
                "excluded": ["internal_critic_scores", "internal_critic_rationale", "scope_shrink_rationale"],
            },
        }
