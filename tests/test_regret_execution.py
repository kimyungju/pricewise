"""Graph boundaries for questions, evidence scope, and bounded research."""

import pytest
from langchain_core.language_models.fake_chat_models import FakeListChatModel
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langchain_core.runnables import RunnableLambda
from langchain_core.tools import tool
from langgraph.checkpoint.memory import InMemorySaver

from pricewise.regret.graph import compile_graph
from pricewise.regret.models import CandidateBatch, ProfilePatch, TurnPlan
from pricewise.regret.state import ModelPorts


@pytest.mark.asyncio
async def test_question_turn_has_no_tool_calls_and_clears_old_receipt():
    # Given: a planner decides one essential clarification is needed.
    calls: list[str] = []
    models = ModelPorts(
        planner=RunnableLambda(
            lambda _messages: TurnPlan(action="ask_tradeoff", ask_attribute="currency")
        ),
        researcher=RunnableLambda(lambda _messages: calls.append("research")),
        extractor=RunnableLambda(lambda _messages: calls.append("extract")),
        responder=FakeListChatModel(responses=["어느 통화 기준인가요?"]),
    )
    graph = compile_graph(models, [], InMemorySaver())
    # When: a question-only turn completes.
    result = await graph.ainvoke(
        {
            "messages": [HumanMessage(content="100달러 이하")],
            "structured_response": {"product_name": "Old", "price": 10},
        },
        {"configurable": {"thread_id": "clarify"}},
    )
    # Then: no fake product receipt or research is emitted.
    assert result["structured_response"] is None
    assert result["asked_attributes"] == ["currency"]
    assert calls == []


@pytest.mark.asyncio
async def test_explicit_new_task_excludes_previous_product_sources():
    # Given: old shoe evidence exists and the user explicitly starts a new task.
    seen: list[str] = []
    models = ModelPorts(
        planner=RunnableLambda(
            lambda _messages: TurnPlan(
                action="recommend", profile_patch=ProfilePatch(reset_quote="New task")
            )
        ),
        researcher=RunnableLambda(
            lambda messages: (
                seen.append("research") or AIMessage(content="No new sources")
            )
        ),
        extractor=RunnableLambda(
            lambda messages: seen.append(str(messages)) or CandidateBatch()
        ),
        responder=FakeListChatModel(responses=["새 요청에 맞는 근거가 필요해요."]),
    )
    graph = compile_graph(models, [], InMemorySaver())
    # When: the user switches to a new product category.
    result = await graph.ainvoke(
        {
            "messages": [
                HumanMessage(content="Shoes"),
                ToolMessage(
                    content="1. Old Shoe USD 80\n   URL: https://shop.example/old",
                    name="search_product",
                    tool_call_id="old",
                ),
                HumanMessage(content="New task: find a laptop"),
            ]
        },
        {"configurable": {"thread_id": "new-task"}},
    )
    # Then: old evidence cannot satisfy the new task or skip fresh research.
    assert seen == ["research"]
    assert result["structured_response"] is None


@pytest.mark.asyncio
async def test_research_loop_stops_after_four_tool_batches():
    # Given: a model keeps requesting the same harmless tool.
    calls: list[str] = []

    @tool
    def get_wishlist() -> str:
        """Read a local test wishlist."""
        calls.append("read")
        return "Wishlist is empty"

    models = ModelPorts(
        planner=RunnableLambda(lambda _messages: TurnPlan(action="assist")),
        researcher=RunnableLambda(
            lambda _messages: AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "get_wishlist",
                        "args": {},
                        "id": f"read-{len(calls)}",
                    }
                ],
            )
        ),
        extractor=RunnableLambda(lambda _messages: CandidateBatch()),
        responder=FakeListChatModel(responses=["위시리스트가 비어 있어요."]),
    )
    graph = compile_graph(models, [get_wishlist], InMemorySaver())
    # When: the real graph executes the repeated requests.
    result = await graph.ainvoke(
        {"messages": [HumanMessage(content="Read wishlist")]},
        {"configurable": {"thread_id": "bounded"}, "recursion_limit": 15},
    )
    # Then: it reaches a response within the normal recursion budget.
    assert len(calls) == 4
    assert result["messages"][-1].text == "위시리스트가 비어 있어요."
