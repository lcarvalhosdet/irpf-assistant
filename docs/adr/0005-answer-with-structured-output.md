# ADR 0005: Answer with structured output and citations rendered by code

- Status: accepted; answer quality is measured in week 2
- Date: 2026-11-20

## Context

Every answer must cite the official question it used, as "(Pergunta nº X)". When no passage is
relevant, the assistant must say it found nothing and point to the Receita Federal or an
accountant, and it must never invent a rule, an amount or a deadline. The models are Qwen3.5
on the local Ollama server, `qwen3.5:9b` for quality and `qwen3.5:4b` for speed.

## Decision

- **Structured output.** The model returns JSON with `found`, `answer` and `citations`, and
  Ollama enforces that shape. The code, not the model, renders each citation as
  "(Pergunta nº NNN)", zero-padded like the guide's own numbering, so the format cannot drift.
- **Deterministic guardrails.** The fixed not-found text replaces the answer when the model
  says `found: false`, when its output has the wrong shape, or when the answer is empty or
  cites no question among the retrieved passages. Citations to questions that were not
  retrieved are dropped, and citations the model writes in its own text are removed before
  the rendered ones are added.
- **Similarity floor of 0.60.** Below it, the best passage is off-topic and the model is not
  called. The floor is provisional. Top-1 similarity ranged from 0.716 to 0.880 on the 30 seed
  queries and from 0.548 to 0.774 on 8 off-topic queries. The two ranges overlap, so the floor
  only catches the obvious cases ("bolo de chocolate"); the model handles the rest.
- **Generation settings.** The model sees the top 3 passages, with each answer cut at 6,000
  characters. Temperature is 0, thinking is off and the context is 16,384 tokens.
  `qwen3.5:9b` is the default; `--model qwen3.5:4b` switches.
- **Prompts as files.** The system prompt, the user template, the not-found text and the
  disclaimer live in `src/irpf_assistant/prompts/`.

## Consequences

- Memory, measured with `ollama ps` at a 16,384-token context: 7.8 GB for `qwen3.5:9b` and
  5.0 GB for `qwen3.5:4b`, both on the GPU through Ollama's MLX runner. Both fit the 12.5 GB
  budget alongside the 0.2–0.6 GB embedding model.
- Smoke test on six questions with the final prompt, with each model already loaded:

  | Question | `qwen3.5:9b` | `qwen3.5:4b` |
  |---|---|---|
  | Lottery prize | answered, cites 316 and 317 (13.7 s) | answered, cites 316 (7.9 s) |
  | Nephew's college fees | answered: only if a dependant; cites 409 (8.2 s) | answered, cites 407, 409, 400 (8.1 s) |
  | "Who has to file?" (retrieval misses 001) | not found (6.0 s) | not found (3.2 s) |
  | IPVA deadline, MEI invoices (off-topic) | not found (9.4 s, 8.6 s) | not found (3.9 s, 3.4 s) |
  | Chocolate cake | floor, model not called | floor, model not called |

  Every statement in the four answers was checked against the retrieved passages; none was
  invented.
- The first prompt made `qwen3.5:9b` refuse the nephew question even though question 409
  answers it with a condition. One rule now says that an answer of "no", "it depends" or "only
  if" still counts and must state the conditions. The off-topic refusals held after the change.
- Generic questions remain limited by retrieval: when the right passage is not retrieved,
  the assistant refuses instead of answering, which is safe but unhelpful (ADR 0004).
- Six questions are a smoke test, not an evaluation. Week 2 measures citation and refusal
  accuracy, agreement with the official answer and p50/p95 latency, and compares 4b with 9b.
