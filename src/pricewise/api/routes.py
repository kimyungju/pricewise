import uuid
import logging
from typing import TypedDict
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from langgraph.types import Command
from pydantic import BaseModel, ConfigDict, Field, StrictBool, JsonValue
from langchain_core.messages import HumanMessage, AIMessage

from pricewise.api.chat_stream import _stream_agent
from pricewise.observability import agent_config
from pricewise.api.approval_state import pending_approval

router = APIRouter()
logger = logging.getLogger(__name__)


class SessionRecord(TypedDict):
    thread_id: str


SSE_HEADERS = {
    "Cache-Control": "no-cache",
    "Connection": "keep-alive",
    "X-Accel-Buffering": "no",
}


class MessageRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    content: str = Field(min_length=1, max_length=20000)


class ApprovalRequest(BaseModel):
    approved: StrictBool
    interrupt_ids: list[str] | None = None


async def _get_session(request: Request, session_id: str) -> SessionRecord:
    """Look up a session or raise 404."""
    sessions = request.app.state.sessions
    if session_id in sessions:
        return sessions[session_id]

    # Check if the checkpointer has persisted state for this thread
    agent = request.app.state.agent
    config = {"configurable": {"thread_id": session_id}}
    try:
        state = await agent.aget_state(config)
        if state and state.values and state.values.get("messages"):
            sessions[session_id] = {"thread_id": session_id}
            return sessions[session_id]
    except Exception as exc:  # Preserve session identity during checkpoint outages.
        logger.error("Checkpoint lookup failed (%s)", type(exc).__name__)
        raise HTTPException(
            status_code=503,
            detail="Conversation storage is temporarily unavailable. Please retry.",
        ) from exc

    raise HTTPException(status_code=404, detail="Session not found")


@router.post("/sessions")
async def create_session(request: Request):
    """Create a new chat session."""
    session_id = str(uuid.uuid4())
    request.app.state.sessions[session_id] = {
        "thread_id": session_id,
    }
    return {"session_id": session_id}


@router.get("/sessions/{session_id}/messages")
async def get_messages(session_id: str, request: Request):
    """Return the conversation history for a session (used to rehydrate after refresh)."""
    session = await _get_session(request, session_id)
    agent = request.app.state.agent
    config = {"configurable": {"thread_id": session["thread_id"]}}

    state = await agent.aget_state(config)
    raw_messages = state.values.get("messages", [])

    messages = []
    for msg in raw_messages:
        if isinstance(msg, HumanMessage):
            messages.append({"role": "user", "content": msg.text, "id": msg.id})
        elif isinstance(msg, AIMessage):
            if msg.additional_kwargs.get("pricewise_internal"):
                continue
            entry: dict[str, JsonValue] = {
                "role": "assistant",
                "content": str(msg.text),
                "id": msg.id,
            }
            if msg.tool_calls:
                entry["toolCalls"] = [
                    {"name": tc["name"], "args": tc["args"]} for tc in msg.tool_calls
                ]
            messages.append(entry)

    structured = state.values.get("structured_response")
    receipt = structured.model_dump() if structured else None

    profile = state.values.get("profile")
    pending = pending_approval(state)
    return {
        "messages": messages,
        "receipt": receipt,
        "pending_approval": pending.model_dump(exclude_none=True) if pending else None,
        "regret_profile": profile.model_dump(mode="json") if profile else None,
    }


@router.post("/sessions/{session_id}/messages")
async def send_message(session_id: str, body: MessageRequest, request: Request):
    """Send a user message and stream the agent's response via SSE."""
    session = await _get_session(request, session_id)
    agent = request.app.state.agent
    config = agent_config(session["thread_id"], session_id=session_id)

    if pending_approval(await agent.aget_state(config)):
        raise HTTPException(
            status_code=409,
            detail="Please approve or decline the pending tool request first.",
        )

    return StreamingResponse(
        _stream_agent(
            agent,
            config,
            {"messages": [("user", body.content)]},
            session_id=session_id,
        ),
        media_type="text/event-stream",
        headers=SSE_HEADERS,
    )


@router.post("/sessions/{session_id}/approve")
async def approve_tool(session_id: str, body: ApprovalRequest, request: Request):
    """Approve or deny pending tool calls, then stream the rest of the response."""
    session = await _get_session(request, session_id)
    agent = request.app.state.agent
    config = agent_config(session["thread_id"], session_id=session_id)

    # Build resume value. Multiple interrupts require a dict of {id: value}.
    state = await agent.aget_state(config)
    pending = pending_approval(state)
    if not pending:
        raise HTTPException(
            status_code=409, detail="There is no pending tool request to approve."
        )
    interrupt_ids = pending.interrupt_ids
    if body.interrupt_ids is not None and set(body.interrupt_ids) != set(interrupt_ids):
        raise HTTPException(
            status_code=409,
            detail="This approval is out of date. Refresh the conversation.",
        )

    if len(interrupt_ids) > 1:
        resume_value = {iid: body.approved for iid in interrupt_ids}
    else:
        resume_value = body.approved

    return StreamingResponse(
        _stream_agent(
            agent,
            config,
            Command(resume=resume_value),
            session_id=session_id,
        ),
        media_type="text/event-stream",
        headers=SSE_HEADERS,
    )
