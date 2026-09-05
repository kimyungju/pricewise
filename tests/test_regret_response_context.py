"""The response Executor sees current tool outcomes, not researcher commentary."""

import pytest
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.runnables import RunnableLambda
from langchain_core.tools import tool
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command

from pricewise.middleware.selective_interrupt import with_approval
from pricewise.regret.graph import compile_graph
from pricewise.regret.models import CandidateBatch, TurnPlan
from pricewise.regret.state import ModelPorts


@pytest.mark.asyncio
@pytest.mark.parametrize("action", ["assist", "research"])
async def test_denial_reaches_responder_without_internal_completion(action):
    # Given: an approved-tool boundary and an internal research completion.
    seen = []
    executed = []

    @tool
    def search_product(query: str) -> str:
        """Search a test catalog."""
        executed.append(query)
        return "Unexpected execution"

    replies = iter(
        [
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "search_product",
                        "args": {"query": "shoe"},
                        "id": "search",
                    }
                ],
            ),
            AIMessage(content="INTERNAL_COMPLETION_NOT_A_CUSTOMER_ANSWER"),
        ]
    )
    models = ModelPorts(
        planner=RunnableLambda(lambda _: TurnPlan(action=action)),
        researcher=RunnableLambda(lambda _: next(replies)),
        extractor=RunnableLambda(lambda _: CandidateBatch()),
        responder=RunnableLambda(
            lambda messages: (
                seen.extend(messages) or AIMessage(content="Search denied.")
            )
        ),
    )
    graph = compile_graph(models, [with_approval(search_product)], InMemorySaver())
    config = {"configurable": {"thread_id": f"denial-{action}"}}
    await graph.ainvoke(
        {"messages": [HumanMessage(content="Search for shoes")]}, config
    )
    # When: the user denies the actual graph interrupt.
    result = await graph.ainvoke(Command(resume=False), config)
    # Then: the final writer can explain denial without continuing private prose.
    assert executed == []
    assert result["structured_response"] is None
    context = "\n".join(message.text for message in seen)
    assert "User denied execution" in context
    assert "INTERNAL_COMPLETION_NOT_A_CUSTOMER_ANSWER" not in context
