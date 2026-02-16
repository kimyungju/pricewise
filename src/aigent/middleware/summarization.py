from langchain_core.messages import AIMessage, SystemMessage, ToolMessage


def create_summarization_hook(model, max_messages: int = 5):
    """Create a pre_model_hook that summarizes conversation history.

    Uses the provided model to compress older messages into a summary,
    keeping only the last 2 messages for immediate context.
    """

    async def summarize_messages(state: dict) -> dict:
        messages = state["messages"]

        if len(messages) <= max_messages:
            return {"llm_input_messages": messages}

        # Find a safe split point that doesn't break tool_call/response pairs.
        # Walk backwards from the target split to avoid cutting between an
        # AIMessage with tool_calls and its corresponding ToolMessages.
        split = len(messages) - 2
        while split > 0 and isinstance(messages[split], ToolMessage):
            split -= 1
        if split > 0 and isinstance(messages[split], AIMessage) and getattr(messages[split], "tool_calls", None):
            split -= 1
            while split > 0 and isinstance(messages[split], ToolMessage):
                split -= 1

        if split <= 0:
            return {"llm_input_messages": messages}

        messages_to_summarize = messages[:split]
        recent_messages = messages[split:]

        # Build summarization prompt
        summary_prompt = [
            SystemMessage(
                content=(
                    "Summarize the following conversation concisely. "
                    "Preserve key facts, decisions, and product details mentioned."
                )
            ),
            *messages_to_summarize,
        ]

        summary_response = await model.ainvoke(summary_prompt)

        summarized_messages = [
            SystemMessage(content=f"Summary of earlier conversation:\n{summary_response.content}"),
            *recent_messages,
        ]

        return {"llm_input_messages": summarized_messages}

    return summarize_messages
