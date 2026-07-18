from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from PIL import Image

from site_agent.acceptance import AcceptanceAuditor
from site_agent.media import CloudinaryUploader, MediaCandidate, MediaPreparer, authorised_media_assets
from site_agent.models import CritiqueReport, IssueSeverity, TechnicalGate
from site_agent.workflow import selected_references


class _Uploader:
    def upload(self, path: Path, *, public_id: str) -> dict:
        return {
            "url": f"https://res.cloudinary.com/siteagent/image/upload/v1/{public_id}.jpg",
            "cloudinary_public_id": public_id,
            "cloudinary_asset_id": "asset-1",
            "cloudinary_version": "1",
        }

    def _is_own_cloudinary_url(self, url: str) -> bool:
        return url.startswith("https://res.cloudinary.com/siteagent/")


def _critique() -> CritiqueReport:
    return CritiqueReport.model_validate({
        "score": 90,
        "technical_gate": TechnicalGate(passed=True).model_dump(),
        "visual_director_approved": True,
        "business_approved": True,
        "issues": [],
        "summary": "independent review passed",
    })


class CalibrationContractTests(unittest.TestCase):
    def test_existing_business_site_is_never_a_design_reference(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "site_designs"
            root.mkdir(parents=True)
            records = []
            for ident, url in (("same-business", "http://example.test/"), ("reference-a", "https://a.test/"), ("reference-b", "https://b.test/"), ("reference-c", "https://c.test/")):
                folder = root / ident
                folder.mkdir()
                for name in ("desktop.png", "mobile.png"):
                    (folder / name).write_bytes(ident.encode())
                import hashlib
                records.append({"id": ident, "source_url": url, "normalized_url": url, "capture_status": "captured", "analysis_status": "completed", "screenshot_paths": ["desktop.png", "mobile.png"], "capture": {"screenshots": {name: hashlib.sha256((folder / name).read_bytes()).hexdigest() for name in ("desktop.png", "mobile.png")}}, "traits": ["calm conversion"], "search_text": "calm conversion"})
            (root / "catalog.json").write_text(json.dumps({"references": records, "decision_artifact": "reference_decisions.json"}), encoding="utf-8")
            (root / "reference_decisions.json").write_text(json.dumps({"decisions": [{"reference_id": record["id"], "decision": "active", "confidence": 95} for record in records]}), encoding="utf-8")
            selected = selected_references(root=root, business_research={"research": {"instagram_url": "https://example.test/"}})
            self.assertNotIn("same-business", [item["id"] for item in selected])
    def test_prepared_manifest_keeps_required_local_provenance(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "orange-work.jpg"
            Image.new("RGB", (1400, 1000), (90, 130, 160)).save(source)
            manifest = MediaPreparer(uploader=_Uploader()).prepare([MediaCandidate(
                path=source,
                business_id="orange-beauty-studio",
                source_url="https://example.test/original/orange-work.jpg",
                original_origin="Orange authorised local project",
                original_filename="orange-work.jpg",
                alt="Orange Beauty Studio nail work",
                selected_use="hero",
                source_kind="business",
                user_authorized=True,
                allowed_for_public_site=True,
            )], root / "prepared")
            item = manifest["media"][0]
            for field in ("business_id", "source_kind", "source_url", "original_origin", "original_filename", "raw_checksum", "url", "crop", "recommended_use", "alt"):
                self.assertTrue(item.get(field), field)
            self.assertTrue(item["user_authorized"])
            self.assertTrue(item["allowed_for_public_site"])

    def test_only_authorised_manifest_media_can_satisfy_readiness(self) -> None:
        media = [{
            "asset_id": f"asset-{index}", "url": f"https://res.cloudinary.com/siteagent/image/upload/v1/{index}.jpg",
            "source_kind": "business", "user_authorized": True, "allowed_for_public_site": True,
            "width": 1600, "height": 1067, "alt": f"Business scene {index}", "recommended_use": "gallery",
            "source_url": "https://example.test/original.jpg", "original_origin": "authorised business source",
        } for index in range(6)]
        media.append({"url": "https://images.example/stock.jpg", "source_kind": "stock", "user_authorized": True, "allowed_for_public_site": True, "width": 1600, "height": 1000})
        assets = authorised_media_assets({"media": media})
        self.assertEqual(len(assets), 6)
        self.assertTrue(all(asset.source_kind == "business" for asset in assets))

    def test_acceptance_rejects_forged_self_reports_without_product_director_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            studio, site = root / "studio", root / "site"
            (studio / "input").mkdir(parents=True)
            (studio / "concept_reviews").mkdir(parents=True)
            (studio / "final_reviews").mkdir(parents=True)
            site.mkdir()
            (site / "index.html").write_text("<main>Accepted</main>", encoding="utf-8")
            for path in (studio / "build_provenance.json", studio / "concept_reviews" / "comparison.json", studio / "concept_reviews" / "selected_concept.json", studio / "art_director_report.json", studio / "commercial_usefulness_report.json", studio / "language_fit_report.json", studio / "semantic_repetition_report.json", studio / "input" / "scope_decision.json", studio / "scope_compliance_report.json"):
                path.write_text("{}", encoding="utf-8")
            for path in (studio / "final_reviews" / "desktop.png", studio / "final_reviews" / "tablet.png", studio / "final_reviews" / "mobile.png"):
                path.write_bytes(b"png")
            package = {"design_implementation_brief": {"central_idea": "test"}}
            package["sha256"] = hashlib.sha256(json.dumps(package, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
            (studio / "input" / "implementation_package.json").write_text(json.dumps(package), encoding="utf-8")
            (studio / "input" / "media_manifest.json").write_text(json.dumps({"media": []}), encoding="utf-8")
            (studio / "art_director_report.json").write_text(json.dumps({"approved": True}), encoding="utf-8")
            (studio / "commercial_usefulness_report.json").write_text(json.dumps({"approved": True, "score": 90}), encoding="utf-8")
            (studio / "input" / "scope_decision.json").write_text(json.dumps({"scope": "full_site"}), encoding="utf-8")
            (studio / "scope_compliance_report.json").write_text(json.dumps({"approved": True, "scope": "full_site"}), encoding="utf-8")
            result = AcceptanceAuditor().audit(critique=_critique(), site_dir=site, studio_dir=studio)
            self.assertFalse(result.approved)
            self.assertIn("product_director_report.json", " ".join(result.reasons))

    def test_acceptance_rejects_scope_escalation(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            studio, site = root / "studio", root / "site"
            (studio / "input").mkdir(parents=True)
            (studio / "concept_reviews").mkdir(parents=True)
            (studio / "final_reviews").mkdir(parents=True)
            site.mkdir()
            (site / "index.html").write_text("<main>Accepted</main>", encoding="utf-8")
            for path in (studio / "build_provenance.json", studio / "concept_reviews" / "comparison.json", studio / "concept_reviews" / "selected_concept.json", studio / "art_director_report.json", studio / "commercial_usefulness_report.json", studio / "language_fit_report.json", studio / "semantic_repetition_report.json", studio / "scope_compliance_report.json"):
                path.write_text("{}", encoding="utf-8")
            for path in (studio / "final_reviews" / "desktop.png", studio / "final_reviews" / "tablet.png", studio / "final_reviews" / "mobile.png"):
                path.write_bytes(b"png")
            package = {"design_implementation_brief": {"central_idea": "test"}}
            package["sha256"] = hashlib.sha256(json.dumps(package, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
            (studio / "input" / "implementation_package.json").write_text(json.dumps(package), encoding="utf-8")
            (studio / "input" / "media_manifest.json").write_text(json.dumps({"media": []}), encoding="utf-8")
            (studio / "input" / "scope_decision.json").write_text(json.dumps({"scope": "micro_site"}), encoding="utf-8")
            (studio / "art_director_report.json").write_text(json.dumps({"approved": True}), encoding="utf-8")
            (studio / "commercial_usefulness_report.json").write_text(json.dumps({"approved": True, "score": 90}), encoding="utf-8")
            (studio / "scope_compliance_report.json").write_text(json.dumps({"approved": True, "scope": "full_site", "section_count": 4, "image_treatments": 3}), encoding="utf-8")
            result = AcceptanceAuditor().audit(critique=_critique(), site_dir=site, studio_dir=studio)
            self.assertFalse(result.approved)
            self.assertIn("product_director_report.json", " ".join(result.reasons))


if __name__ == "__main__":
    unittest.main()
