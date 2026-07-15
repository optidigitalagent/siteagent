from __future__ import annotations

import hashlib
import json
import mimetypes
from pathlib import Path
from urllib.parse import urlparse

import requests
from jinja2 import Environment, FileSystemLoader, select_autoescape

from site_agent.identifiers import stable_business_id
from site_agent.models import MediaAsset, ResearchBrief, SiteSpec, StrategyBrief
from site_agent.design_quality import BuilderContext, PageComposition, build_context


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
        design_context: BuilderContext | None = None,
    ) -> Path:
        site_dir.mkdir(parents=True, exist_ok=True)
        assets_dir = site_dir / "assets"
        assets_dir.mkdir(parents=True, exist_ok=True)
        local_gallery = self._download_assets(spec.gallery_assets or research.best_media, assets_dir)
        hero_asset = local_gallery[0] if local_gallery else ""
        # Legacy callers still receive a validated composition rather than the
        # historical fixed template. Production always persists this context.
        design_context = design_context or build_context(research, strategy, spec)
        composition = design_context.page_composition
        planned_sections = self._section_payloads(composition, spec, strategy, research, local_gallery)

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
            design_tokens=(design_context.design_system.tokens if design_context else {}),
            visual_direction=(design_context.selected_visual_direction.name if design_context else ""),
            journey_pattern=(design_context.ux_architecture.pattern if design_context else ""),
            composition=composition,
            planned_sections=planned_sections,
        )
        index_path = site_dir / "index.html"
        index_path.write_text(html, encoding="utf-8")
        self._write_manifest(site_dir, composition, planned_sections, design_context, local_gallery)
        return index_path

    def _section_payloads(self, composition: PageComposition, spec: SiteSpec, strategy: StrategyBrief, research: ResearchBrief, gallery: list[str]) -> list[dict]:
        by_id = {section.id: section for section in spec.sections}
        fallback_content = [item for section in spec.sections for item in section.content]
        offerings = research.sells or research.services_or_products or fallback_content
        payloads = []
        for plan in composition.ordered_sections:
            source = by_id.get(plan.id)
            if plan.id == "hero":
                content = [spec.hero_subtitle]
                title = spec.h1
            elif plan.content_source == "BusinessBrief.verified_offerings":
                content, title = offerings, self._title(plan.type, plan.purpose)
            elif plan.content_source == "StrategyBrief.objections":
                content, title = strategy.customer_questions_or_fears or fallback_content, self._title(plan.type, plan.purpose)
            elif plan.content_source == "SiteSpec.process_steps":
                content, title = spec.process_steps or fallback_content, self._title(plan.type, plan.purpose)
            elif plan.content_source == "SiteSpec.trust_points":
                content, title = spec.trust_points or fallback_content, self._title(plan.type, plan.purpose)
            elif plan.content_source == "SiteSpec.contact_lines":
                content, title = spec.contact_lines or ["Use Instagram Direct for current details."], self._title(plan.type, plan.purpose)
            elif plan.content_source == "SiteSpec.sections":
                content, title = ([item for section in spec.sections for item in [section.title, *section.content]] or fallback_content), self._title(plan.type, plan.purpose)
            elif plan.content_source == "MediaManifest":
                content, title = [], self._title(plan.type, plan.purpose)
            else:
                content, title = (source.content if source else fallback_content), (source.title if source else self._title(plan.type, plan.purpose))
            payloads.append({"plan": plan, "title": title, "content": [value for value in content if value], "gallery": gallery, "cta": spec.primary_cta if plan.cta_relationship == "primary" else (spec.secondary_cta if plan.cta_relationship == "secondary" else "")})
        return payloads

    def _title(self, section_type: str, fallback: str) -> str:
        labels = {
            "experience_formats": "Ways to visit", "atmosphere_gallery": "The room and the table", "case_proof": "Useful details before you ask", "booking_closure": "Request a table",
            "treatment_concerns": "Start with your question", "service_matrix": "Choose the relevant route", "process_timeline": "What happens next", "consultation_closure": "Plan a consultation",
            "portfolio_mosaic": "Selected studies", "testimonial_proof": "What guides the work", "inquiry_closure": "Start a project conversation",
            "learning_benefits": "What practice makes possible", "learning_model": "How learning works", "platform_demonstration": "Between each session", "enrollment_closure": "Find your learning route",
            "focused_offer": "One confirmed offer", "direct_editorial_closure": "Ask for current details",
        }
        return labels.get(section_type, fallback)

    def _write_manifest(self, site_dir: Path, composition: PageComposition, payloads: list[dict], context: BuilderContext, gallery: list[str]) -> None:
        reports = site_dir.parent / "generation_reports"
        if not reports.exists():
            return
        manifest = {"page_composition": composition.model_dump(), "sections": [{"id": item["plan"].id, "type": item["plan"].type, "source_storyboard_section": item["plan"].id, "source_business_fact": item["plan"].content_source, "selected_layout_family": item["plan"].layout_family, "text": item["content"], "selected_media": gallery if item["plan"].media_requirements != "optional" else [], "design_tokens": context.design_system.tokens, "responsive_rule": context.page_composition.responsive_behavior} for item in payloads]}
        (reports / "build_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

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
