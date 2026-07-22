from __future__ import annotations

from pathlib import Path

from scripts.repo_hygiene import check_files, default_rules, iter_text_files


def test_hygiene_rules_detect_common_unsafe_changes(tmp_path: Path) -> None:
    candidate = tmp_path / "change.py"
    candidate.write_text(
        "\n".join(
            [
                "import pytest",
                "pytest." + "skip('temporary', allow_module_level=True)",
                "pass" + "word = 'abcdefghijklmnopqrstuvwxyz'",
            ]
        ),
        encoding="utf-8",
    )

    findings = check_files((candidate,), default_rules())

    assert any("disabled_tests" in finding for finding in findings)
    assert any("credential_text" in finding for finding in findings)


def test_hygiene_rules_allow_documented_exceptions(tmp_path: Path) -> None:
    docs = tmp_path / "docs"
    docs.mkdir()
    allowed = docs / "FAILURE_ANALYSIS.md"
    allowed.write_text("Use " + "post" + "-outcome mode only after results close.", encoding="utf-8")

    findings = check_files((allowed,), default_rules())

    assert findings == []


def test_iter_text_files_skips_ignored_local_outputs(tmp_path: Path) -> None:
    included = tmp_path / "docs" / "guide.md"
    skipped = tmp_path / "artifacts" / "run.md"
    included.parent.mkdir()
    skipped.parent.mkdir()
    included.write_text("ok", encoding="utf-8")
    skipped.write_text("skip", encoding="utf-8")

    files = iter_text_files((tmp_path,))

    assert included in files
    assert skipped not in files


def test_required_templates_exist() -> None:
    names = [
        "WORKFLOW_GUARDRAILS.md",
        "TASK_TEMPLATE.md",
        "COMPLETION_REPORT_TEMPLATE.md",
        "INPUT_SELECTION_TREE.md",
        "CHANGE_REVIEW_CHECKLIST.md",
    ]

    assert all((Path("docs") / name).exists() for name in names)
    assert Path("A" + "GENTS.md").exists()
