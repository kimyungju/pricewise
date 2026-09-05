"""Wire Pricewise's Planner/Executor graph to approved shopping tools."""
from langchain.chat_models import init_chat_model
from langgraph.checkpoint.memory import InMemorySaver

from pricewise.regret.graph import create_regret_agent
from pricewise.tools import (
    search_product,
    compare_prices,
    get_reviews,
    calculate_budget,
    add_to_wishlist,
    get_wishlist,
    scrape_url,
    find_coupons,
    check_availability,
    delegate_research,
)
from pricewise.middleware.selective_interrupt import with_approval

# Tool safety policy. Every tool that reaches the network (Tavily search,
# extraction, sub-agent research) MUST be in UNSAFE_TOOLS so it is gated by
# a human-approval interrupt. tests/test_safety.py enforces this invariant.
UNSAFE_TOOLS = [
    search_product,
    compare_prices,
    get_reviews,
    scrape_url,
    find_coupons,
    check_availability,
    delegate_research,
]

SAFE_TOOLS = [
    calculate_budget,    # safe: pure math
    add_to_wishlist,     # safe: local state
    get_wishlist,        # safe: local state
]

def build_agent(checkpointer=None):
    """Build and return the compiled agent graph.

    The agent:
      1. Uses gpt-4o via init_chat_model (provider-agnostic initialization)
      2. Has tools for search, price comparison, reviews, budget, wishlist, and URL scraping
      3. Persists forbidden, negotiable, and important preferences separately from history
      4. Selectively pauses for approval: web-calling tools require HITL, safe tools auto-execute
      5. Filters and ranks grounded candidates before generating a Receipt or question
    """
    model = init_chat_model("gpt-4o", model_provider="openai")
    if checkpointer is None:
        checkpointer = InMemorySaver()

    # Unsafe tools (external API calls) require human approval.
    # Safe tools (pure computation, local state) auto-execute.
    tools = [with_approval(t) for t in UNSAFE_TOOLS] + list(SAFE_TOOLS)

    agent = create_regret_agent(
        model=model,
        tools=tools,
        checkpointer=checkpointer,
    )

    return agent
