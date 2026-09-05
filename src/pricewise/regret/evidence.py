"""Resolve claims to individual tool-returned web sources."""

import re
from collections.abc import Sequence
from decimal import Decimal
from typing import Final

from langchain_core.messages import AnyMessage, ToolMessage

from pricewise.regret.models import Candidate, Source

SOURCE_TOOLS: Final = frozenset(
    {
        "search_product",
        "compare_prices",
        "get_reviews",
        "scrape_url",
        "check_availability",
        "delegate_research",
    }
)


def collect_sources(messages: Sequence[AnyMessage]) -> list[Source]:
    """Keep evidence tied to its own URL, never to a neighboring result."""
    sources: dict[str, Source] = {}
    for message in messages:
        if not isinstance(message, ToolMessage) or message.name not in SOURCE_TOOLS:
            continue
        content = message.text
        for match in re.finditer(
            r"(?:^|\n\n)\d+\. (.*?)\n\s+(?:URL|Source): (https?://\S+)",
            content,
            re.DOTALL,
        ):
            text, url = match.groups()
            sources[url] = Source(url=url, text=text)
        extracted = re.fullmatch(
            r"Content from (https?://\S+):\n\n(.*)", content, re.DOTALL
        )
        if extracted:
            url, text = extracted.groups()
            sources[url] = Source(url=url, text=text)
    return list(sources.values())


def price_is_grounded(candidate: Candidate, source: Source) -> bool:
    """Verify price digits and explicit currency in the same quoted source."""
    if candidate.price is None or not candidate.price_quote or not candidate.currency:
        return False
    if candidate.price_quote not in source.text:
        return False
    symbols = {"USD": "US$", "SGD": "S$", "EUR": "€", "GBP": "£"}
    markers = [candidate.currency]
    if candidate.currency in symbols:
        markers.append(symbols[candidate.currency])
    marker = (
        r"(?<![A-Za-z])(?:"
        + "|".join(re.escape(item) for item in markers)
        + r")(?![A-Za-z])"
    )
    amount = r"(\d[\d,]*(?:\.\d{1,2})?)(?![\d.])"
    patterns = [rf"{marker}\s*{amount}", rf"{amount}\s*{marker}"]
    return any(
        Decimal(found.replace(",", "")) == candidate.price
        for pattern in patterns
        for found in re.findall(pattern, candidate.price_quote)
    )
