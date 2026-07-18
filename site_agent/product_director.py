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
        self.language_options: set[str] = set()
        self.portfolio_filters: set[str] = set()
        self.image_count = 0
        self.video_count = 0
        self.meta_redirect = False
        self.script_redirect = False
        self.has_header = False
        self.has_footer = False
        self.footer_navigation_links = 0
        self.footer_has_primary_cta = False
        self._in_footer = False
        self._in_footer_nav = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        data = {key.lower(): value or "" for key, value in attrs}
        if tag == "header":
            self.has_header = True
        if tag == "footer":
            self.has_footer = True
            self._in_footer = True
        if tag == "nav" and self._in_footer:
            self._in_footer_nav = True
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
            if self._in_footer_nav:
                self.footer_navigation_links += 1
            if self._in_footer and (
                data.get("data-site-cta") == "primary"
                or re.search(r"(?:contact|book|brief|enquir|zapyt|kontakt)", data["href"], flags=re.I)
                or data["href"].startswith(("mailto:", "tel:"))
            ):
                self.footer_has_primary_cta = True
        if tag == "form":
            self.has_form = True
        if tag == "button" and data.get("data-lang"):
            self.language_options.add(data["data-lang"].strip().lower())
        if tag == "button" and data.get("data-filter"):
            self.portfolio_filters.add(data["data-filter"].strip().lower())
        if tag == "img" and data.get("src"):
            self.image_count += 1
        if tag == "video":
            self.video_count += 1
        if tag == "meta" and data.get("http-equiv", "").lower() == "refresh":
            self.meta_redirect = True

    def handle_endtag(self, tag: str) -> None:
        if tag == "nav" and self._in_footer_nav:
            self._in_footer_nav = False
        if tag == "footer":
            self._in_footer = False

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
        multi_page_request = requested_product_type == "multi_page_commercial_site"
        required_pages = ("index.html", "services.html", "portfolio.html", "about.html", "contact.html")
        required_navigation = {"services.html", "portfolio.html", "about.html", "contact.html"}
        page_contract: dict[str, dict[str, Any]] = {}
        for page_name in required_pages:
            page_path = site_dir / page_name
            page_parser = _PageParser()
            if page_path.is_file():
                page_parser.feed(page_path.read_text(encoding="utf-8"))
            local_links = {
                href.split("#", 1)[0]
                for href in page_parser.anchors
                if href and not href.startswith(("#", "http://", "https://", "mailto:", "tel:"))
            }
            page_contract[page_name] = {
                "exists": page_path.is_file(),
                "navigation_complete": required_navigation.issubset(local_links),
                "language_switch_complete": {"pl", "en"}.issubset(page_parser.language_options),
                "has_header": page_parser.has_header,
                "has_footer": page_parser.has_footer,
                "footer_navigation_links": page_parser.footer_navigation_links,
                "footer_has_primary_cta": page_parser.footer_has_primary_cta,
                "has_form": page_parser.has_form,
                "portfolio_filters": sorted(page_parser.portfolio_filters),
                "image_count": page_parser.image_count,
                "video_count": page_parser.video_count,
            }
        missing_pages = [name for name, state in page_contract.items() if not state["exists"]]
        incomplete_navigation = [name for name, state in page_contract.items() if state["exists"] and not state["navigation_complete"]]
        incomplete_language_switches = [name for name, state in page_contract.items() if state["exists"] and not state["language_switch_complete"]]
        incomplete_shell_pages = [
            name for name, state in page_contract.items()
            if state["exists"] and not (
                state["has_header"] and state["has_footer"]
                and state["footer_navigation_links"] >= 2
                and state["footer_has_primary_cta"]
            )
        ]
        portfolio_filters_complete = {"all", "commercial", "corporate", "private", "zones"}.issubset(
            set(page_contract["portfolio.html"]["portfolio_filters"])
        )
        contact_form_present = bool(page_contract["contact.html"]["has_form"])
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
        if full_request and not (
            parser.has_header and parser.has_footer
            and parser.footer_navigation_links >= 2
            and parser.footer_has_primary_cta
        ):
            caps.append({"reason": "functional header/footer shell is incomplete", "maximum_score": 60})
        if multi_page_request and missing_pages:
            caps.append({"reason": "requested multi-page product is missing required pages", "maximum_score": 45})
        if multi_page_request and (incomplete_navigation or incomplete_language_switches):
            caps.append({"reason": "multi-page navigation or language switching is incomplete", "maximum_score": 60})
        if multi_page_request and incomplete_shell_pages:
            caps.append({"reason": "one or more pages has an incomplete functional shell", "maximum_score": 60})
        if multi_page_request and (not portfolio_filters_complete or not contact_form_present):
            caps.append({"reason": "portfolio filtering or contact conversion is incomplete", "maximum_score": 55})
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
        if full_request and not parser.has_header:
            reasons.append("final site lacks a header landmark")
        if full_request and not parser.has_footer:
            reasons.append("final site lacks a footer landmark")
        if full_request and parser.footer_navigation_links < 2:
            reasons.append("footer lacks useful navigation")
        if full_request and not parser.footer_has_primary_cta:
            reasons.append("footer lacks a primary conversion/contact action")
        if multi_page_request and missing_pages:
            reasons.append("missing required pages: " + ", ".join(missing_pages))
        if multi_page_request and incomplete_navigation:
            reasons.append("incomplete cross-page navigation: " + ", ".join(incomplete_navigation))
        if multi_page_request and incomplete_language_switches:
            reasons.append("missing PL/EN switching: " + ", ".join(incomplete_language_switches))
        if multi_page_request and incomplete_shell_pages:
            reasons.append("incomplete functional shell: " + ", ".join(incomplete_shell_pages))
        if multi_page_request and not portfolio_filters_complete:
            reasons.append("portfolio page lacks the required business filters")
        if multi_page_request and not contact_form_present:
            reasons.append("contact page lacks a working-form surface")
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
            "multi_page_contract": {
                "required": multi_page_request,
                "pages": page_contract,
                "missing_pages": missing_pages,
                "incomplete_navigation": incomplete_navigation,
                "incomplete_language_switches": incomplete_language_switches,
                "incomplete_shell_pages": incomplete_shell_pages,
                "portfolio_filters_complete": portfolio_filters_complete,
                "contact_form_present": contact_form_present,
            },
            "score_caps": caps,
            "reasons": reasons,
            "blind_input_contract": {
                "included": ["business_request", "business_research", "requested_product_type", "final_site", "final_screenshots", "media_provenance"],
                "excluded": ["internal_critic_scores", "internal_critic_rationale", "scope_shrink_rationale"],
            },
        }
