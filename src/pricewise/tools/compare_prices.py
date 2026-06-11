import logging
import os

from langchain_core.tools import tool
from pricewise.schemas import PriceComparisonQuery
from pricewise.tools._client import get_tavily, parse_tavily_response, format_results
from pricewise.matching.matcher import MatcherUnavailable, get_matcher

logger = logging.getLogger(__name__)


def _filter_same_product(product_name: str, results: list) -> tuple[list, bool]:
    """Keep only listings the trained matcher scores as the same product.

    Returns (results, filtered_flag). Disabled (default), unavailable, or
    failing matchers all fall back to the unfiltered results — matching is
    an enhancement, never a point of failure.
    """
    if os.getenv("MATCHER_ENABLED", "").lower() != "true":
        return results, False

    threshold = float(os.getenv("MATCH_THRESHOLD", "0.5"))
    try:
        scores = get_matcher().score(
            product_name, [r.get("content", "") for r in results]
        )
    except MatcherUnavailable as exc:
        logger.warning("Product matcher unavailable: %s", exc)
        return results, False
    except Exception:
        logger.exception("Product matcher failed; returning unfiltered results")
        return results, False

    kept = []
    for result, score in zip(results, scores):
        if score >= threshold:
            annotated = dict(result)
            annotated["content"] = f"{result.get('content', '')} [match {score:.2f}]"
            kept.append(annotated)
    return kept, True


@tool(args_schema=PriceComparisonQuery)
def compare_prices(product_name: str, max_sources: int = 5) -> str:
    """Compare prices for a product across multiple online retailers."""
    response = get_tavily().invoke(f"{product_name} price buy")

    results, error = parse_tavily_response(response)
    if error:
        return error

    if not results:
        return "No price information found."

    results, filtered = _filter_same_product(product_name, results)
    if filtered and not results:
        return (
            f"No listings matched '{product_name}' closely enough to compare "
            "prices. The search results may be accessories or different models."
        )

    return format_results(results, max_sources)
