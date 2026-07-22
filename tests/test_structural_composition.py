from __future__ import annotations

import tempfile
import re
import unittest
from pathlib import Path

from site_agent.builder import SiteBuilder
from site_agent.design_quality import audit_quality, build_context, composition_similarity, fingerprint_breakdown
from site_agent.fixture_e2e import fixture_data, run_all


class StructuralCompositionTests(unittest.TestCase):
    def test_identical_sequence_cannot_have_zero_similarity(self) -> None:
        research, strategy, spec = fixture_data()["restaurant"]
        features = fingerprint_breakdown(spec, build_context(research, strategy, spec))
        similarity = composition_similarity(features, features)
        self.assertEqual(similarity["section_sequence_similarity"], 1.0)
        self.assertGreater(similarity["complete_composition_similarity"], 0.9)

    def test_palette_or_copy_alone_is_not_unique_composition(self) -> None:
        research, strategy, spec = fixture_data()["restaurant"]
        first = build_context(research, strategy, spec)
        second = build_context(research, strategy, spec)
        second.design_system.tokens["accent"] = "#000000"
        spec.h1 = "Completely different words"
        similarity = composition_similarity(fingerprint_breakdown(spec, first), fingerprint_breakdown(spec, second))
        self.assertEqual(similarity["section_sequence_similarity"], 1.0)
        self.assertEqual(similarity["dom_tree_similarity"], 1.0)

    def test_category_compositions_have_distinct_hero_and_closure(self) -> None:
        values = [build_context(*fixture_data()[name]).page_composition for name in ("restaurant", "dental", "decorator", "school")]
        self.assertEqual(len({item.journey_pattern for item in values}), 4)
        self.assertGreaterEqual(len({item.hero_type for item in values}), 3)
        self.assertGreaterEqual(len({item.closing_pattern for item in values}), 3)

    def test_builder_follows_validated_section_graph_and_writes_manifest(self) -> None:
        research, strategy, spec = fixture_data()["dental"]
        context = build_context(research, strategy, spec)
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); (root / "generation_reports").mkdir()
            index = SiteBuilder().build(site_dir=root / "site", research=research, strategy=strategy, spec=spec, design_context=context)
            html = index.read_text(encoding="utf-8")
            self.assertIn('data-section-type="authority_hero"', html)
            self.assertIn('data-section-type="consultation_closure"', html)
            rendered_ids = set(re.findall(r'\sid="([^"]+)"', html))
            for fragment in re.findall(r'href="#([^"]+)"', html):
                self.assertIn(fragment, rendered_ids)
            self.assertTrue((root / "generation_reports" / "build_manifest.json").is_file())

    def test_score_breakdown_is_evidence_backed_and_not_default_92(self) -> None:
        research, strategy, spec = fixture_data()["school"]
        report = audit_quality(spec, build_context(research, strategy, spec), technical_passed=True)
        self.assertTrue(report.approved)
        self.assertTrue(all(value.status == "evaluated" for value in report.score_breakdown.values()))
        self.assertNotEqual(set(report.category_scores.values()), {92})

    def test_fixture_e2e_sequences_and_copy_are_distinct(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            evidence = run_all(Path(temp) / "fixtures")
            primary = [evidence["runs"][name] for name in ("restaurant", "dental", "decorator", "school")]
            sequences = {tuple(item["fingerprint_breakdown"]["section_sequence"]) for item in primary}
            self.assertEqual(len(sequences), 4)
            self.assertTrue(all(item["status"] == "approved" for item in primary))
            matrix = evidence["similarity_matrix"]
            self.assertTrue(all(matrix[a][b]["dom_tree_similarity"] < .4 for a in ("restaurant", "dental", "decorator", "school") for b in ("restaurant", "dental", "decorator", "school") if a != b))
            self.assertEqual(evidence["runs"]["level_c"]["builder_started"], False)
            self.assertEqual(evidence["runs"]["yacht_placeholder"]["status"], "blocked")
