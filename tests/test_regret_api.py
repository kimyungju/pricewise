"""Offline end-to-end scenarios through the production chat API and graph."""

import json

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from pricewise.api.routes import router
from tests.regret_fixtures import FIRST_MESSAGE, SECOND_MESSAGE, shopping_scenario


@pytest.mark.asyncio
async def test_tradeoff_answer_updates_profile_and_returns_ranked_receipt():
    # Given: the real API and graph, with model outputs and search data fixed.
    scenario = shopping_scenario()
    app = FastAPI()
    app.include_router(router, prefix="/chat")
    app.state.agent = scenario.graph
    app.state.sessions = {}
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        session = (await client.post("/chat/sessions")).json()["session_id"]
        base = f"/chat/sessions/{session}"
        pending = await client.post(f"{base}/messages", json={"content": FIRST_MESSAGE})
        assert "event: approval_required" in pending.text
        assert scenario.tool_calls == []
        first = await client.post(f"{base}/approve", json={"approved": True})
        assert "event: error" not in first.text
        assert "event: receipt" not in first.text
        assert "event: token" in first.text
        assert "internal-research" not in first.text
        history = (await client.get(f"{base}/messages")).json()
        assert len(history["messages"]) == 2
        assert history["receipt"] is None
        assert {item["level"] for item in history["regret_profile"]["criteria"]} == {
            "important"
        }
        # When: the user accepts a less sleek design.
        second = await client.post(f"{base}/messages", json={"content": SECOND_MESSAGE})
        # Then: the state changes, research is reused, and comfort wins.
        assert "event: error" not in second.text
        assert "event: receipt" in second.text
        history = (await client.get(f"{base}/messages")).json()
        assert history["receipt"]["product_name"] == "Comfort Shoe"
        assert history["receipt"]["price"] == 90
        assert history["regret_profile"]["budget"]["amount"] == "100"
        assert {
            item["key"]: item["level"] for item in history["regret_profile"]["criteria"]
        } == {
            "comfort": "important",
            "design": "negotiable",
        }
        assert len(scenario.planner_calls) == 2
        assert len(scenario.tool_calls) == 1


@pytest.mark.asyncio
async def test_denial_performs_no_search_and_creates_no_receipt():
    # Given: research is paused at the real approval boundary.
    scenario = shopping_scenario()
    app = FastAPI()
    app.include_router(router, prefix="/chat")
    app.state.agent = scenario.graph
    app.state.sessions = {}
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        session = (await client.post("/chat/sessions")).json()["session_id"]
        base = f"/chat/sessions/{session}"
        await client.post(f"{base}/messages", json={"content": FIRST_MESSAGE})
        # When: the user denies the search.
        response = await client.post(f"{base}/approve", json={"approved": False})
        # Then: no product evidence, receipt, or duplicated planner invocation.
        assert "event: error" not in response.text
        assert "event: receipt" not in response.text
        assert scenario.tool_calls == []
        assert len(scenario.planner_calls) == 1


@pytest.mark.asyncio
async def test_new_session_has_no_profile_or_previous_products():
    # Given: another session already has saved shopping preferences.
    scenario = shopping_scenario()
    app = FastAPI()
    app.include_router(router, prefix="/chat")
    app.state.agent = scenario.graph
    app.state.sessions = {}
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        first = (await client.post("/chat/sessions")).json()["session_id"]
        await client.post(
            f"/chat/sessions/{first}/messages", json={"content": FIRST_MESSAGE}
        )
        # When: a separate session is opened.
        second = (await client.post("/chat/sessions")).json()["session_id"]
        response = await client.get(f"/chat/sessions/{second}/messages")
        # Then: none of the first session's state is exposed.
        assert response.json() == {
            "messages": [],
            "receipt": None,
            "regret_profile": None,
        }
        assert first not in json.dumps(response.json())
