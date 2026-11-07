"""Acceptance evidence must distinguish expected rejections from defects."""
import json

from evals.mentor import CASES, CaseResult, make_inputs, summary, write_reports


def test_mentor_plan_has_exactly_three_positive_and_two_negative_cases():
    assert [case["id"] for case in CASES] == ["S1", "S2", "S3", "F1", "F2"]
    assert sum(case["kind"] == "success" for case in CASES) == 3
    assert sum(case["kind"] == "expected_failure" for case in CASES) == 2


def test_correct_rejection_passes_but_unexpected_acceptance_fails():
    correct = CaseResult(**CASES[3])
    correct.check("Expected HTTP 400", True, 400)
    assert correct.export()["scenario_outcome"] == "expected rejection"
    assert correct.export()["verdict"] == "PASS"
    incorrect = CaseResult(**CASES[3])
    incorrect.check("Expected HTTP 400", False, 200)
    assert incorrect.export()["scenario_outcome"] == "unexpected result"
    assert incorrect.export()["verdict"] == "FAIL"
    aggregate = summary([correct.export(), incorrect.export()])
    assert aggregate["expected_failure_scenarios"] == 1
    assert aggregate["checks_failed"] == 1
    assert aggregate["successful_scenarios"] == 0


def test_evidence_export_escapes_untrusted_response_text_and_preserves_actual_data(tmp_path):
    case = CaseResult(**CASES[0])
    case.observed = {"model_output": "<script>alert('untrusted')</script>"}
    case.check("An assertion actually passed", True)
    result = case.export()
    report = {"finished_at": "2026-11-05T00:00:00+00:00", "environment": {"test_doubles": False},
              "results": [result], "summary": summary([result])}
    write_reports(tmp_path, report)
    rendered = (tmp_path / "report.html").read_text(encoding="utf-8")
    assert "<script>alert" not in rendered
    assert "&lt;script&gt;" in rendered
    assert json.loads((tmp_path / "results.json").read_text(encoding="utf-8"))["results"][0]["observed"] == case.observed
    assert "1/3" in rendered  # Counts reflect measured cases, not the requested split.


def test_controlled_inputs_are_readable_documents_and_the_exe_is_only_text(tmp_path):
    from pypdf import PdfReader
    from PIL import Image
    make_inputs(tmp_path)
    text = PdfReader(tmp_path / "S1_inspection.pdf").pages[0].extract_text()
    assert "critical crack" in text and "CONTROLLED ACCEPTANCE TEST INPUT" in text
    with Image.open(tmp_path / "S2_invoice.png") as image:
        assert image.size == (1600, 700)
    assert (tmp_path / "F1_disallowed.exe").read_bytes().startswith(b"Harmless plain text")
    assert json.loads((tmp_path / "F2_missing_document_request.json").read_text())["document_id"] == 2147483647
