# irpf-assistant

A local assistant that answers questions about Brazilian personal income tax (IRPF) and always
cites the official Receita Federal guide *Perguntas e Respostas IRPF 2026* (745 questions covering
the 2026 return, calendar year 2025).

> [!NOTE]
> Work in progress. Ingestion and indexing are done, with a first retrieval baseline below.
> The search command, answering and the API come next; architecture and a demo will follow.

> [!IMPORTANT]
> Informational content only. It does not replace an accountant or the legislation.

## What it will do

- Answer in Portuguese and cite the official question it used, e.g. "(Pergunta nº 123)".
- Say it found nothing, and suggest the Receita Federal or an accountant, when the guide has no
  relevant passage. It never invents a rule, an amount or a deadline.
- Call a deterministic tool built on the official tax table, e.g. to compare the simplified
  discount (*desconto simplificado*) with itemized deductions.
- Back every quality claim with a repeatable evaluation: retrieval hit@k and MRR, answer
  agreement, citation and refusal accuracy, latency.

## Data

[`data/processed/questions.jsonl`](data/processed/questions.jsonl) holds the guide's 745
questions, one JSON object per line (`id`, `chapter`, `title`, `question`, `answer`, `page`).
It is built from the official PDF with PyMuPDF ([ADR 0002](docs/adr/0002-pdf-parser.md)) and
versioned so CI can test it without the PDF ([ADR 0003](docs/adr/0003-version-parsed-dataset.md)).
The parser cross-checks the guide's table of contents against its body. That check found a
numbering error in the official document (question 424 is listed as "423") and 26 titles that
differ between the two. Source, version and checksum are in [`data/SOURCE.md`](data/SOURCE.md).

## Results so far

A first retrieval baseline, on a seed set of 30 paraphrased questions (vector search only,
`granite-embedding:278m`, top 10). Embedding each question together with its answer beats
embedding the question alone ([ADR 0004](docs/adr/0004-index-question-and-answer.md)):

| Index | hit@1 | hit@3 | hit@5 | MRR@10 |
|---|---|---|---|---|
| question only | 0.567 | 0.667 | 0.800 | 0.657 |
| question + answer | **0.633** | **0.900** | **0.933** | **0.761** |

Raw runs are in [`evals/results/`](evals/results/). The full evaluation set, about 100 queries,
comes next.

## Constraints

- Runs entirely on a MacBook Pro M4 (Apple Silicon), with no paid APIs.
- Planned for 16 GB of RAM, which leaves about 12.5 GB for models.

## Stack

Python 3.12 managed with uv · Qwen3.5 (`qwen3.5:9b` / `qwen3.5:4b`) and `granite-embedding:278m`
via Ollama · LanceDB · FastAPI · Gradio · ruff · pytest · GitHub Actions.
Decisions are recorded as ADRs in [`docs/adr/`](docs/adr/).

## Development

Requires [uv](https://docs.astral.sh/uv/), which installs Python 3.12 if needed.

```bash
uv sync               # create .venv with Python 3.12 and the dev tools
uv run irpf-ingest    # rebuild the dataset from the PDF (download it first: data/SOURCE.md)
uv run irpf-index     # embed the questions into LanceDB (needs Ollama and granite-embedding:278m)
uv run python evals/run_eval.py --name <experiment>  # retrieval metrics -> evals/results/
uv run pytest         # run the tests
uv run ruff check .   # lint
uv run ruff format .  # format
```

## Resumo em português

O irpf-assistant é um assistente local de dúvidas sobre o Imposto de Renda da Pessoa Física. Toda
resposta se baseia no guia oficial da Receita Federal "Perguntas e Respostas IRPF 2026" e cita o
número da pergunta usada. Quando o guia não cobre a dúvida, o assistente diz que não encontrou e
sugere consultar a Receita ou um contador. Tudo roda num Mac, sem APIs pagas. O conteúdo é
informativo e não substitui um contador nem a legislação.
