"""Versioned product identity resolution with reproducible as-of lookup."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date, datetime
from typing import Literal

import pandas as pd


class ProductIdentityError(ValueError):
    """Raised when product identity mappings are invalid or ambiguous."""


MappingStatus = Literal["accepted", "rejected", "pending_review"]


@dataclass(frozen=True)
class RawProductRecord:
    """Raw product attributes available for deterministic matching."""

    raw_item_id: str
    sellable_sku_id: str
    supplier_id: str
    supplier_item_id: str
    category_id: str
    product_family_id: str
    unit_of_measure: str
    pack_size: float
    gtin: str | None = None
    effective_from: date | None = None
    effective_to: date | None = None


@dataclass(frozen=True)
class ProductIdentityMapping:
    """Slowly changing mapping from raw item IDs to stable demand entities."""

    raw_item_id: str
    sellable_sku_id: str
    canonical_product_id: str
    demand_entity_id: str
    product_family_id: str
    category_id: str
    supplier_id: str
    supplier_item_id: str
    unit_of_measure: str
    pack_size: float
    effective_from: date
    effective_to: date | None
    mapping_confidence: float
    mapping_status: MappingStatus
    rule_id: str
    known_at: datetime
    gtin: str | None = None
    replacement_for: str | None = None


@dataclass(frozen=True)
class MappingResolution:
    """Result of resolving one source product at a business-time cutoff."""

    raw_item_id: str
    canonical_product_id: str
    demand_entity_id: str
    mapping_confidence: float
    rule_id: str
    known_at: datetime


@dataclass(frozen=True)
class CandidateMatch:
    """Candidate match with reasons and review recommendation."""

    raw_item_id: str
    candidate_raw_item_id: str
    canonical_product_id: str
    demand_entity_id: str
    confidence: float
    reasons: tuple[str, ...]
    review_action: Literal["auto_accept", "needs_review", "reject"]
    ambiguous: bool = False


@dataclass(frozen=True)
class ReviewDecision:
    """Human decision for an identity candidate."""

    raw_item_id: str
    candidate_raw_item_id: str
    decision: Literal["accepted", "rejected"]
    decided_by: str
    decided_at: datetime
    reason: str


def _normalise_mappings(mappings: list[ProductIdentityMapping]) -> pd.DataFrame:
    frame = pd.DataFrame([asdict(mapping) for mapping in mappings])
    if frame.empty:
        raise ProductIdentityError("At least one product identity mapping is required")
    frame["effective_from"] = pd.to_datetime(frame["effective_from"]).dt.normalize()
    frame["effective_to"] = pd.to_datetime(frame["effective_to"]).dt.normalize()
    frame["known_at"] = pd.to_datetime(frame["known_at"], utc=True)
    frame["pack_size"] = pd.to_numeric(frame["pack_size"], errors="coerce")
    frame["mapping_confidence"] = pd.to_numeric(frame["mapping_confidence"], errors="coerce")
    if bool(frame["mapping_confidence"].lt(0.0).any()) or bool(frame["mapping_confidence"].gt(1.0).any()):
        raise ProductIdentityError("Mapping confidence must be between 0 and 1")
    return frame.sort_values(
        ["raw_item_id", "known_at", "effective_from", "canonical_product_id"],
        ignore_index=True,
    )


def _overlaps(left: pd.Series, right: pd.Series) -> bool:
    left_start = pd.Timestamp(left["effective_from"])
    right_start = pd.Timestamp(right["effective_from"])
    left_end = pd.Timestamp.max if pd.isna(left["effective_to"]) else pd.Timestamp(left["effective_to"])
    right_end = pd.Timestamp.max if pd.isna(right["effective_to"]) else pd.Timestamp(right["effective_to"])
    return left_start <= right_end and right_start <= left_end


def _validate_mappings(frame: pd.DataFrame) -> None:
    accepted = frame[frame["mapping_status"] == "accepted"]
    for raw_item_id, group in accepted.groupby("raw_item_id", sort=True):
        group_frame = pd.DataFrame(group).sort_values(["effective_from", "known_at"]).reset_index(drop=True)
        for left_index in range(len(group_frame)):
            for right_index in range(left_index + 1, len(group_frame)):
                left = group_frame.iloc[left_index]
                right = group_frame.iloc[right_index]
                if not _overlaps(left, right):
                    continue
                same_known_at = left["known_at"] == right["known_at"]
                different_target = (
                    left["demand_entity_id"] != right["demand_entity_id"]
                    or left["canonical_product_id"] != right["canonical_product_id"]
                )
                if same_known_at and different_target:
                    raise ProductIdentityError(
                        f"Overlapping accepted mappings for {raw_item_id} at the same known_at"
                    )


class ProductIdentityService:
    """Resolve stable demand entities using mappings known at a historical cutoff."""

    def __init__(self, mappings: list[ProductIdentityMapping]) -> None:
        self._frame = _normalise_mappings(mappings)
        _validate_mappings(self._frame)

    @property
    def mappings(self) -> pd.DataFrame:
        """Return a copy of the normalized mapping table."""
        return self._frame.copy(deep=True)

    def resolve(
        self,
        raw_item_id: str,
        *,
        business_date: date | str,
        known_at: datetime | str,
    ) -> MappingResolution:
        """Resolve one raw item using only mappings known at the requested cutoff."""
        business_ts = pd.Timestamp(business_date).normalize()
        known_ts = pd.Timestamp(known_at).tz_convert("UTC") if pd.Timestamp(known_at).tzinfo else pd.Timestamp(known_at).tz_localize("UTC")
        candidates = self._frame[
            (self._frame["raw_item_id"] == raw_item_id)
            & (self._frame["mapping_status"] == "accepted")
            & (self._frame["effective_from"] <= business_ts)
            & (self._frame["known_at"] <= known_ts)
            & (self._frame["effective_to"].isna() | (self._frame["effective_to"] >= business_ts))
        ]
        if candidates.empty:
            raise ProductIdentityError(f"No accepted mapping for {raw_item_id} as of {known_ts}")
        best = candidates.sort_values(["known_at", "effective_from"], ascending=[False, False]).iloc[0]
        return MappingResolution(
            raw_item_id=raw_item_id,
            canonical_product_id=str(best["canonical_product_id"]),
            demand_entity_id=str(best["demand_entity_id"]),
            mapping_confidence=float(best["mapping_confidence"]),
            rule_id=str(best["rule_id"]),
            known_at=best["known_at"].to_pydatetime(),
        )

    def resolve_frame(
        self,
        frame: pd.DataFrame,
        *,
        raw_item_column: str = "source_product_id",
        business_date_column: str = "business_date",
        known_at_column: str = "known_at",
    ) -> pd.DataFrame:
        """Add canonical identity columns and lineage to a source frame."""
        resolved = frame.copy(deep=True)
        records: list[dict[str, object]] = []
        for _, row in resolved.iterrows():
            mapping = self.resolve(
                str(row[raw_item_column]),
                business_date=row[business_date_column],
                known_at=row[known_at_column],
            )
            records.append(asdict(mapping))
        mapping_frame = pd.DataFrame(records).add_prefix("identity_")
        return pd.concat([resolved.reset_index(drop=True), mapping_frame], axis=1)


def _candidate_score(source: RawProductRecord, candidate: ProductIdentityMapping) -> tuple[float, tuple[str, ...]]:
    score = 0.0
    reasons: list[str] = []
    if source.gtin and candidate.gtin and source.gtin == candidate.gtin:
        score += 0.55
        reasons.append("gtin")
    if (
        source.supplier_id == candidate.supplier_id
        and source.supplier_item_id == candidate.supplier_item_id
    ):
        score += 0.20
        reasons.append("supplier_item")
    if source.unit_of_measure == candidate.unit_of_measure:
        score += 0.10
        reasons.append("unit")
    pack_size_matches = abs(float(source.pack_size) - float(candidate.pack_size)) <= 1e-9
    if pack_size_matches:
        score += 0.10
        reasons.append("pack_size")
    if source.product_family_id == candidate.product_family_id:
        score += 0.10
        reasons.append("product_family")
    elif source.category_id == candidate.category_id:
        score += 0.05
        reasons.append("category")
    if not pack_size_matches:
        score = min(score, 0.89)
    return min(score, 1.0), tuple(reasons)


def rank_identity_candidates(
    source: RawProductRecord,
    mappings: list[ProductIdentityMapping],
    *,
    auto_accept_threshold: float = 0.90,
    review_threshold: float = 0.50,
) -> list[CandidateMatch]:
    """Rank candidate mappings deterministically without auto-merging weak matches."""
    matches: list[CandidateMatch] = []
    accepted = [mapping for mapping in mappings if mapping.mapping_status == "accepted"]
    for mapping in accepted:
        confidence, reasons = _candidate_score(source, mapping)
        if confidence >= auto_accept_threshold and "category" not in reasons:
            action: Literal["auto_accept", "needs_review", "reject"] = "auto_accept"
        elif confidence >= review_threshold:
            action = "needs_review"
        else:
            action = "reject"
        matches.append(
            CandidateMatch(
                raw_item_id=source.raw_item_id,
                candidate_raw_item_id=mapping.raw_item_id,
                canonical_product_id=mapping.canonical_product_id,
                demand_entity_id=mapping.demand_entity_id,
                confidence=round(confidence, 4),
                reasons=reasons,
                review_action=action,
            )
        )

    matches = sorted(
        matches,
        key=lambda item: (-item.confidence, item.canonical_product_id, item.candidate_raw_item_id),
    )
    if matches:
        top_score = matches[0].confidence
        ambiguous = sum(match.confidence == top_score for match in matches) > 1
        matches = [
            CandidateMatch(
                raw_item_id=match.raw_item_id,
                candidate_raw_item_id=match.candidate_raw_item_id,
                canonical_product_id=match.canonical_product_id,
                demand_entity_id=match.demand_entity_id,
                confidence=match.confidence,
                reasons=match.reasons,
                review_action="needs_review" if ambiguous and match.confidence >= review_threshold else match.review_action,
                ambiguous=ambiguous and match.confidence == top_score,
            )
            for match in matches
        ]
    return matches


def build_review_queue(candidates: list[CandidateMatch]) -> pd.DataFrame:
    """Return candidate matches that require human review."""
    rows = [
        {
            **asdict(candidate),
            "reasons": "|".join(candidate.reasons),
        }
        for candidate in candidates
        if candidate.review_action == "needs_review"
    ]
    return pd.DataFrame(rows).sort_values(
        ["raw_item_id", "confidence", "candidate_raw_item_id"],
        ascending=[True, False, True],
        ignore_index=True,
    )


def review_history_frame(decisions: list[ReviewDecision]) -> pd.DataFrame:
    """Return accepted/rejected decision history in deterministic order."""
    if not decisions:
        return pd.DataFrame(
            columns=["raw_item_id", "candidate_raw_item_id", "decision", "decided_by", "decided_at", "reason"]
        )
    frame = pd.DataFrame([asdict(decision) for decision in decisions])
    frame["decided_at"] = pd.to_datetime(frame["decided_at"], utc=True)
    return frame.sort_values(["raw_item_id", "candidate_raw_item_id", "decided_at"], ignore_index=True)
