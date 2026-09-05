"""Missing price evidence must survive extraction without authorizing a price."""

import json

import httpx
import pytest
from langchain_core.language_models.fake_chat_models import FakeListChatModel
from langchain_core.messages import HumanMessage, ToolMessage
from langchain_core.runnables import RunnableLambda
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.memory import InMemorySaver

from pricewise.regret.graph import compile_graph
from pricewise.regret.models import (
    BudgetLimit,
    CandidateBatch,
    RegretProfile,
    TurnPlan,
)
from pricewise.regret.state import ModelPorts


@pytest.mark.asyncio
@pytest.mark.parametrize("price", [None, 90])
@pytest.mark.parametrize("hard_budget", [False, True])
async def test_null_price_quotes_do_not_crash_or_produce_verified_prices(
    price, hard_budget
):
    # Given: the real SDK receives three candidates with explicit null quotes.
    candidates = [
        {
            "product_name": f"Shoe {i}",
            "source_url": f"https://shop.example/{i}",
            "price": price,
            "currency": "USD",
            "price_quote": None,
        }
        for i in range(3)
    ]

    def respond(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "id": "nullable-extraction",
                "object": "chat.completion",
                "created": 0,
                "model": "gpt-4o",
                "choices": [
                    {
                        "index": 0,
                        "finish_reason": "tool_calls",
                        "message": {
                            "role": "assistant",
                            "content": None,
                            "tool_calls": [
                                {
                                    "id": "extract",
                                    "type": "function",
                                    "function": {
                                        "name": "CandidateBatch",
                                        "arguments": json.dumps(
                                            {"candidates": candidates}
                                        ),
                                    },
                                }
                            ],
                        },
                    }
                ],
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
        model = ChatOpenAI(model="gpt-4o", api_key="test", http_async_client=client)
        graph = compile_graph(
            ModelPorts(
                planner=RunnableLambda(lambda _: TurnPlan(action="recommend")),
                researcher=FakeListChatModel(responses=["Unused"]),
                extractor=model.with_structured_output(
                    CandidateBatch, method="function_calling"
                ),
                responder=FakeListChatModel(responses=["Price evidence is missing."]),
            ),
            [],
            InMemorySaver(),
        )
        profile = RegretProfile(
            budget=BudgetLimit(
                amount=100,
                currency="USD",
                source_quote="USD 100 maximum",
            )
            if hard_budget
            else None
        )
        # When: extraction, grounding, ranking and receipt handling all execute.
        result = await graph.ainvoke(
            {
                "profile": profile,
                "messages": [
                    ToolMessage(
                        content="\n\n".join(
                            f"{i + 1}. Shoe {i}, comfortable.\n   URL: https://shop.example/{i}"
                            for i in range(3)
                        ),
                        name="search_product",
                        tool_call_id="source",
                    ),
                    HumanMessage(content="Recommend from those sources"),
                ],
            },
            {"configurable": {"thread_id": "null-quotes"}},
        )
    # Then: even a claimed numeric price stays unverified and cannot pass a hard budget.
    ranking = result["ranking"]
    assert len(ranking.excluded if hard_budget else ranking.ranked) == 3
    assert all(
        item.candidate.price is None for item in [*ranking.ranked, *ranking.excluded]
    )
    assert result["structured_response"] is None
    assert result["messages"][-1].text == "Price evidence is missing."
