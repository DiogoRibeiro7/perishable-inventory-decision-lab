from __future__ import annotations

from pathlib import Path

from scripts.release_gate import (
    REQUIRED_PATHS,
    _card_version_check,
    _markdown_links_check,
    run_release_gate,
)


def test_release_gate_passes_for_current_tree() -> None:
    report = run_release_gate()

    assert report["status"] == "pass"
    assert {check["name"] for check in report["checks"]} >= {
        "required_paths",
        "card_versions",
        "markdown_links",
        "tracked_data",
        "tracked_file_sizes",
        "repository_hygiene",
    }


def test_markdown_link_check_detects_missing_local_target(tmp_path: Path) -> None:
    readme = tmp_path / "README.md"
    readme.write_text("[missing](docs/missing.md)", encoding="utf-8")
    (tmp_path / "docs").mkdir()

    check = _markdown_links_check(tmp_path)

    assert check.status == "fail"
    assert "docs/missing.md" in check.detail


def test_card_version_check_detects_mismatch(tmp_path: Path) -> None:
    docs = tmp_path / "docs"
    docs.mkdir()
    for name in ["MODEL_CARD.md", "POLICY_CARD.md", "SIMULATOR_CARD.md", "SYSTEM_CARD.md"]:
        (docs / name).write_text("Package version: `0.0.0`", encoding="utf-8")

    check = _card_version_check(tmp_path, "0.1.0")

    assert check.status == "fail"
    assert "MODEL_CARD.md" in check.detail


def test_release_package_docs_are_required() -> None:
    required = {path.as_posix() for path in REQUIRED_PATHS}

    assert "docs/FINAL_RELEASE_AUDIT.md" in required
    assert "docs/LIVE_DEMO_GUIDE.md" in required
    assert "docs/ROLE_ALIGNMENT_MATRIX.md" in required
    assert ".zenodo.json" in required
    assert "CITATION.cff" in required
    assert "CODE_OF_CONDUCT.md" in required
    assert "CONTRIBUTING.md" in required
    assert "SECURITY.md" in required
    assert "SUPPORT.md" in required
    assert ".github/pull_request_template.md" in required
    assert "reports/release/v0.1.0_commands.md" in required
