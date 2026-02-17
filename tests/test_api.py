import pytest
import pytest_asyncio
import os
from unittest.mock import patch
from httpx import AsyncClient, ASGITransport
from pricewise.api.app import create_app, lifespan


@pytest_asyncio.fixture
async def client():
    with patch.dict(os.environ, {
        "OPENAI_API_KEY": "sk-test",
        "TAVILY_API_KEY": "tvly-test",
        "USE_MEMORY_SAVER": "true",
    }):
        app = create_app()
        async with lifespan(app):
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as c:
                yield c


@pytest.mark.asyncio
async def test_create_session(client):
    response = await client.post("/chat/sessions")
    assert response.status_code == 200
    data = response.json()
    assert "session_id" in data
    assert isinstance(data["session_id"], str)


@pytest.mark.asyncio
async def test_create_two_sessions_different_ids(client):
    r1 = await client.post("/chat/sessions")
    r2 = await client.post("/chat/sessions")
    assert r1.json()["session_id"] != r2.json()["session_id"]


@pytest.mark.asyncio
async def test_send_message_invalid_session(client):
    response = await client.post(
        "/chat/sessions/nonexistent/messages",
        json={"content": "Hello"},
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_send_message_returns_sse_stream(client):
    # Create session first
    session_resp = await client.post("/chat/sessions")
    session_id = session_resp.json()["session_id"]

    # Send message — should get SSE stream back
    response = await client.post(
        f"/chat/sessions/{session_id}/messages",
        json={"content": "Hello"},
    )
    assert response.status_code == 200
    assert "text/event-stream" in response.headers["content-type"]
    # Should contain at least a done or error event
    assert "event: done" in response.text or "event: error" in response.text


@pytest.mark.asyncio
async def test_approve_invalid_session(client):
    response = await client.post(
        "/chat/sessions/nonexistent/approve",
        json={"approved": True},
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_approve_endpoint_exists(client):
    session_resp = await client.post("/chat/sessions")
    session_id = session_resp.json()["session_id"]
    response = await client.post(
        f"/chat/sessions/{session_id}/approve",
        json={"approved": True},
    )
    # Should return SSE stream (even if agent has nothing to resume)
    assert response.status_code == 200
    assert "text/event-stream" in response.headers["content-type"]
