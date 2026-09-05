"""Unknown currency and attribute quotes cannot become verified evidence."""

import pytest

from pricewise.regret.models import CandidateBatch, Criterion, RegretProfile, Source
from pricewise.regret.ranking import rank_candidates


@pytest.mark.parametrize("outcome", ["unknown", "matched", "contradicted"])
def test_null_currency_and_assessment_quote_are_unknown(outcome):
    batch = CandidateBatch.model_validate(
        {
            "candidates": [
                {
                    "product_name": "Shoe",
                    "source_url": "https://shop.example/shoe",
                    "price": 90,
                    "currency": None,
                    "price_quote": "USD 90",
                    "assessments": [
                        {
                            "key": "logos",
                            "outcome": outcome,
                            "quote": None,
                        }
                    ],
                }
            ]
        }
    )
    profile = RegretProfile(
        criteria=[
            Criterion(
                key="logos",
                description="No logos",
                level="forbidden",
                source_quote="no logos",
            )
        ]
    )
    result = rank_candidates(
        profile,
        batch.candidates,
        [Source(url="https://shop.example/shoe", text="Shoe USD 90, no logos")],
    )
    assert not result.ranked
    assert result.excluded[0].candidate.price is None
    assert result.excluded[0].candidate.assessments[0].outcome == "unknown"
