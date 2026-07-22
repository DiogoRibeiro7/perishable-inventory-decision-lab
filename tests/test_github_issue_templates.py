from __future__ import annotations

from pathlib import Path

import yaml

TEMPLATE_DIR = Path(".github/ISSUE_TEMPLATE")
FORM_NAMES = {
    "bug_report.yml",
    "feature_request.yml",
    "documentation.yml",
    "question.yml",
}
KNOWN_LABELS = {"bug", "documentation", "enhancement", "question"}


def test_issue_forms_are_parseable_and_labelled() -> None:
    for name in FORM_NAMES:
        payload = yaml.safe_load((TEMPLATE_DIR / name).read_text(encoding="utf-8"))

        assert payload["name"]
        assert payload["description"]
        assert payload["title"]
        assert set(payload["labels"]).issubset(KNOWN_LABELS)
        assert payload["body"]


def test_issue_template_config_disables_blank_issues() -> None:
    payload = yaml.safe_load((TEMPLATE_DIR / "config.yml").read_text(encoding="utf-8"))

    assert payload["blank_issues_enabled"] is False
    assert len(payload["contact_links"]) == 2
