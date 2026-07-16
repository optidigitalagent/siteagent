"""Authorised media preparation for the strategy-to-Studio handoff."""
from __future__ import annotations

import hashlib
import io
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import requests
from PIL import Image, ImageChops

from site_agent.config import Settings, settings


class MediaInputBlocked(RuntimeError):
    """Raised before design when publishable business media is unavailable."""


@dataclass(frozen=True)
class MediaCandidate:
    path: Path
    source_url: str = ""
    user_authorized: bool = False
    allowed_for_public_site: bool = False
    source_kind: str = "business"


class CloudinaryUploader:
    def __init__(self, config: Settings = settings, post=requests.post) -> None:
        self.config, self.post = config, post

    def upload(self, path: Path, *, public_id: str) -> str:
        if not (self.config.cloudinary_cloud_name and self.config.cloudinary_api_key and self.config.cloudinary_api_secret):
            raise MediaInputBlocked("Cloudinary is not configured (CLOUDINARY_CLOUD_NAME/API_KEY/API_SECRET are required).")
        timestamp = str(int(time.time()))
        signature_source = f"public_id={public_id}&timestamp={timestamp}{self.config.cloudinary_api_secret}"
        signature = hashlib.sha1(signature_source.encode("utf-8")).hexdigest()
        endpoint = f"https://api.cloudinary.com/v1_1/{self.config.cloudinary_cloud_name}/image/upload"
        with path.open("rb") as handle:
            response = self.post(endpoint, data={"api_key": self.config.cloudinary_api_key, "timestamp": timestamp, "public_id": public_id, "signature": signature}, files={"file": handle}, timeout=60)
        response.raise_for_status()
        url = str(response.json().get("secure_url", ""))
        if not url.startswith("https://"):
            raise MediaInputBlocked("Cloudinary upload returned no secure URL.")
        return url


class MediaPreparer:
    def __init__(self, config: Settings = settings, uploader: CloudinaryUploader | None = None) -> None:
        self.config = config
        self.uploader = uploader or CloudinaryUploader(config)

    def prepare(self, candidates: Iterable[MediaCandidate], output_dir: Path) -> dict:
        output_dir.mkdir(parents=True, exist_ok=True)
        accepted: list[dict] = []
        missing: list[str] = []
        seen: set[str] = set()
        for candidate in candidates:
            if candidate.source_kind != "business" or not candidate.user_authorized or not candidate.allowed_for_public_site:
                missing.append(f"{candidate.path.name}: requires source_kind=business, user_authorized=true and allowed_for_public_site=true")
                continue
            if not candidate.path.is_file():
                missing.append(f"{candidate.path}: file is unavailable")
                continue
            raw = candidate.path.read_bytes()
            checksum = hashlib.sha256(raw).hexdigest()
            if checksum in seen:
                continue
            seen.add(checksum)
            prepared = self._prepare_image(candidate.path, output_dir / f"{checksum[:16]}.jpg")
            with Image.open(prepared) as image:
                width, height = image.size
            orientation = "landscape" if width > height * 1.15 else ("portrait" if height > width * 1.15 else "square")
            quality = "high" if min(width, height) >= 1200 else ("usable" if min(width, height) >= 720 else "low")
            if quality == "low":
                missing.append(f"{candidate.path.name}: resolution {width}x{height} is below the 720px minimum")
                continue
            use = "hero" if not accepted and orientation == "landscape" else ("gallery" if len(accepted) < 6 else "detail")
            url = self.uploader.upload(prepared, public_id=f"siteagent/{checksum[:24]}")
            accepted.append({"asset_id": checksum[:24], "url": url, "source_url": candidate.source_url, "local_checksum": checksum, "source_kind": "business", "user_authorized": True, "allowed_for_public_site": True, "width": width, "height": height, "orientation": orientation, "quality": quality, "recommended_use": use, "prepared_file": prepared.name})
        if missing or not accepted:
            detail = "; ".join(missing or ["no authorised media candidates were supplied"])
            raise MediaInputBlocked("media-input checkpoint blocked: " + detail)
        return {"schema_version": 1, "media": accepted, "deduplicated_count": len(accepted), "provenance_policy": "selected media must be authorised business media with a Cloudinary secure URL"}

    @staticmethod
    def load_candidates(manifest_path: Path) -> list[MediaCandidate]:
        if not manifest_path.is_file():
            raise MediaInputBlocked(f"media-input checkpoint blocked: provide {manifest_path} with authorised local media entries.")
        import json
        data = json.loads(manifest_path.read_text(encoding="utf-8"))
        candidates = []
        for item in data.get("media", []):
            candidates.append(MediaCandidate(
                path=Path(item.get("path", "")), source_url=str(item.get("source_url", "")),
                user_authorized=bool(item.get("user_authorized")),
                allowed_for_public_site=bool(item.get("allowed_for_public_site")),
                source_kind=str(item.get("source_kind", "unknown")),
            ))
        return candidates

    @staticmethod
    def _prepare_image(source: Path, destination: Path) -> Path:
        """Trim uniform screenshot borders; preserve the photo when no UI crop is reliable."""
        with Image.open(source) as original:
            image = original.convert("RGB")
            border = Image.new("RGB", image.size, image.getpixel((0, 0)))
            diff = ImageChops.difference(image, border)
            bbox = diff.getbbox()
            # Only apply a conservative crop. This handles framed screenshots
            # without guessing away content from a real photograph.
            if bbox and bbox[0] <= image.width * .08 and bbox[1] <= image.height * .08:
                left, top, right, bottom = bbox
                if right - left >= image.width * .65 and bottom - top >= image.height * .65:
                    image = image.crop(bbox)
            image.save(destination, format="JPEG", quality=90, optimize=True)
        return destination
