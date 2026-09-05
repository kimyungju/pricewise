"""Hard requirements have the same satisfaction semantics as soft ones."""

import pytest

from pricewise.regret.models import (
    Assessment,
    Candidate,
    Criterion,
    RegretProfile,
    Source,
)
from pricewise.regret.ranking import rank_candidates


@pytest.mark.parametrize(
    "outcome,quote,eligible",
    [
        ("matched", "No large logos", True),
        ("contradicted", "Large visible logos", False),
        ("unknown", "", False),
    ],
)
def test_forbidden_bucket_checks_user_requirement_satisfaction(
    outcome, quote, eligible
):
    # Given: the live planner expresses a prohibition as a desired condition.
    profile = RegretProfile(
        criteria=[
            Criterion(
                key="large logos",
                description="큰 로고 없는 디자인",
                level="forbidden",
                source_quote="큰 로고는 절대 싫어요.",
            )
        ]
    )
    source = Source(
        url="https://shop.example/shoe", text=f"Wedding Shoe USD 90. {quote}."
    )
    candidate = Candidate(
        product_name="Wedding Shoe",
        source_url=source.url,
        price=90,
        price_quote="USD 90",
        assessments=[Assessment(key="large logos", outcome=outcome, quote=quote)],
    )
    # When: deterministic ranking evaluates fulfillment of the user's request.
    result = rank_candidates(profile, [candidate], [source])
    # Then: no-logo shoes pass; logo violations and missing evidence do not.
    assert bool(result.ranked) is eligible
