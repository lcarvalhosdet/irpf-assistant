"""Vector search over the LanceDB index built by ``irpf_assistant.index``.

``uv run irpf-search "pergunta"`` prints the official questions closest to a query. It searches
the ``question_answer`` table by default, the mode that won the comparison in ADR 0004.
"""

from __future__ import annotations

import argparse
import sys
import time
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

import lancedb

from irpf_assistant.index import Embedder, Mode, OllamaEmbedder
from irpf_assistant.paths import INDEX_DIR

DEFAULT_MODE = Mode.QUESTION_ANSWER  # ADR 0004


@dataclass(frozen=True)
class Hit:
    id: int
    title: str
    question: str
    answer: str
    page: int
    distance: float  # cosine distance: 0 is identical, 2 is opposite

    @property
    def similarity(self) -> float:
        """Cosine similarity: 1 is identical."""
        return 1 - self.distance


class Retriever:
    """Embeds a query and returns the closest questions from one index table."""

    def __init__(
        self, mode: Mode = DEFAULT_MODE, db_path: Path = INDEX_DIR, embed: Embedder | None = None
    ) -> None:
        self.mode = mode
        self.embed = embed or OllamaEmbedder()
        self._table = lancedb.connect(db_path).open_table(mode.value)
        metadata = self._table.schema.metadata or {}
        index_model = metadata.get(b"embedding_model", b"").decode()
        if index_model != self.embed.model:
            raise ValueError(
                f"index '{mode}' was built with {index_model!r}, queries use {self.embed.model!r}"
            )

    def search(self, query: str, k: int = 5) -> list[Hit]:
        vector = self.embed(query).vector
        rows = (
            self._table.search(vector)
            .distance_type("cosine")
            .select(["id", "title", "question", "answer", "page", "_distance"])
            .limit(k)
            .to_list()
        )
        return [
            Hit(
                id=row["id"],
                title=row["title"],
                question=row["question"],
                answer=row["answer"],
                page=row["page"],
                distance=row["_distance"],
            )
            for row in rows
        ]


def format_hits(hits: Sequence[Hit], show_answers: bool = False) -> str:
    """One block per hit: rank, official number, similarity, page and title, then the question."""
    lines = []
    for rank, hit in enumerate(hits, start=1):
        lines.append(
            f"{rank:>2}. Pergunta nº {hit.id:03d}  sim {hit.similarity:.3f}  "
            f"p. {hit.page}  {hit.title}"
        )
        lines.append(f"    {hit.question}")
        if show_answers:
            lines.extend(f"    | {line}" for line in hit.answer.splitlines())
    return "\n".join(lines)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Show the official questions closest to a query.")
    parser.add_argument("query", nargs="+", help="the question, in Portuguese (quote it)")
    parser.add_argument("-k", type=int, default=5, help="how many questions to show (default: 5)")
    parser.add_argument(
        "--mode",
        choices=[mode.value for mode in Mode],
        default=DEFAULT_MODE.value,
        help=f"index table to search (default: {DEFAULT_MODE.value})",
    )
    parser.add_argument("--answers", action="store_true", help="print each answer as well")
    parser.add_argument("--db", type=Path, default=INDEX_DIR, help="LanceDB directory")
    args = parser.parse_args(argv)

    try:
        retriever = Retriever(Mode(args.mode), args.db)
        start = time.perf_counter()
        hits = retriever.search(" ".join(args.query), k=args.k)
        elapsed_ms = (time.perf_counter() - start) * 1000
    except ConnectionError:
        print("cannot reach Ollama; start it with `ollama serve`", file=sys.stderr)
        return 1
    except ValueError as error:
        print(f"cannot search: {error}. Build the index with `uv run irpf-index`.", file=sys.stderr)
        return 1

    print(f"index {args.mode} · {retriever.embed.model} · {elapsed_ms:.0f} ms")
    print(format_hits(hits, show_answers=args.answers))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
