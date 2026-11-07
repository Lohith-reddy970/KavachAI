"""Regression checks for the deterministic evaluation corpus and metrics."""
from __future__ import annotations

from evals.run import character_error_rate, evaluate_citations, word_error_rate


def test_labeled_citation_cases_have_correct_pages_and_source_spans():
    result = evaluate_citations()

    assert result["status"] == "passed", result["cases"]
    assert result["citation_precision"] == 1.0
    assert result["citation_recall"] == 1.0
    assert result["page_accuracy"] == 1.0
    assert result["source_location_accuracy"] == 1.0
    assert result["expected_citations"] == 4


def test_character_and_word_error_rates_are_normalized_edit_distance():
    assert character_error_rate("Pump P-101", "pump P-101") == 0.0
    assert word_error_rate("pump p-101 repair", "pump p-101 repair") == 0.0
    assert character_error_rate("scan", "scam") == 0.25
    assert word_error_rate("one two", "one three") == 0.5
