"""Vector search over the LanceDB index built by ``irpf_assistant.index``."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import lancedb

from irpf_assistant.index import Embedder, Mode, OllamaEmbedder
from irpf_assistant.paths import INDEX_DIR


@dataclass(frozen=True)
class Hit:
    id: int
    title: str
    question: str
    answer: str
    page: int
    distance: float  # cosine distance: 0 is identical, 2 is opposite


class Retriever:
    """Embeds a query and returns the closest questions from one index table."""

    def __init__(
        self, mode: Mode, db_path: Path = INDEX_DIR, embed: Embedder | None = None
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
