"""Reviewer-labelled correlation candidates and honest metrics."""

from __future__ import annotations

import uuid
from collections import Counter, defaultdict
from datetime import datetime, timezone

from sqlalchemy import exists, select
from sqlalchemy.orm import Session

from app.auth.dependencies import AuthenticatedUser
from app.governance.errors import GovernanceError
from app.models.enums import CorrelationDecision, Role
from app.models.incident import Incident
from app.models.pilot import CorrelationCandidate, CorrelationReview
from app.models.profile import Profile


def _now() -> datetime:
    return datetime.now(timezone.utc)


def get_candidate(session: Session, candidate_id: uuid.UUID) -> CorrelationCandidate:
    candidate = session.get(CorrelationCandidate, candidate_id)
    if candidate is None:
        raise GovernanceError(
            "Correlation candidate not found",
            status_code=404,
            code="candidate_not_found",
        )
    return candidate


def create_candidate(
    session: Session,
    source_id: uuid.UUID,
    target_id: uuid.UUID,
    similarity_score: float,
    method: str,
    method_version: str,
    universe_key: str,
    reference_complete: bool,
    reference_size: int | None,
    reference_note: str | None,
    synthetic_fixture: bool,
    generated_at: datetime | None,
    actor: AuthenticatedUser,
) -> CorrelationCandidate:
    if source_id == target_id:
        raise GovernanceError(
            "A candidate requires two distinct incidents", code="invalid_candidate_pair"
        )
    for incident_id in (source_id, target_id):
        if session.get(Incident, incident_id) is None:
            raise GovernanceError(
                "Incident not found",
                status_code=404,
                code="incident_not_found",
            )
    existing = session.scalar(
        select(CorrelationCandidate.id).where(
            CorrelationCandidate.source_incident_id == source_id,
            CorrelationCandidate.target_incident_id == target_id,
            CorrelationCandidate.method_version == method_version,
        )
    )
    if existing is not None:
        raise GovernanceError(
            "This incident pair is already registered for this method version",
            status_code=409,
            code="candidate_exists",
        )
    generated = generated_at or _now()
    if generated.tzinfo is None:
        generated = generated.replace(tzinfo=timezone.utc)
    if generated > _now():
        raise GovernanceError(
            "generated_at cannot be in the future", code="invalid_generated_at"
        )
    if reference_complete and reference_size is None:
        raise GovernanceError(
            "reference_universe_size is required for a complete reference universe",
            code="reference_size_required",
        )
    if reference_complete and not (reference_note and reference_note.strip()):
        raise GovernanceError(
            "reference_note is required for a complete reference universe",
            code="reference_note_required",
        )
    candidate = CorrelationCandidate(
        candidate_key=f"cc-{uuid.uuid4().hex[:16]}",
        source_incident_id=source_id,
        target_incident_id=target_id,
        similarity_score=similarity_score,
        method=method,
        method_version=method_version,
        universe_key=universe_key,
        universe_reference_complete=reference_complete,
        reference_universe_size=reference_size,
        reference_note=reference_note,
        synthetic_fixture=synthetic_fixture,
        generated_at=generated,
        created_by=actor.profile.id,
    )
    session.add(candidate)
    session.commit()
    return candidate


def review_candidate(
    session: Session,
    candidate: CorrelationCandidate,
    decision: CorrelationDecision,
    note: str | None,
    explanation: str | None,
    actor: AuthenticatedUser,
) -> CorrelationReview:
    profile = session.get(Profile, actor.profile.id)
    if profile is None or profile.role not in {Role.WORKER, Role.ADMIN}:
        raise GovernanceError(
            "Only staff reviewers may label candidates",
            status_code=403,
            code="reviewer_required",
        )
    existing = session.scalar(
        select(CorrelationReview.id).where(
            CorrelationReview.candidate_id == candidate.id,
            CorrelationReview.reviewer_id == actor.profile.id,
        )
    )
    if existing is not None:
        raise GovernanceError(
            "This reviewer already labelled the candidate; labels are immutable",
            status_code=409,
            code="review_already_recorded",
        )
    review = CorrelationReview(
        candidate_id=candidate.id,
        reviewer_id=actor.profile.id,
        reviewer_email=actor.email,
        decision=decision,
        note=note.strip() if note else None,
        explanation=explanation.strip() if explanation else None,
    )
    session.add(review)
    session.commit()
    return review


def reviews_by_candidate(
    session: Session, candidate_ids: list[uuid.UUID]
) -> dict[uuid.UUID, list[CorrelationReview]]:
    grouped: dict[uuid.UUID, list[CorrelationReview]] = defaultdict(list)
    if not candidate_ids:
        return grouped
    rows = session.scalars(
        select(CorrelationReview)
        .where(CorrelationReview.candidate_id.in_(candidate_ids))
        .order_by(CorrelationReview.created_at)
    ).all()
    for row in rows:
        grouped[row.candidate_id].append(row)
    return grouped


def _majority(reviews: list[CorrelationReview]) -> tuple[str | None, bool]:
    if not reviews:
        return None, False
    counts = Counter(review.decision.value for review in reviews)
    top = counts.most_common()
    if len(top) > 1 and top[0][1] == top[1][1]:
        return CorrelationDecision.INSUFFICIENT_EVIDENCE.value, True
    if top[0][0] == CorrelationDecision.INSUFFICIENT_EVIDENCE.value:
        return None, False
    return top[0][0], False


def metrics_for_universe(session: Session, universe_key: str) -> dict:
    candidates = session.scalars(
        select(CorrelationCandidate)
        .where(CorrelationCandidate.universe_key == universe_key)
        .order_by(CorrelationCandidate.created_at)
    ).all()
    grouped = reviews_by_candidate(session, [item.id for item in candidates])
    true_positive = 0
    false_positive = 0
    abstained = 0
    unreviewed = 0
    contested = 0
    labelled = 0
    pair_total = 0
    pair_agree = 0
    by_reviewer: Counter[str] = Counter()
    for candidate in candidates:
        reviews = grouped.get(candidate.id, [])
        for review in reviews:
            by_reviewer[review.reviewer_email or str(review.reviewer_id)] += 1
        if not reviews:
            unreviewed += 1
            continue
        label, tie = _majority(reviews)
        if tie:
            contested += 1
        if label is None:
            abstained += 1
            continue
        if label == CorrelationDecision.DUPLICATE.value:
            true_positive += 1
        elif label == CorrelationDecision.NOT_DUPLICATE.value:
            false_positive += 1
        else:
            abstained += 1
            continue
        labelled += 1
        decisions = [review.decision for review in reviews]
        for index, first in enumerate(decisions):
            for second in decisions[index + 1 :]:
                pair_total += 1
                if first == second:
                    pair_agree += 1
    precision = None
    if true_positive + false_positive > 0:
        precision = round(true_positive / (true_positive + false_positive), 6)
    sizes = {
        item.reference_universe_size
        for item in candidates
        if item.reference_universe_size is not None
    }
    reference_size_value = sizes.pop() if len(sizes) == 1 else None
    complete = bool(candidates) and all(
        item.universe_reference_complete for item in candidates
    )
    recall = None
    recall_reason = (
        "Recall is not computed because the candidate universe is not attested "
        "as a complete reference set with an external true-duplicate count."
    )
    false_negative = None
    true_negative = None
    if (
        complete
        and reference_size_value is not None
        and unreviewed == 0
        and abstained == 0
    ):
        reference_size = reference_size_value
        if reference_size >= true_positive:
            false_negative = reference_size - true_positive
            recall = (
                round(true_positive / reference_size, 6) if reference_size else None
            )
            recall_reason = (
                "Recall uses the reviewer-attested complete reference universe "
                f"of {reference_size} true duplicate pairs. True negatives remain "
                "unknown because no exhaustive negative sample exists."
            )
    f1 = None
    if precision is not None and recall is not None and precision + recall > 0:
        f1 = round(2 * precision * recall / (precision + recall), 6)
    agreement = round(pair_agree / pair_total, 6) if pair_total else None
    provenance_flags = {item.synthetic_fixture for item in candidates}
    if not provenance_flags or None in provenance_flags:
        is_simulated: bool | None = None
        synthetic_provenance = "UNKNOWN"
    elif provenance_flags == {True}:
        is_simulated = True
        synthetic_provenance = "SYNTHETIC"
    elif provenance_flags == {False}:
        is_simulated = False
        synthetic_provenance = "OPERATIONAL"
    else:
        is_simulated = None
        synthetic_provenance = "MIXED"
    return {
        "protocol": "phase10-correlation-metrics-v1",
        "universe_key": universe_key,
        "generated_at": _now().isoformat(),
        "evidence_kind": "HUMAN_REVIEWED_GENERATED_CANDIDATES",
        "candidates": len(candidates),
        "reviewed_candidates": len(candidates) - unreviewed,
        "unreviewed_candidates": unreviewed,
        "labelled_candidates": labelled,
        "abstained_candidates": abstained,
        "contested_candidates": contested,
        "decision_counts": {
            "duplicate": true_positive,
            "not_duplicate": false_positive,
            "insufficient_evidence": abstained,
        },
        "metrics": {
            "precision": precision,
            "recall": recall,
            "f1": f1,
        },
        "confusion_matrix": {
            "true_positive": true_positive,
            "false_positive": false_positive,
            "false_negative": false_negative,
            "true_negative": true_negative,
        },
        "reviewer_agreement": {
            "pairwise_agreement": agreement,
            "compared_reviewer_pairs": pair_total,
            "reviewers": dict(by_reviewer),
            "distinct_reviewers": len(by_reviewer),
            "multi_review_candidates": sum(
                1 for reviews in grouped.values() if len(reviews) >= 2
            ),
        },
        "reference": {
            "complete": complete,
            "reference_universe_size": reference_size_value,
            "recall_reason": recall_reason,
        },
        "limitations": [
            "Precision is measured only over generated candidate pairs that humans reviewed.",
            "Recall is null unless a complete external reference universe is attested.",
            "True negatives are unknown; no exhaustive negative sample was labelled.",
            "Synthetic fixtures are never reported as empirical performance.",
            "Synthetic provenance is declared per candidate; unknown or mixed universes are not treated as operational.",
            "Reviewer labels are human judgments about this sample, not confirmed ground truth.",
        ],
        "is_simulated": is_simulated,
        "synthetic_provenance": synthetic_provenance,
        "is_validated_ground_truth": False,
    }


def candidates_payload(
    session: Session,
    candidates: list[CorrelationCandidate],
    incidents: dict[uuid.UUID, Incident],
    reviews: dict[uuid.UUID, list[CorrelationReview]],
) -> list[dict]:
    from app.governance.serialization import serialize_correlation_candidate

    return [
        serialize_correlation_candidate(
            candidate,
            source=incidents.get(candidate.source_incident_id),
            target=incidents.get(candidate.target_incident_id),
            reviews=reviews.get(candidate.id, []),
        )
        for candidate in candidates
    ]


def review_filter(reviewed: bool):  # type: ignore[no-untyped-def]
    exists_clause = exists().where(
        CorrelationReview.candidate_id == CorrelationCandidate.id
    )
    return exists_clause if reviewed else ~exists_clause
