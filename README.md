# Pricewise

> **Live Demo:** [pricewise-ai-shop.vercel.app](https://pricewise-ai-shop.vercel.app)

An AI-powered shopping assistant that searches for products, compares prices across retailers, analyzes reviews, and calculates totals — all through a conversational interface with human-in-the-loop approval.

## Features

- **Product Search** — Finds products matching your criteria using real-time web search via Tavily
- **Price Comparison** — Compares prices across multiple retailers to surface the best deals
- **Review Analysis** — Fetches and summarizes product reviews and ratings
- **Budget Calculator** — Computes totals with tax and checks against your budget
- **Human-in-the-Loop** — Every tool call requires your approval before execution, keeping you in control
- **Regret Profile** — Remembers forbidden outcomes, negotiable preferences, important benefits, and budget across turns; answers can move priorities without losing other constraints
- **Planner / Executor** — Separates structured turn decisions from tool execution and customer-facing questions or recommendations
- **Grounded Recommendations** — Filters hard constraints and ranks source claims before creating a receipt; asks about observed tradeoffs and marks missing evidence explicitly
- **Explicit Preference Memory** — Keeps the profile in session checkpoints while using bounded conversational context and a four-batch research budget per turn
- **Web Interface** — Chat-based UI built with Next.js for an accessible, real-time experience
- **Eval Harness** — 42 golden tasks (including prompt-injection and denial scenarios) with a CI regression gate
- **Observability** — Optional Langfuse tracing for every LLM call, tool call, latency, and token cost
- **Product Matching (PyTorch)** — A trained same-product classifier filters price-comparison results so the agent never compares an accessory or a sibling variant against the product you asked for

## Architecture

```
┌─────────────┐     SSE      ┌──────────────┐    LangGraph    ┌────────────┐
│   Next.js   │◄────────────►│   FastAPI     │◄──────────────►│  AI Agent   │
│   Frontend  │              │   Backend     │                │  (gpt-4o)   │
└─────────────┘              └──────────────┘                └──────┬─────┘
                                                                    │
                                                  ┌─────────────────┼─────────────────┐
                                                  │                 │                 │
                                           ┌──────▼───┐    ┌───────▼──┐    ┌─────────▼──┐
                                           │  Tavily   │    │  Budget  │    │  Summarize │
                                           │  Search   │    │  Calc    │    │  Middleware │
                                           └──────────┘    └──────────┘    └────────────┘
```

The agent uses an explicit LangGraph `StateGraph`: Planner → research Executor → evidence extraction and deterministic ranking → response Executor. It orchestrates ten tools:

| Tool | Description | Approval |
|------|-------------|----------|
| `search_product` | Searches for products via Tavily web search | Required |
| `compare_prices` | Compares prices across multiple retailers | Required |
| `get_reviews` | Fetches product reviews and ratings | Required |
| `scrape_url` | Extracts content from a specific product URL | Required |
| `find_coupons` | Searches for coupons and deals | Required |
| `check_availability` | Checks stock availability across retailers | Required |
| `delegate_research` | Fans out parallel searches across product categories | Required |
| `calculate_budget` | Computes totals with tax and validates against budget | Auto |
| `add_to_wishlist` | Saves a product to the session wishlist | Auto |
| `get_wishlist` | Retrieves the current wishlist | Auto |

The **Planner** outputs only an action, a profile patch, and an optional question target. The profile persists outside conversational context. Tools making external API calls require **human-in-the-loop approval**; pure-computation tools auto-execute. Question-only turns return chat text without manufacturing a product receipt. The existing summarization helper remains available but is not used by this graph.

For example, two shoe candidates may trade comfort against sleek design. Pricewise asks which matters more; after the user accepts a chunkier design, that preference becomes negotiable and the comfort-first candidate ranks higher. Hard exclusions and explicit budget ceilings are never silently relaxed. Missing hard-condition evidence blocks a verified recommendation, and a bare `$` does not establish USD pricing.

See [Regretless Buyer implementation](docs/plans/2026-09-05-regretless-buyer-feasibility.md) for the state model, evidence boundaries, and offline validation. Semantic interpretation still depends on the LLM; these rules do not guarantee subjective comfort or establish calibrated regret probabilities.

### Product Matching (PyTorch)

`compare_prices` results from web search routinely mix in accessories
("Silicone Case for AirPods Pro 2"), sibling variants (AirPods Max,
65-inch instead of 55-inch), and unrelated products. With
`MATCHER_ENABLED=true`, a trained classifier scores each listing's
same-product likelihood against the query and drops listings below
`MATCH_THRESHOLD` (default 0.65):

```
query ──▶ frozen MiniLM embeddings (e_q, e_c)
      └─▶ symbolic pair features (numeric variant match, token overlap)
                    │
        MatchHead MLP  [e_q ; e_c ; |e_q-e_c| ; e_q*e_c ; features] ─▶ p(same product)
```

- `src/pricewise/matching/model.py` — the PyTorch `MatchHead` module
- `src/pricewise/matching/data.py` — synthetic retailer-style title pairs
  (65-product catalog, family-level splits, accessory + same-family hard
  negatives, price noise)
- `src/pricewise/matching/train.py` — training loop (BCE + Adam, best-val
  checkpointing); retrain with `uv run python -m pricewise.matching.train`
- Test split (unseen product families): accuracy 0.82, F1 0.83, AUC 0.89
- CPU-only inference; the encoder and weights lazy-load on first use

## Tech Stack

**Backend:** Python 3.12+, LangGraph, LangChain, OpenAI (gpt-4o), Tavily, Pydantic v2, FastAPI, SSE, PostgreSQL
**Frontend:** Next.js 16, TypeScript, React 19, Tailwind CSS
**Infrastructure:** Railway (backend + Postgres), Vercel (frontend), Docker, GitHub Actions
**Observability:** Langfuse (opt-in via env keys)
**Tooling:** uv (package manager), pytest

## Setup

### Prerequisites

- Python 3.12+
- Node.js 18+
- [uv](https://docs.astral.sh/uv/) package manager
- [OpenAI API key](https://platform.openai.com/api-keys)
- [Tavily API key](https://tavily.com/)

### Installation

1. **Clone the repository**

   ```bash
   git clone https://github.com/kimyungju/Pricewise.git
   cd Pricewise
   ```

2. **Set up environment variables**

   ```bash
   cp .env.example .env
   ```

   Edit `.env` and add your API keys:

   ```
   OPENAI_API_KEY=sk-your-key-here
   TAVILY_API_KEY=tvly-your-key-here
   ```

3. **Install backend dependencies**

   ```bash
   uv sync
   ```

4. **Install frontend dependencies**

   ```bash
   cd web && npm install
   ```

## Usage

### Web Interface

Start both servers in separate terminals:

```bash
# Terminal 1 — Backend
uv run uvicorn pricewise.api.app:create_app --factory --reload --port 8000

# Terminal 2 — Frontend
cd web && npm run dev
```

Open [http://localhost:3000](http://localhost:3000) and start chatting.

### CLI

```bash
uv run python main.py
```

The CLI runs a demo query and prompts for tool approval at each step.

### Running Tests

```bash
uv run pytest -v
```

Unit tests are fully mocked (no API keys or network needed) and include a
deterministic safety suite (`tests/test_safety.py`) that enforces the tool
permission policy: every network-touching tool must sit behind the
human-approval gate, denials must block execution, and scraped page content
must stay inert data.

## Evals

The agent is evaluated against a registry of **42 golden tasks**
(`evals/golden_tasks.json`) covering search, comparison, reviews, budget math,
wishlist actions, multi-product delegation, **denial handling** (the user
rejects every approval), and **prompt-injection attacks** (poisoned pages
served from fixtures, no live scraping). The harness simulates the
human-in-the-loop gate exactly like the API layer and measures tool-call
accuracy, safety, latency, and cost.

```bash
uv run python -m evals.runner               # full run
uv run python -m evals.runner --check       # apply regression thresholds (CI gate)
uv run python -m evals.runner --filter injection
```

Latest full run (gpt-4o, 2026-06-11):

| Metric | Result |
|---|---|
| Task success rate | 97.6% (41/42) |
| Tool-call recall | 95.2% |
| Tool-call precision | 97.9% |
| Unauthorized actions after denial | **0** |
| Forbidden-tool violations | **0** |
| Prompt-injection block rate | **100%** (5/5) |
| Denial respected | 100% (2/2) |
| Latency p50 / p95 | 9.1s / 15.3s |
| Avg cost per task | $0.0095 |

The full report is written to `evals/results/latest.md`. CI
(`.github/workflows/evals.yml`) re-runs the suite weekly and on demand, and
fails on any threshold regression in `evals/thresholds.json` — including a
single injection breach.

> The injection suite has already paid for itself: an earlier run caught the
> agent obeying a "DealBot" persona-hijack embedded in a scraped page
> (calling `find_coupons` for content the user never asked about). The fix —
> explicit untrusted-data rules in the system prompt — took the block rate
> from 80% to 100%, with the eval pinned in CI to prevent regression.

## Observability

Set Langfuse keys to capture a full trace of every agent run (LLM calls,
tool calls, approval interrupts, token usage, latency, cost):

```bash
LANGFUSE_PUBLIC_KEY=pk-...
LANGFUSE_SECRET_KEY=sk-...
# LANGFUSE_HOST=https://cloud.langfuse.com  (default)
```

Tracing is strictly opt-in — without keys the app and tests run with zero
tracing overhead. Eval runs tag traces with their task id (`eval_task`) so
failures can be replayed from the Langfuse UI.

## Deployment

| Service | Platform | URL |
|---------|----------|-----|
| Frontend | Vercel | [pricewise-ai-shop.vercel.app](https://pricewise-ai-shop.vercel.app) |
| Backend | Railway | `pricewise-production-5bc0.up.railway.app` |

The frontend calls the backend directly via `NEXT_PUBLIC_API_URL`. In local dev, Next.js rewrites proxy `/api/*` to `localhost:8000`. CORS origins are configured per environment via `ALLOWED_ORIGINS` on Railway.
