"""Autonomous reference discovery, validation, and library decisions.

Raw screenshot records are deliberately immutable evidence.  This module writes
the separate decision layer consumed by production reference selection: an
award/gallery page may introduce a candidate, but only its resolved live site
can become an active reference.
"""
from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
from typing import Any, Iterable, Protocol
from urllib.parse import urljoin, urlsplit

import requests
from bs4 import BeautifulSoup
from PIL import Image, ImageStat


AWARD_HOSTS = {"www.awwwards.com", "awwwards.com", "www.cssdesignawards.com", "cssdesignawards.com"}
BLOCKED_HOST_TOKENS = ("facebook.", "instagram.", "linkedin.", "twitter.", "x.com", "youtube.", "vimeo.")
PARKING_TOKENS = ("domain for sale", "buy this domain", "coming soon", "parked domain", "website coming soon")
INVALID_REASONS = {
    "capture_failed", "analysis_incomplete", "blank", "404", "parking", "login_wall",
    "unrelated_redirect", "mobile_mismatch", "critical_assets_missing", "duplicate",
    "near_duplicate", "low_confidence", "curator_auditor_disagreement", "insufficient_scope",
}


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def normalized_host(url: str) -> str:
    return urlsplit(url).netloc.lower().removeprefix("www.")


def image_signature(path: Path) -> tuple[str, float, tuple[int, int]]:
    """Return a lightweight visual signature, contrast score and dimensions."""
    with Image.open(path) as source:
        image = source.convert("L")
        dimensions = image.size
        contrast = float(ImageStat.Stat(image).var[0])
        sample = image.resize((16, 16))
        values = list(sample.get_flattened_data())
        average = sum(values) / 256
        bits = "".join("1" if value >= average else "0" for value in values)
    return f"{int(bits, 2):064x}", contrast, dimensions


def signature_distance(left: str, right: str) -> int:
    return (int(left, 16) ^ int(right, 16)).bit_count()


@dataclass(frozen=True)
class DiscoveryCandidate:
    source: str
    source_url: str
    award: str
    year: int | None
    title: str
    candidate_url: str
    score: float | None = None


class DiscoveryAdapter(Protocol):
    name: str

    def discover(self, *, limit: int, session: requests.Session) -> list[DiscoveryCandidate]: ...


class AwardPageAdapter:
    """Conservative adapter for an award listing page.

    It records only candidates.  A later resolver rejects a gallery URL unless
    it can find a distinct original live URL, which prevents a gallery itself
    ever being selected as a reference.
    """

    def __init__(self, name: str, source_url: str, award: str, year: int | None = None) -> None:
        self.name, self.source_url, self.award, self.year = name, source_url, award, year

    def discover(self, *, limit: int, session: requests.Session) -> list[DiscoveryCandidate]:
        response = session.get(self.source_url, timeout=25, headers={"User-Agent": "SiteAgent Reference Discovery/1.0"})
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
        seen: set[str] = set()
        candidates: list[DiscoveryCandidate] = []
        for anchor in soup.select("a[href]"):
            href = urljoin(response.url, str(anchor.get("href", "")).strip())
            host = normalized_host(href)
            if not href.startswith(("http://", "https://")) or host not in AWARD_HOSTS:
                continue
            if href in seen or "/sites/" not in urlsplit(href).path:
                continue
            title = " ".join(anchor.stripped_strings) or urlsplit(href).path.rsplit("/", 1)[-1].replace("-", " ")
            if len(title) < 3:
                continue
            seen.add(href)
            candidates.append(DiscoveryCandidate(self.name, response.url, self.award, self.year, title[:180], href))
            if len(candidates) >= limit:
                break
        return candidates


class OriginalLiveSiteResolver:
    """Resolve a gallery record to an independently hosted original site."""

    def resolve(self, candidate: DiscoveryCandidate, *, session: requests.Session) -> dict[str, Any]:
        response = session.get(candidate.candidate_url, timeout=25, headers={"User-Agent": "SiteAgent Reference Discovery/1.0"})
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
        links: list[str] = []
        for anchor in soup.select("a[href]"):
            href = urljoin(response.url, str(anchor.get("href", "")).strip())
            host = normalized_host(href)
            if not href.startswith(("http://", "https://")) or host in AWARD_HOSTS:
                continue
            if any(token in host for token in BLOCKED_HOST_TOKENS):
                continue
            label = " ".join(anchor.stripped_strings).lower()
            score = 0
            if any(token in label for token in ("visit", "website", "view site", "live site", "launch")):
                score += 4
            if host and host != normalized_host(candidate.candidate_url):
                score += 1
            links.append((score, href))
        if not links:
            return {"status": "unresolved", "reason": "original_live_url_not_found"}
        links.sort(key=lambda item: (-item[0], item[1]))
        original = links[0][1]
        return {"status": "resolved", "original_url": original, "resolution_source": response.url}


class ReferenceDiscoveryAgent:
    """Fetch award candidates and preserve failure state without blocking resume."""

    def __init__(self, adapters: Iterable[DiscoveryAdapter] | None = None, resolver: OriginalLiveSiteResolver | None = None) -> None:
        self.adapters = tuple(adapters or (
            AwardPageAdapter("css_design_awards", "https://www.cssdesignawards.com/wotd-award-winners", "WOTD"),
            AwardPageAdapter("awwwards", "https://www.awwwards.com/websites/", "SOTD / Honorable Mention"),
        ))
        self.resolver = resolver or OriginalLiveSiteResolver()

    def discover(self, *, limit_per_source: int = 12) -> list[dict[str, Any]]:
        session = requests.Session()
        results: list[dict[str, Any]] = []
        for adapter in self.adapters:
            try:
                candidates = adapter.discover(limit=limit_per_source, session=session)
            except Exception as exc:
                results.append({"source": adapter.name, "status": "failed", "reason": _safe(str(exc))})
                continue
            for candidate in candidates:
                try:
                    resolved = self.resolver.resolve(candidate, session=session)
                    results.append({**asdict(candidate), **resolved, "discovered_at": now()})
                except Exception as exc:
                    results.append({**asdict(candidate), "status": "unresolved", "reason": _safe(str(exc)), "discovered_at": now()})
        return results


def _safe(value: str) -> str:
    return re.sub(r"(?i)(api[_-]?key|authorization|bearer)\s*[:= ]\s*\S+", r"\1=[REDACTED_SECRET]", value)[:500]


class ReferenceCurator:
    """Makes an evidence-bound usefulness decision from raw captures and analysis."""

    def assess(self, record: dict[str, Any], folder: Path, *, covered_traits: set[str]) -> dict[str, Any]:
        reasons: list[str] = []
        rejected: list[str] = []
        if record.get("capture_status") != "captured":
            rejected.append("capture_failed")
        if record.get("analysis_status") != "completed":
            rejected.append("analysis_incomplete")
        capture = record.get("capture", {})
        final_url = capture.get("final_url", "")
        title = str(record.get("title", "")).strip()
        if not final_url:
            rejected.append("unrelated_redirect")
        statuses = capture.get("http_status", {})
        if any(isinstance(code, int) and code >= 400 for code in statuses.values()):
            rejected.append("404")
        if any(token in (title + " " + str(record.get("analysis", {}).get("business_context", ""))).lower() for token in ("404", "site not found", "page not found", "default error page")):
            rejected.append("404")
        if capture.get("failed_critical_assets"):
            rejected.append("critical_assets_missing")
        scope = "full_site"
        screenshot_fingerprints: dict[str, str] = {}
        for name in ("desktop.png", "mobile.png"):
            path = folder / name
            if not path.is_file():
                rejected.append("capture_failed")
                continue
            try:
                fingerprint, contrast, size = image_signature(path)
            except Exception:
                rejected.append("capture_failed")
                continue
            screenshot_fingerprints[name] = fingerprint
            if contrast < 4 or min(size) < 300:
                rejected.append("blank")
        text = " ".join(str(value) for value in record.get("analysis", {}).values()).lower()
        if any(token in text for token in PARKING_TOKENS):
            rejected.append("parking")
        if any(token in text for token in ("login wall", "sign in to continue", "log in to continue", "authentication required")):
            rejected.append("login_wall")
        analysis = record.get("analysis", {})
        traits = [str(item).strip().lower() for item in analysis.get("traits", record.get("traits", [])) if str(item).strip()]
        transferable = analysis.get("reusable_cross_category_traits", record.get("reusable_cross_category_traits", []))
        learn = analysis.get("learn", record.get("learn", []))
        do_not_copy = analysis.get("do_not_copy", record.get("do_not_copy", []))
        if len(transferable) < 2 or len(do_not_copy) < 1:
            rejected.append("low_confidence")
        architecture = analysis.get("information_architecture", [])
        if len(architecture) < 3:
            scope = _bounded_scope(analysis)
            if scope is None:
                rejected.append("insufficient_scope")
        desktop_path, mobile_path = folder / "desktop.png", folder / "mobile.png"
        if desktop_path.is_file() and mobile_path.is_file():
            try:
                with Image.open(desktop_path) as desktop_image, Image.open(mobile_path) as mobile_image:
                    # Device scale factors vary; correspondence is about a distinct narrow
                    # capture, not an exact pixel width copied from browser configuration.
                    if mobile_image.width >= desktop_image.width * 0.9:
                        rejected.append("mobile_mismatch")
            except OSError:
                rejected.append("capture_failed")
        contribution = sorted(set(traits) - covered_traits)
        if not contribution and covered_traits:
            reasons.append("does not introduce a new primary trait; retained only if it materially strengthens a sparse trait")
        if not rejected:
            reasons.extend([f"transferable principle: {item}" for item in transferable[:3]])
            reasons.append(f"learning scope: {scope}")
        score = 100 - 18 * len(set(rejected))
        if len(learn) >= 2:
            score += 2
        decision = "active" if not rejected and score >= 90 else "excluded"
        return {
            "role": "ReferenceCurator", "decision": decision, "confidence": max(0, min(100, score)),
            "reasons": reasons, "rejection_reasons": sorted(set(rejected)), "scope_of_learning": scope,
            "traits": traits, "coverage_contribution": contribution, "screenshot_fingerprints": screenshot_fingerprints,
            "assessed_at": now(),
        }


class ReferenceAuditor:
    """Independent, stricter challenge to a curator decision."""

    def assess(self, record: dict[str, Any], folder: Path, curator: dict[str, Any], *, active_signatures: dict[str, str]) -> dict[str, Any]:
        rejected = list(curator.get("rejection_reasons", []))
        capture = record.get("capture", {})
        final_url = str(capture.get("final_url", ""))
        source_url = str(record.get("original_url") or record.get("normalized_url") or record.get("source_url") or "")
        if final_url and source_url and normalized_host(final_url) != normalized_host(source_url):
            # Cross-host redirects are only valid when discovery explicitly resolved the original.
            discovery = record.get("discovery", {})
            if normalized_host(final_url) != normalized_host(str(discovery.get("original_url", source_url))):
                rejected.append("unrelated_redirect")
        for name, signature in curator.get("screenshot_fingerprints", {}).items():
            for other_id, other_signature in active_signatures.items():
                if other_id != record.get("id") and signature_distance(signature, other_signature) <= 4:
                    rejected.append("near_duplicate")
                    break
        analysis = record.get("analysis", {})
        mobile = str(analysis.get("mobile_behavior", "")).lower()
        desktop = str(analysis.get("desktop_behavior", "")).lower()
        if not mobile or not desktop or mobile == desktop:
            rejected.append("mobile_mismatch")
        if len(analysis.get("do_not_copy", [])) < 1:
            rejected.append("low_confidence")
        decision = "active" if not rejected else "excluded"
        return {
            "role": "ReferenceAuditor", "decision": decision,
            "confidence": 96 if decision == "active" else 30,
            "rejection_reasons": sorted(set(rejected)),
            "reasons": ["Independent validation of live capture, completeness, mobile evidence and visual duplication."],
            "assessed_at": now(),
        }


def _bounded_scope(analysis: dict[str, Any]) -> str | None:
    text = " ".join(str(item) for item in analysis.values()).lower()
    candidates = {
        "hero_only": ("hero", "first viewport"), "typography_only": ("typography",),
        "gallery_rhythm_only": ("gallery", "media rhythm"), "mobile_header_only": ("mobile", "header"),
        "CTA_only": ("cta",), "section_transition_only": ("transition",),
    }
    return next((scope for scope, tokens in candidates.items() if all(token in text for token in tokens)), None)


def decide_library(records: list[dict[str, Any]], root: Path) -> dict[str, Any]:
    """Return decisions separately from immutable raw records, safe to re-run."""
    curator, auditor = ReferenceCurator(), ReferenceAuditor()
    decisions: list[dict[str, Any]] = []
    covered: set[str] = set()
    signatures: dict[str, str] = {}
    for record in sorted(records, key=lambda item: str(item.get("id", ""))):
        item_id = str(record.get("id", ""))
        folder = root / item_id
        c = curator.assess(record, folder, covered_traits=covered)
        a = auditor.assess(record, folder, c, active_signatures=signatures)
        disagreement = c["decision"] != a["decision"]
        final = "active" if c["decision"] == a["decision"] == "active" else "excluded"
        final_reasons = sorted(set(c.get("rejection_reasons", []) + a.get("rejection_reasons", [])))
        if disagreement:
            final_reasons.append("curator_auditor_disagreement")
        if final == "active":
            covered.update(c["traits"])
            signatures.update(c["screenshot_fingerprints"])
        decisions.append({
            "reference_id": item_id, "decision": final,
            "confidence": min(c["confidence"], a["confidence"]), "scope_of_learning": c["scope_of_learning"],
            "curator": c, "auditor": a, "rejection_reasons": sorted(set(final_reasons)),
            "decision_at": now(),
        })
    counts = Counter(item["decision"] for item in decisions)
    return {
        "schema_version": 1, "generated_at": now(), "decisions": decisions,
        "active_reference_count": counts["active"], "excluded_reference_count": counts["excluded"],
        "covered_traits": sorted(covered), "status": "AUTONOMOUS_REFERENCE_LIBRARY_READY" if counts["active"] >= 30 else "AUTONOMOUS_REFERENCE_LIBRARY_INCOMPLETE",
    }


def write_decisions(root: Path, records: list[dict[str, Any]]) -> dict[str, Any]:
    result = decide_library(records, root)
    payload = json.dumps(result, ensure_ascii=False, indent=2)
    target = root / "reference_decisions.json"
    temporary = target.with_suffix(".json.tmp")
    temporary.write_text(payload, encoding="utf-8")
    temporary.replace(target)
    result["decision_checksum"] = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    return result
