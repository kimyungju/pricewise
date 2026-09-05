"""Malformed model responses get one bounded retry, without running tools twice."""

import json

import httpx
import pytest
from langchain_core.messages import HumanMessage, ToolMessage
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.memory import InMemorySaver

from pricewise.regret.graph import create_regret_agent
from pricewise.regret.recovery import recover_output
from pricewise.regret.models import TurnPlan
from langchain_core.runnables import RunnableLambda
from pydantic import ValidationError


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "stage,bad",
    [
        ("TurnPlan", '{"action":'),
        ("TurnPlan", '{"action":"unexpected"}'),
        ("TurnPlan", '{"action":"assist","profile_patch":null}'),
        ("TurnPlan", None),
        ("CandidateBatch", '{"candidates":null}'),
        (
            "CandidateBatch",
            '{"candidates":[{"product_name":"Shoe","source_url":"https://shop.example/shoe","price":-5}]}',
        ),
        ("text", ""),
    ],
)
async def test_bad_output_is_retried_once(stage, bad):
    counts = {}

    def respond(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        available = [item["function"]["name"] for item in body.get("tools", [])]
        name = next(
            (n for n in available if n in {"TurnPlan", "CandidateBatch"}), "text"
        )
        counts[name] = counts.get(name, 0) + 1
        message = {"role": "assistant", "content": "Done"}
        if name != "text":
            args = (
                (
                    {"action": "recommend"}
                    if stage == "CandidateBatch"
                    else {"action": "ask_tradeoff", "ask_attribute": "currency"}
                )
                if name == "TurnPlan"
                else {"candidates": []}
            )
            arguments = bad if name == stage and counts[name] == 1 else json.dumps(args)
            message = {"role": "assistant", "content": None}
            if arguments is not None:
                message["tool_calls"] = [
                    {
                        "id": "schema",
                        "type": "function",
                        "function": {"name": name, "arguments": arguments},
                    }
                ]
        elif stage == "text" and counts[name] == 1:
            message["content"] = ""
        return httpx.Response(
            200,
            json={
                "id": f"test-{sum(counts.values())}",
                "object": "chat.completion",
                "created": 0,
                "model": "gpt-4o",
                "choices": [{"index": 0, "finish_reason": "stop", "message": message}],
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
        graph = create_regret_agent(
            ChatOpenAI(model="gpt-4o", api_key="test", http_async_client=client),
            [],
            InMemorySaver(),
        )
        result = await graph.ainvoke(
            {
                "messages": [
                    ToolMessage(
                        content="1. Shoe USD 90\n   URL: https://shop.example/shoe",
                        name="search_product",
                        tool_call_id="source",
                    ),
                    HumanMessage(content="Help me choose"),
                ]
            },
            {"configurable": {"thread_id": "retry"}},
        )
    assert counts[stage] == 2
    assert result["messages"][-1].text == "Done"
    assert result["structured_response"] is None


@pytest.mark.asyncio
async def test_persistent_invalid_output_stops_after_two_attempts():
    calls = []

    def invalid(messages):
        calls.append(messages)
        return TurnPlan.model_validate({"action": "invalid"})

    runnable = recover_output(RunnableLambda(invalid))
    with pytest.raises(ValidationError):
        await runnable.ainvoke([HumanMessage(content="Help")])
    assert len(calls) == 2
