from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from site_agent.acceptance import AcceptanceAuditor
from site_agent.models import CritiqueIssue, CritiqueReport, IssueSeverity, TechnicalGate


class AcceptanceAuditorTests(unittest.TestCase):
    def test_approved_critic_and_built_index_pass(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            site = Path(temp)
            (site / "index.html").write_text("<html></html>", encoding="utf-8")
            report = CritiqueReport(
                score=90,
                technical_gate=TechnicalGate(passed=True),
                visual_director_approved=True,
                business_approved=True,
                issues=[],
                summary="approved",
            )
            result = AcceptanceAuditor().audit(critique=report, site_dir=site)
            self.assertTrue(result.approved)

    def test_blocking_issue_fails_acceptance(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            site = Path(temp)
            (site / "index.html").write_text("<html></html>", encoding="utf-8")
            report = CritiqueReport(
                score=92,
                technical_gate=TechnicalGate(passed=True),
                visual_director_approved=True,
                business_approved=True,
                issues=[
                    CritiqueIssue(
                        severity=IssueSeverity.high,
                        area="technical",
                        problem="broken",
                        why_it_matters="delivery",
                        fix="repair",
                    )
                ],
                summary="blocked",
            )
            result = AcceptanceAuditor().audit(critique=report, site_dir=site)
            self.assertFalse(result.approved)
            self.assertFalse(result.no_blocking_issues)


if __name__ == "__main__":
    unittest.main()
