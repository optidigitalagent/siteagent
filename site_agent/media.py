"""Authorised, non-destructive media preparation for the strategy-to-Studio handoff."""
from __future__ import annotations

import hashlib
import json
import math
import shutil
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable
from urllib.parse import urlparse

import requests
from PIL import Image, ImageDraw, ImageFilter, ImageStat

from site_agent.config import Settings, settings


class MediaInputBlocked(RuntimeError):
    """Raised before design when publishable business media is unavailable."""


@dataclass(frozen=True)
class MediaCandidate:
    path: Path | None = None
    source_url: str = ""
    user_authorized: bool = False
    allowed_for_public_site: bool = False
    source_kind: str = "business"
    existing_cloudinary_url: str = ""
    cloudinary_public_id: str = ""
    cloudinary_asset_id: str = ""
    business_id: str = ""
    original_origin: str = ""
    original_filename: str = ""
    alt: str = ""
    selected_use: str = ""
    width: int = 0
    height: int = 0
    kind: str = "image"


class CloudinaryUploader:
    def __init__(self, config: Settings = settings, post=requests.post) -> None:
        self.config, self.post = config, post

    def upload(self, path: Path, *, public_id: str, resource_type: str = "image") -> dict:
        if not (self.config.cloudinary_cloud_name and self.config.cloudinary_api_key and self.config.cloudinary_api_secret):
            raise MediaInputBlocked("Cloudinary is not configured (CLOUDINARY_CLOUD_NAME/API_KEY/API_SECRET are required).")
        timestamp = str(int(time.time()))
        signature = hashlib.sha1(f"public_id={public_id}&timestamp={timestamp}{self.config.cloudinary_api_secret}".encode("utf-8")).hexdigest()
        if resource_type not in {"image", "video"}:
            raise MediaInputBlocked(f"Unsupported Cloudinary resource type: {resource_type}")
        endpoint = f"https://api.cloudinary.com/v1_1/{self.config.cloudinary_cloud_name}/{resource_type}/upload"
        with path.open("rb") as handle:
            response = self.post(endpoint, data={"api_key": self.config.cloudinary_api_key, "timestamp": timestamp, "public_id": public_id, "signature": signature, **({"upload_preset": self.config.cloudinary_upload_preset} if self.config.cloudinary_upload_preset else {})}, files={"file": handle}, timeout=60)
        response.raise_for_status(); payload = response.json(); url = str(payload.get("secure_url", ""))
        if not self._is_own_cloudinary_url(url):
            raise MediaInputBlocked("Cloudinary upload returned an unexpected secure URL.")
        return {"url": url, "cloudinary_public_id": str(payload.get("public_id", public_id)), "cloudinary_asset_id": str(payload.get("asset_id", "")), "cloudinary_version": str(payload.get("version", ""))}

    def _is_own_cloudinary_url(self, url: str) -> bool:
        host = urlparse(url).hostname or ""
        return url.startswith("https://") and host == "res.cloudinary.com" and f"/{self.config.cloudinary_cloud_name}/" in url


class MediaPreparer:
    def __init__(self, config: Settings = settings, uploader: CloudinaryUploader | None = None) -> None:
        self.config, self.uploader = config, uploader or CloudinaryUploader(config)

    def prepare(self, candidates: Iterable[MediaCandidate], output_dir: Path) -> dict:
        output_dir.mkdir(parents=True, exist_ok=True); originals = output_dir / "originals"; originals.mkdir(exist_ok=True)
        accepted, diagnostics, missing, seen_raw, seen_prepared = [], [], [], set(), set()
        for index, candidate in enumerate(candidates):
            try:
                item, diagnostic = self._prepare_candidate(candidate, output_dir, originals, index)
                diagnostics.append(diagnostic)
                if item["raw_checksum"] in seen_raw:
                    diagnostic["dedupe_status"] = "duplicate_raw"; continue
                seen_raw.add(item["raw_checksum"])
                if item["prepared_checksum"] in seen_prepared:
                    diagnostic["dedupe_status"] = "duplicate_prepared"; continue
                seen_prepared.add(item["prepared_checksum"])
                accepted.append(item)
            except MediaInputBlocked as exc:
                missing.append(str(exc)); diagnostics.append({"candidate": str(candidate.path or candidate.existing_cloudinary_url), "status": "blocked", "reason": str(exc)})
        self._assign_use_cases(accepted)
        sheet = self._contact_sheet(output_dir, diagnostics)
        if not accepted:
            raise MediaInputBlocked("media-input checkpoint blocked: " + "; ".join(missing or ["no authorised media candidates were supplied"]))
        # A real catalog can contain a few validly rejected weak frames. Keep
        # their diagnostics and continue with the classified, usable set; the
        # Design Director receives the selected/rejected evidence rather than
        # losing the entire business package to one dark or soft detail frame.
        return {"schema_version": 2, "media": accepted, "deduplicated_count": len(accepted), "raw_candidate_count": len(diagnostics), "rejected_count": len(missing), "rejected_reasons": missing, "contact_sheet": sheet.name, "provenance_policy": "selected media must be authorised business media with a Cloudinary secure URL; low-confidence Instagram crops are never destructive and require manual review."}

    def _prepare_candidate(self, candidate: MediaCandidate, output_dir: Path, originals: Path, index: int) -> tuple[dict, dict]:
        if candidate.source_kind != "business" or not candidate.user_authorized or not candidate.allowed_for_public_site:
            raise MediaInputBlocked(f"{candidate.path or candidate.existing_cloudinary_url}: requires source_kind=business, user_authorized=true and allowed_for_public_site=true")
        if candidate.existing_cloudinary_url:
            if not candidate.business_id or not candidate.original_origin:
                raise MediaInputBlocked(f"{candidate.existing_cloudinary_url}: existing Cloudinary media requires business_id and original_origin.")
            if not self.uploader._is_own_cloudinary_url(candidate.existing_cloudinary_url):
                raise MediaInputBlocked(f"{candidate.existing_cloudinary_url}: not an authorised asset in the configured Cloudinary account.")
            digest = hashlib.sha256(candidate.existing_cloudinary_url.encode()).hexdigest()
            width, height = candidate.width, candidate.height
            orientation = "landscape" if width > height * 1.15 else ("portrait" if height > width * 1.15 else ("square" if width and height else "unknown"))
            item = {"asset_id": candidate.cloudinary_asset_id or digest[:24], "url": candidate.existing_cloudinary_url, "source_url": candidate.source_url, "original_origin": candidate.original_origin, "original_filename": candidate.original_filename or Path(urlparse(candidate.existing_cloudinary_url).path).name, "business_id": candidate.business_id, "raw_checksum": digest, "prepared_checksum": digest, "source_kind": "business", "user_authorized": True, "allowed_for_public_site": True, "cloudinary_public_id": candidate.cloudinary_public_id, "cloudinary_asset_id": candidate.cloudinary_asset_id, "cloudinary_version": "existing", "width": width, "height": height, "alt": candidate.alt, "recommended_use": candidate.selected_use, "crop": {"method": "existing_authorised_cloudinary", "coordinates": None, "confidence": 1.0, "manual_review_required": False}, "orientation": orientation, "quality": "authorised_existing", "quality_score": None, "prepared_file": ""}
            return item, {"candidate": candidate.existing_cloudinary_url, "status": "reused", "asset_id": item["asset_id"], "crop": item["crop"]}
        if candidate.path is None or not candidate.path.is_file():
            raise MediaInputBlocked(f"{candidate.path}: file is unavailable")
        raw = candidate.path.read_bytes(); raw_checksum = hashlib.sha256(raw).hexdigest(); suffix = candidate.path.suffix or ".bin"
        original_copy = originals / f"{raw_checksum}{suffix.lower()}"; shutil.copy2(candidate.path, original_copy)
        if candidate.kind == "video":
            if not candidate.width or not candidate.height:
                raise MediaInputBlocked(f"{candidate.path.name}: video dimensions are required")
            upload = self.uploader.upload(candidate.path, public_id=f"siteagent/{raw_checksum[:24]}", resource_type="video")
            if isinstance(upload, str):
                upload = {"url": upload, "cloudinary_public_id": f"siteagent/{raw_checksum[:24]}", "cloudinary_asset_id": "", "cloudinary_version": ""}
            orientation = "landscape" if candidate.width > candidate.height * 1.15 else ("portrait" if candidate.height > candidate.width * 1.15 else "square")
            item = {"asset_id": upload["cloudinary_asset_id"] or raw_checksum[:24], "url": upload["url"], "source_url": candidate.source_url, "original_origin": candidate.original_origin or str(candidate.path), "original_filename": candidate.original_filename or candidate.path.name, "business_id": candidate.business_id, "raw_checksum": raw_checksum, "prepared_checksum": raw_checksum, "source_kind": "business", "user_authorized": True, "allowed_for_public_site": True, **upload, "kind": "video", "width": candidate.width, "height": candidate.height, "alt": candidate.alt, "recommended_use": candidate.selected_use, "orientation": orientation, "quality": "authorised_video", "quality_score": None, "crop": {"method": "documented_video_crop", "coordinates": None, "confidence": 1.0, "manual_review_required": False}, "prepared_file": "", "original_file": str(original_copy.relative_to(output_dir))}
            return item, {"candidate": candidate.path.name, "status": "prepared_video", "asset_id": item["asset_id"], "dimensions": [candidate.width, candidate.height], "prepared_file": ""}
        try:
            with Image.open(candidate.path) as source:
                image = source.convert("RGB")
        except Exception as exc:
            raise MediaInputBlocked(f"{candidate.path.name}: unsupported media; supply a still image or a manually prepared video frame.") from exc
        crop = self._instagram_crop(image)
        prepared = output_dir / f"{raw_checksum[:16]}.jpg"
        if crop["coordinates"] and not crop["manual_review_required"]:
            image = image.crop(tuple(crop["coordinates"]))
        image.save(prepared, format="JPEG", quality=92, optimize=True)
        prepared_checksum = hashlib.sha256(prepared.read_bytes()).hexdigest(); width, height = image.size
        if min(width, height) < 480:
            raise MediaInputBlocked(f"{candidate.path.name}: resolution {width}x{height} is below the 480px minimum")
        quality_score = self._quality_score(image)
        if quality_score < 0.30:
            raise MediaInputBlocked(f"{candidate.path.name}: image quality is too low ({quality_score:.2f}); supply a sharper exposure.")
        upload = self.uploader.upload(prepared, public_id=f"siteagent/{raw_checksum[:24]}")
        # Keep the narrow uploader seam backwards compatible for deterministic
        # tests and integrations that previously returned just a secure URL.
        if isinstance(upload, str):
            upload = {"url": upload, "cloudinary_public_id": f"siteagent/{raw_checksum[:24]}", "cloudinary_asset_id": "", "cloudinary_version": ""}
        orientation = "landscape" if width > height * 1.15 else ("portrait" if height > width * 1.15 else "square")
        item = {"asset_id": upload["cloudinary_asset_id"] or raw_checksum[:24], "url": upload["url"], "source_url": candidate.source_url, "original_origin": candidate.original_origin or str(candidate.path), "original_filename": candidate.original_filename or candidate.path.name, "business_id": candidate.business_id, "raw_checksum": raw_checksum, "prepared_checksum": prepared_checksum, "source_kind": "business", "user_authorized": True, "allowed_for_public_site": True, **upload, "kind": "image", "width": width, "height": height, "alt": candidate.alt, "recommended_use": candidate.selected_use, "orientation": orientation, "quality": "high" if quality_score >= .65 else "usable", "quality_score": round(quality_score, 3), "crop": crop, "prepared_file": prepared.name, "original_file": str(original_copy.relative_to(output_dir))}
        return item, {"candidate": candidate.path.name, "status": "prepared", "asset_id": item["asset_id"], "crop": crop, "quality_score": item["quality_score"], "dimensions": [width, height], "prepared_file": prepared.name}

    @staticmethod
    def _quality_score(image: Image.Image) -> float:
        gray = image.convert("L"); variance = ImageStat.Stat(gray).var[0] / (255**2)
        edges = ImageStat.Stat(gray.filter(ImageFilter.FIND_EDGES)).mean[0] / 255
        resolution = min(image.size) / 1200
        return min(1.0, .45 * min(1, resolution) + .35 * min(1, variance * 8) + .20 * min(1, edges * 3))

    @staticmethod
    def _instagram_crop(image: Image.Image) -> dict:
        """Conservatively identify full-width light/dark Instagram UI bands.

        Ambiguous bands are recorded for review but are never cropped automatically.
        """
        width, height = image.size; pixels = image.convert("L")
        def band(end: str) -> tuple[int, float]:
            max_band = min(int(height * .22), 260); rows = range(max_band) if end == "top" else range(height - 1, height - max_band - 1, -1)
            count = 0
            for y in rows:
                values = [pixels.getpixel((x, y)) for x in range(0, width, max(1, width // 80))]
                mean = sum(values) / len(values); spread = max(values) - min(values)
                if (mean > 228 or mean < 28) and spread < 45: count += 1
                else: break
            return count, min(1.0, count / 70)
        top, top_score = band("top"); bottom, bottom_score = band("bottom")
        if top < 20 and bottom < 20:
            return {"method": "no_detected_instagram_chrome", "coordinates": None, "confidence": .95, "manual_review_required": False}
        confidence = round((top_score + bottom_score) / 2, 2)
        coords = [0, top, width, height - bottom]
        high = (top >= 28 or bottom >= 28) and confidence >= .55 and (height - top - bottom) >= height * .62
        return {"method": "instagram_chrome_heuristic", "coordinates": coords, "confidence": confidence, "manual_review_required": not high, "detected_bands": {"top": top, "bottom": bottom}}

    @staticmethod
    def _assign_use_cases(media: list[dict]) -> None:
        ranked = sorted(media, key=lambda item: ((item.get("quality_score") or .7), item.get("width", 0) * item.get("height", 0)), reverse=True)
        for index, item in enumerate(ranked):
            item["recommended_use"] = "hero" if index == 0 else ("gallery" if index < 6 else "detail")

    @staticmethod
    def _contact_sheet(output_dir: Path, diagnostics: list[dict]) -> Path:
        cell_w, cell_h = 640, 150; canvas = Image.new("RGB", (cell_w, max(cell_h, cell_h * len(diagnostics))), "white"); draw = ImageDraw.Draw(canvas)
        for index, item in enumerate(diagnostics):
            y = index * cell_h
            preview = output_dir / str(item.get("prepared_file", ""))
            if preview.is_file():
                with Image.open(preview) as image:
                    image.thumbnail((190, 134)); canvas.paste(image.convert("RGB"), (8, y + 8))
            text = f"{item.get('status', 'unknown')} | {item.get('candidate', '')}\n{item.get('asset_id', '')} | {item.get('dimensions', '')}\n{item.get('crop', {})}\n{item.get('reason', '')}"
            draw.text((210, y + 8), text[:650], fill="black")
        path = output_dir / "preview_contact_sheet.jpg"; canvas.save(path, quality=88); return path

    @staticmethod
    def load_candidates(manifest_path: Path) -> list[MediaCandidate]:
        if not manifest_path.is_file():
            raise MediaInputBlocked(f"media-input checkpoint blocked: provide {manifest_path} with authorised media entries.")
        data = json.loads(manifest_path.read_text(encoding="utf-8")); candidates = []
        for item in data.get("media", []):
            raw_path = str(item.get("path", "")).strip()
            candidates.append(MediaCandidate(path=Path(raw_path) if raw_path else None, source_url=str(item.get("source_url", "")), user_authorized=bool(item.get("user_authorized")), allowed_for_public_site=bool(item.get("allowed_for_public_site")), source_kind=str(item.get("source_kind", "unknown")), existing_cloudinary_url=str(item.get("existing_cloudinary_url", item.get("url", ""))), cloudinary_public_id=str(item.get("cloudinary_public_id", "")), cloudinary_asset_id=str(item.get("cloudinary_asset_id", item.get("asset_id", ""))), business_id=str(item.get("business_id", "")), original_origin=str(item.get("original_origin", "")), original_filename=str(item.get("original_filename", "")), alt=str(item.get("alt", "")), selected_use=str(item.get("selected_use", item.get("recommended_use", ""))), width=int(item.get("width", 0) or 0), height=int(item.get("height", 0) or 0), kind=str(item.get("kind", "image"))))
        return candidates

    def validate_manifest(self, manifest: dict) -> None:
        media = manifest.get("media", [])
        if not media:
            raise MediaInputBlocked("media-input checkpoint blocked: cached media manifest has no authorised media.")
        for item in media:
            if item.get("source_kind") != "business" or item.get("user_authorized") is not True or item.get("allowed_for_public_site") is not True:
                raise MediaInputBlocked("media-input checkpoint blocked: cached manifest contains unauthorised media.")
            if not self.uploader._is_own_cloudinary_url(str(item.get("url", ""))):
                raise MediaInputBlocked("media-input checkpoint blocked: cached manifest contains a non-Cloudinary or wrong-account URL.")


def authorised_media_assets(manifest: dict):
    """Create Studio-readable media facts from the prepared, authorised manifest.

    This is intentionally one-way: public/scraped research URLs are never
    promoted into a publishable media list.  Only MediaPreparer output can
    satisfy the full-site media readiness requirement.
    """
    from site_agent.models import MediaAsset

    assets = []
    for item in manifest.get("media", []):
        if not (
            item.get("source_kind") == "business"
            and item.get("user_authorized") is True
            and item.get("allowed_for_public_site") is True
            and str(item.get("url", "")).startswith("https://res.cloudinary.com/")
        ):
            continue
        width, height = int(item.get("width", 0) or 0), int(item.get("height", 0) or 0)
        if width < 480 or height < 480:
            continue
        assets.append(MediaAsset(
            url=str(item["url"]), kind=str(item.get("kind", "image")), asset_id=str(item.get("asset_id", "")),
            alt=str(item.get("alt") or item.get("original_filename") or "Business media"),
            recommended_use=str(item.get("recommended_use") or "gallery"), width=width, height=height,
            source_kind="business", source_url=str(item.get("source_url", "")),
            provenance_note=f"Authorised business media: {item.get('original_origin', '')}", portfolio_claim=True,
        ))
    return assets
