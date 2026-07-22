from __future__ import annotations

from pathlib import Path

import pytest

from perishable_lab.security import (
    ArtifactApproval,
    AuditEvent,
    RoleGrant,
    SecurityPolicy,
    SecurityPolicyError,
    artifact_provenance_hash,
    audit_event_hash,
    authorize_action,
    authorize_publication,
    default_data_assets,
    default_role_grants,
    redact_log_payload,
    scan_text_for_secrets,
    validate_dynamic_identifier,
    validate_environment_isolation,
    validate_no_key_files,
    validate_no_shared_admin,
)


def _policy() -> SecurityPolicy:
    return SecurityPolicy(default_role_grants())


def _approval() -> ArtifactApproval:
    return ArtifactApproval(
        artifact_id="batch-20260105",
        artifact_hash="abc123",
        environment="prod",
        approved_by="group-policy-review",
        approver_role="policy_approver",
        ticket_id="SEC-1",
        created_at_utc="2026-01-05T06:00:00Z",
    )


def test_default_assets_have_classification_retention_and_encryption() -> None:
    assets = {asset.name: asset for asset in default_data_assets()}

    assert assets["transactions"].classification == "confidential"
    assert assets["staff_overrides"].contains_sensitive_rows
    assert all(asset.retention_days > 0 for asset in assets.values())
    assert all(asset.encryption_required for asset in assets.values())


def test_no_shared_all_powerful_principal_is_allowed() -> None:
    validate_no_shared_admin(_policy())
    bad_policy = SecurityPolicy(
        (
            RoleGrant(
                "svc-admin-prod",
                "prod",
                ("read_data", "train_model"),
                ("prod.features.*",),
            ),
            RoleGrant(
                "svc-admin-prod",
                "prod",
                ("approve_policy", "override_order", "audit_changes"),
                ("prod.review.*",),
            ),
            RoleGrant(
                "svc-admin-prod",
                "prod",
                ("publish_recommendations",),
                ("prod.publication.*",),
            ),
        )
    )

    with pytest.raises(SecurityPolicyError, match="all-powerful"):
        validate_no_shared_admin(bad_policy)


def test_authorization_rejects_unauthorised_publication() -> None:
    with pytest.raises(SecurityPolicyError):
        authorize_action(
            _policy(),
            principal="svc-score-prod",
            action="publish_recommendations",
            environment="prod",
            resource="prod.publication.batch-20260105",
        )


def test_publication_requires_matching_separate_approval() -> None:
    authorize_publication(
        _policy(),
        publisher="svc-publish-prod",
        approval=_approval(),
        artifact_id="batch-20260105",
        artifact_hash="abc123",
    )

    with pytest.raises(SecurityPolicyError, match="approval"):
        authorize_publication(
            _policy(),
            publisher="svc-publish-prod",
            approval=None,
            artifact_id="batch-20260105",
            artifact_hash="abc123",
        )


def test_environment_isolation_and_identifier_validation() -> None:
    validate_environment_isolation("prod.publication.batch", "prod")
    assert validate_dynamic_identifier("project.dataset.table") == "project.dataset.table"

    with pytest.raises(SecurityPolicyError, match="environment"):
        validate_environment_isolation("dev.publication.batch", "prod")
    with pytest.raises(SecurityPolicyError, match="identifier"):
        validate_dynamic_identifier("dataset.table;drop table x")


def test_key_files_and_secret_text_are_rejected(tmp_path: Path) -> None:
    key_path = tmp_path / "service-account.json"
    key_path.write_text('{"private_key": "-----BEGIN PRIVATE KEY-----\\nabc"}', encoding="utf-8")

    with pytest.raises(SecurityPolicyError, match="key files"):
        validate_no_key_files((key_path,))

    assert scan_text_for_secrets("api_key = 'abcdefghijklmnopqrstuvwxyz'") == ("secret_pattern_2",)


def test_logs_are_redacted_and_hashes_are_stable() -> None:
    payload = {
        "store_id": "s1",
        "customer_token": "sensitive",
        "nested": {"staff_name": "reviewer", "quantity": 4},
    }
    redacted = redact_log_payload(payload)
    event = AuditEvent(
        event_type="override",
        actor="group-store-review",
        environment="prod",
        resource="prod.store_orders.s1",
        action="override_order",
        timestamp_utc="2026-01-05T06:00:00Z",
        metadata=payload,
    )

    assert redacted["customer_token"] == "<redacted>"
    assert redacted["nested"] == {"staff_name": "<redacted>", "quantity": 4}
    assert audit_event_hash(event) == audit_event_hash(event)


def test_artifact_provenance_changes_when_inputs_change() -> None:
    first = artifact_provenance_hash(
        artifact_hash="artifact-a",
        config_hash="config-a",
        data_manifest_hash="data-a",
        code_revision="rev-a",
    )
    second = artifact_provenance_hash(
        artifact_hash="artifact-b",
        config_hash="config-a",
        data_manifest_hash="data-a",
        code_revision="rev-a",
    )

    assert first != second
