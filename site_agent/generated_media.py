"""Truthful AI media planning and generation for preview-first SiteAgent runs."""
from __future__ import annotations

import base64
import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Literal

import requests
from openai import OpenAI
from PIL import Image
from pydantic import BaseModel, Field, model_validator

from site_agent.config import settings
from site_agent.json_io import write_json
from site_agent.llm import LLMClient
from site_agent.media import CloudinaryUploader, MediaInputBlocked
from site_agent.media_policy import (
    FORBIDDEN_GENERATED_CLAIM_ROLES,
    MediaProvenanceType,
    SAFE_GENERATED_CLAIM_ROLES,
    checksum_text,
    asset_is_renderable,
    canonical_provenance_type,
    manifest_policy_issues,
    normalize_manifest_provenance,
)
from site_agent.workflow import checksum


class MediaPlanItem(BaseModel):
    section: str
    required_visual: str
    source_strategy: Literal[
        "user_provided_business_asset",
        "verified_official_business_asset",
        "licensed_stock_asset",
        "ai_generated_original",
        "reference_only",
        "unavailable",
    ]
    truthfulness_constraint: str
    claim_role: str
    prompt: str = ""
    alt: str = ""
    aspect_ratio: Literal["landscape", "portrait", "square"] = "landscape"
    output_required: bool = True

    @model_validator(mode="after")
    def validate_generated_role(self) -> "MediaPlanItem":
        if self.source_strategy == MediaProvenanceType.AI_GENERATED_ORIGINAL.value:
            if self.claim_role not in SAFE_GENERATED_CLAIM_ROLES:
                raise ValueError(f"Generated media claim role is not safe: {self.claim_role}")
            if not self.prompt.strip() or not self.truthfulness_constraint.strip():
                raise ValueError("Generated media requires a prompt and truthfulness constraint")
        if self.claim_role in FORBIDDEN_GENERATED_CLAIM_ROLES:
            raise ValueError(f"Media plan contains forbidden documentary role: {self.claim_role}")
        return self


class MediaPlan(BaseModel):
    schema_version: int = 1
    input_checksum: str
    real_business_media_only: bool = False
    items: list[MediaPlanItem] = Field(min_length=1, max_length=12)
    omitted_evidence_sections: list[str] = Field(default_factory=list)
    production_warnings: list[str] = Field(default_factory=list)
    summary: str

    @model_validator(mode="after")
    def validate_plan(self) -> "MediaPlan":
        generated_outputs = [
            item for item in self.items
            if item.output_required and item.source_strategy == MediaProvenanceType.AI_GENERATED_ORIGINAL.value
        ]
        if len(generated_outputs) > 5:
            raise ValueError("Media plan may request at most five generated outputs")
        if self.real_business_media_only and any(
            item.source_strategy == MediaProvenanceType.AI_GENERATED_ORIGINAL.value
            for item in self.items
        ):
            raise ValueError("real_business_media_only forbids generated media")
        if not any(item.output_required for item in self.items):
            raise ValueError("Media plan has no usable output")
        return self


MEDIA_PLANNER_SYSTEM = """
You are SiteAgent Media Planner. Create a small, intentional visual plan for a
commercial website from verified research. The absence of real business photos
does not by itself block an isolated preview. Use ai_generated_original for
hero atmosphere, service visualizations, object scenes, neutral lifestyle,
abstract brand compositions, textures or illustrations.

Never present generated media as a real employee, named doctor, owner, clinic
interior, office, company work, before/after case, review, certificate, award,
document, client documentary photo or proof of a specific result. Omit cases,
reviews, team or other evidence sections when real evidence is unavailable.
Reference-only images may inform direction but must have output_required=false.
When fewer than five usable non-logo visuals already exist, generate enough
originals to reach five; when none exist, generate exactly five. Use only these generated claim roles: atmosphere, background_composition,
service_visualization, object_scene, lifestyle_neutral, abstract_brand,
decorative_texture, illustration. Use at most one neutral lifestyle scene.
Prompts must contain no brand logo or embedded
text and must explicitly avoid documentary claims.
""".strip()


class GeneratedMediaPlanner:
    def __init__(self, llm: LLMClient | None = None) -> None:
        self.llm = llm or LLMClient(provider=settings.research_strategist_provider)

    def run(
        self,
        *,
        business_research: dict[str, Any],
        existing_manifest: dict[str, Any],
        real_business_media_only: bool,
    ) -> MediaPlan:
        input_payload = {
            "business_research": business_research,
            "existing_media": [
                {
                    key: item.get(key)
                    for key in (
                        "asset_id", "provenance_type", "source_role", "recommended_use",
                        "alt", "width", "height",
                    )
                }
                for item in existing_manifest.get("media", [])
                if isinstance(item, dict)
            ],
            "real_business_media_only": real_business_media_only,
        }
        input_checksum = checksum(input_payload)
        plan = self.llm.structured(
            system=MEDIA_PLANNER_SYSTEM,
            user=(
                "Create the section media table for this exact business. Return the complete MediaPlan. "
                f"Set input_checksum exactly to {input_checksum}.\n\n"
                + json.dumps(input_payload, ensure_ascii=False, indent=2)
            ),
            schema=MediaPlan,
        )
        if plan.input_checksum != input_checksum:
            raise MediaInputBlocked("media planning blocked: plan checksum does not match the research input")
        return plan


class OpenAIImageGenerator:
    def __init__(
        self,
        *,
        client: OpenAI | None = None,
        model: str | None = None,
        get: Callable[..., Any] = requests.get,
    ) -> None:
        if not settings.openai_api_key and client is None:
            raise MediaInputBlocked("media generation is unavailable: OPENAI_API_KEY is not configured")
        self.client = client or OpenAI(api_key=settings.openai_api_key)
        self.model = model or settings.image_generation_model
        self.get = get

    def generate(self, item: MediaPlanItem, output_path: Path) -> dict[str, Any]:
        size = {
            "landscape": "1536x1024",
            "portrait": "1024x1536",
            "square": "1024x1024",
        }[item.aspect_ratio]
        prompt = self._safe_prompt(item)
        try:
            response = self.client.images.generate(
                model=self.model,
                prompt=prompt,
                size=size,
                quality=settings.image_generation_quality,
                output_format="png",
                response_format="b64_json",
                n=1,
            )
        except Exception as exc:
            raise MediaInputBlocked("media generation is unavailable: image service request failed") from exc
        if not response.data:
            raise MediaInputBlocked("media generation returned no image")
        result = response.data[0]
        encoded = getattr(result, "b64_json", None)
        if encoded:
            payload = base64.b64decode(encoded)
        else:
            url = str(getattr(result, "url", "") or "")
            if not url.startswith("https://"):
                raise MediaInputBlocked("media generation returned neither image bytes nor a safe URL")
            downloaded = self.get(url, timeout=90)
            downloaded.raise_for_status()
            payload = bytes(downloaded.content)
        if not payload:
            raise MediaInputBlocked("media generation returned an empty image")
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(payload)
        try:
            with Image.open(output_path) as image:
                image.verify()
            with Image.open(output_path) as image:
                width, height = image.size
        except Exception as exc:
            raise MediaInputBlocked("generated media is not a decodable image") from exc
        return {
            "prompt": prompt,
            "prompt_checksum": checksum_text(prompt),
            "generation_model": self.model,
            "width": width,
            "height": height,
        }

    @staticmethod
    def _safe_prompt(item: MediaPlanItem) -> str:
        return (
            f"Use case: ads-marketing\nAsset type: responsive website {item.section} visual\n"
            f"Primary request: {item.prompt.strip()}\nComposition: {item.aspect_ratio}; leave practical crop room.\n"
            f"Truthfulness constraint: {item.truthfulness_constraint.strip()}\n"
            "Constraints: original image for this project; generic and non-identifying people only when requested; "
            "no real employee, named doctor, owner, real business interior, real case, before/after, review, certificate, "
            "award, document or proof claim. No logo, no readable text, no watermark."
        )


class GeneratedMediaManager:
    def __init__(
        self,
        *,
        planner: GeneratedMediaPlanner | None = None,
        generator: OpenAIImageGenerator | None = None,
        uploader: CloudinaryUploader | None = None,
    ) -> None:
        self.planner = planner
        self.generator = generator
        self.uploader = uploader or CloudinaryUploader()

    def prepare(
        self,
        *,
        run_dir: Path,
        business_research: dict[str, Any],
        existing_manifest: dict[str, Any],
        real_business_media_only: bool,
        job_id: str,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        normalized = normalize_manifest_provenance(existing_manifest)
        normalized = self._upload_user_provided_visuals(
            run_dir=run_dir,
            manifest=normalized,
            job_id=job_id,
        )
        existing_renderable = [
            item for item in normalized.get("media", [])
            if item.get("source_role") not in {"profile_avatar", "official_profile_avatar", "user_provided_logo"}
            and asset_is_renderable(item, target="isolated_preview")
            and self.uploader._is_own_cloudinary_url(str(item.get("url", "")))
        ]
        if len(existing_renderable) >= 5:
            return normalized, self._existing_media_plan(business_research, normalized, real_business_media_only)
        if real_business_media_only:
            raise MediaInputBlocked(
                "media-input checkpoint blocked: real_business_media_only=true and no real business photos are available"
            )

        plan_input = {
            "business_research": business_research,
            "existing_media": [
                {key: item.get(key) for key in ("asset_id", "provenance_type", "source_role", "recommended_use", "alt", "width", "height")}
                for item in normalized.get("media", [])
            ],
            "real_business_media_only": real_business_media_only,
        }
        expected_input_checksum = checksum(plan_input)
        reports_dir = run_dir / "generation_reports"
        plan_path = reports_dir / "media_plan.json"
        plan = self._load_plan(plan_path, expected_input_checksum)
        if plan is None:
            planner = self.planner or GeneratedMediaPlanner()
            plan = planner.run(
                business_research=business_research,
                existing_manifest=normalized,
                real_business_media_only=real_business_media_only,
            )
        plan = self._bound_plan(plan, max_generated_assets=max(0, 5 - len(existing_renderable)))
        write_json(plan_path, plan.model_dump())

        plan_checksum = checksum(plan.model_dump())
        generated_root = run_dir / "generated_media"
        manifest_path = generated_root / "manifest.json"
        cached = self._load_generated_manifest(manifest_path, plan_checksum)
        generated = self._generate_plan_assets(
            plan=plan,
            generated_root=generated_root,
            job_id=job_id,
            existing_media=list((cached or {}).get("media", [])),
            manifest_path=manifest_path,
            plan_checksum=plan_checksum,
            max_generated_assets=max(0, 5 - len(existing_renderable)),
        )
        cached = self._generated_checkpoint(
            plan_checksum=plan_checksum,
            media=generated,
            status="completed",
        )
        write_json(manifest_path, cached)
        merged = self._merge_manifest(normalized, cached, plan)
        issues = manifest_policy_issues(merged, target="isolated_preview")
        usable_non_logo = [
            item for item in merged.get("media", [])
            if item.get("source_role") not in {"profile_avatar", "official_profile_avatar", "user_provided_logo"}
            and asset_is_renderable(item, target="isolated_preview")
            and str(item.get("url", "")).startswith("https://")
        ]
        if len(usable_non_logo) < 5:
            issues.append(
                f"minimal visual set is incomplete: {len(usable_non_logo)} of 5 usable non-logo assets"
            )
        if issues:
            raise MediaInputBlocked("media generation policy blocked: " + "; ".join(issues))
        write_json(run_dir / "media_input" / "manifest.json", merged)
        return merged, plan.model_dump()

    @staticmethod
    def _load_plan(path: Path, input_checksum: str) -> MediaPlan | None:
        try:
            plan = MediaPlan.model_validate_json(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None
        return plan if plan.input_checksum == input_checksum else None

    def _load_generated_manifest(self, path: Path, plan_checksum: str) -> dict[str, Any] | None:
        try:
            manifest = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None
        if manifest.get("plan_checksum") != plan_checksum:
            return None
        media = manifest.get("media", [])
        if not isinstance(media, list) or any(
            not self.uploader._is_own_cloudinary_url(str(item.get("url", "")))
            for item in media if isinstance(item, dict)
        ):
            return None
        return normalize_manifest_provenance(manifest)

    def _generate_plan_assets(
        self,
        *,
        plan: MediaPlan,
        generated_root: Path,
        job_id: str,
        existing_media: list[dict[str, Any]],
        manifest_path: Path,
        plan_checksum: str,
        max_generated_assets: int,
    ) -> list[dict[str, Any]]:
        generator: OpenAIImageGenerator | Any | None = self.generator
        originals = generated_root / "originals"
        eligible_indices = [
            index for index, item in enumerate(plan.items)
            if item.output_required and item.source_strategy == MediaProvenanceType.AI_GENERATED_ORIGINAL.value
        ][:max_generated_assets]
        expected_indices = set(eligible_indices)
        media_by_index = {
            int(record["plan_item_index"]): dict(record)
            for record in existing_media
            if isinstance(record, dict)
            and isinstance(record.get("plan_item_index"), int)
            and int(record["plan_item_index"]) in expected_indices
            and self.uploader._is_own_cloudinary_url(str(record.get("url", "")))
        }
        write_json(
            manifest_path,
            self._generated_checkpoint(
                plan_checksum=plan_checksum,
                media=[media_by_index[index] for index in sorted(media_by_index)],
                status="in_progress",
            ),
        )
        for index, item in enumerate(plan.items):
            if not item.output_required or item.source_strategy != MediaProvenanceType.AI_GENERATED_ORIGINAL.value:
                continue
            if index in media_by_index:
                continue
            if generator is None:
                generator = OpenAIImageGenerator()
            filename = f"{index + 1:02d}-{self._slug(item.section)}.png"
            output = originals / filename
            generation = generator.generate(item, output)
            original_checksum = hashlib.sha256(output.read_bytes()).hexdigest()
            uploaded = self.uploader.upload(
                output,
                public_id=f"siteagent-generated/{job_id}/{original_checksum[:24]}",
            )
            media_by_index[index] = {
                "asset_id": str(uploaded.get("cloudinary_asset_id") or original_checksum[:24]),
                "kind": "image",
                "url": str(uploaded["url"]),
                "source_kind": "ai_generated",
                "provenance_type": MediaProvenanceType.AI_GENERATED_ORIGINAL.value,
                "source_url": "siteagent://generated-media",
                "source_role": "generated_project_visual",
                "original_origin": "siteagent_ai_generation",
                "original_filename": filename,
                "original_file": str(output.relative_to(generated_root.parent)).replace("\\", "/"),
                "original_checksum": original_checksum,
                "prepared_checksum": original_checksum,
                "generation_model": generation["generation_model"],
                "prompt": generation["prompt"],
                "prompt_checksum": generation["prompt_checksum"],
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "plan_item_index": index,
                "planned_section": item.section,
                "recommended_use": item.section,
                "alt": item.alt or item.required_visual,
                "truthfulness_constraint": item.truthfulness_constraint,
                "claim_role": item.claim_role,
                "portfolio_claim": False,
                "user_authorized_for_preview": True,
                "allowed_for_customer_production": True,
                "user_authorized": True,
                "allowed_for_public_site": True,
                "width": int(generation["width"]),
                "height": int(generation["height"]),
                "orientation": item.aspect_ratio,
                "quality": "ai_generated_original",
                **uploaded,
            }
            write_json(
                manifest_path,
                self._generated_checkpoint(
                    plan_checksum=plan_checksum,
                    media=[media_by_index[key] for key in sorted(media_by_index)],
                    status="in_progress",
                ),
            )
        media = [media_by_index[index] for index in sorted(media_by_index)]
        if not media:
            raise MediaInputBlocked("media generation is unavailable: media plan produced no generated output")
        return media

    @staticmethod
    def _bound_plan(plan: MediaPlan, *, max_generated_assets: int) -> MediaPlan:
        retained = 0
        items: list[dict[str, Any]] = []
        for item in plan.items:
            payload = item.model_dump()
            if item.output_required and item.source_strategy == MediaProvenanceType.AI_GENERATED_ORIGINAL.value:
                retained += 1
                if retained > max_generated_assets:
                    payload["output_required"] = False
            items.append(payload)
        return MediaPlan.model_validate({**plan.model_dump(), "items": items})

    @staticmethod
    def _generated_checkpoint(
        *, plan_checksum: str, media: list[dict[str, Any]], status: str
    ) -> dict[str, Any]:
        return {
            "schema_version": 1,
            "provenance_schema_version": 1,
            "purpose": "isolated_preview",
            "plan_checksum": plan_checksum,
            "status": status,
            "media": media,
            "generated_count": len(media),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }

    def _upload_user_provided_visuals(
        self,
        *,
        run_dir: Path,
        manifest: dict[str, Any],
        job_id: str,
    ) -> dict[str, Any]:
        media: list[dict[str, Any]] = []
        changed = False
        media_root = (run_dir / "media_input").resolve()
        for raw in manifest.get("media", []):
            item = dict(raw)
            should_upload = (
                canonical_provenance_type(item) == MediaProvenanceType.USER_PROVIDED_BUSINESS_ASSET.value
                and item.get("source_role") != "user_provided_logo"
                and not str(item.get("url", ""))
            )
            if should_upload:
                source = (media_root / str(item.get("original_file", ""))).resolve()
                try:
                    source.relative_to(media_root)
                except ValueError as exc:
                    raise MediaInputBlocked("user-provided media path escapes the run-scoped media directory") from exc
                if not source.is_file():
                    raise MediaInputBlocked("user-provided business visual is missing from the run-scoped media directory")
                digest = str(item.get("original_checksum") or hashlib.sha256(source.read_bytes()).hexdigest())
                uploaded = self.uploader.upload(
                    source,
                    public_id=f"siteagent-user/{job_id}/{digest[:24]}",
                )
                if isinstance(uploaded, str):
                    uploaded = {"url": uploaded}
                item.update(uploaded)
                changed = True
            media.append(item)
        result = normalize_manifest_provenance({**manifest, "media": media})
        if changed:
            write_json(run_dir / "media_input" / "manifest.json", result)
        return result

    @staticmethod
    def _merge_manifest(existing: dict[str, Any], generated: dict[str, Any], plan: MediaPlan) -> dict[str, Any]:
        media = [*existing.get("media", []), *generated.get("media", [])]
        images = sum(item.get("kind", "image") == "image" for item in media)
        videos = sum(item.get("kind") == "video" for item in media)
        real_business_photo_count = sum(
            item.get("provenance_type") in {
                MediaProvenanceType.USER_PROVIDED_BUSINESS_ASSET.value,
                MediaProvenanceType.VERIFIED_OFFICIAL_BUSINESS_ASSET.value,
            }
            and item.get("source_role") not in {"profile_avatar", "official_profile_avatar", "user_provided_logo"}
            for item in media
        )
        production_warnings = list(plan.production_warnings)
        if real_business_photo_count == 0:
            production_warnings.append(
                "No real business photos were supplied or verified; generated visuals are not documentary evidence."
            )
        return {
            **existing,
            "schema_version": max(int(existing.get("schema_version", 1)), 2),
            "provenance_schema_version": 1,
            "purpose": "isolated_preview",
            "media": media,
            "media_count": len(media),
            "image_count": images,
            "video_count": videos,
            "generated_media_count": len(generated.get("media", [])),
            "real_business_photo_count": real_business_photo_count,
            "full_preview_media_sufficient": sum(
                item.get("source_role") not in {"profile_avatar", "official_profile_avatar", "user_provided_logo"}
                and asset_is_renderable(item, target="isolated_preview")
                and str(item.get("url", "")).startswith("https://")
                for item in media
            ) >= 5,
            "composition_mode": "generated_media",
            "media_plan_checksum": checksum(plan.model_dump()),
            "production_warnings": list(dict.fromkeys(production_warnings)),
            "omitted_evidence_sections": list(plan.omitted_evidence_sections),
            "production_policy": "generated originals retain AI provenance and never become documentary business evidence",
        }

    @staticmethod
    def _existing_media_plan(
        business_research: dict[str, Any], manifest: dict[str, Any], real_business_media_only: bool
    ) -> dict[str, Any]:
        payload = {
            "business_research": business_research,
            "existing_media": [
                {key: item.get(key) for key in ("asset_id", "provenance_type", "source_role", "recommended_use", "alt", "width", "height")}
                for item in manifest.get("media", [])
            ],
            "real_business_media_only": real_business_media_only,
        }
        return MediaPlan(
            input_checksum=checksum(payload),
            real_business_media_only=real_business_media_only,
            items=[
                MediaPlanItem(
                    section=str(item.get("recommended_use") or "site visual"),
                    required_visual=str(item.get("alt") or "Verified business visual"),
                    source_strategy=str(item.get("provenance_type") or MediaProvenanceType.VERIFIED_OFFICIAL_BUSINESS_ASSET.value),
                    truthfulness_constraint="Use only for claims supported by its recorded provenance.",
                    claim_role=str(item.get("claim_role") or "service_visualization"),
                    prompt=str(item.get("prompt") or "Reuse the existing provenance-approved visual without alteration."),
                    output_required=True,
                )
                for item in manifest.get("media", [])
            ],
            summary="Existing authorised media satisfies the preview visual plan.",
        ).model_dump()

    @staticmethod
    def _slug(value: str) -> str:
        cleaned = "".join(char.lower() if char.isalnum() else "-" for char in value)
        return "-".join(part for part in cleaned.split("-") if part)[:48] or "visual"


def merge_user_provided_business_assets(run_dir: Path, manifest: dict[str, Any]) -> dict[str, Any]:
    """Adopt files directly supplied under ``media_input/user_provided``.

    Direct placement in this run-scoped directory is the explicit authorisation
    boundary. Files are never discovered from Downloads or unrelated folders.
    """
    root = run_dir / "media_input" / "user_provided"
    if not root.is_dir():
        return normalize_manifest_provenance(manifest)
    supported = {".png", ".jpg", ".jpeg", ".webp"}
    candidates = [path for path in sorted(root.iterdir()) if path.is_file() and path.suffix.lower() in supported]
    existing_checksums = {
        str(item.get("original_checksum", ""))
        for item in manifest.get("media", [])
        if isinstance(item, dict)
    }
    adopted = list(manifest.get("media", []))
    for path in candidates:
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        if digest in existing_checksums:
            continue
        with Image.open(path) as image:
            width, height = image.size
        is_logo = "logo" in path.stem.lower()
        adopted.append({
            "asset_id": digest[:24],
            "kind": "image",
            "url": "",
            "source_kind": "business",
            "provenance_type": MediaProvenanceType.USER_PROVIDED_BUSINESS_ASSET.value,
            "source_url": "user://direct-upload",
            "source_role": "user_provided_logo" if is_logo else "user_provided_business_visual",
            "original_origin": "user:direct-upload",
            "original_filename": path.name,
            "original_file": str(path.relative_to(run_dir / "media_input")).replace("\\", "/"),
            "original_checksum": digest,
            "prepared_checksum": digest,
            "width": width,
            "height": height,
            "alt": "Business logo" if is_logo else "User-provided business visual",
            "recommended_use": "logo" if is_logo else "business visual",
            "user_authorized_for_preview": True,
            "allowed_for_customer_production": True,
            "user_authorized": True,
            "allowed_for_public_site": True,
            "portfolio_claim": False,
        })
        existing_checksums.add(digest)
    normalized = normalize_manifest_provenance({**manifest, "media": adopted})
    normalized["media_count"] = len(adopted)
    normalized["image_count"] = sum(item.get("kind", "image") == "image" for item in adopted)
    return normalized
