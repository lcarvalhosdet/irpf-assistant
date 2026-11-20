"""Retriever over a tiny index built with hand-picked vectors; no Ollama needed."""

from pathlib import Path

import lancedb
import pytest

from irpf_assistant.index import Embedding, Mode, build_table
from irpf_assistant.ingest import Question
from irpf_assistant.retrieve import Retriever

VECTORS = {
    "Como declarar aluguel recebido?": [1.0, 0.0, 0.0],
    "Pensão alimentícia é dedutível?": [0.0, 1.0, 0.0],
    "Venda de ações é isenta?": [0.0, 0.0, 1.0],
    "quanto pago de imposto sobre o aluguel": [0.9, 0.1, 0.0],
}


class TableEmbedder:
    model = "table-embedder"

    def __call__(self, text: str) -> Embedding:
        return Embedding(vector=VECTORS[text], tokens=len(text.split()))


class OtherEmbedder(TableEmbedder):
    model = "other-model"


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    questions = [
        Question(id=n, chapter="C", title=f"T{n}", question=text, answer="R.", page=30 + n)
        for n, text in enumerate(list(VECTORS)[:3], start=1)
    ]
    build_table(lancedb.connect(tmp_path), Mode.QUESTION, questions, TableEmbedder())
    return tmp_path


def test_search_returns_the_closest_questions_first(db_path: Path) -> None:
    retriever = Retriever(Mode.QUESTION, db_path, TableEmbedder())

    hits = retriever.search("quanto pago de imposto sobre o aluguel", k=2)

    assert [hit.id for hit in hits] == [1, 2]
    assert hits[0].question == "Como declarar aluguel recebido?"
    assert hits[0].distance < hits[1].distance


def test_retriever_refuses_an_index_built_with_another_model(db_path: Path) -> None:
    with pytest.raises(ValueError, match="built with 'table-embedder'"):
        Retriever(Mode.QUESTION, db_path, OtherEmbedder())
