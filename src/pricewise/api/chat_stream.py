"""Emit public chat events without leaking internal model output or partial calls."""

import logging

from langchain_core.messages import AIMessage, AIMessageChunk, ToolMessage

from pricewise.api.approval_state import pending_approval
from pricewise.api.streaming import format_sse_event
from pricewise.tools.wishlist import session_id_var

logger = logging.getLogger(__name__)


async def _stream_agent(agent, config, input_value, session_id: str = "default"):
    """Stream one turn; model/tool failures become a safe terminal error event."""
    token = session_id_var.set(session_id)
    sent_text = False
    try:
        async for mode, payload in agent.astream(
            input_value, config=config, stream_mode=["messages", "updates"]
        ):
            if mode == "messages":
                message, metadata = payload
                if (
                    metadata.get("langgraph_node") == "respond"
                    and isinstance(message, AIMessageChunk)
                    and message.text
                ):
                    sent_text = True
                    yield format_sse_event("token", {"content": message.text})
            elif mode == "updates" and isinstance(payload, dict):
                for node, output in payload.items():
                    if not isinstance(output, dict):
                        continue
                    for message in output.get("messages", []):
                        if node == "agent" and isinstance(message, AIMessage):
                            for call in message.tool_calls:
                                yield format_sse_event(
                                    "tool_call",
                                    {
                                        "id": call["id"],
                                        "name": call["name"],
                                        "args": call["args"],
                                    },
                                )
                        if node == "tools" and isinstance(message, ToolMessage):
                            yield format_sse_event(
                                "tool_result",
                                {
                                    "id": message.tool_call_id,
                                    "name": message.name or "",
                                    "result": message.text[:2000],
                                },
                            )
        state = await agent.aget_state(config)
        pending = pending_approval(state)
        if pending:
            yield format_sse_event(
                "approval_required", pending.model_dump(exclude_none=True)
            )
        elif not state.next:
            messages = state.values.get("messages", [])
            last = messages[-1] if messages else None
            if (
                not sent_text
                and isinstance(last, AIMessage)
                and last.text
                and not last.additional_kwargs.get("pricewise_internal")
            ):
                yield format_sse_event("token", {"content": last.text})
            structured = state.values.get("structured_response")
            if structured:
                yield format_sse_event("receipt", structured.model_dump())
    except Exception as exc:  # API boundary: report failure without provider payloads.
        logger.error(
            "Chat turn failed (%s), session=%s", type(exc).__name__, session_id
        )
        yield format_sse_event(
            "error",
            {
                "message": "Couldn't complete the response. Please try again. If it keeps failing, start a new chat.",
                "code": "chat_failed",
            },
        )
    finally:
        session_id_var.reset(token)
    yield format_sse_event("done", {})
