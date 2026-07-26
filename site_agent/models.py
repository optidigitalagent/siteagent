from __future__ import annotations

from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field, HttpUrl, field_validator, model_validator


class Evidence(BaseModel):
    source: str
    value: str
    confidence: Literal["high", "medium", "low"] = "medium"


class MediaAsset(BaseModel):
    url: str
    kind: Literal["image", "video", "unknown"] = "image"
    alt: str = ""
    recommended_use: str = ""
    width: int = 0
    height: int = 0
    asset_id: str = ""
    source_kind: Literal["business", "business_social", "business_web", "stock", "fixture_stock", "unknown"] = "unknown"
    source_url: str = ""
    provenance_note: str = ""
    portfolio_claim: bool = False


class ContentProvenance(BaseModel):
    """One customer-facing claim and the evidence class controlling its use."""

    field: str
    value: str = ""
    status: Literal[
        "verified_fact", "inferred_brand_copy", "generated_demo_content", "missing_required_fact"
    ]
    sources: list[str] = Field(default_factory=list)
    production_blocker: bool = False


class ProductIdentity(BaseModel):
    """A concrete offering whose wording and provenance are safe to publish."""

    exact_product: str
    evidence_sources: list[str] = Field(default_factory=list)
    confidence: Literal["high", "medium", "low"] = "medium"


class ContentTheme(BaseModel):
    """One non-overlapping decision, proof, or offer theme for the page."""

    label: str
    decision_role: Literal["offer", "format", "process", "proof", "audience", "conversion"]
    evidence_sources: list[str] = Field(default_factory=list)


class ResearchBrief(BaseModel):
    instagram_url: str
    # Evidence controls which facts may be used. It never gets to replace the
    # product the customer ordered with a smaller, unrequested page.
    requested_product_type: Literal[
        "full_commercial_site", "multi_page_commercial_site", "campaign_landing",
        "micro_site", "portfolio", "catalog", "web_app",
    ] = "full_commercial_site"
    business_name: str = ""
    city: str = ""
    country: str = ""
    primary_language: str = ""
    niche: str = ""
    sells: list[str] = Field(default_factory=list)
    services_or_products: list[str] = Field(default_factory=list)
    visible_prices_offers: list[str] = Field(default_factory=list)
    contacts: list[str] = Field(default_factory=list)
    communication_style: str = ""
    brand_atmosphere: str = ""
    visual_style: str = ""
    colors: list[str] = Field(default_factory=list)
    best_media: list[MediaAsset] = Field(default_factory=list)
    verified_facts: list[Evidence] = Field(default_factory=list)
    product_identity: ProductIdentity | None = None
    content_themes: list[ContentTheme] = Field(default_factory=list)
    unknowns: list[str] = Field(default_factory=list)
    forbidden_claims: list[str] = Field(default_factory=list)
    content_provenance: list[ContentProvenance] = Field(default_factory=list)


class BusinessResearch(BaseModel):
    """Cited strategist artifact; it is richer than the renderer compatibility data."""

    research: ResearchBrief
    target_audience: str = ""
    buying_context: str = ""
    business_level: str = ""
    positioning: list[str] = Field(default_factory=list)
    differentiators: list[str] = Field(default_factory=list)
    customer_questions: list[str] = Field(default_factory=list)
    trust_signals: list[str] = Field(default_factory=list)
    brand_media_signals: list[str] = Field(default_factory=list)
    recommended_scope: Literal["full_site", "micro_site", "blocked"] = "blocked"
    missing_content_manifest: list[str] = Field(default_factory=list)
    citations: list[Evidence] = Field(default_factory=list)


class DesignImplementationBrief(BaseModel):
    """The complete non-template contract handed to Codex Studio."""

    central_idea: str
    page_structure: list[str]
    narrative: str
    first_viewport: str
    typography: str
    palette: str
    spacing_grid: str
    media_treatment: str
    motion: str
    cta_logic: str
    responsive_behavior: str
    copy_direction: str
    section_requirements: list[str] = Field(default_factory=list)
    anti_patterns: list[str] = Field(default_factory=list)
    selected_references: list[dict[str, str]] = Field(default_factory=list)
    reference_rationale: str = ""
    do_not_copy: list[str] = Field(default_factory=list)
    brand_application: str = ""
    brand_identity_checksum: str = ""
    # Compatibility data is validation-only; Studio is explicitly told not to
    # infer its composition from it.
    strategy: "StrategyBrief"
    site_spec: "SiteSpec"


class StrategyBrief(BaseModel):
    target_customer: str
    reason_to_choose: list[str]
    customer_questions_or_fears: list[str]
    niche_specific_sections: list[str]
    primary_cta: str
    secondary_cta: str
    site_structure: Literal["one-page", "multi-page"] = "one-page"
    tone: str
    color_direction: str
    typography_direction: str
    business_logic: str


class SectionSpec(BaseModel):
    id: str
    title: str
    purpose: str
    content: list[str] = Field(default_factory=list)
    cta: str = ""


class SiteSpec(BaseModel):
    language: str
    title: str
    meta_description: str
    h1: str
    hero_subtitle: str
    primary_cta: str
    secondary_cta: str
    sections: list[SectionSpec]
    trust_points: list[str]
    process_steps: list[str]
    gallery_assets: list[MediaAsset] = Field(default_factory=list)
    contact_lines: list[str] = Field(default_factory=list)
    footer_note: str
    no_fake_claims_checklist: list[str]


class IssueSeverity(str, Enum):
    critical = "critical"
    high = "high"
    medium = "medium"
    low = "low"


class CritiqueIssue(BaseModel):
    severity: IssueSeverity
    area: Literal[
        "hero",
        "mobile",
        "copy",
        "CTA",
        "business fit",
        "visual rhythm",
        "trust",
        "media",
        "layout",
        "technical",
    ]
    problem: str
    why_it_matters: str
    fix: str


class TechnicalGate(BaseModel):
    passed: bool
    horizontal_scroll: bool = False
    missing_images: list[str] = Field(default_factory=list)
    console_errors: list[str] = Field(default_factory=list)
    failed_network_requests: list[str] = Field(default_factory=list)
    broken_links: list[str] = Field(default_factory=list)
    small_tap_targets: list[str] = Field(default_factory=list)
    persistent_header_issues: list[str] = Field(default_factory=list)
    footer_issues: list[str] = Field(default_factory=list)
    clipped_primary_ctas: list[str] = Field(default_factory=list)
    functional_issues: list[str] = Field(default_factory=list)
    reduced_motion_issues: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)

    @field_validator(
        "missing_images", "console_errors", "failed_network_requests",
        "broken_links", "small_tap_targets", "persistent_header_issues",
        "footer_issues", "clipped_primary_ctas", "functional_issues",
        "reduced_motion_issues", "notes", mode="after",
    )
    @classmethod
    def normalize_findings(cls, values: list[str]) -> list[str]:
        return list(dict.fromkeys(
            normalized for value in values
            if (normalized := " ".join(value.split()))
        ))

    @property
    def blocking_reasons(self) -> list[str]:
        """Return the existing technical findings that make readiness unsafe."""
        reasons: list[str] = []
        if self.horizontal_scroll:
            reasons.append("horizontal overflow")
        for field, label in (
            (self.missing_images, "broken or missing images"),
            (self.console_errors, "console errors"),
            (self.failed_network_requests, "blocking failed network requests"),
            (self.broken_links, "broken links"),
            (self.small_tap_targets, "small tap targets"),
            (self.persistent_header_issues, "persistent header issues"),
            (self.footer_issues, "footer issues"),
            (self.clipped_primary_ctas, "clipped primary CTAs"),
            (self.functional_issues, "functional issues"),
            (self.reduced_motion_issues, "reduced-motion issues"),
        ):
            if field:
                reasons.append(label)
        return reasons

    @model_validator(mode="after")
    def enforce_readiness_invariants(self) -> "TechnicalGate":
        blocking = self.blocking_reasons
        if blocking and self.passed:
            # A producer cannot override observed blocking evidence. Normalize
            # fail-closed so downstream consumers never see the contradiction.
            self.passed = False
        if not self.passed and not blocking:
            raise ValueError(
                "A failed technical gate requires blocking evidence in an existing issue field."
            )
        return self


class CritiqueReport(BaseModel):
    score: int = Field(ge=0, le=100)
    technical_gate: TechnicalGate
    visual_director_approved: bool
    business_approved: bool
    issues: list[CritiqueIssue]
    summary: str

    @property
    def has_blocking_issues(self) -> bool:
        return any(issue.severity in {IssueSeverity.critical, IssueSeverity.high} for issue in self.issues)

    @property
    def approved_for_delivery(self) -> bool:
        return (
            self.technical_gate.passed
            and self.visual_director_approved
            and self.business_approved
            and self.score >= 88
            and not self.has_blocking_issues
        )


class AcceptanceAuditResult(BaseModel):
    approved: bool
    technical_gate_passed: bool
    visual_director_approved: bool
    business_approved: bool
    score: int = Field(ge=0, le=100)
    no_blocking_issues: bool
    index_present: bool
    reasons: list[str] = Field(default_factory=list)
    audited_at: str
    pipeline_schema_version: int = 1
    category_scores: dict[str, int] = Field(default_factory=dict)
    quality_floors: dict[str, int] = Field(default_factory=dict)
    artifacts_reviewed: list[str] = Field(default_factory=list)

    @field_validator("reasons", "artifacts_reviewed", mode="after")
    @classmethod
    def normalize_audit_lists(cls, values: list[str]) -> list[str]:
        return list(dict.fromkeys(
            normalized for value in values
            if (normalized := " ".join(value.split()))
        ))

    @field_validator("category_scores", "quality_floors", mode="after")
    @classmethod
    def validate_quality_values(cls, values: dict[str, int]) -> dict[str, int]:
        invalid = {
            name: value for name, value in values.items()
            if not 0 <= value <= 100
        }
        if invalid:
            raise ValueError("Acceptance quality scores and floors must be between 0 and 100.")
        return values

    @model_validator(mode="after")
    def enforce_approval_invariants(self) -> "AcceptanceAuditResult":
        contradictions: list[str] = []
        if not self.technical_gate_passed:
            contradictions.append("Technical gate did not pass.")
        if not self.visual_director_approved:
            contradictions.append("Visual director approval is missing.")
        if not self.business_approved:
            contradictions.append("Business approval is missing.")
        if self.score < 88:
            contradictions.append(f"Critic score {self.score} is below 88.")
        if not self.no_blocking_issues:
            contradictions.append("Critical or high severity issues remain.")
        if not self.index_present:
            contradictions.append("Built site/index.html is missing or empty.")
        for category, floor in self.quality_floors.items():
            score = self.category_scores.get(category)
            if score is None:
                contradictions.append(
                    f"Quality category {category!r} is missing for its declared floor."
                )
            elif score < floor:
                contradictions.append(
                    f"Quality category {category!r} score {score} is below floor {floor}."
                )
        if (self.category_scores or self.quality_floors) and (
                set(self.category_scores) != set(self.quality_floors)):
            contradictions.append(
                "Acceptance category scores and quality floors must cover the same categories."
            )

        # A producer cannot assert approval over contradictory gate evidence.
        # Normalize fail-closed and retain a durable explanation, matching the
        # TechnicalGate invariant above.
        if self.approved and (contradictions or self.reasons):
            self.approved = False
            self.reasons = list(dict.fromkeys(self.reasons + contradictions))
        if not self.approved and not self.reasons:
            raise ValueError("A rejected acceptance audit requires at least one reason.")
        return self


class DeploymentResult(BaseModel):
    provider: Literal["cloudflare_pages", "git", "local"]
    project_name: str = ""
    production_url: str
    deployment_url: str
    deployment_id: str = ""
    status: Literal["success", "local_preview"]
    deployed_at: str
    verification_status: Literal["verified", "not_required"]
    repo_url: str = ""

    @property
    def site_url(self) -> str:
        return self.production_url

    @property
    def deployed(self) -> bool:
        return self.status == "success" and self.provider != "local"

    @property
    def is_verified_production(self) -> bool:
        return (
            self.status == "success"
            and self.verification_status == "verified"
            and self.production_url.startswith("https://")
        )


PublishResult = DeploymentResult

# Resolve the validation-only forward references in DesignImplementationBrief.
DesignImplementationBrief.model_rebuild()
