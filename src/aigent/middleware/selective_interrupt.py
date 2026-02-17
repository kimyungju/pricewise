"""Selective human-in-the-loop approval for tools.

Instead of interrupt_before=["tools"] (which pauses before EVERY tool call),
this module provides a decorator that adds per-tool interrupt() calls.
Safe tools like calculate_budget skip the interrupt entirely.
"""

from copy import copy
from functools import wraps

from langgraph.types import interrupt


def with_approval(tool_fn):
    """Wrap a LangChain tool so it pauses for human approval before executing.

    Returns a **copy** of the tool with the interrupt wrapper applied,
    leaving the original tool object unchanged (important for tests that
    invoke tools directly outside a LangGraph context).

    Usage::

        safe_tools   = [calculate_budget]           # no wrapper
        unsafe_tools = [with_approval(search_product)]  # pauses first
    """
    wrapped = copy(tool_fn)
    original = tool_fn.func

    @wraps(original)
    def wrapper(*args, **kwargs):
        # Pause the graph — the host loop must resume with Command(resume=value).
        # interrupt() returns the value passed via Command(resume=...).
        approved = interrupt({"tool": wrapped.name, "args": kwargs})
        if not approved:
            return f"User denied execution of tool '{wrapped.name}'. Do not retry this tool unless the user asks."
        return original(*args, **kwargs)

    wrapped.func = wrapper
    return wrapped
