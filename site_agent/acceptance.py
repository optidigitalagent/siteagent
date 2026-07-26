from __future__ import annotations

import json
import hashlib
from datetime import datetime, timezone
from pathlib import Path

from site_agent.design_quality import QualityReport
from site_agent.models import AcceptanceAuditResult, CritiqueReport
from site_agent.media_policy import manifest_policy_issues, rendered_media_policy_issues
from site_agent.product_director import ProductDirectorAuditor


class AcceptanceAuditor:
    def audit(
        self,
        *,
        critique: CritiqueReport,
        site_dir: Path,
        quality_report: QualityReport | None = None,
        studio_dir: Path | None = None,
        preview: bool = False,
    ) -> AcceptanceAuditResult:
        index_path = site_dir / "index.html"
        index_present = index_path.is_file() and index_path.stat().st_size > 0
        reasons: list[str] = []
        if not critique.technical_gate.passed:
            reasons.append("Technical gate did not pass.")
        if not critique.visual_director_approved:
            reasons.append("Visual director approval is missing.")
        if not critique.business_approved:
            reasons.append("Business approval is missing.")
        if critique.score < 88:
            reasons.append(f"Critic score {critique.score} is below 88.")
        if critique.has_blocking_issues:
            reasons.append("Critical or high severity issues remain.")
        if not index_present:
            reasons.append("Built site/index.html is missing or empty.")
        if quality_report is not None and not quality_report.approved:
            reasons.extend(quality_report.blocking_reasons)
        artifacts = ["critique", "site/index.html"] + (["quality_report"] if quality_report else [])
        if studio_dir is not None:
            required = (
                studio_dir / "build_provenance.json",
                studio_dir / "concept_reviews" / "comparison.json",
                studio_dir / "concept_reviews" / "selected_concept.json",
                # The Studio runner renders the promoted selected build here.
                # Concept screenshots live elsewhere; accepting those instead
                # would sever approval from the final static HTML revision.
                studio_dir / "final_reviews" / "desktop.png",
                studio_dir / "final_reviews" / "tablet.png",
                studio_dir / "final_reviews" / "mobile.png",
                studio_dir / "art_director_report.json",
                studio_dir / "commercial_usefulness_report.json",
                studio_dir / "product_director_report.json",
                studio_dir / "brand_fidelity_report.json",
                studio_dir / "language_fit_report.json",
                studio_dir / "semantic_repetition_report.json",
                studio_dir / "input" / "scope_decision.json",
                studio_dir / "scope_compliance_report.json",
                studio_dir / "input" / "implementation_package.json",
                studio_dir / "input" / "media_manifest.json",
            )
            missing = [str(item.relative_to(studio_dir)) for item in required if not item.is_file()]
            if missing:
                reasons.append("Studio acceptance artifacts are missing: " + ", ".join(missing))
            else:
                try:
                    art_director = json.loads((studio_dir / "art_director_report.json").read_text(encoding="utf-8"))
                    if art_director.get("approved") is not True:
                        reasons.append("Art Director did not approve the screenshot-led Studio build.")
                    commercial = json.loads((studio_dir / "commercial_usefulness_report.json").read_text(encoding="utf-8"))
                    if commercial.get("approved") is not True or commercial.get("score", 0) < 85:
                        reasons.append("Commercial usefulness did not pass the mandatory 85-point gate.")
                    product = json.loads((studio_dir / "product_director_report.json").read_text(encoding="utf-8"))
                    if product.get("auditor") != "ProductDirectorAuditor" or product.get("product_accepted") is not True:
                        reasons.append("Independent Product Director did not accept the requested commercial product.")
                    brand = json.loads((studio_dir / "brand_fidelity_report.json").read_text(encoding="utf-8"))
                    if brand.get("auditor") != "BrandFidelityAuditor" or brand.get("approved") is not True:
                        reasons.append("Independent Brand Fidelity auditor did not accept the final business identity.")
                    scope = json.loads((studio_dir / "scope_compliance_report.json").read_text(encoding="utf-8"))
                    decision = json.loads((studio_dir / "input" / "scope_decision.json").read_text(encoding="utf-8"))
                    if scope.get("approved") is not True or scope.get("scope") not in {"full_site", "micro_site"}:
                        reasons.append("Studio page scope did not pass the mandatory readiness contract.")
                    elif scope.get("scope") != decision.get("scope"):
                        reasons.append("Studio scope compliance does not match the immutable approved scope decision.")
                    elif scope.get("scope") == "micro_site" and (scope.get("section_count", 4) > 3 or scope.get("image_treatments", 3) > 2):
                        reasons.append("Micro-site exceeds its approved section or image-treatment budget.")
                    package = json.loads((studio_dir / "input" / "implementation_package.json").read_text(encoding="utf-8"))
                    manifest = json.loads((studio_dir / "input" / "media_manifest.json").read_text(encoding="utf-8"))
                    if not package.get("sha256") or not package.get("design_implementation_brief"):
                        reasons.append("Studio implementation package is incomplete or lacks an integrity checksum.")
                    elif package.get("implementation_package_information_loss") is not True:
                        reasons.append("Studio implementation package lost mandatory research or Design Director information.")
                    else:
                        canonical = dict(package)
                        supplied = canonical.pop("sha256")
                        canonical.pop("studio_input_sha256", None)
                        canonical.pop("contract", None)
                        actual = hashlib.sha256(json.dumps(canonical, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
                        if supplied != actual:
                            reasons.append("Studio implementation package checksum does not match its content.")
                    if not package.get("brand_identity", {}).get("brand_identity_checksum"):
                        reasons.append("Studio implementation package lacks the verified brand identity package.")
                    package_logo = package.get("brand_assets_manifest", {}).get("logo", {})
                    if package_logo.get("available") is True and not package_logo.get("processed_checksum"):
                        reasons.append("Studio implementation package lacks the checksum-bound official logo asset.")
                    if brand.get("brand_identity_checksum") != package.get("brand_identity", {}).get("brand_identity_checksum"):
                        reasons.append("Brand Fidelity report is stale or bound to a different brand identity package.")
                    target = "isolated_preview" if preview else "customer_production"
                    media_issues = manifest_policy_issues(manifest, target=target, require_media=True)
                    if media_issues:
                        reasons.append("Studio media provenance failed: " + "; ".join(media_issues))
                    generated = [
                        item for item in manifest.get("media", [])
                        if item.get("provenance_type") == "ai_generated_original"
                    ]
                    if generated and not package.get("media_plan", {}).get("items"):
                        reasons.append("Generated Studio media is missing its checksum-bound media plan.")
                    if index_present:
                        rendered_issues: list[str] = []
                        for html_path in sorted(site_dir.rglob("*.html")):
                            rendered_issues.extend(
                                f"{html_path.relative_to(site_dir)}: {issue}"
                                for issue in rendered_media_policy_issues(
                                    manifest,
                                    html_path.read_text(encoding="utf-8"),
                                )
                            )
                        if rendered_issues:
                            reasons.append("Rendered media truthfulness failed: " + "; ".join(rendered_issues))
                except (OSError, ValueError, AttributeError):
                    reasons.append("Studio approval or commercial report is unreadable.")
                artifacts.extend(["studio/provenance", "studio/concept-comparison", "studio/selection", "studio/full-screenshots", "studio/implementation-package", "studio/authorised-media", "studio/commercial-usefulness", "studio/product-director", "studio/brand-fidelity", "studio/language-fit", "studio/semantic-repetition", "studio/scope-decision", "studio/scope-compliance"])

        return AcceptanceAuditResult(
            approved=not reasons,
            technical_gate_passed=critique.technical_gate.passed,
            visual_director_approved=critique.visual_director_approved,
            business_approved=critique.business_approved,
            score=critique.score,
            no_blocking_issues=not critique.has_blocking_issues,
            index_present=index_present,
            reasons=reasons,
            audited_at=datetime.now(timezone.utc).isoformat(),
            pipeline_schema_version=quality_report.pipeline_schema_version if quality_report else 1,
            category_scores=quality_report.category_scores if quality_report else {},
            quality_floors=quality_report.floors if quality_report else {},
            artifacts_reviewed=artifacts,
        )
