"""Public stream events contain complete calls and safe, terminal errors."""

import json

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from pricewise.api.routes import _stream_agent, router
from tests.regret_fixtures import FIRST_MESSAGE, shopping_scenario


@pytest.mark.asyncio
async def test_complete_call_and_result_have_matching_ids():
    scenario = shopping_scenario()
    app = FastAPI()
    app.include_router(router, prefix="/chat")
    app.state.agent = scenario.graph
    app.state.sessions = {}
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        sid = (await client.post("/chat/sessions")).json()["session_id"]
        base = f"/chat/sessions/{sid}"
        pending = await client.post(base + "/messages", json={"content": FIRST_MESSAGE})
        events = [
            (b.splitlines()[0][7:], json.loads(b.splitlines()[1][6:]))
            for b in pending.text.strip().split("\n\n")
        ]
        calls = [data for event, data in events if event == "tool_call"]
        assert len(calls) == 1
        assert calls[0]["name"] == "search_product"
        assert calls[0]["args"]
        assert calls[0]["id"]
        approval = next(data for event, data in events if event == "approval_required")
        assert approval["tool_calls"][0]["id"] == calls[0]["id"]
        approved = await client.post(base + "/approve", json={"approved": False})
        results = [
            json.loads(b.splitlines()[1][6:])
            for b in approved.text.strip().split("\n\n")
            if b.startswith("event: tool_result")
        ]
        assert results[0]["id"] == calls[0]["id"]


@pytest.mark.asyncio
async def test_internal_exception_is_not_exposed_in_stream():
    class FailedAgent:
        async def astream(self, *args, **kwargs):
            raise ValueError("private-provider-payload and sensitive-token")
            yield  # pragma: no cover

    events = "".join([event async for event in _stream_agent(FailedAgent(), {}, None)])
    assert "event: error" in events
    assert "event: done" in events
    assert "private-provider-payload" not in events
    assert "sensitive-token" not in events
