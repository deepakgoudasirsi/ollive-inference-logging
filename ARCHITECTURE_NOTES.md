## Architecture Notes

### Ingestion flow

1. **User** sends a message from the UI.
2. **Backend** persists the user message to `message`.
3. Backend calls the provider adapter (mock/OpenAI/Anthropic) and **streams tokens** back to the UI via SSE.
4. In parallel, the backend’s **logging wrapper** creates an `InferenceEvent` with:
   - provider/model
   - timestamps + latency
   - status/errors
   - session/conversation IDs
   - redacted input/output previews
5. When generation ends (success/error/cancel), the wrapper **POSTs** the event to `POST /api/ingest/inference`.
6. The ingestion endpoint validates auth + parses payload, **re-redacts previews**, and stores to `inferencelog`.

### Logging strategy

- **Near-real-time**: inference events are sent asynchronously (fire-and-forget) so user-facing latency is not dominated by ingestion.
- **Best-effort**: retries with exponential backoff; if ingestion remains unavailable the event is dropped (documented tradeoff).
- **Preview-only text**: only short previews are logged (not full prompts/completions), reducing cost/risk.
- **PII redaction**: ingestion runs regex-based redaction for emails/phones/cards on previews.

### Scaling considerations

- Split services:
  - chat API (LLM calls)
  - ingestion API (write-heavy)
- Add a durable queue between them (Kafka/Redis Streams/SQS) to absorb spikes and isolate failures.
- Move from SQLite to **Postgres** and add indexes (provider/model/status/started_at) plus partitioning for long retention.
- Add OpenTelemetry spans (trace_id already exists) for end-to-end tracing.

### Failure handling assumptions

- **Provider errors**: logged as `status=error` with `error_type` and truncated message.
- **Client disconnect / stop**: treated as `status=cancelled` (stream stops; no assistant message is persisted).
- **Ingestion down**: inference still completes; logs may be dropped after retries.
- **Idempotency**: event IDs are UUIDs; ingestion writes by primary key (duplicates would fail in stricter DBs; for prod, use upsert).

