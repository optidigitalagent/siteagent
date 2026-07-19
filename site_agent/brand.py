from __future__ import annotations

import colorsys
import hashlib
import json
import math
import re
import shutil
from collections import Counter, defaultdict
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from PIL import Image, ImageChops
from bs4 import BeautifulSoup

from site_agent.workflow import checksum


_LOGO_SCREENSHOT_CACHE: dict[tuple[str, str], bool] = {}


class BrandIdentityError(RuntimeError):
    """The bounded business evidence cannot produce a valid brand package."""


def _file_checksum(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _hex(rgb: tuple[int, int, int]) -> str:
    return "#" + "".join(f"{value:02X}" for value in rgb)


def _hsl(rgb: tuple[int, int, int]) -> dict[str, float]:
    hue, lightness, saturation = colorsys.rgb_to_hls(*(value / 255 for value in rgb))
    return {
        "h": round(hue * 360, 1),
        "s": round(saturation * 100, 1),
        "l": round(lightness * 100, 1),
    }


def _relative_luminance(rgb: tuple[int, int, int]) -> float:
    channels = []
    for value in rgb:
        channel = value / 255
        channels.append(channel / 12.92 if channel <= 0.04045 else ((channel + 0.055) / 1.055) ** 2.4)
    return 0.2126 * channels[0] + 0.7152 * channels[1] + 0.0722 * channels[2]


def _contrast(a: tuple[int, int, int], b: tuple[int, int, int]) -> float:
    high, low = sorted((_relative_luminance(a), _relative_luminance(b)), reverse=True)
    return round((high + 0.05) / (low + 0.05), 2)


def _quantized_colours(path: Path, *, minimum_fraction: float = 0.004) -> list[tuple[tuple[int, int, int], float]]:
    with Image.open(path) as source:
        image = source.convert("RGB")
        image.thumbnail((320, 320))
        pixels = list(image.get_flattened_data())
    if not pixels:
        return []
    counter: Counter[tuple[int, int, int]] = Counter()
    for red, green, blue in pixels:
        hue, lightness, saturation = colorsys.rgb_to_hls(red / 255, green / 255, blue / 255)
        if lightness > 0.94 or lightness < 0.12 or saturation < 0.28:
            continue
        counter[(red // 16 * 16 + 8, green // 16 * 16 + 8, blue // 16 * 16 + 8)] += 1
    total = len(pixels)
    return [
        (colour, count / total)
        for colour, count in counter.most_common(24)
        if count / total >= minimum_fraction
    ]


def _colour_distance(a: tuple[int, int, int], b: tuple[int, int, int]) -> float:
    return math.sqrt(sum((left - right) ** 2 for left, right in zip(a, b)))


def _platform_owned_asset(item: dict[str, Any]) -> bool:
    value = str(item.get("asset_url") or item.get("url") or "").lower()
    return "lookaside.fbsbx.com/elementpath" in value or "/t39.8562-6/" in value


def brand_media_checksum(media_manifest: dict[str, Any]) -> str:
    projection = [
        {
            key: entry.get(key)
            for key in (
                "asset_id", "asset_url", "url", "original_checksum", "source_role",
                "source_kind", "source_url", "source_record_id", "ownership_evidence",
                "business_link_confidence", "user_authorized_for_preview",
                "allowed_for_customer_production", "user_authorized", "allowed_for_public_site",
            )
        }
        for entry in media_manifest.get("media", [])
        if isinstance(entry, dict) and not _platform_owned_asset(entry)
    ]
    return checksum(projection)


def _candidate_path(run_dir: Path, item: dict[str, Any]) -> Path | None:
    media_root = run_dir / "media_input"
    for key in ("original_file", "processed_file"):
        value = str(item.get(key, "")).strip()
        if not value:
            continue
        candidate = (media_root / value).resolve()
        try:
            candidate.relative_to(media_root.resolve())
        except ValueError:
            continue
        if candidate.is_file():
            return candidate
    return None


def _brand_mark_score(path: Path) -> tuple[int, dict[str, float]]:
    """Conservatively distinguish a flat brand mark from a profile photo."""
    with Image.open(path) as opened:
        image = opened.convert("RGB")
        image.thumbnail((256, 256))
        pixels = list(image.get_flattened_data())
    if not pixels:
        return 0, {}
    quantized = Counter((r // 24, g // 24, b // 24) for r, g, b in pixels)
    flat_coverage = sum(count for _colour, count in quantized.most_common(8)) / len(pixels)
    near_white = sum(1 for r, g, b in pixels if min(r, g, b) >= 235) / len(pixels)
    skin_like = sum(
        1 for r, g, b in pixels
        if r > 85 and g > 40 and b > 20 and r > g and r - b > 15 and abs(r - g) > 8
    ) / len(pixels)
    score = 0
    score += 35 if flat_coverage >= 0.72 else 18 if flat_coverage >= 0.58 else 0
    score += 30 if near_white >= 0.18 else 15 if near_white >= 0.08 else 0
    score += 20 if len(quantized) <= 80 else 10 if len(quantized) <= 140 else 0
    score += 15 if skin_like < 0.12 else 0
    if skin_like >= 0.28:
        score -= 35
    return score, {
        "flat_colour_coverage": round(flat_coverage, 4),
        "near_white_fraction": round(near_white, 4),
        "skin_like_fraction": round(skin_like, 4),
        "score": float(score),
    }


def _logo_candidate(
    run_dir: Path,
    media_manifest: dict[str, Any],
) -> tuple[dict[str, Any], Path, dict[str, float]] | None:
    ranked: list[tuple[int, dict[str, Any], Path]] = []
    for item in media_manifest.get("media", []):
        path = _candidate_path(run_dir, item)
        if path is None or _platform_owned_asset(item):
            continue
        source = str(item.get("asset_url") or "").lower()
        width, height = int(item.get("width") or 0), int(item.get("height") or 0)
        is_profile = "/t51.82787-19/" in source or "profile" in str(item.get("recommended_use", "")).lower()
        if not is_profile:
            continue
        mark_score, evidence = _brand_mark_score(path)
        logo_colours = _select_logo_colours(path)
        repeated_colour_evidence = [
            _confirm_logo_colour(colour, run_dir, media_manifest) for colour in logo_colours[:2]
        ]
        chromatic_mark_confirmed = (
            len(logo_colours) >= 2
            and len(repeated_colour_evidence) >= 2
            and all(len(asset_ids) >= 2 for asset_ids in repeated_colour_evidence)
        )
        monochrome_mark_confirmed = (
            evidence.get("near_white_fraction", 0) >= 0.55
            and evidence.get("flat_colour_coverage", 0) >= 0.92
            and evidence.get("skin_like_fraction", 1) < 0.03
        )
        if (
            mark_score < 80
            or evidence.get("near_white_fraction", 0) < 0.4
            or not (chromatic_mark_confirmed or monochrome_mark_confirmed)
        ):
            continue
        evidence["cross_media_colour_sets"] = float(len(repeated_colour_evidence))
        evidence["cross_media_confirmed"] = float(chromatic_mark_confirmed)
        evidence["monochrome_mark_confirmed"] = float(monochrome_mark_confirmed)
        score = 100 + mark_score
        if width and height and abs(width - height) <= max(width, height) * 0.08:
            score += 20
        if 160 <= min(width or 0, height or 0) <= 800:
            score += 5
        enriched = dict(item)
        enriched["brand_mark_evidence"] = evidence
        ranked.append((score, enriched, path))
    if not ranked:
        return None
    score, item, path = max(ranked, key=lambda entry: (entry[0], str(entry[1].get("asset_id", ""))))
    return item, path, dict(item.get("brand_mark_evidence", {}))


def _business_label(business_research: dict[str, Any], source_url: str) -> str:
    candidate = str(
        business_research.get("research", {}).get("business_name")
        or business_research.get("business_name")
        or ""
    ).strip()
    if candidate and candidate.casefold() not in {"business", "unknown", "instagram business"}:
        return candidate
    handle = urlsplit(source_url).path.strip("/").split("/")[0]
    return " ".join(part.capitalize() for part in re.split(r"[_\-.]+", handle) if part) or "Business"


def _prepare_logo(source: Path, target: Path) -> tuple[int, int, str]:
    """Crop only uniform near-white outer padding; never redraw or recolour."""
    with Image.open(source) as opened:
        image = opened.convert("RGB")
        white = Image.new("RGB", image.size, (255, 255, 255))
        difference = ImageChops.difference(image, white).convert("L")
        mask = difference.point(lambda value: 255 if value > 14 else 0)
        bbox = mask.getbbox()
        if bbox:
            left, top, right, bottom = bbox
            padding = max(4, round(max(image.size) * 0.025))
            bbox = (
                max(0, left - padding),
                max(0, top - padding),
                min(image.width, right + padding),
                min(image.height, bottom + padding),
            )
            image = image.crop(bbox)
        target.parent.mkdir(parents=True, exist_ok=True)
        image.save(target, format="PNG", optimize=True)
        return image.width, image.height, "deterministic_near_white_outer_crop"


def _select_logo_colours(logo_path: Path) -> list[tuple[int, int, int]]:
    candidates = _quantized_colours(logo_path, minimum_fraction=0.002)
    selected: list[tuple[int, int, int]] = []
    for colour, _fraction in candidates:
        if all(_colour_distance(colour, existing) >= 70 for existing in selected):
            selected.append(colour)
        if len(selected) == 3:
            break
    return selected


def _recurring_template_colours(
    run_dir: Path,
    media_manifest: dict[str, Any],
) -> list[tuple[tuple[int, int, int], list[str]]]:
    occurrences: dict[tuple[int, int, int], set[str]] = defaultdict(set)
    for item in media_manifest.get("media", []):
        if _platform_owned_asset(item) or "/t51.82787-19/" in str(item.get("asset_url", "")):
            continue
        path = _candidate_path(run_dir, item)
        if path is None:
            continue
        asset_id = str(item.get("asset_id") or path.name)
        for colour, fraction in _quantized_colours(path, minimum_fraction=0.018):
            if fraction >= 0.018:
                occurrences[colour].add(asset_id)
    ranked = sorted(
        ((colour, sorted(asset_ids)) for colour, asset_ids in occurrences.items() if len(asset_ids) >= 2),
        key=lambda entry: (-len(entry[1]), entry[0]),
    )
    selected: list[tuple[tuple[int, int, int], list[str]]] = []
    for colour, asset_ids in ranked:
        if all(_colour_distance(colour, existing) >= 64 for existing, _ in selected):
            selected.append((colour, asset_ids))
        if len(selected) == 3:
            break
    return selected


def _confirm_logo_colour(
    colour: tuple[int, int, int],
    run_dir: Path,
    media_manifest: dict[str, Any],
) -> list[str]:
    confirmed: list[str] = []
    for item in media_manifest.get("media", []):
        if _platform_owned_asset(item) or "/t51.82787-19/" in str(item.get("asset_url", "")):
            continue
        path = _candidate_path(run_dir, item)
        if path is None:
            continue
        if any(_colour_distance(colour, candidate) <= 64 and fraction >= 0.004 for candidate, fraction in _quantized_colours(path)):
            confirmed.append(str(item.get("asset_id") or path.name))
    return sorted(set(confirmed))


def _colour_record(
    role: str,
    rgb: tuple[int, int, int],
    *,
    source: str,
    evidence_assets: list[str],
    confidence: str,
) -> dict[str, Any]:
    return {
        "role": role,
        "hex": _hex(rgb),
        "rgb": {"r": rgb[0], "g": rgb[1], "b": rgb[2]},
        "hsl": _hsl(rgb),
        "source": source,
        "evidence_count": 1 + len(evidence_assets),
        "instagram_uses": evidence_assets,
        "confidence": confidence,
        "accessibility_contrast_notes": {
            "against_white": _contrast(rgb, (255, 255, 255)),
            "against_brand_text": _contrast(rgb, (22, 49, 45)),
            "guidance": "Use as a large accent/control surface unless the recorded contrast supports normal text.",
        },
    }


def _write_brand_markdown(path: Path, identity: dict[str, Any]) -> None:
    palette = identity["palette"]
    lines = [
        "# Brand identity",
        "",
        f"- **Business:** {identity['business_name']}",
        f"- **Confidence:** {identity['confidence']}",
        f"- **Logo:** `{identity['logo']['processed_path']}` from {identity['logo']['source_url']}",
        "",
        "## Evidence",
        "",
        *[f"- {item}" for item in identity["evidence_summary"]],
        "",
        "## Required website palette",
        "",
        *[f"- **{name}:** `{record['hex']}` — {record['source']}" for name, record in palette.items()],
        "",
        "## Visual direction",
        "",
        *[f"- {item}" for item in identity["required_website_direction"]],
        "",
        "## Forbidden",
        "",
        *[f"- {item}" for item in identity["forbidden_stylistic_decisions"]],
        "",
        "## Production blockers",
        "",
        *[f"- {item}" for item in identity["production_blockers"]],
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


class BrandIdentityAnalyzer:
    """Build a deterministic brand package before art direction.

    Official logo pixels and recurring business-owned graphic signals outrank
    incidental colours in clinical, portrait, interior or product photography.
    """

    schema_version = 1

    def analyze(
        self,
        *,
        run_dir: Path,
        business_research: dict[str, Any],
        media_manifest: dict[str, Any],
        source_url: str,
        preview: bool,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        candidate = _logo_candidate(run_dir, media_manifest)
        brand_dir = run_dir / "brand_input"
        brand_dir.mkdir(parents=True, exist_ok=True)
        item: dict[str, Any] = {}
        mark_evidence: dict[str, float] = {}
        logo_record: dict[str, Any]
        if candidate is not None:
            item, source, mark_evidence = candidate
            original = brand_dir / f"logo_original{source.suffix.lower() or '.bin'}"
            processed = brand_dir / "logo_processed.png"
            shutil.copy2(source, original)
            width, height, method = _prepare_logo(original, processed)
            logo_colours = _select_logo_colours(processed)
            logo_record = {
                "available": True,
                "source_asset_id": item.get("asset_id", ""),
                "source_url": item.get("asset_url") or item.get("source_url") or source_url,
                "original_path": "brand_input/" + original.name,
                "processed_path": "brand_input/" + processed.name,
                "original_checksum": _file_checksum(original),
                "processed_checksum": _file_checksum(processed),
                "extraction_method": method,
                "classification_method": "deterministic_flat_mark_heuristic",
                "classification_evidence": mark_evidence,
                "original_resolution": {
                    "width": int(item.get("width") or 0),
                    "height": int(item.get("height") or 0),
                },
                "processed_resolution": {"width": width, "height": height},
                "confidence": "high" if mark_evidence.get("score", 0) >= 80 else "medium",
                "user_authorized_for_preview": bool(item.get("user_authorized_for_preview")) if preview else False,
                "allowed_for_customer_production": bool(item.get("allowed_for_customer_production")),
                "generatively_redrawn": False,
                "recoloured": False,
            }
        else:
            logo_colours = []
            logo_record = {
                "available": False,
                "source_asset_id": "",
                "source_url": "",
                "original_path": "",
                "processed_path": "",
                "original_checksum": "",
                "processed_checksum": "",
                "extraction_method": "none_profile_avatar_not_proven_to_be_a_logo",
                "classification_method": "deterministic_flat_mark_heuristic",
                "classification_evidence": {},
                "original_resolution": {"width": 0, "height": 0},
                "processed_resolution": {"width": 0, "height": 0},
                "confidence": "low",
                "user_authorized_for_preview": False,
                "allowed_for_customer_production": False,
                "generatively_redrawn": False,
                "recoloured": False,
            }
        recurring = _recurring_template_colours(run_dir, media_manifest)
        chromatic_logo = logo_record["available"] and len(logo_colours) >= 2
        if chromatic_logo:
            primary, secondary = logo_colours[:2]
            accent = logo_colours[2] if len(logo_colours) > 2 else secondary
            palette_confidence = "high"
            palette_source = "official profile logo, cross-checked against recurring Instagram graphics"
        elif logo_record["available"] and recurring:
            primary = recurring[0][0]
            secondary = recurring[1][0] if len(recurring) > 1 else (35, 45, 43)
            accent = recurring[2][0] if len(recurring) > 2 else primary
            palette_confidence = "medium"
            palette_source = "black/white logo fallback using colours repeated in multiple business-owned social graphics"
        else:
            primary, secondary, accent = (37, 55, 52), (91, 109, 104), (37, 55, 52)
            palette_confidence = "low"
            palette_source = "conservative neutral fallback; no reliable chromatic brand evidence"

        confirmations = {
            _hex(colour): _confirm_logo_colour(colour, run_dir, media_manifest)
            for colour in (primary, secondary, accent)
        }
        surface = tuple(round(0.08 * value + 0.92 * 255) for value in primary)
        palette = {
            "brand_primary": _colour_record("brand_primary", primary, source=palette_source, evidence_assets=confirmations[_hex(primary)], confidence=palette_confidence),
            "brand_secondary": _colour_record("brand_secondary", secondary, source=palette_source, evidence_assets=confirmations[_hex(secondary)], confidence=palette_confidence),
            "brand_accent": _colour_record("brand_accent", accent, source=palette_source, evidence_assets=confirmations[_hex(accent)], confidence=palette_confidence),
            "brand_background": _colour_record("brand_background", (255, 255, 255), source="official logo field and conservative web neutral", evidence_assets=[], confidence="high" if chromatic_logo else "medium"),
            "brand_surface": _colour_record("brand_surface", surface, source="accessible pale extension of the evidenced primary colour", evidence_assets=[], confidence="medium"),
            "brand_text": _colour_record("brand_text", (26, 31, 30), source="accessible neutral extension; never a replacement logo colour", evidence_assets=[], confidence="medium"),
            "brand_muted": _colour_record("brand_muted", (91, 99, 96), source="accessible neutral extension", evidence_assets=[], confidence="medium"),
        }
        business_name = _business_label(business_research, source_url)
        assets_manifest = {
            "schema_version": self.schema_version,
            "business_name": business_name,
            "source_url": source_url,
            "delivery_target": "isolated_preview" if preview else "production",
            "source_media_checksum": brand_media_checksum(media_manifest),
            "source_research_checksum": checksum(business_research),
            "logo": logo_record,
            "analysed_media_asset_ids": [
                str(entry.get("asset_id", ""))
                for entry in media_manifest.get("media", [])
                if not _platform_owned_asset(entry)
            ],
            "excluded_platform_asset_ids": [
                str(entry.get("asset_id", ""))
                for entry in media_manifest.get("media", [])
                if _platform_owned_asset(entry)
            ],
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        identity = {
            "schema_version": self.schema_version,
            "business_name": business_name,
            "source_url": source_url,
            "confidence": "high" if chromatic_logo and logo_record["confidence"] == "high" else palette_confidence,
            "brand_palette_confidence": palette_confidence,
            "logo": assets_manifest["logo"],
            "palette": palette,
            "typography_character": "Clear contemporary typography whose tone follows the verified business evidence; retain an exact official wordmark only when the logo classifier confirms one.",
            "instagram_visual_patterns": [
                "real business-owned imagery takes priority over category stock conventions",
                "repeated evidenced colours may be used for compact controls and graphic accents",
                "service and educational content should retain the source account's direct visual rhythm",
            ],
            "forms_and_geometry": ["geometry present in the verified mark when available", "compact caption bars", "open neutral field"],
            "brand_level": "evidence-grounded social identity",
            "allowed_visual_tone": f"professional, direct and recognisably tied to the verified {business_name} evidence",
            "evidence_summary": [
                "The preserved Instagram profile avatar is accepted as an official mark only when deterministic flat-mark evidence passes.",
                "Confirmed chromatic mark pixels establish the primary palette; matching hues are cross-checked across business-owned social graphics.",
                "Generic Meta/platform assets are excluded from business brand evidence.",
            ],
            "required_website_direction": [
                "Use the unmodified official logo in the persistent site shell only when logo.available is true; otherwise use a plain text business name without inventing a mark.",
                "Use evidenced high-confidence colours for hierarchy, controls and graphic accents on a calm neutral base.",
                "References may influence composition, never the logo or high-confidence palette.",
                "Keep desktop, tablet and mobile recognisably within the same identity.",
            ],
            "forbidden_stylistic_decisions": [
                "Do not redraw, recolour, distort or replace the official logo.",
                "Do not use an unrelated category-default or reference-derived palette as the primary identity.",
                "Do not infer brand colours from skin, teeth, flowers, equipment, uniforms, paintings or other incidental objects.",
                "Do not let reference-site colours override the verified brand package.",
            ],
            "production_blockers": [
                "Logo and social media assets are authorised for isolated preview only; customer-production rights remain unconfirmed."
            ] if preview and logo_record["available"] and not logo_record["allowed_for_customer_production"] else [],
        }
        identity["brand_assets_checksum"] = checksum(assets_manifest)
        identity["brand_identity_checksum"] = checksum(identity)
        (brand_dir / "brand_identity.json").write_text(json.dumps(identity, ensure_ascii=False, indent=2), encoding="utf-8")
        (brand_dir / "brand_assets_manifest.json").write_text(json.dumps(assets_manifest, ensure_ascii=False, indent=2), encoding="utf-8")
        _write_brand_markdown(brand_dir / "brand_identity.md", identity)
        return identity, assets_manifest


class _BrandHtmlParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.asset_references: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = dict(attrs)
        for key in ("src", "href", "style"):
            if values.get(key):
                self.asset_references.append(str(values[key]))


class BrandFidelityAuditor:
    """Independent deterministic gate binding final bytes to the brand package."""

    @staticmethod
    def _rgb_from_hex(value: str) -> tuple[int, int, int]:
        value = value.strip().lstrip("#")
        return tuple(int(value[index:index + 2], 16) for index in (0, 2, 4))  # type: ignore[return-value]

    @staticmethod
    def _screenshot_brand_evidence(
        path: Path,
        colours: list[tuple[int, int, int]],
    ) -> dict[str, Any]:
        try:
            with Image.open(path) as opened:
                image = opened.convert("RGB")
                image.thumbnail((900, 2400))
                top = image.crop((0, 0, image.width, max(1, min(image.height, round(image.height * 0.35)))))
                pixels = list(image.get_flattened_data())
                top_pixels = list(top.get_flattened_data())
        except (OSError, ValueError):
            return {"valid": False, "colour_fractions": [], "top_colour_fractions": [], "brand_cluster_present": False}
        fractions: list[float] = []
        top_fractions: list[float] = []
        top_colour_counts: list[int] = []
        top_colour_bboxes: list[list[int] | None] = []
        for colour in colours:
            fractions.append(round(sum(_colour_distance(pixel, colour) <= 42 for pixel in pixels) / max(1, len(pixels)), 6))
            indexes = [index for index, pixel in enumerate(top_pixels) if _colour_distance(pixel, colour) <= 42]
            top_colour_counts.append(len(indexes))
            top_fractions.append(round(len(indexes) / max(1, len(top_pixels)), 6))
            if indexes:
                xs = [index % top.width for index in indexes]
                ys = [index // top.width for index in indexes]
                top_colour_bboxes.append([min(xs), min(ys), max(xs), max(ys)])
            else:
                top_colour_bboxes.append(None)
        meaningful = []
        for count, bbox in zip(top_colour_counts, top_colour_bboxes):
            area = 0 if bbox is None else (bbox[2] - bbox[0] + 1) * (bbox[3] - bbox[1] + 1)
            meaningful.append(count >= 100 and area >= 200)
        return {
            "valid": True,
            "colour_fractions": fractions,
            "top_colour_fractions": top_fractions,
            "top_colour_counts": top_colour_counts,
            "top_colour_bboxes": top_colour_bboxes,
            "brand_cluster_present": len(meaningful) >= 2 and all(meaningful[:2]),
        }

    @staticmethod
    def _logo_visible_in_screenshot(screenshot_path: Path, logo_path: Path) -> bool:
        try:
            cache_key = (_file_checksum(screenshot_path), _file_checksum(logo_path))
        except OSError:
            return False
        if cache_key in _LOGO_SCREENSHOT_CACHE:
            return _LOGO_SCREENSHOT_CACHE[cache_key]
        try:
            with Image.open(screenshot_path) as opened:
                screenshot = opened.convert("RGB")
                screenshot.thumbnail((900, 2400))
                screenshot = screenshot.crop((0, 0, screenshot.width, max(1, min(screenshot.height, round(screenshot.height * 0.35)))))
            with Image.open(logo_path) as opened_logo:
                logo = opened_logo.convert("RGB")
        except (OSError, ValueError):
            return False
        screenshot_pixels = screenshot.load()
        for scale in (0.55, 0.7, 0.45, 0.85, 1.0):
            width, height = max(12, round(logo.width * scale)), max(12, round(logo.height * scale))
            if width > screenshot.width or height > screenshot.height:
                continue
            rendered = logo.resize((width, height), Image.Resampling.LANCZOS)
            distinctive = [
                (x, y, rendered.getpixel((x, y)))
                for y in range(0, height, max(1, height // 18))
                for x in range(0, width, max(1, width // 18))
                if max(rendered.getpixel((x, y))) - min(rendered.getpixel((x, y))) >= 35
                or max(rendered.getpixel((x, y))) <= 110
            ]
            if len(distinctive) < 12:
                continue
            samples = distinctive[::max(1, len(distinctive) // 18)][:18]
            anchor_x, anchor_y, anchor_colour = samples[0]
            candidates = []
            for sy in range(anchor_y, screenshot.height - (height - anchor_y)):
                for sx in range(anchor_x, screenshot.width - (width - anchor_x)):
                    if _colour_distance(screenshot_pixels[sx, sy], anchor_colour) <= 55:
                        candidates.append((sx - anchor_x, sy - anchor_y))
                        if len(candidates) >= 800:
                            break
                if len(candidates) >= 800:
                    break
            for left, top in candidates:
                matches = sum(
                    _colour_distance(screenshot_pixels[left + x, top + y], colour) <= 70
                    for x, y, colour in samples
                )
                if matches / len(samples) >= 0.78:
                    _LOGO_SCREENSHOT_CACHE[cache_key] = True
                    return True
        _LOGO_SCREENSHOT_CACHE[cache_key] = False
        return False

    @staticmethod
    def _rendered_logo_references(site_dir: Path, expected_checksum: str) -> list[str]:
        stylesheet = "\n".join(
            path.read_text(encoding="utf-8", errors="ignore")
            for path in site_dir.rglob("*.css")
        )
        stylesheet += "\n" + "\n".join(
            style.get_text(" ", strip=True)
            for html_path in site_dir.rglob("*.html")
            for style in BeautifulSoup(
                html_path.read_text(encoding="utf-8", errors="ignore"), "html.parser"
            ).find_all("style")
        )

        def hidden_by_css(image: Any) -> bool:
            selectors = {"img"}
            for node in [image, *list(image.parents)[:5]]:
                node_id = str(node.get("id") or "").strip()
                if node_id:
                    selectors.add("#" + node_id)
                selectors.update("." + value for value in (node.get("class") or []))
                inline = str(node.get("style") or "").replace(" ", "").lower()
                if node.has_attr("hidden") or any(
                    token in inline for token in (
                        "display:none", "visibility:hidden", "opacity:0", "width:0", "height:0",
                        "scale(0)", "left:-", "right:-", "clip-path:inset(100",
                    )
                ):
                    return True
            for selector_text, declarations in re.findall(r"([^{}]+)\{([^{}]+)\}", stylesheet):
                normalized = declarations.replace(" ", "").lower()
                if not any(token in normalized for token in (
                    "display:none", "visibility:hidden", "opacity:0", "width:0", "height:0",
                    "scale(0)", "left:-", "right:-", "clip-path:inset(100",
                )):
                    continue
                if any(
                    re.search(r"(?<![\w-])img(?![\w-])", selector_text)
                    if token == "img"
                    else re.search(re.escape(token) + r"(?![\w-])", selector_text)
                    for token in selectors
                ):
                    return True
            return False

        references: list[str] = []
        for html_path in site_dir.rglob("*.html"):
            soup = BeautifulSoup(html_path.read_text(encoding="utf-8", errors="ignore"), "html.parser")
            for image in soup.find_all("img"):
                source = str(image.get("src") or "").strip()
                if not source or urlsplit(source).scheme or source.startswith("//"):
                    continue
                source_path = urlsplit(source).path
                resolved = (
                    site_dir / source_path.lstrip("/")
                    if source_path.startswith("/")
                    else html_path.parent / source_path
                ).resolve()
                if not resolved.is_relative_to(site_dir.resolve()) or not resolved.is_file():
                    continue
                if _file_checksum(resolved) != expected_checksum:
                    continue
                if hidden_by_css(image):
                    continue
                width, height = image.get("width"), image.get("height")
                if width and height:
                    try:
                        with Image.open(resolved) as logo_image:
                            expected_ratio = logo_image.width / logo_image.height
                        authored_ratio = float(width) / float(height)
                        if abs(authored_ratio - expected_ratio) / expected_ratio > 0.12:
                            continue
                    except (OSError, ValueError, ZeroDivisionError):
                        continue
                if not str(image.get("alt") or "").strip():
                    continue
                references.append(str(html_path.relative_to(site_dir)).replace("\\", "/") + ":" + source)
        return references

    @staticmethod
    def _no_logo_identity_violations(site_dir: Path, business_name: str) -> list[str]:
        violations: set[str] = set()
        normalized_name = re.sub(r"\W+", "", business_name, flags=re.UNICODE).casefold()
        plain_name_present = False
        forbidden_tokens = re.compile(r"(?:^|[-_])(logo|mark|monogram|wordmark|brand[-_]?(?:icon|symbol))(?:$|[-_])", re.I)
        for html_path in site_dir.rglob("*.html"):
            soup = BeautifulSoup(html_path.read_text(encoding="utf-8", errors="ignore"), "html.parser")
            identity_regions = list(soup.find_all("nav")) + list(soup.select("[role='banner'], .site-header, .navbar, .site-nav"))
            for region in identity_regions:
                region_text = re.sub(r"\W+", "", region.get_text(" ", strip=True), flags=re.UNICODE).casefold()
                if normalized_name and normalized_name in region_text:
                    plain_name_present = True
                    name_nodes = [
                        node for node in region.find_all(string=True)
                        if normalized_name in re.sub(r"\W+", "", str(node), flags=re.UNICODE).casefold()
                    ]
                    for node in name_nodes:
                        identity_container = node.parent
                        if identity_container.parent and identity_container.parent.name in {"a", "span", "div"}:
                            identity_container = identity_container.parent
                        elif identity_container.parent is region:
                            identity_container = region
                        for child in identity_container.find_all(recursive=False):
                            child_text = re.sub(r"\W+", "", child.get_text(" ", strip=True), flags=re.UNICODE).casefold()
                            if child_text and child_text in normalized_name:
                                continue
                            if not child_text or not child_text.isalnum():
                                violations.add("decorative sibling is attached to the plain-name identity without a proven logo")
                if region.find(["svg", "canvas", "img"]):
                    violations.add("visual identity asset appears in the persistent shell without a proven logo")
                for node in region.find_all(True):
                    tokens = " ".join([str(node.get("id") or ""), *[str(value) for value in (node.get("class") or [])]])
                    if forbidden_tokens.search(tokens):
                        violations.add("logo/mark/monogram element is authored despite logo.available=false")
        stylesheet = "\n".join(
            path.read_text(encoding="utf-8", errors="ignore") for path in site_dir.rglob("*.css")
        )
        if re.search(r"(?i)(logo|monogram|brand[-_]?(?:mark|icon|symbol)).*\{", stylesheet):
            violations.add("logo-like CSS component is authored despite logo.available=false")
        if not plain_name_present:
            violations.add("plain business name is missing from the persistent navigation identity")
        return sorted(violations)

    def audit(
        self,
        *,
        brand_identity: dict[str, Any],
        brand_assets_manifest: dict[str, Any],
        site_dir: Path,
        screenshots_dir: Path,
        preview: bool,
    ) -> dict[str, Any]:
        logo = brand_assets_manifest.get("logo", {})
        logo_available = logo.get("available") is True
        expected_logo_checksum = str(logo.get("processed_checksum", ""))
        matching_logo_files = [
            path for path in site_dir.rglob("*")
            if path.is_file() and path.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp", ".svg"}
            and _file_checksum(path) == expected_logo_checksum
        ] if expected_logo_checksum else []
        authored = "\n".join(
            path.read_text(encoding="utf-8", errors="ignore")
            for path in sorted(site_dir.rglob("*"))
            if path.is_file() and path.suffix.lower() in {".html", ".css", ".js"}
        )
        rendered_logo_references = self._rendered_logo_references(site_dir, expected_logo_checksum) if logo_available else []
        referenced_logo = bool(rendered_logo_references)
        required_colours = [
            brand_identity.get("palette", {}).get(role, {}).get("hex", "").upper()
            for role in ("brand_primary", "brand_secondary")
        ]
        authored_upper = authored.upper()
        colour_use = {colour: bool(colour and colour in authored_upper) for colour in required_colours}
        colour_rgbs = [self._rgb_from_hex(value) for value in required_colours if value]
        screenshot_evidence = {
            name: self._screenshot_brand_evidence(screenshots_dir / name, colour_rgbs)
            for name in ("desktop.png", "tablet.png", "mobile.png")
        }
        screenshot_checks = {name: evidence["valid"] for name, evidence in screenshot_evidence.items()}
        screenshot_logo_visibility = {
            name: self._logo_visible_in_screenshot(screenshots_dir / name, matching_logo_files[0])
            for name in ("desktop.png", "tablet.png", "mobile.png")
        } if logo_available and matching_logo_files else {}
        issues: list[dict[str, str]] = []
        if logo_available and (
            not matching_logo_files
            or not referenced_logo
            or not screenshot_logo_visibility
            or not all(screenshot_logo_visibility.values())
        ):
            issues.append({"severity": "high", "area": "logo", "problem": "The checksum-matched official processed logo is not rendered by the final site.", "fix": "Copy and render the exact processed logo without redraw, recolour or distortion."})
        no_logo_violations = (
            self._no_logo_identity_violations(site_dir, str(brand_identity.get("business_name", "")))
            if not logo_available
            else []
        )
        if no_logo_violations:
            issues.append({"severity": "high", "area": "logo", "problem": "; ".join(no_logo_violations), "fix": "Remove invented marks and use the plain verified business name in the persistent shell."})
        if brand_identity.get("brand_palette_confidence") == "high" and (
            not all(colour_use.values())
            or not all(evidence.get("brand_cluster_present") for evidence in screenshot_evidence.values())
        ):
            issues.append({"severity": "high", "area": "palette", "problem": "The rendered desktop/tablet/mobile site does not visibly preserve both high-confidence primary and secondary brand colours.", "fix": "Rebuild visible controls, the persistent shell and graphic accents around the verified brand palette, then render fresh screenshots."})
        if not all(screenshot_checks.values()):
            issues.append({"severity": "high", "area": "responsive", "problem": "Desktop/tablet/mobile brand evidence is incomplete.", "fix": "Render all required final viewports and repeat the brand audit."})
        if not preview and logo_available and logo.get("allowed_for_customer_production") is not True:
            issues.append({"severity": "critical", "area": "rights", "problem": "The official logo lacks confirmed customer-production rights.", "fix": "Record explicit production rights before promotion."})
        decision = "PASS" if not any(item["severity"] in {"critical", "high"} for item in issues) else "BLOCK"
        return {
            "schema_version": 1,
            "auditor": "BrandFidelityAuditor",
            "decision": decision,
            "approved": decision == "PASS",
            "brand_identity_checksum": brand_identity.get("brand_identity_checksum", ""),
            "brand_assets_checksum": brand_identity.get("brand_assets_checksum", ""),
            "official_logo_checksum": expected_logo_checksum,
            "matching_logo_files": [str(path.relative_to(site_dir)).replace("\\", "/") for path in matching_logo_files],
            "rendered_logo_references": rendered_logo_references,
            "official_logo_rendered": referenced_logo,
            "screenshot_logo_visibility": screenshot_logo_visibility,
            "no_logo_identity_violations": no_logo_violations,
            "required_colour_use": colour_use,
            "screenshots": screenshot_checks,
            "screenshot_brand_evidence": screenshot_evidence,
            "preview_rights_accepted": preview and logo.get("user_authorized_for_preview") is True,
            "production_rights_confirmed": logo.get("allowed_for_customer_production") is True,
            "issues": issues,
            "checked_at": datetime.now(timezone.utc).isoformat(),
        }
