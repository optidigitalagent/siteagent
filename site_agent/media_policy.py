"""Canonical media provenance and truthfulness policy for SiteAgent.

Legacy ``source_kind`` values remain readable for crash recovery, but every
new or upgraded asset receives exactly one ``provenance_type`` from the public
product contract defined here.
"""
from __future__ import annotations

import hashlib
import re
from enum import Enum
from html import unescape
from typing import Any, Iterable


class MediaProvenanceType(str, Enum):
    USER_PROVIDED_BUSINESS_ASSET = "user_provided_business_asset"
    VERIFIED_OFFICIAL_BUSINESS_ASSET = "verified_official_business_asset"
    LICENSED_STOCK_ASSET = "licensed_stock_asset"
    AI_GENERATED_ORIGINAL = "ai_generated_original"
    REFERENCE_ONLY = "reference_only"


SITE_USABLE_PROVENANCE = frozenset({
    MediaProvenanceType.USER_PROVIDED_BUSINESS_ASSET.value,
    MediaProvenanceType.VERIFIED_OFFICIAL_BUSINESS_ASSET.value,
    MediaProvenanceType.LICENSED_STOCK_ASSET.value,
    MediaProvenanceType.AI_GENERATED_ORIGINAL.value,
})

SAFE_GENERATED_CLAIM_ROLES = frozenset({
    "atmosphere",
    "background_composition",
    "service_visualization",
    "object_scene",
    "lifestyle_neutral",
    "abstract_brand",
    "decorative_texture",
    "illustration",
})

FORBIDDEN_GENERATED_CLAIM_ROLES = frozenset({
    "real_employee",
    "specific_doctor",
    "business_owner",
    "real_business_interior",
    "real_office",
    "real_clinic",
    "real_company_work",
    "real_case",
    "before_after",
    "real_review",
    "certificate",
    "award",
    "document",
    "client_documentary_photo",
    "specific_result_evidence",
})


def canonical_provenance_type(asset: dict[str, Any]) -> str:
    """Return the canonical provenance type, upgrading known legacy records."""
    explicit = str(asset.get("provenance_type", "")).strip()
    source_kind = str(asset.get("source_kind", "unknown")).strip().lower()
    derived = ""
    if source_kind in {"fixture_stock", "reference", "reference_only", "unknown", ""}:
        derived = MediaProvenanceType.REFERENCE_ONLY.value
    if source_kind in {"ai_generated", "generated", "ai_generated_original"}:
        derived = MediaProvenanceType.AI_GENERATED_ORIGINAL.value
    elif source_kind in {"stock", "licensed_stock"}:
        derived = (
            MediaProvenanceType.LICENSED_STOCK_ASSET.value
            if asset.get("license_name") or asset.get("license_url")
            else MediaProvenanceType.REFERENCE_ONLY.value
        )
    elif str(asset.get("source_role", "")).startswith("user_provided"):
        derived = MediaProvenanceType.USER_PROVIDED_BUSINESS_ASSET.value
    elif source_kind == "business" and str(asset.get("original_origin", "")).startswith("user:"):
        derived = MediaProvenanceType.USER_PROVIDED_BUSINESS_ASSET.value
    elif source_kind in {"business", "business_social", "business_web"}:
        derived = MediaProvenanceType.VERIFIED_OFFICIAL_BUSINESS_ASSET.value
    elif not derived:
        derived = MediaProvenanceType.REFERENCE_ONLY.value
    if explicit == MediaProvenanceType.REFERENCE_ONLY.value:
        return explicit
    if explicit in {item.value for item in MediaProvenanceType} and explicit != derived:
        return MediaProvenanceType.REFERENCE_ONLY.value
    return explicit or derived


def with_canonical_provenance(asset: dict[str, Any]) -> dict[str, Any]:
    upgraded = dict(asset)
    upgraded["provenance_type"] = canonical_provenance_type(upgraded)
    return upgraded


def normalize_manifest_provenance(manifest: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(manifest)
    normalized["provenance_schema_version"] = 1
    normalized["media"] = [
        with_canonical_provenance(item)
        for item in manifest.get("media", [])
        if isinstance(item, dict)
    ]
    normalized["metadata_only_media"] = [
        with_canonical_provenance(item)
        for item in manifest.get("metadata_only_media", [])
        if isinstance(item, dict)
    ]
    return normalized


def asset_is_renderable(asset: dict[str, Any], *, target: str) -> bool:
    """Check rights/provenance without converting one provenance into another."""
    provenance = canonical_provenance_type(asset)
    if provenance not in SITE_USABLE_PROVENANCE:
        return False
    if provenance == MediaProvenanceType.LICENSED_STOCK_ASSET.value:
        if not (asset.get("license_name") or asset.get("license_url")):
            return False
    if provenance == MediaProvenanceType.AI_GENERATED_ORIGINAL.value:
        if not (
            asset.get("generation_model")
            and asset.get("prompt_checksum")
            and asset.get("original_checksum")
            and str(asset.get("claim_role", "")) in SAFE_GENERATED_CLAIM_ROLES
            and asset.get("portfolio_claim") is not True
        ):
            return False
    if target == "isolated_preview":
        if provenance == MediaProvenanceType.VERIFIED_OFFICIAL_BUSINESS_ASSET.value:
            return asset.get("user_authorized_for_preview") is True
        if provenance == MediaProvenanceType.USER_PROVIDED_BUSINESS_ASSET.value:
            return asset.get("user_authorized_for_preview") is True or asset.get("user_authorized") is True
        return asset.get("user_authorized_for_preview") is True
    if target == "customer_production":
        return (
            asset.get("allowed_for_customer_production") is True
            or asset.get("allowed_for_public_site") is True
        )
    raise ValueError(f"Unsupported media target: {target}")


def manifest_policy_issues(
    manifest: dict[str, Any],
    *,
    target: str,
    require_media: bool = True,
) -> list[str]:
    media = [item for item in manifest.get("media", []) if isinstance(item, dict)]
    issues: list[str] = []
    if require_media and not media:
        issues.append("media manifest contains no renderable assets")
    for index, item in enumerate(media):
        provenance = canonical_provenance_type(item)
        if str(item.get("provenance_type", "")) != provenance:
            issues.append(f"media[{index}] lacks one canonical provenance_type")
        if provenance == MediaProvenanceType.REFERENCE_ONLY.value:
            issues.append(f"media[{index}] is reference_only and cannot enter site output")
            continue
        if not asset_is_renderable(item, target=target):
            issues.append(f"media[{index}] is not authorised or truthful for {target}")
        if provenance == MediaProvenanceType.AI_GENERATED_ORIGINAL.value:
            role = str(item.get("claim_role", ""))
            if role in FORBIDDEN_GENERATED_CLAIM_ROLES:
                issues.append(f"media[{index}] generated asset claims forbidden documentary role {role}")
    return issues


def _rendered_tags(html: str, url: str) -> list[str]:
    escaped = re.escape(url)
    return re.findall(
        rf"<(?:img|source|video|audio|embed|object|image)\b[^>]*(?:src|srcset|poster|data|href|xlink:href)=[\"'][^\"']*{escaped}[^\"']*[\"'][^>]*>",
        html,
        flags=re.I,
    )


def rendered_media_policy_issues(manifest: dict[str, Any], html: str) -> list[str]:
    """Validate actual rendered use, including generated-media claim labels."""
    decoded = unescape(html)
    issues: list[str] = []
    for item in manifest.get("media", []):
        if not isinstance(item, dict):
            continue
        url = str(item.get("url", ""))
        if not url or url not in decoded:
            continue
        provenance = canonical_provenance_type(item)
        if provenance == MediaProvenanceType.REFERENCE_ONLY.value:
            issues.append(f"reference_only asset is rendered: {item.get('asset_id') or url}")
            continue
        if provenance != MediaProvenanceType.AI_GENERATED_ORIGINAL.value:
            continue
        tags = _rendered_tags(decoded, url)
        if not tags:
            issues.append(f"generated asset rendered outside a traceable media element: {item.get('asset_id') or url}")
            continue
        for use_index, tag in enumerate(tags, start=1):
            label = f"{item.get('asset_id') or url} use {use_index}"
            provenance_attr = re.search(r"data-media-provenance=[\"']([^\"']+)", tag, flags=re.I)
            role_attr = re.search(r"data-media-claim-role=[\"']([^\"']+)", tag, flags=re.I)
            if not provenance_attr or provenance_attr.group(1) != MediaProvenanceType.AI_GENERATED_ORIGINAL.value:
                issues.append(f"generated asset lacks data-media-provenance: {label}")
            rendered_role = role_attr.group(1) if role_attr else ""
            if rendered_role not in SAFE_GENERATED_CLAIM_ROLES:
                issues.append(f"generated asset has unsafe or missing rendered claim role: {label}")
            if rendered_role and rendered_role != str(item.get("claim_role", "")):
                issues.append(f"generated asset rendered claim role does not match its media plan: {label}")
    return issues


def provenance_summary(manifest: dict[str, Any]) -> dict[str, int]:
    counts = {item.value: 0 for item in MediaProvenanceType}
    for asset in manifest.get("media", []):
        if isinstance(asset, dict):
            counts[canonical_provenance_type(asset)] += 1
    return counts


def checksum_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()
