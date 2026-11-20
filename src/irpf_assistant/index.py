"""Embed the questions and store them in LanceDB, one table per indexing mode.

Two modes are compared:

- ``question``: the official question text only;
- ``question_answer``: the question followed by its answer. The embedding model reads at most
  512 tokens, so long answers are cut short; the ``tokens`` column records how many tokens the
  model read for each row.

Vectors come from ``granite-embedding:278m`` on the local Ollama server, one request per
question so that each row gets its own token count. Each row also keeps the full question
record, so a search result needs no second lookup.

Run ``uv run irpf-index`` to rebuild every table; Ollama must be running.
"""

from __future__ import annotations

import argparse
import sys
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Protocol

import lancedb
import ollama
import pyarrow as pa

from irpf_assistant.ingest import Question, read_jsonl
from irpf_assistant.paths import INDEX_DIR, QUESTIONS_PATH, display_path

EMBEDDING_MODEL = "granite-embedding:278m"
CONTEXT_TOKENS = 512  # context length of granite-embedding:278m, as reported by `ollama show`


class Mode(StrEnum):
    QUESTION = "question"
    QUESTION_ANSWER = "question_answer"


@dataclass(frozen=True)
class Embedding:
    vector: list[float]
    tokens: int  # tokens the model read, capped at its context length


class Embedder(Protocol):
    model: str

    def __call__(self, text: str) -> Embedding: ...


class OllamaEmbedder:
    """Embeds one text per request through the local Ollama server."""

    def __init__(self, model: str = EMBEDDING_MODEL, host: str | None = None) -> None:
        self.model = model
        self._client = ollama.Client(host=host)

    def __call__(self, text: str) -> Embedding:
        response = self._client.embed(model=self.model, input=text)
        return Embedding(
            vector=list(response.embeddings[0]), tokens=response.prompt_eval_count or 0
        )


@dataclass(frozen=True)
class BuildReport:
    mode: Mode
    rows: int
    truncated: int  # rows whose text reached the model's context limit
    seconds: float


def document_text(question: Question, mode: Mode) -> str:
    """The text that stands for a question in the given mode."""
    if mode is Mode.QUESTION:
        return question.question
    return f"{question.question}\n{question.answer}"


def table_schema(dim: int, model: str, mode: Mode) -> pa.Schema:
    return pa.schema(
        [
            pa.field("id", pa.int32()),
            pa.field("chapter", pa.string()),
            pa.field("title", pa.string()),
            pa.field("question", pa.string()),
            pa.field("answer", pa.string()),
            pa.field("page", pa.int32()),
            pa.field("text", pa.string()),
            pa.field("tokens", pa.int32()),
            pa.field("vector", pa.list_(pa.float32(), dim)),
        ],
        metadata={"embedding_model": model, "mode": mode.value},
    )


def build_table(
    db: lancedb.DBConnection,
    mode: Mode,
    questions: Sequence[Question],
    embed: Embedder,
    on_progress: Callable[[int, int], None] | None = None,
) -> BuildReport:
    """Embed every question in one mode and replace that mode's table."""
    if not questions:
        raise ValueError("no questions to index")
    start = time.perf_counter()
    rows = []
    for done, question in enumerate(questions, start=1):
        text = document_text(question, mode)
        embedding = embed(text)
        rows.append(
            {
                "id": question.id,
                "chapter": question.chapter,
                "title": question.title,
                "question": question.question,
                "answer": question.answer,
                "page": question.page,
                "text": text,
                "tokens": embedding.tokens,
                "vector": embedding.vector,
            }
        )
        if on_progress:
            on_progress(done, len(questions))

    dims = {len(row["vector"]) for row in rows}
    if len(dims) != 1:
        raise ValueError(f"embeddings have different sizes: {sorted(dims)}")
    schema = table_schema(dims.pop(), embed.model, mode)
    db.create_table(mode.value, data=rows, schema=schema, mode="overwrite")
    truncated = sum(row["tokens"] >= CONTEXT_TOKENS for row in rows)
    return BuildReport(mode, len(rows), truncated, time.perf_counter() - start)


def _progress_printer(label: str) -> Callable[[int, int], None]:
    def show(done: int, total: int) -> None:
        print(f"\r{label}: {done}/{total}", end="", file=sys.stderr, flush=True)

    return show


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--mode",
        choices=[mode.value for mode in Mode],
        action="append",
        help="table to build (repeatable); default: every mode",
    )
    parser.add_argument("--limit", type=int, help="index only the first N questions")
    parser.add_argument("--db", type=Path, default=INDEX_DIR, help="LanceDB directory")
    args = parser.parse_args(argv)

    modes = [Mode(value) for value in args.mode] if args.mode else list(Mode)
    questions = read_jsonl(QUESTIONS_PATH)[: args.limit]
    embed = OllamaEmbedder()
    db = lancedb.connect(args.db)
    try:
        for mode in modes:
            report = build_table(db, mode, questions, embed, _progress_printer(mode))
            print("\r", end="", file=sys.stderr)
            print(
                f"{mode}: {report.rows} rows in {report.seconds:.1f}s, "
                f"{report.truncated} cut at {CONTEXT_TOKENS} tokens"
            )
    except ConnectionError:
        print("\ncannot reach Ollama; start it with `ollama serve`", file=sys.stderr)
        return 1
    except ollama.ResponseError as error:
        print(f"\nOllama error: {error.error} (is {EMBEDDING_MODEL} pulled?)", file=sys.stderr)
        return 1
    print(f"index written to {display_path(args.db)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
