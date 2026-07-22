from __future__ import annotations

import pytest

from perishable_lab.cards import (
    CardMetadata,
    CardValidationError,
    ClaimReference,
    MetricReference,
    manifest_consistency_report,
    release_card_gate,
    validate_card_metadata,
)


def _model_card() -> CardMetadata:
    return CardMetadata(
        card_type="model",
        card_version="model-card-v1",
        package_version="0.1.0",
        owner="forecasting",
        reviewed_at="2026-01-05",
        artifact_versions=("quantile_forecaster:0.1.0",),
        metrics=(
            MetricReference(
                name="empirical_coverage",
                artifact_path="reports/example_run/forecast_metrics.json",
                artifact_field="empirical_coverage",
            ),
        ),
        claims=(
            ClaimReference(
                claim="Forecast intervals are checked against held-out synthetic outcomes.",
                evidence_type="test",
                reference="tests/test_conformal.py",
            ),
            ClaimReference(
                claim="Synthetic evaluation does not establish real retailer impact.",
                evidence_type="assumption",
                reference="synthetic_results_are_not_field_impact",
            ),
        ),
        assumptions=("synthetic_results_are_not_field_impact",),
        interface_names=("ForecastDistribution", "QuantileForecaster"),
    )


def test_card_metadata_requires_metric_artifact_links() -> None:
    validate_card_metadata(_model_card())
    broken = CardMetadata(
        **{
            **_model_card().__dict__,
            "metrics": (MetricReference("coverage", "", "empirical_coverage"),),
        }
    )

    with pytest.raises(CardValidationError, match="metric_without_artifact"):
        validate_card_metadata(broken)


def test_assumption_claims_must_reference_registered_assumption() -> None:
    broken = CardMetadata(
        **{
            **_model_card().__dict__,
            "claims": (ClaimReference("Unsupported impact claim.", "assumption", "missing_assumption"),),
        }
    )

    with pytest.raises(CardValidationError, match="registered_assumption"):
        validate_card_metadata(broken)


def test_manifest_consistency_checks_versions_and_artifacts() -> None:
    manifest = {
        "package_version": "0.1.0",
        "model_version": "quantile_forecaster:0.1.0",
        "feature_columns": ["demand_lag_1"],
        "artifacts": ["forecast_metrics.json", "policy_metrics.csv"],
    }

    report = manifest_consistency_report(
        _model_card(),
        manifest,
        required_artifacts=("forecast_metrics.json", "policy_metrics.csv"),
    )

    assert report.status == "pass"
    assert report.issues == ()


def test_manifest_consistency_fails_on_missing_model_version() -> None:
    manifest = {
        "package_version": "0.1.0",
        "model_version": "other-model",
        "feature_columns": [],
        "artifacts": [],
    }

    report = manifest_consistency_report(_model_card(), manifest, required_artifacts=("forecast_metrics.json",))

    assert report.status == "fail"
    assert "model_version_missing_from_card" in report.issues
    assert "feature_columns_empty" in report.issues
    assert "missing_artifact:forecast_metrics.json" in report.issues


def test_release_gate_requires_changed_interfaces_to_have_card_coverage() -> None:
    report = release_card_gate((_model_card(),), changed_interfaces=("ForecastDistribution",))
    missing = release_card_gate((_model_card(),), changed_interfaces=("NewPublicationContract",))

    assert report.status == "pass"
    assert missing.status == "fail"
    assert missing.issues == ("changed_interface_without_card:NewPublicationContract",)
