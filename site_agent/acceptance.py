from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from site_agent.models import AcceptanceAuditResult, CritiqueReport


class AcceptanceAuditor:
    def audit(self, *, critique: CritiqueReport, site_dir: Path) -> AcceptanceAuditResult:
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
        )
