"""Reject invalid tool arguments before arithmetic or thread-pool work."""

import pytest
from pydantic import ValidationError

from pricewise.schemas import (
    ProductQuery,
    PriceComparisonQuery,
    ReviewQuery,
    CouponQuery,
    AvailabilityQuery,
)
from pricewise.tools.calculate_budget import calculate_budget
from pricewise.tools.delegate_research import delegate_research


def test_empty_delegation_is_a_validation_error_not_a_thread_pool_crash():
    with pytest.raises(ValidationError):
        delegate_research.invoke({"products": []})


@pytest.mark.parametrize("price", [-1, float("nan"), float("inf")])
def test_budget_tool_rejects_invalid_prices(price):
    with pytest.raises(ValidationError):
        calculate_budget.invoke({"items": [{"name": "Shoe", "price": price}]})


@pytest.mark.parametrize(
    "schema,args",
    [
        (ProductQuery, {"query": "shoes", "max_results": 0}),
        (PriceComparisonQuery, {"product_name": "shoes", "max_sources": -1}),
        (ReviewQuery, {"product_name": "shoes", "max_reviews": 0}),
        (CouponQuery, {"product_or_retailer": "shoes", "max_results": -1}),
        (AvailabilityQuery, {"product_name": "shoes", "max_sources": 0}),
    ],
)
def test_result_counts_must_be_positive(schema, args):
    with pytest.raises(ValidationError):
        schema.model_validate(args)
