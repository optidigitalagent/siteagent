from __future__ import annotations

from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field, HttpUrl


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
    source_kind: Literal["business", "stock", "fixture_stock", "unknown"] = "unknown"
    source_url: str = ""
    provenance_note: str = ""
    portfolio_claim: bool = False


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
    notes: list[str] = Field(default_factory=list)


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
    score: int
    no_blocking_issues: bool
    index_present: bool
    reasons: list[str] = Field(default_factory=list)
    audited_at: str
    pipeline_schema_version: int = 1
    category_scores: dict[str, int] = Field(default_factory=dict)
    quality_floors: dict[str, int] = Field(default_factory=dict)
    artifacts_reviewed: list[str] = Field(default_factory=list)


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
