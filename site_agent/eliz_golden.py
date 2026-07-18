"""Recover and validate the blind Eliz de Fleur golden-calibration input.

The deployed baseline is used only as a media catalog source during recovery
and as a comparison target after a build. Its HTML, copy and screenshots are
never placed in the researcher, Design Director or Builder input package.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from urllib.parse import urljoin

import requests

CATALOG_URL = "https://optidigitalagent.github.io/eliz-de-fleur-site-20260711095843/media/media-catalog.json"
BASE_URL = "https://optidigitalagent.github.io/eliz-de-fleur-site-20260711095843/"
BASELINE_REFERENCE = "references/site_designs/optidigitalagent-github-io-eliz-de-fleur-site-20260711095843"


def _write(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def validate_catalog(catalog: list[dict]) -> None:
    images = [item for item in catalog if item.get("type") == "image"]
    videos = [item for item in catalog if item.get("type") == "video"]
    if len(catalog) != 26 or len(images) != 24 or len(videos) != 2:
        raise ValueError("Eliz golden input requires exactly 24 image and 2 video catalog records.")
    required = {"id", "processedFile", "type", "project", "usage", "width", "height", "altPl", "altEn"}
    malformed = [str(item.get("id", "unknown")) for item in catalog if not required <= set(item)]
    if malformed:
        raise ValueError("Eliz catalog has incomplete records: " + ", ".join(malformed))


def recover_blind_input(run_dir: Path, *, download: bool = True) -> dict:
    response = requests.get(CATALOG_URL, timeout=30)
    response.raise_for_status()
    catalog = response.json()
    if not isinstance(catalog, list):
        raise ValueError("Eliz media catalog must be a list.")
    validate_catalog(catalog)
    source_dir = run_dir / "golden_input_recovery"
    raw_dir = source_dir / "raw_media"
    source_dir.mkdir(parents=True, exist_ok=True)
    candidates = []
    recovered = []
    for item in catalog:
        # The public catalog records its source preparation paths, while the
        # deploy exposes the derivative assets under stable /media/photos and
        # /media/videos URLs. Do not fetch the baseline page itself.
        relative = f"media/photos/{item['id']}.jpg" if item["type"] == "image" else f"media/videos/{item['id']}.mp4"
        local = raw_dir / Path(relative).name
        url = urljoin(BASE_URL, relative)
        if download and not local.is_file():
            asset = requests.get(url, timeout=60)
            asset.raise_for_status()
            local.parent.mkdir(parents=True, exist_ok=True)
            local.write_bytes(asset.content)
        checksum = hashlib.sha256(local.read_bytes()).hexdigest() if local.is_file() else ""
        recovered.append({"id": item["id"], "type": item["type"], "source_url": url, "local_path": str(local), "checksum": checksum, "project": item["project"], "usage": item["usage"], "width": item["width"], "height": item["height"]})
        candidates.append({
            "path": str(local), "source_url": url, "source_kind": "business",
            "user_authorized": True, "allowed_for_public_site": True,
            "business_id": "eliz-de-fleur", "original_origin": "Eliz de Fleur documented golden-calibration media catalog",
            "original_filename": Path(relative).name, "alt": item["altPl"],
            "selected_use": item["usage"], "width": item["width"], "height": item["height"], "kind": item["type"],
        })
    research = {
        "research": {
            "instagram_url": "https://www.instagram.com/eliz_de_fleur/",
            "requested_product_type": "multi_page_commercial_site",
            "business_name": "Eliz de Fleur", "city": "Warszawa", "country": "Poland", "primary_language": "pl",
            "niche": "event and wedding design studio",
            "sells": ["event scenography", "wedding and private-event design", "corporate-event design", "photo zones and installations"],
            "services_or_products": ["Commercial Spaces", "Brand & Corporate Events", "Weddings & Private Events", "Photo Zones & Installations"],
            "contacts": ["contact form"],
            "product_identity": {"exact_product": "event scenography and floral installations for weddings, private, corporate and commercial spaces", "evidence_sources": ["golden media catalog serviceGroup/project fields"], "confidence": "high"},
            "content_themes": [
                {"label": "commercial botanical installations", "decision_role": "offer", "evidence_sources": ["golden catalog: botanical-installation"]},
                {"label": "corporate event scenography", "decision_role": "format", "evidence_sources": ["golden catalog: holiday-table"]},
                {"label": "weddings and private events", "decision_role": "format", "evidence_sources": ["golden catalog: blue-wedding, red-private-event"]},
                {"label": "photo zones and installations", "decision_role": "proof", "evidence_sources": ["golden catalog: ethno-photo-zone"]},
            ],
            "verified_facts": [
                {"source": "golden media catalog", "value": "24 processed photos and 2 processed videos; Instagram interface removed", "confidence": "high"},
                {"source": "golden media catalog", "value": "Polish and English media descriptions identify Eliz de Fleur work in Warsaw", "confidence": "high"},
            ],
            "unknowns": ["Current pricing, availability and timing are not in the calibration source."],
            "forbidden_claims": ["Do not invent price, availability, awards, team, guarantees or unrecorded case results."],
        },
        "target_audience": "Clients and planners commissioning event, wedding, private and corporate scenography in Warsaw.",
        "buying_context": "A visual portfolio must establish fit before a consultation request.",
        "positioning": ["Project-specific event and floral scenography grounded in documented work."],
        "differentiators": ["Coverage across commercial installations, corporate tables, private events and photo zones."],
        "customer_questions": ["Which project type is relevant?", "How do I start a consultation?"],
        "trust_signals": ["Documented project media with project/category provenance."],
        "brand_media_signals": ["Layered floral/event imagery and vertical process clips."],
        "recommended_scope": "full_site",
        "missing_content_manifest": [],
        "citations": [],
    }
    contract = {
        "requested_product_type": "multi_page_commercial_site",
        "blind_input_rule": "Baseline screenshots, HTML, design, copy and layout are excluded from research/design/builder inputs.",
        "minimum_output": {"default_language": "pl", "secondary_language": "en", "navigation": ["Home", "Services", "Portfolio", "Contact"], "working_form": True, "portfolio_filter": True, "required_media": {"images": 24, "videos": 2}, "viewports": ["desktop", "tablet", "mobile"]},
        "comparison_after_build_only": {"reference_dir": BASELINE_REFERENCE, "dimensions": ["completeness", "information_architecture", "media_use", "visual_quality", "mobile", "language_switching", "portfolio_depth", "commercial_journey"]},
    }
    _write(source_dir / "media_catalog.json", catalog)
    _write(source_dir / "media_recovery_report.json", {"catalog_url": CATALOG_URL, "assets": recovered, "image_count": 24, "video_count": 2, "baseline_used_as_input": False})
    _write(run_dir / "media_input" / "manifest.json", {"schema_version": 1, "media": candidates, "calibration_only": True})
    _write(source_dir / "business_research.json", research)
    _write(source_dir / "golden_contract.json", contract)
    return {"run_dir": str(run_dir), "images": 24, "videos": 2, "baseline_used_as_input": False}


def main() -> None:
    parser = argparse.ArgumentParser(description="Recover blind Eliz golden-calibration input without publishing.")
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--catalog-only", action="store_true")
    args = parser.parse_args()
    print(json.dumps(recover_blind_input(args.run_dir, download=not args.catalog_only), ensure_ascii=False))


if __name__ == "__main__":
    main()
