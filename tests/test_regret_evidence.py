"""Evidence must belong to its product, currency, and source."""

from langchain_core.messages import ToolMessage
from pydantic import ValidationError
import pytest

from pricewise.regret.evidence import collect_sources, price_is_grounded
from pricewise.regret.models import Assessment, Candidate, Source


def test_sources_keep_quotes_separate_by_url():
    # Given: two listings are returned in a single tool message.
    messages = [
        ToolMessage(
            name="search_product",
            tool_call_id="one",
            content=(
                "1. Shoe A USD 80. No logo.\n   URL: https://shop.example/a\n\n"
                "2. Shoe B USD 90. Large logo.\n   URL: https://shop.example/b"
            ),
        )
    ]
    # When: evidence is collected.
    sources = collect_sources(messages)
    # Then: one product cannot borrow the other's claim.
    assert sources == [
        Source(url="https://shop.example/a", text="Shoe A USD 80. No logo."),
        Source(url="https://shop.example/b", text="Shoe B USD 90. Large logo."),
    ]


@pytest.mark.parametrize("quote", ["$90", "USD 9", "SGD 90", "XUSD 90"])
def test_price_requires_exact_amount_and_currency(quote: str):
    # Given: a claimed USD 90 price with insufficient or different evidence.
    source = Source(url="https://shop.example/a", text=f"Shoe {quote}")
    candidate = Candidate(
        product_name="Shoe", source_url=source.url, price=90, price_quote=quote
    )
    # When: the claim is grounded.
    result = price_is_grounded(candidate, source)
    # Then: no price is certified based on that quote.
    assert result is False


def test_duplicate_assessments_cannot_override_a_hard_violation():
    # Given: contradictory claims use the same preference key.
    assessments = [
        Assessment(key="logo", outcome="matched", quote="large logo"),
        Assessment(key="logo", outcome="contradicted", quote="no logo"),
    ]
    # When: model output is parsed at the boundary.
    # Then: the last claim cannot silently overwrite the first.
    with pytest.raises(ValidationError):
        Candidate(
            product_name="Shoe",
            source_url="https://shop.example/a",
            assessments=assessments,
        )
