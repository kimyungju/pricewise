"""Exercise structured model output through the real OpenAI SDK transport."""

import json

import httpx
import pytest
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.memory import InMemorySaver

from pricewise.regret.graph import create_regret_agent


@pytest.mark.asyncio
@pytest.mark.parametrize("action", ["assist", "recommend"])
@pytest.mark.parametrize("legacy", ["none", "completed", "pending"])
async def test_structured_nodes_use_provider_supported_function_calls(
    action: str, legacy: str
):
    # Given: the observed provider fails JSON-schema responses but supports tools.
    schemas: list[str] = []

    def handle(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        pending: set[str] = set()
        for message in payload["messages"]:
            if message["role"] == "tool":
                assert message["tool_call_id"] in pending
                pending.remove(message["tool_call_id"])
            else:
                assert not pending, f"Tool calls without results: {pending}"
                pending = {call["id"] for call in message.get("tool_calls", [])}
        assert not pending, f"Unanswered tool calls at end: {pending}"
        if payload.get("response_format", {}).get("type") == "json_schema":
            choice = {
                "index": 0,
                "finish_reason": "length",
                "message": {"role": "assistant", "content": ""},
            }
        else:
            available = [item["function"]["name"] for item in payload.get("tools", [])]
            structured = next(
                (name for name in available if name in {"TurnPlan", "CandidateBatch"}),
                None,
            )
            if structured:
                schemas.append(structured)
                args = (
                    {"action": action, "profile_patch": {}, "ask_attribute": None}
                    if structured == "TurnPlan"
                    else {"candidates": []}
                )
                choice = {
                    "index": 0,
                    "finish_reason": "tool_calls",
                    "message": {
                        "role": "assistant",
                        "content": None,
                        "tool_calls": [
                            {
                                "id": "schema-call",
                                "type": "function",
                                "function": {
                                    "name": structured,
                                    "arguments": json.dumps(args),
                                },
                            }
                        ],
                    },
                }
            else:
                choice = {
                    "index": 0,
                    "finish_reason": "stop",
                    "message": {"role": "assistant", "content": "Hello"},
                }
        return httpx.Response(
            200,
            json={
                "id": "transport-test",
                "object": "chat.completion",
                "created": 0,
                "model": "gpt-4o",
                "choices": [choice],
                "usage": {
                    "prompt_tokens": 10,
                    "completion_tokens": 0,
                    "total_tokens": 10,
                },
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as client:
        model = ChatOpenAI(
            model="gpt-4o", api_key="unit-test", http_async_client=client
        )
        graph = create_regret_agent(model, [], InMemorySaver())
        old_messages = []
        if legacy != "none":
            old_messages = [
                HumanMessage(content="Earlier shopping request"),
                AIMessage(
                    content="Searching",
                    tool_calls=[
                        {
                            "id": "legacy-call",
                            "name": "search_product",
                            "args": {"query": "shoe"},
                        }
                    ],
                ),
            ]
            if legacy == "completed":
                old_messages.append(
                    ToolMessage(
                        content="No results",
                        name="search_product",
                        tool_call_id="legacy-call",
                    )
                )
            old_messages.append(AIMessage(content="Earlier conversation"))
        # When: both structured nodes run through the real provider SDK.
        result = await graph.ainvoke(
            {
                "messages": [
                    *old_messages,
                    ToolMessage(
                        content="1. Shoe USD 90\n   URL: https://shop.example/shoe",
                        name="search_product",
                        tool_call_id="source",
                    ),
                    HumanMessage(content="Hello"),
                ]
            },
            {"configurable": {"thread_id": action}},
        )
        # Then: typed decisions and extraction complete without a length error.
        assert result["plan"].action == action
        assert schemas == (
            ["TurnPlan", "CandidateBatch"] if action == "recommend" else ["TurnPlan"]
        )
