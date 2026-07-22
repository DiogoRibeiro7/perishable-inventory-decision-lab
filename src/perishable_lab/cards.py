"""Card metadata consistency checks for release documentation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

CardType = Literal["model", "policy", "simulator", "system"]
EvidenceType = Literal["test", "report", "artifact", "assumption"]


class CardValidationError(ValueError):
    """Raised when card metadata is incomplete or inconsistent."""


@dataclass(frozen=True)
class MetricReference:
    """Metric linked to a produced artifact."""

    name: str
    artifact_path: str
    artifact_field: str


@dataclass(frozen=True)
class ClaimReference:
    """Narrative claim linked to evidence or an explicit assumption."""

    claim: str
    evidence_type: EvidenceType
    reference: str


@dataclass(frozen=True)
class CardMetadata:
    """Versioned metadata shared by model, policy, simulator, and system cards."""

    card_type: CardType
    card_version: str
    package_version: str
    owner: str
    reviewed_at: str
    artifact_versions: tuple[str, ...]
    metrics: tuple[MetricReference, ...]
    claims: tuple[ClaimReference, ...]
    assumptions: tuple[str, ...]
    interface_names: tuple[str, ...]


@dataclass(frozen=True)
class ManifestConsistency:
    """Consistency result between a run manifest and card metadata."""

    status: Literal["pass", "fail"]
    issues: tuple[str, ...]


def validate_card_metadata(metadata: CardMetadata) -> None:
    """Validate that card metadata can support release documentation."""
    issues: list[str] = []
    if not metadata.card_version:
        issues.append("missing_card_version")
    if not metadata.package_version:
        issues.append("missing_package_version")
    if not metadata.owner:
        issues.append("missing_owner")
    if not metadata.reviewed_at:
        issues.append("missing_review_date")
    if not metadata.artifact_versions:
        issues.append("missing_artifact_versions")
    if not metadata.metrics:
        issues.append("missing_metrics")
    if not metadata.claims:
        issues.append("missing_claims")
    if not metadata.interface_names:
        issues.append("missing_interfaces")
    for metric in metadata.metrics:
        if not metric.artifact_path or not metric.artifact_field:
            issues.append(f"metric_without_artifact:{metric.name}")
    for claim in metadata.claims:
        if claim.evidence_type != "assumption" and not claim.reference:
            issues.append(f"claim_without_reference:{claim.claim}")
        if claim.evidence_type == "assumption" and claim.reference not in metadata.assumptions:
            issues.append(f"claim_without_registered_assumption:{claim.claim}")
    if issues:
        raise CardValidationError(", ".join(sorted(set(issues))))


def manifest_consistency_report(
    metadata: CardMetadata,
    manifest: dict[str, object],
    *,
    required_artifacts: tuple[str, ...],
) -> ManifestConsistency:
    """Compare card metadata with a run manifest."""
    issues: list[str] = []
    package_version = manifest.get("package_version")
    if package_version is not None and package_version != metadata.package_version:
        issues.append("package_version_mismatch")
    model_version = manifest.get("model_version")
    if isinstance(model_version, str) and model_version not in metadata.artifact_versions:
        issues.append("model_version_missing_from_card")
    artifacts = manifest.get("artifacts", [])
    artifact_set = set(artifacts) if isinstance(artifacts, list) else set()
    for artifact in required_artifacts:
        if artifact not in artifact_set:
            issues.append(f"missing_artifact:{artifact}")
    feature_columns = manifest.get("feature_columns")
    if feature_columns is not None and not isinstance(feature_columns, list):
        issues.append("feature_columns_not_list")
    if isinstance(feature_columns, list) and not feature_columns:
        issues.append("feature_columns_empty")
    return ManifestConsistency("fail" if issues else "pass", tuple(sorted(issues)))


def release_card_gate(
    cards: tuple[CardMetadata, ...],
    *,
    changed_interfaces: tuple[str, ...],
) -> ManifestConsistency:
    """Require card updates when interfaces or assumptions change."""
    issues: list[str] = []
    card_interfaces = {interface for card in cards for interface in card.interface_names}
    for changed_interface in changed_interfaces:
        if changed_interface not in card_interfaces:
            issues.append(f"changed_interface_without_card:{changed_interface}")
    for card in cards:
        try:
            validate_card_metadata(card)
        except CardValidationError as exc:
            issues.append(f"{card.card_type}:{exc}")
    return ManifestConsistency("fail" if issues else "pass", tuple(sorted(issues)))
