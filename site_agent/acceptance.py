from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from site_agent.design_quality import QualityReport
from site_agent.models import AcceptanceAuditResult, CritiqueReport


class AcceptanceAuditor:
    def audit(
        self,
        *,
        critique: CritiqueReport,
        site_dir: Path,
        quality_report: QualityReport | None = None,
        studio_dir: Path | None = None,
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
                studio_dir / "full_build_visuals" / "desktop.png",
                studio_dir / "full_build_visuals" / "mobile.png",
                studio_dir / "art_director_report.json",
                studio_dir / "commercial_usefulness_report.json",
                studio_dir / "language_fit_report.json",
                studio_dir / "semantic_repetition_report.json",
                studio_dir / "input" / "scope_decision.json",
                studio_dir / "scope_compliance_report.json",
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
                    scope = json.loads((studio_dir / "scope_compliance_report.json").read_text(encoding="utf-8"))
                    if scope.get("approved") is not True or scope.get("scope") not in {"full_site", "micro_site"}:
                        reasons.append("Studio page scope did not pass the mandatory readiness contract.")
                except (OSError, ValueError, AttributeError):
                    reasons.append("Studio approval or commercial report is unreadable.")
                artifacts.extend(["studio/provenance", "studio/concept-comparison", "studio/selection", "studio/full-screenshots", "studio/commercial-usefulness", "studio/language-fit", "studio/semantic-repetition", "studio/scope-decision", "studio/scope-compliance"])

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
