# harness/ — reusable, industry-agnostic layer

This is the compounding asset. Every client engagement should harden this,
not just the vertical skin.

Planned components (from the plan, fill in as built — don't scaffold ahead of need):

- `runtime/` — LangGraph agent graph(s); MCP client for external data/tools
- `retrieval/` — hybrid search (dense + BM25), cross-encoder reranking,
  contextual compression
- `schemas/` — Pydantic models for every inter-step handoff (no free-text
  handoffs between steps)
- `guardrails/` — input validation, output claim-checking against source docs,
  PII handling
- `evals/` — RAGAS (retrieval quality), promptfoo/deepeval (regression suites),
  LLM-as-judge rubrics, golden datasets
- `observability/` — Langfuse tracing, cost/latency dashboards, drift alerts
- `serving/` — FastAPI + Docker

Build only what M1 needs first (runtime + schemas + basic tracing). Resist
building retrieval, guardrails, or evals infrastructure before the agent
that needs them exists.
