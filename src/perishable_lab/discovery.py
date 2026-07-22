"""Store operations discovery records and evidence gates."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

Audience = Literal["store_staff", "customer_success", "buyer", "engineering"]
EvidenceStatus = Literal["untested", "observed_once", "observed_repeatedly", "measured", "validated"]
HypothesisPriority = Literal["high", "medium", "low"]


class DiscoveryValidationError(ValueError):
    """Raised when discovery outputs are not tied to operational evidence."""


@dataclass(frozen=True)
class InterviewQuestion:
    """Concrete question for an operations discovery session."""

    audience: Audience
    workflow_area: str
    question: str
    captures: tuple[str, ...]


@dataclass(frozen=True)
class ObservationTemplate:
    """Store-visit observation record for one workflow."""

    workflow: str
    actor: str
    decision: str
    information_visible: tuple[str, ...]
    current_tool_or_workaround: str
    frequency: str
    operational_cost: str
    exceptions: tuple[str, ...]
    data_generated: tuple[str, ...]
    data_missing: tuple[str, ...]
    explanation_needed: tuple[str, ...]


@dataclass(frozen=True)
class OverrideReason:
    """Standard reason code for store-reviewed order changes."""

    code: str
    label: str
    category: str
    data_signal: str
    blame_safe_description: str


@dataclass(frozen=True)
class AssumptionEvidence:
    """Link an operating assumption to observed or measured evidence."""

    assumption_id: str
    assumption: str
    workflow_problem: str
    evidence_status: EvidenceStatus
    evidence_reference: str
    owner: str


@dataclass(frozen=True)
class ProductDataHypothesis:
    """Candidate product or data change tied to store operations."""

    hypothesis_id: str
    priority: HypothesisPriority
    workflow_problem: str
    proposed_change: str
    measurable_outcome: str
    required_data: tuple[str, ...]
    validation_method: str
    linked_assumptions: tuple[str, ...]
    acceptance_criteria: tuple[str, ...]


def default_interview_guide() -> tuple[InterviewQuestion, ...]:
    """Return concrete discovery questions by audience."""
    captures = (
        "actor and decision",
        "information visible at the time",
        "current tool or workaround",
        "frequency and operational cost",
        "exceptions and edge cases",
        "data generated or missing",
        "explanation needed",
    )
    return (
        InterviewQuestion("store_staff", "order_cutoff", "What happens in the final hour before orders are locked?", captures),
        InterviewQuestion("store_staff", "back_room_stock", "Where can stock exist outside the shelf count, and when is it checked?", captures),
        InterviewQuestion("store_staff", "waste_recording", "Which wasted items are recorded immediately, later, or not at all?", captures),
        InterviewQuestion("store_staff", "staff_overrides", "When do you change a suggested quantity, and what would make that change easy to explain?", captures),
        InterviewQuestion("customer_success", "failure_escalation", "Which store issues create support tickets, and how are repeated issues grouped?", captures),
        InterviewQuestion("customer_success", "system_trust", "What signs make a store stop trusting recommendations for a category?", captures),
        InterviewQuestion("buyer", "promotions", "Which promotion, display, or local event changes are known before the order cutoff?", captures),
        InterviewQuestion("buyer", "substitutions", "Which products substitute for each other when one item is unavailable?", captures),
        InterviewQuestion("engineering", "data_latency", "Which source tables can arrive late or be restated after recommendations are produced?", captures),
        InterviewQuestion("engineering", "case_packs", "Where are case-pack, storage, and supplier constraints maintained and versioned?", captures),
    )


def default_override_taxonomy() -> tuple[OverrideReason, ...]:
    """Return blame-safe override reason codes."""
    return (
        OverrideReason("back_room_stock", "Back-room stock not reflected", "inventory", "stock_count_gap", "The workflow hid available stock from the system."),
        OverrideReason("display_build", "Display or endcap build", "merchandising", "display_calendar", "The recommendation lacked local display context."),
        OverrideReason("local_event", "Local event demand", "demand", "local_event_calendar", "Local demand context was not represented in the data."),
        OverrideReason("supplier_constraint", "Supplier or delivery constraint", "supply", "supplier_exception", "Supply context changed after planning data was captured."),
        OverrideReason("case_pack_issue", "Case-pack or storage issue", "operations", "constraint_master", "The constraint data did not match physical handling."),
        OverrideReason("quality_issue", "Quality or shelf-life concern", "freshness", "quality_log", "Quality context changed the useful inventory quantity."),
        OverrideReason("substitution", "Expected substitution effect", "assortment", "substitution_group", "Assortment context affected expected demand."),
        OverrideReason("promotion_change", "Promotion changed", "commercial", "promotion_revision", "Commercial context changed after the feature snapshot."),
        OverrideReason("trust_review", "Needs review before use", "trust", "review_flag", "The workflow requires human confirmation for this case."),
    )


def validate_observation(observation: ObservationTemplate) -> None:
    """Ensure a workflow observation captures the required discovery fields."""
    missing: list[str] = []
    if not observation.actor:
        missing.append("actor")
    if not observation.decision:
        missing.append("decision")
    if not observation.information_visible:
        missing.append("information_visible")
    if not observation.current_tool_or_workaround:
        missing.append("current_tool_or_workaround")
    if not observation.frequency:
        missing.append("frequency")
    if not observation.operational_cost:
        missing.append("operational_cost")
    if not observation.explanation_needed:
        missing.append("explanation_needed")
    if missing:
        raise DiscoveryValidationError(f"Observation is missing fields: {missing}")


def validate_hypotheses(
    hypotheses: tuple[ProductDataHypothesis, ...],
    evidence: tuple[AssumptionEvidence, ...],
) -> None:
    """Require every proposed change to link to evidence, data, outcome, and validation."""
    evidence_by_id = {item.assumption_id: item for item in evidence}
    issues: list[str] = []
    for hypothesis in hypotheses:
        if not hypothesis.workflow_problem:
            issues.append(f"{hypothesis.hypothesis_id}:missing_workflow_problem")
        if not hypothesis.measurable_outcome:
            issues.append(f"{hypothesis.hypothesis_id}:missing_measurable_outcome")
        if not hypothesis.required_data:
            issues.append(f"{hypothesis.hypothesis_id}:missing_required_data")
        if not hypothesis.validation_method:
            issues.append(f"{hypothesis.hypothesis_id}:missing_validation_method")
        if not hypothesis.acceptance_criteria:
            issues.append(f"{hypothesis.hypothesis_id}:missing_acceptance_criteria")
        for assumption_id in hypothesis.linked_assumptions:
            if assumption_id not in evidence_by_id:
                issues.append(f"{hypothesis.hypothesis_id}:unknown_assumption:{assumption_id}")
                continue
            if evidence_by_id[assumption_id].evidence_status in {"untested", "observed_once"}:
                issues.append(f"{hypothesis.hypothesis_id}:weak_evidence:{assumption_id}")
    if issues:
        raise DiscoveryValidationError(", ".join(sorted(issues)))


def prioritise_hypotheses(hypotheses: tuple[ProductDataHypothesis, ...]) -> tuple[ProductDataHypothesis, ...]:
    """Return hypotheses sorted by priority and identifier."""
    rank = {"high": 0, "medium": 1, "low": 2}
    return tuple(sorted(hypotheses, key=lambda item: (rank[item.priority], item.hypothesis_id)))


def feedback_loop_steps() -> tuple[str, ...]:
    """Return the closed loop from operations finding to validated change."""
    return (
        "Capture workflow observation",
        "Map observation to assumption evidence",
        "Create product or data hypothesis",
        "Define required data and acceptance criteria",
        "Link to backlog item",
        "Validate through monitoring, fixture, pilot, or field test",
        "Review outcome with store operations and customer success",
        "Update card, runbook, or model monitor",
    )
