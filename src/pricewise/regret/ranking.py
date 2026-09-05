"""Deterministic exclusion, priority scoring, and evidence-based tradeoffs."""

from itertools import combinations
from typing import assert_never

from pricewise.regret.evidence import price_is_grounded
from pricewise.regret.models import (
    Assessment,
    Candidate,
    Outcome,
    RankedCandidate,
    RankingResult,
    RegretProfile,
    Source,
)


def _ground(candidate: Candidate, source: Source) -> Candidate:
    """Downgrade unsupported claims instead of silently accepting them."""
    assessments = [
        item
        if item.quote and item.quote in source.text
        else Assessment(key=item.key, outcome="unknown")
        for item in candidate.assessments
    ]
    return candidate.model_copy(
        update={
            "price": candidate.price if price_is_grounded(candidate, source) else None,
            "assessments": assessments,
        }
    )


def _score(
    profile: RegretProfile, candidate: Candidate
) -> tuple[RankedCandidate, bool]:
    outcomes: dict[str, Outcome] = {
        item.key: item.outcome for item in candidate.assessments
    }
    reasons: list[str] = []
    warnings: list[str] = []
    score = 0.0
    excluded = False
    for item in profile.criteria:
        outcome: Outcome = outcomes.get(item.key, "unknown")
        match item.level:
            case "forbidden":
                if outcome != "matched":
                    excluded = True
                    warnings.append(f"{item.description}: {outcome} (hard exclusion)")
                else:
                    reasons.append(f"Required: {item.description}")
            case "important" | "negotiable":
                weight = 3.0 if item.level == "important" else 1.0
                match outcome:
                    case "matched":
                        score += weight
                        reasons.append(item.description)
                    case "contradicted":
                        score -= weight
                        warnings.append(f"Tradeoff: {item.description}")
                    case "unknown":
                        score -= weight / 2
                        warnings.append(f"Unverified: {item.description}")
                    case unreachable:
                        assert_never(unreachable)
            case unreachable:
                assert_never(unreachable)
    if profile.budget:
        budget = profile.budget
        known = candidate.price is not None and candidate.currency == budget.currency
        if not known:
            warnings.append("Budget compliance unverified (price or currency missing)")
            excluded |= budget.level == "forbidden"
        elif candidate.price is not None and candidate.price > budget.amount:
            warnings.append(f"Over budget: {budget.currency} {budget.amount}")
            excluded |= budget.level == "forbidden"
            score -= float((candidate.price - budget.amount) / budget.amount)
    if candidate.price is None:
        warnings.append("Price and currency have not been verified")
    return RankedCandidate(
        candidate=candidate, score=score, reasons=reasons, warnings=warnings
    ), excluded


def _tradeoff(profile: RegretProfile, ranked: list[RankedCandidate]) -> list[str]:
    """Ask only about a demonstrated two-way conflict among top candidates."""
    important = [item.key for item in profile.criteria if item.level == "important"]
    outcomes: list[dict[str, Outcome]] = [
        {item.key: item.outcome for item in result.candidate.assessments}
        for result in ranked[:5]
    ]
    if any(all(row.get(key) == "matched" for key in important) for row in outcomes):
        return []
    for left, right in combinations(important, 2):
        forward = any(
            row.get(left) == "matched" and row.get(right) == "contradicted"
            for row in outcomes
        )
        reverse = any(
            row.get(right) == "matched" and row.get(left) == "contradicted"
            for row in outcomes
        )
        if forward and reverse:
            return [left, right]
    return []


def rank_candidates(
    profile: RegretProfile,
    candidates: list[Candidate],
    sources: list[Source],
) -> RankingResult:
    """Return only source-grounded, eligible candidates in stable score order."""
    documents = {source.url: source for source in sources}
    ranked: list[RankedCandidate] = []
    excluded: list[RankedCandidate] = []
    seen: set[str] = set()
    for candidate in candidates:
        source = documents.get(candidate.source_url)
        if (
            source is None
            or candidate.product_name.casefold() not in source.text.casefold()
        ):
            excluded.append(
                RankedCandidate(
                    candidate=candidate,
                    score=0,
                    warnings=["Product identity is not grounded in its source"],
                )
            )
            continue
        if candidate.source_url in seen:
            continue
        seen.add(candidate.source_url)
        result, blocked = _score(profile, _ground(candidate, source))
        (excluded if blocked else ranked).append(result)
    ranked.sort(key=lambda item: item.score, reverse=True)
    conflict = _tradeoff(profile, ranked)
    return RankingResult(
        ranked=ranked,
        excluded=excluded,
        ask_attribute=conflict[0] if conflict else None,
        tradeoff=conflict,
    )
