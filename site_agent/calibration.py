"""Run a supplied, evidence-grounded Studio calibration without publishing.

This command never claims a Telegram job and never constructs a Publisher.
It intentionally requires a cited research artifact and an authorised media
candidate manifest so no legacy site copy, reference capture or scraped URL can
quietly enter the creative plane.
"""
from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

from site_agent.json_io import write_json
from site_agent.models import BusinessResearch
from site_agent.orchestrator import CalibrationResult, SiteAgentOrchestrator
from site_agent.workflow import checksum, write_markdown


def run_calibration(*, business_id: str, run_dir: Path, business_research_path: Path, media_manifest_path: Path) -> CalibrationResult:
    business = json.loads(business_research_path.read_text(encoding="utf-8"))
    validated = BusinessResearch.model_validate(business)
    if not validated.research.instagram_url:
        raise ValueError("Business research requires a verified primary source URL.")
    if not media_manifest_path.is_file():
        raise ValueError(f"Authorised media manifest is missing: {media_manifest_path}")

    reports = run_dir / "generation_reports"
    media_input = run_dir / "media_input"
    reports.mkdir(parents=True, exist_ok=True)
    media_input.mkdir(parents=True, exist_ok=True)
    write_json(reports / "01_business_research.json", business)
    write_markdown(reports / "business_research.md", "Business research", business)
    write_json(reports / "01_business_research.provenance.json", {
        "role": "Calibration evidence intake",
        "input_path": str(business_research_path),
        "output_checksum": checksum(business),
        "contains_secrets": False,
    })
    destination = media_input / "manifest.json"
    if media_manifest_path.resolve() != destination.resolve():
        shutil.copy2(media_manifest_path, destination)

    result = SiteAgentOrchestrator().run(
        validated.research.instagram_url,
        production=False,
        run_id=business_id,
        run_path=run_dir,
        calibration_only=True,
    )
    if not isinstance(result, CalibrationResult):
        raise RuntimeError("Calibration unexpectedly reached a delivery path.")
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Run no-publish SiteAgent Studio calibration.")
    parser.add_argument("--business-id", required=True)
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--business-research", type=Path, required=True)
    parser.add_argument("--media-manifest", type=Path, required=True)
    args = parser.parse_args()
    result = run_calibration(
        business_id=args.business_id,
        run_dir=args.run_dir,
        business_research_path=args.business_research,
        media_manifest_path=args.media_manifest,
    )
    print(json.dumps({"status": "completed_human_calibration_required", "business_id": result.job_id, "run_dir": str(result.run_dir), "score": result.final_score}, ensure_ascii=False))


if __name__ == "__main__":
    main()
