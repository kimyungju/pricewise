"""Approval state must survive refresh without accepting stale or duplicate work."""

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from langchain_core.messages import AIMessage, HumanMessage

from pricewise.api.routes import router
from tests.regret_fixtures import FIRST_MESSAGE, shopping_scenario


@pytest.mark.asyncio
async def test_pending_approval_survives_refresh_and_rejects_stale_requests():
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
        await client.post(base + "/messages", json={"content": FIRST_MESSAGE})
        restored = (await client.get(base + "/messages")).json()
        assert restored["pending_approval"]["tool_calls"][0]["name"] == "search_product"
        ids = restored["pending_approval"]["interrupt_ids"]
        assert ids
        assert (
            await client.post(base + "/messages", json={"content": "Another search"})
        ).status_code == 409
        assert (
            await client.post(
                base + "/approve", json={"approved": True, "interrupt_ids": ["stale"]}
            )
        ).status_code == 409
        assert scenario.tool_calls == []
        response = await client.post(
            base + "/approve", json={"approved": False, "interrupt_ids": ids}
        )
        assert "event: error" not in response.text
        assert scenario.tool_calls == []
        assert (await client.get(base + "/messages")).json()["pending_approval"] is None
        assert (
            await client.post(base + "/approve", json={"approved": True})
        ).status_code == 409


@pytest.mark.asyncio
@pytest.mark.parametrize("content", ["", "   ", "\n\t"])
async def test_blank_message_is_rejected_before_model_execution(content):
    app = FastAPI()
    app.include_router(router, prefix="/chat")
    app.state.sessions = {}
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        sid = (await client.post("/chat/sessions")).json()["session_id"]
        response = await client.post(
            f"/chat/sessions/{sid}/messages", json={"content": content}
        )
        assert response.status_code == 422


@pytest.mark.asyncio
async def test_string_false_is_not_treated_as_approval():
    app = FastAPI()
    app.include_router(router, prefix="/chat")
    app.state.sessions = {}
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        sid = (await client.post("/chat/sessions")).json()["session_id"]
        response = await client.post(
            f"/chat/sessions/{sid}/approve", json={"approved": "false"}
        )
        assert response.status_code == 422


@pytest.mark.asyncio
async def test_storage_failure_does_not_claim_session_was_deleted():
    class UnavailableCheckpoint:
        async def aget_state(self, config):
            raise RuntimeError("database unavailable")

    app = FastAPI()
    app.include_router(router, prefix="/chat")
    app.state.sessions = {}
    app.state.agent = UnavailableCheckpoint()
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/chat/sessions/existing-session/messages")
        assert response.status_code == 503
        assert "database unavailable" not in response.text


@pytest.mark.asyncio
async def test_restored_content_blocks_are_public_text():
    scenario = shopping_scenario()
    app = FastAPI()
    app.include_router(router, prefix="/chat")
    app.state.agent = scenario.graph
    app.state.sessions = {}
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        sid = (await client.post("/chat/sessions")).json()["session_id"]
        await scenario.graph.aupdate_state(
            {"configurable": {"thread_id": sid}},
            {
                "messages": [
                    HumanMessage(content="Hello"),
                    AIMessage(content=[{"type": "text", "text": "Saved answer"}]),
                ]
            },
            as_node="respond",
        )
        restored = (await client.get(f"/chat/sessions/{sid}/messages")).json()
        assert restored["messages"][-1]["content"] == "Saved answer"
