"""HTTP API: ``POST /ask`` answers a question; ``GET /health`` reports that the server is up.

Run ``uv run irpf-api`` and open http://127.0.0.1:8000/docs. The server listens on localhost
only. Requests run in FastAPI's thread pool, since answering blocks on Ollama.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Annotated

import ollama
import uvicorn
from fastapi import Depends, FastAPI, HTTPException
from pydantic import BaseModel, Field, StringConstraints

from irpf_assistant import __version__
from irpf_assistant.answer import Answer, Answerer, Model, answerer_for, load_text

DISCLAIMER = load_text("disclaimer.md")

QuestionText = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=3, max_length=1000)
]


class AskRequest(BaseModel):
    question: QuestionText = Field(description="A question about IRPF 2026, in Portuguese")
    model: Model = Field(
        default=Model.QUALITY, description="qwen3.5:9b for quality, qwen3.5:4b for speed"
    )


class Source(BaseModel):
    id: int
    title: str
    page: int
    similarity: float
    cited: bool


class AskResponse(BaseModel):
    answer: str
    found: bool
    citations: list[int]
    sources: list[Source]
    reason: str
    model: str
    retrieval_ms: float
    generation_ms: float
    disclaimer: str


app = FastAPI(
    title="irpf-assistant",
    version=__version__,
    description=(
        "Answers questions about IRPF 2026 from the official Receita Federal guide "
        '"Perguntas e Respostas IRPF 2026", citing the question it used.'
    ),
)


def get_answerer_factory() -> Callable[[str], Answerer]:
    """Overridden in tests to swap in a fake."""
    return answerer_for


AnswererFactory = Annotated[Callable[[str], Answerer], Depends(get_answerer_factory)]


def to_response(answer: Answer, model: str) -> AskResponse:
    return AskResponse(
        answer=answer.text,
        found=answer.found,
        citations=list(answer.citations),
        sources=[
            Source(
                id=hit.id,
                title=hit.title,
                page=hit.page,
                similarity=round(hit.similarity, 4),
                cited=hit.id in answer.citations,
            )
            for hit in answer.hits
        ],
        reason=answer.reason,
        model=model,
        retrieval_ms=round(answer.retrieval_ms, 1),
        generation_ms=round(answer.generation_ms, 1),
        disclaimer=DISCLAIMER,
    )


@app.post("/ask")
def ask(request: AskRequest, make_answerer: AnswererFactory) -> AskResponse:
    try:
        answer = make_answerer(request.model.value).ask(request.question)
    except ConnectionError as error:
        detail = "Ollama is not reachable; start it with `ollama serve`"
        raise HTTPException(status_code=503, detail=detail) from error
    except ollama.ResponseError as error:
        raise HTTPException(status_code=503, detail=f"Ollama error: {error.error}") from error
    except ValueError as error:
        raise HTTPException(status_code=503, detail=f"Index unavailable: {error}") from error
    return to_response(answer, request.model.value)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "default_model": Model.QUALITY.value}


def main() -> None:
    uvicorn.run(app, host="127.0.0.1", port=8000)


if __name__ == "__main__":
    main()
