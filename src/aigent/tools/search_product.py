import os
from langchain_core.tools import tool
from langchain_tavily import TavilySearch
from aigent.schemas import ProductQuery

# Module-level Tavily client (lazy-initialized, overridable for testing)
_tavily = None


def _get_tavily():
    global _tavily
    if _tavily is None:
        _tavily = TavilySearch(max_results=5, topic="general")
    return _tavily


@tool(args_schema=ProductQuery)
def search_product(query: str, max_results: int = 3) -> str:
    """Search for a product online using Tavily and return formatted results."""
    response = _get_tavily().invoke(query)

    if "error" in response:
        return f"Search error: {response['error']}"

    results = response.get("results", [])
    if not results:
        return "No products found for this query."

    formatted = []
    for i, r in enumerate(results[:max_results], 1):
        url = r.get("url", "N/A")
        content = r.get("content", "No description")
        formatted.append(f"{i}. {content}\n   URL: {url}")

    return "\n\n".join(formatted)
