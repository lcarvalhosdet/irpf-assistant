# irpf-assistant

A local assistant that answers questions about Brazilian personal income tax (IRPF) and always
cites the official Receita Federal guide *Perguntas e Respostas IRPF 2026* (745 questions covering
the 2026 return, calendar year 2025).

> [!NOTE]
> Work in progress. The project skeleton is in place; ingestion, retrieval and answering come next.
> Architecture, results and a demo will be added here as they land.

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
