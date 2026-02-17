# PriceWise — Portfolio Write-Up

## 1. Overview & Motivation

Shopping online for the right product at the right price requires visiting multiple retailers, cross-referencing reviews, and mentally tracking a budget. Most consumers repeat this process from scratch every time. The tooling that exists — browser extensions, deal aggregators — is fragmented, passive, and unable to synthesize information across sources into a single recommendation.

PriceWise is an autonomous agent that handles the full product research workflow conversationally. A user describes what they want, and the agent searches for products, compares prices across retailers, gathers reviews, calculates budget impact with tax, and delivers a structured receipt with a recommendation. Every external API call requires explicit human approval before execution — the user stays in control while the agent handles the legwork.

The system is built on LangGraph's ReAct architecture with a FastAPI streaming backend and a Next.js chat frontend. Key capabilities:

- **Multi-tool orchestration** — ten tools (product search, price comparison, reviews, budget calculation, wishlist, URL scraping, coupon/deal finder, availability checker, multi-product delegation) composed into a single agent loop
- **Selective human-in-the-loop** — only tools that make external API calls pause for approval; pure-computation tools auto-execute
- **Structured output** — every conversation ends with a typed Pydantic `Receipt`, not free-form text
- **Real-time streaming** — SSE delivers token-by-token responses, tool call notifications, approval prompts, and final receipts to the browser as they happen
- **Conversation summarization** — a pre-model hook compresses long conversations without mutating graph state
- **Persistent checkpointing** — `AsyncPostgresSaver` keeps conversation state across server restarts, with `InMemorySaver` fallback for local dev
- **Multi-product delegation** — a delegation tool fans out parallel Tavily searches across product categories via `ThreadPoolExecutor`, synthesizing results with budget tracking

PriceWise targets anyone making a considered purchase — from students comparing laptops to professionals evaluating software subscriptions. The agent reduces a 30-minute multi-tab research session to a single conversation.

This project exists as both a functional product and an engineering demonstration. Every architectural decision described below was made to serve both goals: build something usable, and build something worth examining.

## 2. Technical Architecture & Workflow

### System Overview

```
     Vercel                                Railway
┌─────────────────┐              ┌─────────────────────────┐
│  Next.js 16     │   fetch()    │     FastAPI + SSE        │
│  + React 19     │─────────────>│  (Session Manager,       │
│  (Chat UI,      │   SSE stream │   Stream Generator)      │
│   SSE Read)     │<─────────────│                          │
└─────────────────┘              └────────────┬────────────┘
  NEXT_PUBLIC_API_URL              CORS: ALLOWED_ORIGINS
  points to Railway                astream() │ Command(resume=...)
                                             v
┌──────────────┐    ┌──────────────────────────────────┐    ┌──────────────┐
│ Summarization│───>│        LangGraph ReAct Agent      │<──>│  OpenAI      │
│ pre_model    │    │                                    │    │  gpt-4o      │
│ _hook        │    │  interrupt() ──> approve ──> resume│    └──────────────┘
└──────────────┘    └──────────┬──────────┬─────────────┘
                               │          │         │
                    ┌──────────┘          │         └──────────┐
                    v                     v                    v
          ┌──────────────────┐  ┌──────────────────┐  ┌──────────────┐
          │  Tavily Tools    │  │  Local Tools      │  │  PostgreSQL  │
          │  (search, compare│  │  (budget calc,    │  │  (checkpoint │
          │   reviews, scrape│  │   wishlist)       │  │   persistence│
          │   coupons, avail,│  │   auto-execute    │  │   via Async  │
          │   delegation)    │  │                   │  │   PostgresSvr│
          │  with_approval() │  │                   │  │   )          │
          └──────────────────┘  └──────────────────┘  └──────────────┘
```

### Streaming & State Flow

The API layer uses a shared SSE generator for both new messages and approval resumes. Two LangGraph stream modes run simultaneously: `"messages"` for low-latency per-token delivery, and `"updates"` for complete tool results. After the stream ends, the generator inspects graph state to determine the terminal event — either an interrupt requiring approval or a structured receipt:

```python
# src/pricewise/api/routes.py — post-stream state inspection
state = await agent.aget_state(config)

if state.next:
    # Agent paused at interrupt() — extract tool info from tasks
    for task in state.tasks:
        if hasattr(task, "interrupts") and task.interrupts:
            for intr in task.interrupts:
                if isinstance(intr.value, dict) and "tool" in intr.value:
                    tool_calls.append({"name": intr.value["tool"], ...})
    yield format_sse_event("approval_required", {"tool_calls": tool_calls})
else:
    structured = state.values.get("structured_response")
    if structured:
        yield format_sse_event("receipt", structured.model_dump())
```

The interrupt state is only accessible through `state.tasks`, not from the message stream itself. This decoupling means the streaming logic and the control-flow logic operate independently — the stream handles content delivery, and the post-stream check handles orchestration decisions.

### Data Model

Pydantic v2 models serve double duty: they define tool input schemas (enabling the LLM to generate valid arguments) and the structured output format. The `Receipt` model includes optional `comparison_products` and `comparison_summary` fields, allowing the same schema to handle both single-product lookups and multi-product comparisons without branching logic.

Sessions are keyed by UUID and backed by a configurable checkpointer — `AsyncPostgresSaver` for production (persists across restarts) or `InMemorySaver` for local dev. The choice is made at startup via a FastAPI `lifespan` async context manager that manages the Postgres connection pool. Each session maps to a LangGraph thread ID, and the agent checkpoints its full state (messages, tool calls, pending interrupts) after every node execution. On restart, `_get_session()` queries the checkpointer to rehydrate sessions that exist in Postgres but not yet in the in-memory registry.

## 3. Tech Stack Deep Dive

| Technology | Role | Why This Over Alternatives | Tradeoff |
|---|---|---|---|
| **LangGraph** | Agent orchestration | Declarative graph with native checkpointing, interrupt, and hook support. `create_react_agent` replaces the legacy `AgentExecutor` with explicit node/edge control | Newer API surface — patterns like `pre_model_hook` and per-tool `interrupt()` have limited community examples |
| **FastAPI + SSE** | HTTP API & streaming | Native async, Pydantic integration for request validation, and `sse-starlette` for streaming without WebSocket complexity | SSE is unidirectional — approval responses require a separate POST endpoint rather than a bidirectional channel |
| **OpenAI gpt-4o** | LLM backbone | Strong tool-calling accuracy and structured output compliance via `response_format`. `init_chat_model` provides a provider-agnostic interface for future swaps | Per-token cost; vendor dependency on OpenAI's tool-calling format |
| **Tavily** | Web search API | Purpose-built for LLM applications — returns clean, parsed content rather than raw HTML. Shared client factory (`get_tavily`) centralizes configuration | Smaller ecosystem than SerpAPI or Google Custom Search; rate limits require defensive error handling |
| **Next.js 16 + React 19** | Frontend (Vercel) | App Router for server/client boundaries, `fetch` with `AbortController` for SSE lifecycle management. Deployed to Vercel with `NEXT_PUBLIC_API_URL` pointing to Railway | Vercel serverless functions have a 10s timeout — SSE streams bypass this by calling Railway directly from the browser |
| **Pydantic v2** | Schema validation | Dual-use as both tool input schemas (LLM argument validation) and structured output format (`response_format=Receipt`). Single source of truth for data contracts | Schema changes require coordination between agent output and frontend rendering |
| **PostgreSQL + AsyncPostgresSaver** | Persistent checkpointing | LangGraph-native checkpoint backend with async connection pooling. Managed via FastAPI `lifespan` context — auto-creates tables on first run, cleans up on shutdown | Requires a running Postgres instance; `InMemorySaver` fallback simplifies local dev |
| **Docker + Railway** | Backend deployment | Dockerfile with multi-stage `uv` install for fast, reproducible builds. Railway provides managed Postgres, health checks, and auto-restart. `ALLOWED_ORIGINS` env var configures CORS per environment | Railway's free tier has resource limits; SSE anti-buffering headers (`X-Accel-Buffering: no`) required to prevent proxy buffering |

## 4. Technical Challenges & Solutions

### Challenge 1: Per-Tool Human Approval Without Global Interrupts

**Constraint:** PriceWise has ten tools. Seven make external API calls (search, compare, reviews, scrape, coupons, availability, delegation) and must require human approval. Three are safe (budget calculation, wishlist add/get) and should auto-execute. LangGraph's built-in `interrupt_before=["tools"]` pauses before *every* tool call — there is no native mechanism for selective interruption.

**Why the naive approach fails:** Wrapping tool functions with a decorator is straightforward, but LangChain's `@tool` decorator produces `StructuredTool` objects, not plain functions. A naive `functools.wraps` wrapper loses the tool's `.name`, `.description`, and `.args_schema` — metadata the LLM relies on to generate valid tool calls.

**Solution:** Shallow-copy the tool object and swap only its `.func` attribute:

```python
# src/pricewise/middleware/selective_interrupt.py
def with_approval(tool_fn):
    wrapped = copy(tool_fn)       # preserve name, description, args_schema
    original = tool_fn.func

    @wraps(original)
    def wrapper(*args, **kwargs):
        approved = interrupt({"tool": wrapped.name, "args": kwargs})
        if not approved:
            return f"User denied execution of tool '{wrapped.name}'. ..."
        return original(*args, **kwargs)

    wrapped.func = wrapper
    return wrapped
```

`copy()` creates a shallow clone of the `StructuredTool` instance, preserving all metadata. The `interrupt()` call inside the wrapper raises `GraphInterrupt` — a special exception the LangGraph runtime catches to pause execution and serialize state. The original tool object remains unmodified, which matters for tests that invoke tools directly outside a graph context.

**Tradeoff:** Each approved tool wraps the original with an extra function call and interrupt serialization round-trip. For compute-bound tools this overhead would matter; for tools that call external APIs with 200ms+ latency, it is negligible.

### Challenge 2: Dual-Mode SSE Streaming with Interrupt Detection

**Constraint:** The frontend needs three categories of real-time data: per-token text (for typing animation), complete tool results (for rendering tool cards), and control signals (approval prompts, final receipts). LangGraph's `astream` supports multiple `stream_mode` values simultaneously, but each mode produces differently-shaped payloads — and interrupt state is not available from either stream mode.

**Why a single stream mode fails:** `"messages"` mode delivers `AIMessageChunk` tokens but does not emit `ToolMessage` results (they arrive as a single non-chunked message). `"updates"` mode delivers complete node outputs but arrives too late for token-by-token streaming. Neither mode surfaces interrupt state.

**Solution:** Run both modes simultaneously and inspect state post-stream:

```python
# src/pricewise/api/routes.py — dual-mode stream processing
async for mode, payload in agent.astream(
    input_value, config=config, stream_mode=["messages", "updates"]
):
    if mode == "messages":
        message, _metadata = payload
        if isinstance(message, AIMessageChunk):
            if message.content:
                yield format_sse_event("token", {"content": message.content})
            if message.tool_calls:
                for tc in message.tool_calls:
                    yield format_sse_event("tool_call", {...})
    elif mode == "updates":
        if isinstance(payload, dict):
            for node_name, node_output in payload.items():
                if node_name == "tools" and isinstance(node_output, dict):
                    for msg in node_output.get("messages", []):
                        if isinstance(msg, ToolMessage):
                            yield format_sse_event("tool_result", {...})
```

The `"messages"` arm handles content streaming. The `"updates"` arm captures tool execution results. After the async generator exhausts, `aget_state()` reveals whether the agent paused at an interrupt or completed with a structured response — information that exists only in the checkpoint, not in the stream.

**Tradeoff:** Dual-mode streaming doubles the number of payloads the generator must process. For conversations with many tool calls, this increases SSE event volume. The alternative — polling state after each tool call — would add latency and complexity to the frontend.

### Challenge 3: Safe Message Splitting for Conversation Summarization

**Constraint:** LangGraph's message history interleaves `AIMessage` (with `.tool_calls`) and `ToolMessage` (with tool results) in strict pairs. The summarization hook must split this history into "old messages to summarize" and "recent messages to keep." Splitting in the wrong place — between an `AIMessage` that requested a tool call and its corresponding `ToolMessage` — produces malformed context that causes LLM validation errors.

**Why a fixed offset fails:** A naive `messages[:-2]` split assumes the last two messages are a clean boundary. But if the LLM called multiple tools in its last turn, the tail of the message list contains one `AIMessage` followed by multiple `ToolMessage` responses. Splitting at `-2` would separate a `ToolMessage` from its parent `AIMessage`.

**Solution:** Walk backwards from the target split point, skipping over tool-call/response pairs:

```python
# src/pricewise/middleware/summarization.py — safe split algorithm
split = len(messages) - 2
while split > 0 and isinstance(messages[split], ToolMessage):
    split -= 1
if (split > 0
    and isinstance(messages[split], AIMessage)
    and getattr(messages[split], "tool_calls", None)):
    split -= 1
    while split > 0 and isinstance(messages[split], ToolMessage):
        split -= 1
```

The algorithm first skips past any `ToolMessage` entries at the split boundary. If it lands on an `AIMessage` with tool calls, it steps back again and skips any preceding `ToolMessage` entries from the previous turn. The result is a split point that always falls between complete conversation turns. The summarized prefix is compressed via LLM into a `SystemMessage`, and the recent suffix is preserved verbatim — the hook returns `{"llm_input_messages": [...]}` without mutating graph state.

**Tradeoff:** The backward walk can push the split point earlier than intended, summarizing more messages than necessary. For conversations where every turn involves tool calls, this means the "recent" window grows. The alternative — parsing tool-call IDs to match pairs explicitly — would be more precise but would couple the hook to LangChain's internal message ID format.

### Challenge 4: Parallel Research Inside a Sync Tool Running in an Async Context

**Constraint:** When a user asks "I need a laptop, monitor, and keyboard under $2000," the agent should research all three products in parallel. But LangGraph tools are synchronous functions, the Tavily client is synchronous, and the entire agent runs inside FastAPI's async event loop. You cannot call `asyncio.run()` or `asyncio.new_event_loop()` from within an already-running event loop without deadlocking.

**Why async approaches fail:** The natural instinct is `asyncio.gather()` with `run_in_executor`, but that requires an async function — and `@tool`-decorated functions must be sync (LangGraph invokes them synchronously from the tools node). Creating a new event loop with `asyncio.new_event_loop()` risks conflicts with the outer FastAPI loop and is explicitly warned against in Python's asyncio documentation.

**Solution:** Use `concurrent.futures.ThreadPoolExecutor` for thread-based parallelism:

```python
# src/pricewise/tools/delegate_research.py
@tool(args_schema=DelegationQuery)
def delegate_research(products: list, total_budget: float | None = None) -> str:
    items = [ProductResearchItem(**p) if isinstance(p, dict) else p for p in products]

    with ThreadPoolExecutor(max_workers=min(len(items), 5)) as pool:
        futures = {pool.submit(_research_one, item): item for item in items}
        results = [f.result() for f in as_completed(futures)]
    # ... synthesize results
```

Each thread gets its own call stack and runs the synchronous Tavily client independently. The `ThreadPoolExecutor` context manager ensures clean shutdown even if one search fails. The worker cap (`min(len(items), 5)`) prevents excessive concurrent API calls.

**Tradeoff:** Thread-based parallelism has higher overhead than async I/O and does not share the event loop's cooperative scheduling. For the typical case of 2–5 concurrent Tavily searches (each taking 500ms–2s), the thread overhead is negligible compared to network latency. A true async approach would require either an async Tavily client or LangGraph support for async tool functions — neither of which currently exists.

## 5. Impact & Future Roadmap

### Current State

- Full product research pipeline: search, price comparison, reviews, budget calculation, wishlist, URL scraping, coupon/deal finding, availability checking, and multi-product delegation — orchestrated in a single conversation
- Real-time streaming UI with per-token delivery, tool call visualization, approval prompts, and structured receipt rendering
- Persistent checkpointing via `AsyncPostgresSaver` — conversations survive server restarts and rehydrate automatically. `InMemorySaver` fallback for local dev and tests via `USE_MEMORY_SAVER` env var
- Multi-product delegation tool that fans out parallel Tavily searches across product categories via `ThreadPoolExecutor`, with budget tracking and result synthesis
- Twelve test modules covering schemas, tools (including new tools), middleware, streaming format, and API integration with zero live API calls
- Production-ready deployment: Dockerfile with `uv`, Railway config with health checks and restart policies, configurable CORS, and SSE anti-buffering headers

### Scalability Considerations

- `AsyncPostgresSaver` provides persistent checkpointing with connection pooling managed via FastAPI's lifespan. The checkpointer interface is pluggable — swapping to Redis or another backend requires changing one factory call
- The `ContextVar`-scoped wishlist handles concurrent sessions on a single event loop. Scaling beyond a single process requires moving wishlist state to an external store, following the same session-keyed pattern
- The multi-product delegation tool parallelizes Tavily searches via `ThreadPoolExecutor` with a configurable worker cap. This avoids async event loop conflicts (Tavily's client is synchronous) while achieving concurrent I/O
- SSE streaming is unidirectional by design. Adding real-time features (collaborative sessions, push notifications) would require upgrading to WebSockets, though the existing event format could be preserved

### Deployment Architecture

The frontend (Next.js) deploys to Vercel, and the backend (FastAPI + PostgreSQL) deploys to Railway. In local development, Next.js rewrites proxy `/api/*` to `localhost:8000`. In production, the frontend calls Railway directly via `NEXT_PUBLIC_API_URL`, bypassing Vercel's 10-second serverless timeout. CORS origins are configured per environment via `ALLOWED_ORIGINS`. The Dockerfile uses `uv` for fast, reproducible dependency installation, and Railway's health check endpoint (`/health`) enables automatic restart on failure.

### Planned Features

- **CI/CD pipeline** — Automated testing on push, deployment gating on test pass
- **Structured logging** — JSON-formatted logs for Railway's log viewer with session-scoped context

The architecture is designed for this kind of extension. Each layer — LLM, tools, middleware, API, frontend — can evolve independently. Adding a tool requires a function, a Pydantic schema, and a one-line addition to the agent's tool list. Swapping LLM providers requires changing a single `init_chat_model` call. The complexity lives in the orchestration boundaries, not in the individual components.
