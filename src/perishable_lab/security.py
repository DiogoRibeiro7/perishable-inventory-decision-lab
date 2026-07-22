"""Security, privacy, governance, and access-control helpers."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Literal

AccessAction = Literal[
    "read_data",
    "train_model",
    "score_batch",
    "approve_policy",
    "publish_recommendations",
    "override_order",
    "audit_changes",
]
DataClassification = Literal["public", "internal", "confidential", "restricted"]
Environment = Literal["dev", "staging", "prod"]


class SecurityPolicyError(ValueError):
    """Raised when a security or governance policy is violated."""


@dataclass(frozen=True)
class DataAsset:
    """Classified data asset with retention and deletion rules."""

    name: str
    classification: DataClassification
    contains_sensitive_rows: bool
    retention_days: int
    deletion_method: str
    encryption_required: bool = True

    def __post_init__(self) -> None:
        if self.retention_days < 1:
            raise SecurityPolicyError("retention_days must be positive")
        if self.classification in {"confidential", "restricted"} and not self.encryption_required:
            raise SecurityPolicyError("confidential and restricted assets require encryption")


@dataclass(frozen=True)
class RoleGrant:
    """Least-privilege role grant for one principal."""

    principal: str
    environment: Environment
    actions: tuple[AccessAction, ...]
    resource_patterns: tuple[str, ...]
    human_review_required: bool = False

    def __post_init__(self) -> None:
        if "*" in self.resource_patterns and len(set(self.actions)) > 3:
            raise SecurityPolicyError("broad resource access cannot combine many actions")
        if "publish_recommendations" in self.actions and "approve_policy" in self.actions:
            raise SecurityPolicyError("approval and publication must be separated")


@dataclass(frozen=True)
class SecurityPolicy:
    """Access-control policy with environment separation."""

    role_grants: tuple[RoleGrant, ...]
    allowed_key_suffixes: tuple[str, ...] = (".json", ".pem", ".key", ".p12")

    def principals_for(self, action: AccessAction, environment: Environment) -> tuple[str, ...]:
        """Return principals allowed to perform an action in an environment."""
        return tuple(
            grant.principal
            for grant in self.role_grants
            if grant.environment == environment and action in grant.actions
        )


@dataclass(frozen=True)
class ArtifactApproval:
    """Approved model and policy artifact promotion record."""

    artifact_id: str
    artifact_hash: str
    environment: Environment
    approved_by: str
    approver_role: str
    ticket_id: str
    created_at_utc: str


@dataclass(frozen=True)
class AuditEvent:
    """Governance audit event without row-level sensitive values."""

    event_type: str
    actor: str
    environment: Environment
    resource: str
    action: AccessAction
    timestamp_utc: str
    metadata: dict[str, object]


SENSITIVE_FIELD_PATTERNS = (
    re.compile(".*token.*", re.IGNORECASE),
    re.compile(".*secret.*", re.IGNORECASE),
    re.compile(".*password.*", re.IGNORECASE),
    re.compile(".*key.*", re.IGNORECASE),
    re.compile(".*customer.*", re.IGNORECASE),
    re.compile(".*staff.*", re.IGNORECASE),
    re.compile(".*employee.*", re.IGNORECASE),
)

SECRET_TEXT_PATTERNS = (
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    re.compile(r"AKIA[0-9A-Z]{16}"),
    re.compile(r"(?i)(api[_-]?key|secret|password)\s*[:=]\s*['\"]?[A-Za-z0-9_\-]{20,}"),
)


def default_data_assets() -> tuple[DataAsset, ...]:
    """Return baseline data classification for system records."""
    return (
        DataAsset("transactions", "confidential", False, 730, "partition_delete"),
        DataAsset("store_operations", "internal", False, 365, "partition_delete"),
        DataAsset("supplier_records", "confidential", False, 730, "contractual_delete"),
        DataAsset("staff_overrides", "restricted", True, 365, "row_delete_with_audit"),
        DataAsset("structured_logs", "internal", False, 180, "partition_delete"),
    )


def default_role_grants() -> tuple[RoleGrant, ...]:
    """Return least-privilege role grants without a shared superuser."""
    return (
        RoleGrant("svc-train-dev", "dev", ("read_data", "train_model"), ("dev.features.*",)),
        RoleGrant("svc-score-prod", "prod", ("read_data", "score_batch"), ("prod.features.*", "prod.models.approved")),
        RoleGrant("svc-publish-prod", "prod", ("publish_recommendations",), ("prod.publication.*",), True),
        RoleGrant("group-policy-review", "prod", ("approve_policy",), ("prod.policies.pending",), True),
        RoleGrant("group-store-review", "prod", ("override_order",), ("prod.store_orders.*",), True),
        RoleGrant("group-audit", "prod", ("audit_changes",), ("prod.audit.*",)),
        RoleGrant("svc-monitor-prod", "prod", ("audit_changes", "read_data"), ("prod.metrics.*",)),
    )


def validate_no_shared_admin(policy: SecurityPolicy) -> None:
    """Reject a principal that can perform every critical action."""
    critical: set[AccessAction] = {
        "read_data",
        "train_model",
        "approve_policy",
        "publish_recommendations",
        "override_order",
        "audit_changes",
    }
    by_principal: dict[str, set[AccessAction]] = {}
    for grant in policy.role_grants:
        by_principal.setdefault(grant.principal, set()).update(grant.actions)
    offenders = sorted(principal for principal, actions in by_principal.items() if critical.issubset(actions))
    if offenders:
        raise SecurityPolicyError(f"shared all-powerful principals are not allowed: {offenders}")


def authorize_action(
    policy: SecurityPolicy,
    *,
    principal: str,
    action: AccessAction,
    environment: Environment,
    resource: str,
) -> None:
    """Validate least-privilege authorization for one action."""
    for grant in policy.role_grants:
        if grant.principal != principal or grant.environment != environment or action not in grant.actions:
            continue
        if any(_resource_matches(resource, pattern) for pattern in grant.resource_patterns):
            return
    raise SecurityPolicyError(f"{principal} cannot {action} on {resource} in {environment}")


def authorize_publication(
    policy: SecurityPolicy,
    *,
    publisher: str,
    approval: ArtifactApproval | None,
    artifact_id: str,
    artifact_hash: str,
    environment: Environment = "prod",
) -> None:
    """Require separated approval before production publication."""
    authorize_action(
        policy,
        principal=publisher,
        action="publish_recommendations",
        environment=environment,
        resource=f"{environment}.publication.{artifact_id}",
    )
    if approval is None:
        raise SecurityPolicyError("production publication requires an approval record")
    if approval.environment != environment or approval.artifact_id != artifact_id or approval.artifact_hash != artifact_hash:
        raise SecurityPolicyError("approval record does not match artifact")
    if approval.approved_by == publisher:
        raise SecurityPolicyError("publisher cannot approve the same artifact")


def validate_environment_isolation(resource: str, environment: Environment) -> None:
    """Ensure resource identifiers are scoped to the requested environment."""
    if not resource.startswith(f"{environment}."):
        raise SecurityPolicyError("resource is not scoped to the requested environment")


def validate_dynamic_identifier(identifier: str) -> str:
    """Allow only safe warehouse identifiers used in generated SQL."""
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*(\.[A-Za-z_][A-Za-z0-9_]*){0,2}", identifier):
        raise SecurityPolicyError("unsafe dynamic identifier")
    return identifier


def validate_no_key_files(paths: tuple[Path, ...], policy: SecurityPolicy | None = None) -> None:
    """Reject committed service keys and private-key-like files."""
    active_policy = policy or SecurityPolicy(default_role_grants())
    offenders = [
        str(path)
        for path in paths
        if path.suffix.lower() in active_policy.allowed_key_suffixes and _looks_like_key_file(path)
    ]
    if offenders:
        raise SecurityPolicyError(f"key files are not allowed: {offenders}")


def scan_text_for_secrets(text: str) -> tuple[str, ...]:
    """Return secret-pattern names found in text."""
    matches: list[str] = []
    for index, pattern in enumerate(SECRET_TEXT_PATTERNS):
        if pattern.search(text):
            matches.append(f"secret_pattern_{index}")
    return tuple(matches)


def redact_log_payload(payload: dict[str, object]) -> dict[str, object]:
    """Redact sensitive fields before logs are emitted."""
    redacted: dict[str, object] = {}
    for key, value in payload.items():
        if any(pattern.fullmatch(key) for pattern in SENSITIVE_FIELD_PATTERNS):
            redacted[key] = "<redacted>"
        elif isinstance(value, dict):
            redacted[key] = redact_log_payload(value)
        else:
            redacted[key] = value
    return redacted


def audit_event_hash(event: AuditEvent) -> str:
    """Return a stable audit-event hash for tamper-evident logs."""
    payload = asdict(event)
    payload["metadata"] = redact_log_payload(event.metadata)
    return hashlib.sha256(json.dumps(payload, sort_keys=True, default=str).encode()).hexdigest()


def artifact_provenance_hash(
    *,
    artifact_hash: str,
    config_hash: str,
    data_manifest_hash: str,
    code_revision: str,
) -> str:
    """Bind artifact provenance to config, data, and source revision."""
    payload = {
        "artifact_hash": artifact_hash,
        "config_hash": config_hash,
        "data_manifest_hash": data_manifest_hash,
        "code_revision": code_revision,
    }
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()


def _resource_matches(resource: str, pattern: str) -> bool:
    if pattern.endswith(".*"):
        return resource.startswith(pattern[:-1])
    return resource == pattern


def _looks_like_key_file(path: Path) -> bool:
    name = path.name.lower()
    if any(token in name for token in ("service-account", "credential", "private", "secret")):
        return True
    if not path.exists() or not path.is_file():
        return False
    try:
        sample = path.read_text(encoding="utf-8", errors="ignore")[:4096]
    except OSError:
        return False
    return bool(scan_text_for_secrets(sample))
