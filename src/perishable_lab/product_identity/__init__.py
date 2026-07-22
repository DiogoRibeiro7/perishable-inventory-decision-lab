"""Versioned product identity and mapping utilities."""

from perishable_lab.product_identity.resolution import (
    CandidateMatch,
    MappingResolution,
    ProductIdentityError,
    ProductIdentityMapping,
    ProductIdentityService,
    RawProductRecord,
    ReviewDecision,
    build_review_queue,
    rank_identity_candidates,
    review_history_frame,
)

__all__ = [
    "CandidateMatch",
    "MappingResolution",
    "ProductIdentityError",
    "ProductIdentityMapping",
    "ProductIdentityService",
    "RawProductRecord",
    "ReviewDecision",
    "build_review_queue",
    "rank_identity_candidates",
    "review_history_frame",
]
