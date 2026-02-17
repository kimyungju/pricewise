import uuid
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from langgraph.types import Command
from pydantic import BaseModel
from langchain_core.messages import AIMessageChunk, HumanMessage, AIMessage, ToolMessage

from pricewise.api.streaming import format_sse_event
from pricewise.tools.wishlist import session_id_var

router = APIRouter()

SSE_HEADERS = {
    "Cache-Control": "no-cache",
    "Connection": "keep-alive",
    "X-Accel-Buffering": "no",
}


class MessageRequest(BaseModel):
    content: str


class ApprovalRequest(BaseModel):
    approved: bool


async def _get_session(request: Request, session_id: str) -> dict:
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
    except Exception:
        pass

    raise HTTPException(status_code=404, detail="Session not found")


async def _stream_agent(agent, config, input_value, session_id: str = "default"):
    """Shared SSE generator used by both message and approve endpoints.

    Args:
        agent: The compiled LangGraph agent.
        config: The LangGraph runnable config with thread_id.
        input_value: The input to pass to agent.astream (dict for new message,
                     Command(resume=...) for approval, None for legacy resume).
        session_id: Session ID for wishlist context.
    """
    token = session_id_var.set(session_id)
    try:
        async for mode, payload in agent.astream(
            input_value, config=config, stream_mode=["messages", "updates"]
        ):
            if mode == "messages":
                message, _metadata = payload
                # Skip structured Receipt JSON — it arrives via "receipt" event
                if _metadata.get("langgraph_node") == "generate_structured_response":
                    continue
                if isinstance(message, AIMessageChunk):
                    if message.content:
                        yield format_sse_event("token", {"content": message.content})
                    if message.tool_calls:
                        for tc in message.tool_calls:
                            yield format_sse_event("tool_call", {
                                "name": tc["name"],
                                "args": tc["args"],
                            })
            elif mode == "updates":
                # Emit tool results when the tools node completes
                if isinstance(payload, dict):
                    for node_name, node_output in payload.items():
                        if node_name == "tools" and isinstance(node_output, dict):
                            for msg in node_output.get("messages", []):
                                if isinstance(msg, ToolMessage):
                                    yield format_sse_event("tool_result", {
                                        "name": msg.name or "",
                                        "result": msg.content[:2000] if msg.content else "",
                                    })

        # After streaming completes, inspect the state
        state = await agent.aget_state(config)

        if state.next:
            # Agent is interrupted — either from interrupt_before or per-tool interrupt().
            # With per-tool interrupt(), the interrupt data is in state.tasks.
            tool_calls = []
            interrupt_ids = []
            for task in state.tasks:
                if hasattr(task, "interrupts") and task.interrupts:
                    for intr in task.interrupts:
                        if isinstance(intr.value, dict) and "tool" in intr.value:
                            tool_calls.append({
                                "name": intr.value["tool"],
                                "args": intr.value.get("args", {}),
                            })
                            interrupt_ids.append(intr.id)

            # Fallback: read tool_calls from the last AI message
            if not tool_calls:
                last_msg = state.values["messages"][-1]
                if hasattr(last_msg, "tool_calls") and last_msg.tool_calls:
                    tool_calls = [
                        {"name": tc["name"], "args": tc["args"]}
                        for tc in last_msg.tool_calls
                    ]

            if tool_calls:
                yield format_sse_event("approval_required", {
                    "tool_calls": tool_calls,
                    "interrupt_ids": interrupt_ids,
                })
        else:
            # Check for structured Receipt
            structured = state.values.get("structured_response")
            if structured:
                yield format_sse_event("receipt", structured.model_dump())

        yield format_sse_event("done", {})

    except Exception as exc:
        yield format_sse_event("error", {"message": str(exc)})
        yield format_sse_event("done", {})
    finally:
        session_id_var.reset(token)


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
            messages.append({"role": "user", "content": msg.content, "id": msg.id})
        elif isinstance(msg, AIMessage):
            entry = {"role": "assistant", "content": msg.content or "", "id": msg.id}
            if msg.tool_calls:
                entry["toolCalls"] = [
                    {"name": tc["name"], "args": tc["args"]}
                    for tc in msg.tool_calls
                ]
            messages.append(entry)

    structured = state.values.get("structured_response")
    receipt = structured.model_dump() if structured else None

    return {"messages": messages, "receipt": receipt}


@router.post("/sessions/{session_id}/messages")
async def send_message(session_id: str, body: MessageRequest, request: Request):
    """Send a user message and stream the agent's response via SSE."""
    session = await _get_session(request, session_id)
    agent = request.app.state.agent
    config = {"configurable": {"thread_id": session["thread_id"]}}

    return StreamingResponse(
        _stream_agent(
            agent, config,
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
    config = {"configurable": {"thread_id": session["thread_id"]}}

    # Build resume value. Multiple interrupts require a dict of {id: value}.
    state = await agent.aget_state(config)
    interrupt_ids = [
        intr.id
        for task in state.tasks
        if hasattr(task, "interrupts") and task.interrupts
        for intr in task.interrupts
    ]

    if len(interrupt_ids) > 1:
        resume_value = {iid: body.approved for iid in interrupt_ids}
    else:
        resume_value = body.approved

    return StreamingResponse(
        _stream_agent(
            agent, config,
            Command(resume=resume_value),
            session_id=session_id,
        ),
        media_type="text/event-stream",
        headers=SSE_HEADERS,
    )
