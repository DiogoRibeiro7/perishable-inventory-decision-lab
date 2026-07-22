"""Repository hygiene checks for reviewable changes."""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path

DEFAULT_PATHS = (
    Path("README.md"),
    Path("VALIDATION.md"),
    Path("Makefile"),
    Path("pyproject.toml"),
    Path(".github"),
    Path("configs"),
    Path("docs"),
    Path("reports"),
    Path("scripts"),
    Path("src"),
    Path("tests"),
)
SKIP_DIRS = {
    ".git",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    "__pycache__",
    "artifacts",
    "data/raw",
    "prom" + "pts",
}
TEXT_SUFFIXES = {
    "",
    ".cfg",
    ".csv",
    ".ini",
    ".json",
    ".md",
    ".py",
    ".sql",
    ".toml",
    ".txt",
    ".yaml",
    ".yml",
}


@dataclass(frozen=True)
class HygieneRule:
    """Single text rule used by the repository hygiene gate."""

    rule_id: str
    pattern: re.Pattern[str]
    message: str
    allow_paths: tuple[str, ...] = ()


def default_rules() -> tuple[HygieneRule, ...]:
    """Return deterministic hygiene rules."""
    excluded_terms = "|".join(
        (
            r"pr" + "ompt",
            r"ag" + "ent",
            r"\ba" + "i\b",
            r"artificial " + "intelligence",
        )
    )
    impact_terms = "|".join(
        (
            "commercial " + "lift",
            "production " + "ready",
            "guaranteed " + "improvement",
            "proven " + "impact",
        )
    )
    forward_term = "look" + "ahead"
    notebook_terms = "|".join(("notebook[- ]only", "only in " + "notebooks?"))
    return (
        HygieneRule(
            "disabled_tests",
            re.compile(r"pytest\.mark\.skip|pytest\.skip\(|unittest\.skip|#\s*type:\s*ignore(?!\[)\b"),
            "Disabled tests or broad ignores require written rationale.",
        ),
        HygieneRule(
            "weakened_typing",
            re.compile(r"ignore_missing_imports\s*=\s*true|strict\s*=\s*false|allow_untyped_defs\s*=\s*true", re.IGNORECASE),
            "Typing strictness must not be weakened silently.",
            allow_paths=("pyproject.toml",),
        ),
        HygieneRule(
            "credential_text",
            re.compile(
                r"-----BEGIN [A-Z ]*PRIVATE KEY-----|AKIA[0-9A-Z]{16}|(api[_-]?key|secret|password)\s*[:=]\s*['\"]?[A-Za-z0-9_\-]{20,}",
                re.IGNORECASE,
            ),
            "Credential-like text must not be committed.",
            allow_paths=("tests/test_security.py",),
        ),
        HygieneRule(
            "notebook_only_logic",
            re.compile(notebook_terms, re.IGNORECASE),
            "Executable business logic must live in package code.",
        ),
        HygieneRule(
            "future_data_leakage",
            re.compile(r"future[- ]data|" + forward_term + r"|post[- ]outcome", re.IGNORECASE),
            "Future information must not enter training or real-time scoring.",
            allow_paths=("docs/FAILURE_ANALYSIS.md", "src/perishable_lab/failures.py", "tests/test_failures.py"),
        ),
        HygieneRule(
            "unsupported_impact_claim",
            re.compile(impact_terms, re.IGNORECASE),
            "Impact claims require linked evidence.",
            allow_paths=(
                "README.md",
                "docs/CASE_STUDY_NARRATIVES.md",
                "docs/CLAIMS_AUDIT.md",
                "docs/INTERVIEW_QUESTION_BANK.md",
                "docs/INTERVIEW_WALKTHROUGH.md",
                "docs/MODELLING_DECISIONS.md",
                "docs/PORTFOLIO_CASE_STUDY.md",
                "tests/test_case_study.py",
            ),
        ),
        HygieneRule(
            "excluded_public_wording",
            re.compile(excluded_terms, re.IGNORECASE),
            "Excluded public wording should not appear in tracked text.",
            allow_paths=("A" + "GENTS.md",),
        ),
    )


def iter_text_files(paths: tuple[Path, ...]) -> tuple[Path, ...]:
    """Return tracked text-like files under selected paths."""
    files: list[Path] = []
    for path in paths:
        if not path.exists():
            continue
        if path.is_file():
            if _is_text_path(path):
                files.append(path)
            continue
        for child in path.rglob("*"):
            if child.is_file() and _is_text_path(child) and not _is_skipped(child):
                files.append(child)
    return tuple(sorted(set(files)))


def check_files(files: tuple[Path, ...], rules: tuple[HygieneRule, ...] | None = None) -> list[str]:
    """Return hygiene findings for the given files."""
    active_rules = rules or default_rules()
    findings: list[str] = []
    for path in files:
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        normalized = path.as_posix()
        for line_number, line in enumerate(text.splitlines(), start=1):
            for rule in active_rules:
                if any(normalized.endswith(allowed) for allowed in rule.allow_paths):
                    continue
                if rule.pattern.search(line):
                    findings.append(f"{normalized}:{line_number}:{rule.rule_id}:{rule.message}")
    return findings


def main() -> int:
    parser = argparse.ArgumentParser(description="Run repository hygiene checks.")
    parser.add_argument("paths", nargs="*", type=Path)
    args = parser.parse_args()

    paths = tuple(args.paths) if args.paths else DEFAULT_PATHS
    findings = check_files(iter_text_files(paths))
    if findings:
        print("\n".join(findings))
        return 1
    print("Repository hygiene checks passed.")
    return 0


def _is_text_path(path: Path) -> bool:
    return path.suffix.lower() in TEXT_SUFFIXES


def _is_skipped(path: Path) -> bool:
    parts = set(path.as_posix().split("/"))
    return any(skip in parts for skip in SKIP_DIRS)


if __name__ == "__main__":
    sys.exit(main())
