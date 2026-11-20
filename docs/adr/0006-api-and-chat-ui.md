# ADR 0006: Serve answers through a FastAPI endpoint and a Gradio chat

- Status: accepted
- Date: 2026-11-20

## Context

Week 1 ends with an HTTP endpoint, `POST /ask`, and a simple chat screen. The interface must
always show that the content is informational and does not replace an accountant or the
legislation. Everything runs on one Mac.

## Decision

- **API** (`api.py`, `uv run irpf-api`, port 8000). FastAPI with `POST /ask` and `GET /health`.
  - The request takes a question, trimmed and 3 to 1,000 characters long, and an optional
    model limited to `qwen3.5:9b` and `qwen3.5:4b`.
  - The response carries the answer, the citations, every retrieved source with its similarity
    and whether it was cited, the outcome, both latencies and the disclaimer.
  - Ollama or index failures return 503 with the cause.
- **Chat** (`ui.py`, `uv run irpf-ui`, port 7860). Gradio, with the disclaimer under the title, a
  quality/speed model switch, and the cited questions listed under each answer. It calls the same
  `Answerer` in process instead of the API, so it runs on its own.
- **No conversation memory.** Each question is answered on its own: the chat shows its history
  but does not use it as context.
- **Shared answerers.** One `Answerer` per model is built on first use and reused, sharing the
  LanceDB table and the Ollama clients.
- **Nothing leaves the machine.** Both servers listen on 127.0.0.1 only, and Gradio's usage
  analytics are switched off.

## Consequences

- A follow-up such as "e se for meu neto?" is answered without the earlier turns. A step that
  rewrites follow-ups into standalone questions could add context later.
- Gradio takes about 2 seconds to import, so `ui.py` imports it only when it builds the
  interface; the API and most tests stay fast.
- The endpoint is synchronous; FastAPI runs it in a thread pool while Ollama works, which is
  enough for one local user.
- Checked by hand on the running servers: the API answered an FGTS question with `qwen3.5:9b`
  citing question 484, every detail present in that question's answer; it refused an IPVA
  question with `qwen3.5:4b` and rejected an unknown model with 422. In the chat, the
  nephew's-tuition question got the conditional answer citing 409, and the IPVA question got the
  not-found message.
