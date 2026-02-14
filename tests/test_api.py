import pytest
import pytest_asyncio
import os
from unittest.mock import patch
from httpx import AsyncClient, ASGITransport
from aigent.api.app import create_app


@pytest.fixture
def app():
    with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test", "TAVILY_API_KEY": "tvly-test"}):
        return create_app()


@pytest_asyncio.fixture
async def client(app):
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
