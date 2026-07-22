from __future__ import annotations

from pathlib import Path


def test_claims_audit_references_existing_files() -> None:
    audit = Path("docs/CLAIMS_AUDIT.md").read_text(encoding="utf-8")
    tokens = [token.strip("`;.,") for token in audit.replace("|", " ").split()]
    references = [token for token in tokens if token.startswith(("docs/", "tests/", "src/"))]

    assert references
    assert all(Path(reference).exists() for reference in references)


def test_case_study_does_not_claim_commercial_impact() -> None:
    text = Path("docs/PORTFOLIO_CASE_STUDY.md").read_text(encoding="utf-8").lower()

    forbidden = [
        "proved commercial lift",
        "increased retailer revenue",
        "reduced real-world waste",
        "deployed impact",
    ]

    assert all(phrase not in text for phrase in forbidden)
    assert "not field impact" in text or "not a commercial result" in text


def test_narratives_include_required_timeframes_and_failure_analysis() -> None:
    case_study = Path("docs/PORTFOLIO_CASE_STUDY.md").read_text(encoding="utf-8")
    narratives = Path("docs/CASE_STUDY_NARRATIVES.md").read_text(encoding="utf-8")

    assert "Failure Analysis" in case_study
    assert "First 90 Days" in case_study
    assert "Five-Minute Version" in narratives
    assert "Fifteen-Minute Version" in narratives
