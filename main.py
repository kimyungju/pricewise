# main.py
"""Async entrypoint demonstrating the LangGraph autonomous agent.

This uses the functional create_react_agent approach instead of the legacy
AgentExecutor. The key difference: instead of an opaque while-loop that
calls the LLM and tools in sequence, we have a compiled state graph with
explicit nodes, edges, and checkpointing — making the execution fully
inspectable, interruptible, and resumable.
"""
import asyncio
import os

from dotenv import load_dotenv

from aigent.agent import build_agent
from aigent.middleware.human_approval import prompt_for_approval


async def main():
    load_dotenv()

    if not os.getenv("OPENAI_API_KEY"):
        print("Error: OPENAI_API_KEY not set in .env")
        return
    if not os.getenv("TAVILY_API_KEY"):
        print("Error: TAVILY_API_KEY not set in .env")
        return

    agent = build_agent()

    # Thread config enables checkpointing — the agent remembers state
    # across invocations within the same thread, which powers the
    # interrupt/resume flow for human-in-the-loop approval.
    config = {"configurable": {"thread_id": "demo-session-1"}}

    user_query = "Find me the best wireless headphones under $100"
    print(f"\nUser: {user_query}\n")

    # First invocation: the agent reasons and decides to call SearchProduct.
    # Because interrupt_before=["tools"], execution pauses before the tool runs.
    result = await agent.ainvoke(
        {"messages": [("user", user_query)]},
        config=config,
    )

    # Check if the agent is at an interrupt point (pending tool execution)
    state = await agent.aget_state(config)

    while state.next:
        # The agent wants to call a tool — show it and ask for approval
        last_msg = state.values["messages"][-1]

        if hasattr(last_msg, "tool_calls") and last_msg.tool_calls:
            approved = prompt_for_approval(last_msg.tool_calls)

            if not approved:
                print("\nTool execution denied. Ending session.")
                return

        # Resume: passing None continues from the checkpoint
        result = await agent.ainvoke(None, config=config)
        state = await agent.aget_state(config)

    # Extract the structured Receipt output
    receipt = result.get("structured_response")

    if receipt:
        print("\n=== Final Receipt ===")
        print(f"  Product: {receipt.product_name}")
        print(f"  Price:   {receipt.price} {receipt.currency}")
        print("=====================")
    else:
        # Fallback: print the last agent message
        last_msg = result["messages"][-1]
        print(f"\nAgent: {last_msg.content}")


if __name__ == "__main__":
    asyncio.run(main())
