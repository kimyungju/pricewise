"""One approval representation for live streams and restored sessions."""

from langchain_core.messages import AIMessage
from langgraph.types import StateSnapshot
from pydantic import BaseModel, Field, JsonValue


class ApprovalCall(BaseModel):
    name: str
    args: dict[str, JsonValue] = Field(default_factory=dict)
    id: str | None = None


class PendingApproval(BaseModel):
    tool_calls: list[ApprovalCall]
    interrupt_ids: list[str]


def pending_approval(state: StateSnapshot) -> PendingApproval | None:
    """Only resumable tool interrupts require the user's decision."""
    if not state.next:
        return None
    calls: list[ApprovalCall] = []
    ids: list[str] = []
    requested = next(
        (
            message.tool_calls
            for message in reversed(state.values.get("messages", []))
            if isinstance(message, AIMessage) and message.tool_calls
        ),
        [],
    )
    used: set[str] = set()
    for task in state.tasks:
        for intr in task.interrupts:
            if isinstance(intr.value, dict) and "tool" in intr.value:
                call = ApprovalCall(
                    name=intr.value["tool"], args=intr.value.get("args", {})
                )
                matched = next(
                    (
                        tc["id"]
                        for tc in requested
                        if tc["name"] == call.name
                        and tc["args"] == call.args
                        and tc["id"] not in used
                    ),
                    None,
                )
                if matched:
                    used.add(matched)
                calls.append(call.model_copy(update={"id": matched}))
                ids.append(intr.id)
    if not calls:
        return None
    return PendingApproval(tool_calls=calls, interrupt_ids=ids)
