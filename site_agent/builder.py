from __future__ import annotations

import hashlib
import mimetypes
from pathlib import Path
from urllib.parse import urlparse

import requests
from jinja2 import Environment, FileSystemLoader, select_autoescape

from site_agent.identifiers import stable_business_id
from site_agent.models import MediaAsset, ResearchBrief, SiteSpec, StrategyBrief


class SiteBuilder:
    def __init__(self) -> None:
        templates_dir = Path(__file__).parent / "templates"
        self.env = Environment(
            loader=FileSystemLoader(templates_dir),
            autoescape=select_autoescape(["html", "xml"]),
            trim_blocks=True,
            lstrip_blocks=True,
        )

    def build(
        self,
        *,
        site_dir: Path,
        research: ResearchBrief,
        strategy: StrategyBrief,
        spec: SiteSpec,
    ) -> Path:
        site_dir.mkdir(parents=True, exist_ok=True)
        assets_dir = site_dir / "assets"
        assets_dir.mkdir(parents=True, exist_ok=True)
        local_gallery = self._download_assets(spec.gallery_assets or research.best_media, assets_dir)
        hero_asset = local_gallery[0] if local_gallery else ""

        template = self.env.get_template("site.html.j2")
        html = template.render(
            research=research,
            strategy=strategy,
            spec=spec,
            gallery=local_gallery,
            hero_asset=hero_asset,
            hero_eyebrow=self._hero_eyebrow(research, strategy),
            instagram_handle=self._instagram_handle(research.instagram_url),
            niche_class=self._slug(self._hero_eyebrow(research, strategy)),
            labels=self._labels(
                spec.language or research.primary_language,
                sparse=self._has_sparse_evidence(research),
            ),
            sparse=self._has_sparse_evidence(research),
            siteagent_business_id=stable_business_id(research.instagram_url),
        )
        index_path = site_dir / "index.html"
        index_path.write_text(html, encoding="utf-8")
        return index_path

    def _download_assets(self, assets: list[MediaAsset], assets_dir: Path) -> list[str]:
        local_paths: list[str] = []
        for asset in assets[:12]:
            if not asset.url.startswith(("http://", "https://")):
                continue
            try:
                response = requests.get(asset.url, timeout=20, headers={"User-Agent": "Mozilla/5.0"})
                response.raise_for_status()
            except requests.RequestException:
                continue

            content_type = response.headers.get("content-type", "").split(";")[0]
            extension = mimetypes.guess_extension(content_type) or Path(urlparse(asset.url).path).suffix or ".jpg"
            if extension.lower() not in {".jpg", ".jpeg", ".png", ".webp", ".gif"}:
                extension = ".jpg"
            digest = hashlib.sha256(asset.url.encode("utf-8")).hexdigest()[:12]
            filename = f"media-{digest}{extension}"
            target = assets_dir / filename
            target.write_bytes(response.content)
            local_paths.append(f"assets/{filename}")
        return local_paths

    def _slug(self, value: str) -> str:
        return "".join(ch.lower() if ch.isalnum() else "-" for ch in value).strip("-") or "business"

    def _instagram_handle(self, instagram_url: str) -> str:
        """Return a display-safe Instagram handle without URL query parameters."""
        path_parts = [part for part in urlparse(instagram_url).path.split("/") if part]
        return path_parts[-1] if path_parts else "instagram"

    def _hero_eyebrow(self, research: ResearchBrief, strategy: StrategyBrief) -> str:
        if self._has_sparse_evidence(research):
            return "Instagram Direct"
            base = "Instagram enquiries"
            location = (research.city or "").strip()
            if location and location.lower() not in {"unknown", "n/a", "none"}:
                return f"{base} · {location}"
            return base

        combined = " ".join(
            [
                research.business_name,
                research.niche,
                " ".join(research.sells),
                " ".join(research.services_or_products),
                strategy.primary_cta,
            ]
        ).lower()
        if any(token in combined for token in ["fleur", "flor", "flower", "floral"]):
            base = "Floral enquiries via Instagram"
        else:
            base = "Instagram enquiries"

        location = (research.city or "").strip()
        if location and location.lower() not in {"unknown", "n/a", "none"}:
            return f"{base} · {location}"
        return base

    def _has_sparse_evidence(self, research: ResearchBrief) -> bool:
        evidence_text = " ".join(
            research.unknowns + [research.niche, research.city, research.country]
        ).lower()
        return "unknown" in evidence_text or "inferred" in evidence_text or "likely" in evidence_text

    def _labels(self, language: str, *, sparse: bool = False) -> dict[str, str]:
        normalized = language.lower()
        if normalized.startswith("uk"):
            labels = {
                "skip": "\\u0414\\u043e \\u0437\\u043c\\u0456\\u0441\\u0442\\u0443",
                "gallery": "\\u0413\\u0430\\u043b\\u0435\\u0440\\u0435\\u044f",
                "gallery_purpose": "",
                "trust": "",
                "trust_purpose": "",
                "process": "",
                "process_purpose": "",
                "contacts": "\\u041a\\u043e\\u043d\\u0442\\u0430\\u043a\\u0442",
                "contacts_purpose": "\\u0414\\u0435\\u0442\\u0430\\u043b\\u0456 \\u043c\\u043e\\u0436\\u043d\\u0430 \\u0443\\u0442\\u043e\\u0447\\u043d\\u0438\\u0442\\u0438 \\u0432 Instagram Direct.",
                "contact_fallback": "\\u0412\\u0456\\u0434\\u043a\\u0440\\u0438\\u0439\\u0442\\u0435 Instagram-\\u043f\\u0440\\u043e\\u0444\\u0456\\u043b\\u044c \\u0456 \\u043d\\u0430\\u043f\\u0438\\u0448\\u0456\\u0442\\u044c \\u0443 Direct.",
                "profile_note": "\\u0412\\u0456\\u0434\\u043a\\u0440\\u0438\\u0439\\u0442\\u0435 Instagram-\\u043f\\u0440\\u043e\\u0444\\u0456\\u043b\\u044c \\u0456 \\u043d\\u0430\\u043f\\u0438\\u0448\\u0456\\u0442\\u044c \\u0443 Direct, \\u0449\\u043e\\u0431 \\u0443\\u0442\\u043e\\u0447\\u043d\\u0438\\u0442\\u0438 \\u0434\\u0435\\u0442\\u0430\\u043b\\u0456.",
            }
            return {key: value.encode("utf-8").decode("unicode_escape") for key, value in labels.items()}
        if any(token in normalized for token in ["ru", "russian", "рус"]):
            return {
                "skip": "К содержанию",
                "gallery": "Галерея",
                "gallery_purpose": "Реальные визуальные материалы, выбранные из доступных Instagram-данных.",
                "trust": "Почему выбирают",
                "trust_purpose": "Причины доверия без выдуманных отзывов, рейтингов и цифр.",
                "process": "Как это работает",
                "process_purpose": "Понятный путь от интереса к записи или обращению.",
                "contacts": "Контакты",
                "contacts_purpose": "Только проверенные контактные данные.",
                "contact_fallback": "Актуальные детали, свободное время и цены лучше уточнить через Instagram.",
            }
        labels = {
            "skip": "Skip to content",
            "gallery": "Gallery",
            "gallery_purpose": "Real visual material selected from available Instagram assets.",
            "trust": "Why Choose",
            "trust_purpose": "Trust points without fake reviews, ratings, or numbers.",
            "process": "How It Works",
            "process_purpose": "A clear path from interest to contact.",
            "contacts": "Contacts",
            "contacts_purpose": "Use verified contact details only.",
            "contact_fallback": "For current details, availability, and prices, contact the business through Instagram.",
            "profile_note": "Open the Instagram profile and send a Direct message to confirm the details.",
        }
        if sparse:
            labels["trust"] = "Before You Message"
            labels["trust_purpose"] = "Useful details to confirm in Direct before placing a request."
            labels["contacts_purpose"] = "Start from the live Instagram profile and confirm current details there."
        return labels
