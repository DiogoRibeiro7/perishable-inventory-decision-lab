"""Final release checks for the perishable inventory decision lab."""

from __future__ import annotations

import argparse
import json
import platform
import re
import subprocess
import sys
import tomllib
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path

try:
    from scripts.repo_hygiene import DEFAULT_PATHS, check_files, default_rules, iter_text_files
except ModuleNotFoundError:  # pragma: no cover - used when executed as scripts/release_gate.py
    from repo_hygiene import DEFAULT_PATHS, check_files, default_rules, iter_text_files

REPO_ROOT = Path(__file__).resolve().parents[1]

REQUIRED_PATHS = (
    Path("README.md"),
    Path("LICENSE"),
    Path("pyproject.toml"),
    Path("Dockerfile"),
    Path(".github/workflows/ci.yml"),
    Path("airflow/dags/perishable_decision_pipeline.py"),
    Path("dbt_project/models/schema.yml"),
    Path("gcp/DEPLOYMENT_RUNBOOK.md"),
    Path("docs/MODEL_CARD.md"),
    Path("docs/POLICY_CARD.md"),
    Path("docs/SIMULATOR_CARD.md"),
    Path("docs/SYSTEM_CARD.md"),
    Path("docs/FINAL_RELEASE_AUDIT.md"),
    Path("docs/RELEASE_NOTES.md"),
    Path("docs/LIVE_DEMO_GUIDE.md"),
    Path("docs/ARCHITECTURE_ONE_PAGER.md"),
    Path("docs/DEEP_DIVE_PLAN.md"),
    Path("docs/FAQ_FAILURE_RECOVERY.md"),
    Path("docs/ROLE_ALIGNMENT_MATRIX.md"),
    Path("docs/RETAIL_ADAPTATION_30_60_90.md"),
    Path("docs/THIRD_PARTY_NOTICES.md"),
    Path("reports/example_results.md"),
    Path("reports/example_run/forecast_metrics.json"),
    Path("reports/example_run/policy_metrics.csv"),
    Path("reports/example_run/monitoring_report.json"),
    Path("reports/release/v0.1.0_commands.md"),
)

CARD_PATHS = (
    Path("docs/MODEL_CARD.md"),
    Path("docs/POLICY_CARD.md"),
    Path("docs/SIMULATOR_CARD.md"),
    Path("docs/SYSTEM_CARD.md"),
)

MARKDOWN_PATHS = (
    Path("README.md"),
    Path("VALIDATION.md"),
    Path("docs"),
    Path("reports"),
    Path("gcp"),
    Path("data"),
)

RAW_DATA_PREFIXES = ("data/raw/", "data/processed/")
LOCAL_LINK_RE = re.compile(r"!?\[[^\]]+\]\((?!https?://|mailto:|#)([^)\s]+)(?:\s+\"[^\"]*\")?\)")


@dataclass(frozen=True)
class GateCheck:
    name: str
    status: str
    detail: str


def run_release_gate(root: Path = REPO_ROOT) -> dict[str, object]:
    """Run deterministic release checks and return a JSON-serializable report."""
    version = _package_version(root)
    checks = [
        _required_paths_check(root),
        _card_version_check(root, version),
        _markdown_links_check(root),
        _tracked_data_check(root),
        _tracked_size_check(root),
        _hygiene_check(root),
    ]
    status = "pass" if all(check.status == "pass" for check in checks) else "fail"
    return {
        "status": status,
        "package_version": version,
        "generated_at": datetime.now(UTC).isoformat(),
        "environment": {
            "python": platform.python_version(),
            "platform": platform.platform(),
        },
        "checks": [asdict(check) for check in checks],
    }


def _package_version(root: Path) -> str:
    pyproject = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
    return str(pyproject["tool"]["poetry"]["version"])


def _required_paths_check(root: Path) -> GateCheck:
    missing = [path.as_posix() for path in REQUIRED_PATHS if not (root / path).exists()]
    if missing:
        return GateCheck("required_paths", "fail", "missing: " + ", ".join(missing))
    return GateCheck("required_paths", "pass", f"{len(REQUIRED_PATHS)} required paths present")


def _card_version_check(root: Path, version: str) -> GateCheck:
    expected = f"Package version: `{version}`"
    mismatches = [
        path.as_posix()
        for path in CARD_PATHS
        if expected not in (root / path).read_text(encoding="utf-8")
    ]
    if mismatches:
        return GateCheck("card_versions", "fail", "version mismatch: " + ", ".join(mismatches))
    return GateCheck("card_versions", "pass", f"{len(CARD_PATHS)} cards match package version {version}")


def _markdown_links_check(root: Path) -> GateCheck:
    broken = []
    for path in _iter_markdown_files(root):
        text = path.read_text(encoding="utf-8")
        for match in LOCAL_LINK_RE.finditer(text):
            target = match.group(1).split("#", maxsplit=1)[0]
            if not target:
                continue
            decoded_target = target.replace("%20", " ")
            linked = (path.parent / decoded_target).resolve()
            if not linked.exists():
                broken.append(f"{path.relative_to(root).as_posix()} -> {target}")
    if broken:
        return GateCheck("markdown_links", "fail", "broken: " + "; ".join(broken))
    return GateCheck("markdown_links", "pass", "local markdown links resolve")


def _iter_markdown_files(root: Path) -> tuple[Path, ...]:
    files: list[Path] = []
    for path in MARKDOWN_PATHS:
        resolved = root / path
        if not resolved.exists():
            continue
        if resolved.is_file() and resolved.suffix.lower() == ".md":
            files.append(resolved)
            continue
        files.extend(child for child in resolved.rglob("*.md") if child.is_file())
    return tuple(sorted(set(files)))


def _tracked_data_check(root: Path) -> GateCheck:
    tracked = _git_ls_files(root)
    unsafe = [
        path for path in tracked if any(path.startswith(prefix) for prefix in RAW_DATA_PREFIXES)
    ]
    if unsafe:
        return GateCheck("tracked_data", "fail", "tracked generated data: " + ", ".join(unsafe))
    return GateCheck("tracked_data", "pass", "no raw or processed data files are tracked")


def _tracked_size_check(root: Path, max_bytes: int = 5_000_000) -> GateCheck:
    tracked = _git_ls_files(root)
    oversized = []
    for path in tracked:
        absolute = root / path
        if absolute.exists() and absolute.is_file() and absolute.stat().st_size > max_bytes:
            oversized.append(path)
    if oversized:
        return GateCheck("tracked_file_sizes", "fail", "oversized: " + ", ".join(oversized))
    return GateCheck("tracked_file_sizes", "pass", f"tracked files are <= {max_bytes} bytes")


def _hygiene_check(root: Path) -> GateCheck:
    paths = tuple(root / path for path in DEFAULT_PATHS)
    findings = check_files(iter_text_files(paths), default_rules())
    if findings:
        return GateCheck("repository_hygiene", "fail", f"{len(findings)} finding(s)")
    return GateCheck("repository_hygiene", "pass", "repository hygiene checks pass")


def _git_ls_files(root: Path) -> tuple[str, ...]:
    result = subprocess.run(
        ["git", "ls-files"],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    )
    return tuple(line.strip().replace("\\", "/") for line in result.stdout.splitlines() if line.strip())


def main() -> int:
    parser = argparse.ArgumentParser(description="Run final release checks.")
    parser.add_argument("--write", type=Path, help="Optional JSON report path.")
    args = parser.parse_args()

    report = run_release_gate()
    payload = json.dumps(report, indent=2, sort_keys=True)
    if args.write:
        output_path = args.write
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(payload + "\n", encoding="utf-8")
    print(payload)
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    sys.exit(main())
