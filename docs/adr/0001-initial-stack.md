# ADR 0001: Initial stack

- Status: accepted
- Date: 2026-11-20

## Context

irpf-assistant answers questions about Brazilian personal income tax (IRPF) and always cites the
official Receita Federal guide *Perguntas e Respostas IRPF 2026*. It is a portfolio project, so it
must run entirely on a MacBook Pro M4 (Apple Silicon) with no paid APIs. We plan for 16 GB of RAM,
which leaves about 12.5 GB for models.

## Decision

- **Python 3.12, managed with uv.** uv handles the interpreter, the dependencies and the lockfile.
  `requires-python` is pinned to 3.12: this is an application, not a library, so the lockfile only
  has to resolve for one interpreter. ruff does lint and formatting; pytest runs the tests.
- **LLM: Qwen3.5 served by Ollama** on `localhost:11434`. `qwen3.5:9b` when quality matters most,
  `qwen3.5:4b` when speed does.
- **Embeddings: `granite-embedding:278m` via Ollama.** It is multilingual, Portuguese included, and
  runs on the same server as the LLM.
- **Vector store: LanceDB**, kept in local files with no server to run.
- **PDF parsing: PyMuPDF or Docling, still open.** The winner is whichever better preserves the
  question numbering and boundaries; that choice gets its own ADR.
- **API and UI: FastAPI** (`POST /ask`) **and Gradio.**
- **CI: GitHub Actions** running lint, tests and the retrieval evaluation. CI never calls the LLM.

## Consequences

- A model that does not fit the 12.5 GB budget is not adopted, however good it is.
- Once the models are pulled, everything runs offline and costs nothing per query.
- Because CI does not call the LLM, answer-level metrics (LLM judge, latency) run locally, and
  their results are committed under `evals/results/`.
- Each relevant change to this stack gets its own short ADR in this folder.
