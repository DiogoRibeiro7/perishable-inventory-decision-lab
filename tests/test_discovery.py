from __future__ import annotations

import pytest

from perishable_lab.discovery import (
    AssumptionEvidence,
    DiscoveryValidationError,
    ObservationTemplate,
    ProductDataHypothesis,
    default_interview_guide,
    default_override_taxonomy,
    feedback_loop_steps,
    prioritise_hypotheses,
    validate_hypotheses,
    validate_observation,
)


def _evidence(status: str = "measured") -> tuple[AssumptionEvidence, ...]:
    return (
        AssumptionEvidence(
            assumption_id="A-001",
            assumption="Back-room stock is often unavailable to the ordering workflow.",
            workflow_problem="Stock not visible at cutoff creates avoidable over-orders.",
            evidence_status=status,  # type: ignore[arg-type]
            evidence_reference="store-visit-2026-01-05",
            owner="operations",
        ),
    )


def _hypothesis(priority: str = "high") -> ProductDataHypothesis:
    return ProductDataHypothesis(
        hypothesis_id="H-001",
        priority=priority,  # type: ignore[arg-type]
        workflow_problem="Stock not visible at cutoff creates avoidable over-orders.",
        proposed_change="Add back-room stock visibility to the order review screen.",
        measurable_outcome="Reduce override rate for back_room_stock reason.",
        required_data=("stock_count_gap", "override_reason"),
        validation_method="Compare override rate before and after release in pilot stores.",
        linked_assumptions=("A-001",),
        acceptance_criteria=("back_room_stock override rate drops by 20 percent",),
    )


def test_interview_guide_covers_required_audiences_and_workflows() -> None:
    guide = default_interview_guide()

    assert {question.audience for question in guide} == {
        "store_staff",
        "customer_success",
        "buyer",
        "engineering",
    }
    assert {"order_cutoff", "promotions", "case_packs"}.issubset(
        {question.workflow_area for question in guide}
    )
    assert all("explanation needed" in question.captures for question in guide)


def test_override_taxonomy_is_blame_safe_and_data_linked() -> None:
    taxonomy = default_override_taxonomy()

    assert {reason.code for reason in taxonomy}.issuperset(
        {"back_room_stock", "promotion_change", "supplier_constraint"}
    )
    assert all(reason.data_signal for reason in taxonomy)
    assert all("workflow" in reason.blame_safe_description.lower() or "data" in reason.blame_safe_description.lower() or "context" in reason.blame_safe_description.lower() for reason in taxonomy)


def test_observation_template_requires_operational_context() -> None:
    observation = ObservationTemplate(
        workflow="order_review",
        actor="fresh manager",
        decision="increase order before cutoff",
        information_visible=("shelf count", "back-room count"),
        current_tool_or_workaround="spreadsheet note",
        frequency="daily",
        operational_cost="ten minutes per category",
        exceptions=("local event",),
        data_generated=("override reason",),
        data_missing=("verified back-room count timestamp",),
        explanation_needed=("why quantity changed", "which signal drove the recommendation"),
    )
    validate_observation(observation)

    with pytest.raises(DiscoveryValidationError, match="information_visible"):
        validate_observation(
            ObservationTemplate(
                workflow="order_review",
                actor="fresh manager",
                decision="increase order",
                information_visible=(),
                current_tool_or_workaround="spreadsheet",
                frequency="daily",
                operational_cost="ten minutes",
                exceptions=(),
                data_generated=(),
                data_missing=(),
                explanation_needed=("reason",),
            )
        )


def test_hypotheses_must_link_to_measured_or_repeated_evidence() -> None:
    validate_hypotheses((_hypothesis(),), _evidence("measured"))

    with pytest.raises(DiscoveryValidationError, match="weak_evidence"):
        validate_hypotheses((_hypothesis(),), _evidence("observed_once"))


def test_hypotheses_require_data_outcome_and_validation_method() -> None:
    broken = ProductDataHypothesis(
        hypothesis_id="H-002",
        priority="medium",
        workflow_problem="",
        proposed_change="Add a warning.",
        measurable_outcome="",
        required_data=(),
        validation_method="",
        linked_assumptions=("missing",),
        acceptance_criteria=(),
    )

    with pytest.raises(DiscoveryValidationError, match="missing_required_data"):
        validate_hypotheses((broken,), _evidence("measured"))


def test_prioritisation_and_feedback_loop_are_deterministic() -> None:
    low = _hypothesis("low")
    high = _hypothesis("high")
    medium = _hypothesis("medium")

    ordered = prioritise_hypotheses((low, medium, high))
    steps = feedback_loop_steps()

    assert [item.priority for item in ordered] == ["high", "medium", "low"]
    assert steps[0] == "Capture workflow observation"
    assert steps[-1] == "Update card, runbook, or model monitor"
