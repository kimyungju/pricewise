"""A session lease spans response streaming and is released after failures."""

import anyio
import pytest
from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from httpx import ASGITransport, AsyncClient

from pricewise.api.concurrency import ChatConcurrencyMiddleware


@pytest.mark.asyncio
async def test_same_session_is_rejected_until_stream_finishes():
    started = anyio.Event()
    release = anyio.Event()
    app = FastAPI()
    app.add_middleware(ChatConcurrencyMiddleware)

    @app.post("/chat/sessions/{sid}/messages")
    async def message(sid: str):
        async def body():
            started.set()
            await release.wait()
            yield "done"

        return StreamingResponse(body())

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        async with anyio.create_task_group() as group:
            group.start_soon(client.post, "/chat/sessions/one/messages")
            await started.wait()
            try:
                duplicate = await client.post("/chat/sessions/one/approve")
                assert duplicate.status_code == 409
            finally:
                release.set()
        assert (await client.post("/chat/sessions/one/messages")).status_code == 200


@pytest.mark.asyncio
async def test_failed_request_releases_session_lease():
    app = FastAPI()
    app.add_middleware(ChatConcurrencyMiddleware)
    failed = False

    @app.post("/chat/sessions/one/messages")
    async def message():
        nonlocal failed
        if not failed:
            failed = True
            raise RuntimeError("test failure")
        return {"ok": True}

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        with pytest.raises(RuntimeError, match="test failure"):
            await client.post("/chat/sessions/one/messages")
        assert (await client.post("/chat/sessions/one/messages")).status_code == 200
