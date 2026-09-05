"""Serialize writes per session for this service's single ASGI worker."""

from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send


class ChatConcurrencyMiddleware:
    """Hold the lease through the complete stream, including client cancellation."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app
        self.active: set[str] = set()

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        parts = scope.get("path", "").split("/")
        guarded = (
            scope["type"] == "http"
            and scope.get("method") == "POST"
            and len(parts) == 5
            and parts[1:3] == ["chat", "sessions"]
            and parts[4] in {"messages", "approve"}
        )
        if not guarded:
            await self.app(scope, receive, send)
            return
        session = parts[3]
        if session in self.active:
            await JSONResponse(
                status_code=409,
                content={
                    "detail": "This conversation is still processing a request. Please wait."
                },
            )(scope, receive, send)
            return
        self.active.add(session)
        try:
            await self.app(scope, receive, send)
        finally:
            self.active.discard(session)
