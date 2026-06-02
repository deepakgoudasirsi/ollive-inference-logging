## Ollive – Lightweight LLM Inference Logging + Ingestion

This repo contains a small end-to-end system:

- **Chat UI** (React/Vite): multi-turn chat, list/resume conversations, cancel conversations.
- **Backend API** (FastAPI): chats with an LLM provider (mock/OpenAI/Anthropic), maintains short context, streams responses via SSE.
- **Lightweight logging wrapper**: emits inference metadata events near real-time to an ingestion endpoint.
- **Ingestion pipeline**: validates payloads, **PII-redacts previews**, persists to SQLite.
- **Dashboards**: simple “Metrics” view for latency/success/error + recent inference logs.

### Quickstart (Docker Compose)

From repo root:

```bash
docker compose up --build
```

- UI: `http://localhost:5173`
- API: `http://localhost:8000`

Defaults to a **mock provider** (no API keys required).

### Deploy (hosted)

This repo supports a **single-container deployment** (backend serves the built frontend) via the root `Dockerfile`.

- **Render**: a `render.yaml` is included. Create a new Render “Blueprint” from this repo and deploy.
- **Any VM**: run the container and mount `/data` for SQLite persistence.

### Run locally (no Docker)

Backend:

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

Frontend:

```bash
cd frontend
npm install
npm run dev
```

### Using a real model provider (multi-provider)

Set environment variables for the backend:

- **OpenAI**
  - `OLLIVE_LLM_PROVIDER=openai`
  - `OPENAI_API_KEY=...`
  - `OLLIVE_LLM_MODEL=gpt-4.1-mini` (or any chat-capable model you have access to)

- **Anthropic**
  - `OLLIVE_LLM_PROVIDER=anthropic`
  - `ANTHROPIC_API_KEY=...`
  - `OLLIVE_LLM_MODEL=claude-3-5-sonnet-latest` (or similar)

### Database + schema (SQLite)

SQLite file path (default):
- local: `./ollive.sqlite3`
- docker: `/data/ollive.sqlite3` (in a named volume)

Tables:
- `conversation`: conversation lifecycle (`active`/`cancelled`)
- `message`: chat history
- `inferencelog`: one row per LLM inference call (provider/model/latency/status/previews/token fields when available)

Schema lives in `backend/app/models.py`.

### Tradeoffs / practical decisions

- **Short context**: backend sends only the last 8 messages to reduce cost/latency; this can hurt long-horizon coherence.
- **Best-effort logging**: inference logs are sent asynchronously with small retries; if ingestion is down, events may be dropped.
- **Streaming first**: chat responses use SSE streaming; this simplifies frontend UX but requires careful cancellation handling.
- **SQLite**: easy local demo + clear schema; for production you’d likely move to Postgres.

### What I’d improve with more time

- Durable event queue (disk-backed) for ingestion outages (e.g. Redis/Kafka/SQS).
- Token usage collection for streaming (provider-specific aggregation).
- Stronger PII detection (NER or specialized redaction library) + configurable policies.
- AuthN/AuthZ, rate limiting, idempotency keys, multi-tenant isolation.
- Proper dashboarding (Prometheus/OpenTelemetry + Grafana) instead of a simple UI tab.

### Deliverables map

- **Chatbot app**: `frontend/`
- **Backend + ingestion**: `backend/`
- **Lightweight SDK (standalone)**: `sdk/python/ollive_llm_logger/`
- **Architecture notes**: `ARCHITECTURE_NOTES.md`

