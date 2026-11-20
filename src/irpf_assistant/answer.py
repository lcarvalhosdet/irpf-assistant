"""Answer a question from retrieved passages, citing the official question numbers.

The model must return JSON with ``found``, ``answer`` and ``citations``; Ollama enforces that
shape with structured output. The code, not the model, renders the citations as
"(Pergunta nº NNN)", and it falls back to the fixed not-found message whenever:

- the best passage is too far from the question (similarity below ``MIN_SIMILARITY``);
- the model says the passages do not answer the question;
- the model output does not have the expected shape;
- the answer is empty, or cites no question among the retrieved passages.

Prompts and fixed texts live in ``irpf_assistant/prompts/``. Run ``uv run irpf-ask "pergunta"``.
"""

from __future__ import annotations

import argparse
import functools
import json
import re
import sys
import time
from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum
from importlib.resources import files
from typing import Protocol

import ollama

from irpf_assistant.retrieve import Hit, Retriever


class Model(StrEnum):
    QUALITY = "qwen3.5:9b"
    SPEED = "qwen3.5:4b"


ANSWER_MODEL = Model.QUALITY
DEFAULT_K = 3
MIN_SIMILARITY = 0.60  # provisional floor from a first calibration (ADR 0005)
MAX_PASSAGE_CHARS = 6000
CONTEXT_TOKENS = 16384

OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "found": {"type": "boolean"},
        "answer": {"type": "string"},
        "citations": {"type": "array", "items": {"type": "integer"}},
    },
    "required": ["found", "answer", "citations"],
}
INLINE_CITATION = re.compile(r"\s*\(perguntas? n[º°o]\.?\s*[\d\s,;e]+\)", re.IGNORECASE)


def load_text(name: str) -> str:
    """Read a prompt or a fixed text from irpf_assistant/prompts/."""
    return files("irpf_assistant").joinpath("prompts", name).read_text(encoding="utf-8").strip()


class Searcher(Protocol):
    def search(self, query: str, k: int = ...) -> list[Hit]: ...


class ChatModel(Protocol):
    model: str

    def __call__(self, system: str, user: str) -> str: ...


class OllamaChat:
    """One chat request to the local Ollama server, with the output schema enforced."""

    def __init__(self, model: str = ANSWER_MODEL, think: bool = False, host: str | None = None):
        self.model = model
        self.think = think
        self._client = ollama.Client(host=host)

    def __call__(self, system: str, user: str) -> str:
        response = self._client.chat(
            model=self.model,
            messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
            format=OUTPUT_SCHEMA,
            think=self.think,
            options={"temperature": 0, "num_ctx": CONTEXT_TOKENS},
        )
        return response.message.content or ""


@dataclass(frozen=True)
class Answer:
    text: str
    found: bool
    citations: tuple[int, ...]
    hits: tuple[Hit, ...]
    reason: str  # answered | low_similarity | model_not_found | invalid_output | no_valid_citation
    retrieval_ms: float
    generation_ms: float


def format_passage(hit: Hit, max_chars: int = MAX_PASSAGE_CHARS) -> str:
    """A retrieved question as the model sees it, with long answers cut short."""
    answer = hit.answer
    if len(answer) > max_chars:
        answer = answer[:max_chars].rstrip() + " […]"
    return f"[Pergunta nº {hit.id:03d}] {hit.title}\nPergunta: {hit.question}\nResposta: {answer}"


def render_citations(ids: Sequence[int]) -> str:
    return " ".join(f"(Pergunta nº {qid:03d})" for qid in ids)


def parse_output(raw: str) -> tuple[bool, str, list[int]] | None:
    """Return (found, answer, citations), or None when the output has the wrong shape."""
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return None
    if not isinstance(data, dict):
        return None
    found, answer, citations = data.get("found"), data.get("answer"), data.get("citations")
    if not (isinstance(found, bool) and isinstance(answer, str) and isinstance(citations, list)):
        return None
    if not all(type(qid) is int for qid in citations):
        return None
    return found, answer, citations


class Answerer:
    """Retrieves passages, asks the model and enforces the citation rules on its answer."""

    def __init__(
        self,
        retriever: Searcher,
        chat: ChatModel,
        k: int = DEFAULT_K,
        min_similarity: float = MIN_SIMILARITY,
    ) -> None:
        self.retriever = retriever
        self.chat = chat
        self.k = k
        self.min_similarity = min_similarity
        self.system_prompt = load_text("answer_system.md")
        self.user_template = load_text("answer_user.md")
        self.not_found_text = load_text("not_found.md")

    def build_user_prompt(self, question: str, hits: Sequence[Hit]) -> str:
        passages = "\n\n".join(format_passage(hit) for hit in hits)
        return self.user_template.format(passages=passages, question=question)

    def ask(self, question: str) -> Answer:
        start = time.perf_counter()
        hits = tuple(self.retriever.search(question, k=self.k))
        retrieval_ms = (time.perf_counter() - start) * 1000
        if not hits or hits[0].similarity < self.min_similarity:
            return self._not_found(hits, "low_similarity", retrieval_ms, 0.0)

        start = time.perf_counter()
        raw = self.chat(self.system_prompt, self.build_user_prompt(question, hits))
        generation_ms = (time.perf_counter() - start) * 1000

        parsed = parse_output(raw)
        if parsed is None:
            return self._not_found(hits, "invalid_output", retrieval_ms, generation_ms)
        found, text, citations = parsed
        if not found:
            return self._not_found(hits, "model_not_found", retrieval_ms, generation_ms)
        retrieved = {hit.id for hit in hits}
        valid = tuple(dict.fromkeys(qid for qid in citations if qid in retrieved))
        text = INLINE_CITATION.sub("", text).strip()
        if not text or not valid:
            return self._not_found(hits, "no_valid_citation", retrieval_ms, generation_ms)
        return Answer(
            text=f"{text} {render_citations(valid)}",
            found=True,
            citations=valid,
            hits=hits,
            reason="answered",
            retrieval_ms=retrieval_ms,
            generation_ms=generation_ms,
        )

    def _not_found(
        self, hits: tuple[Hit, ...], reason: str, retrieval_ms: float, generation_ms: float
    ) -> Answer:
        return Answer(
            text=self.not_found_text,
            found=False,
            citations=(),
            hits=hits,
            reason=reason,
            retrieval_ms=retrieval_ms,
            generation_ms=generation_ms,
        )


@functools.cache
def shared_retriever() -> Retriever:
    return Retriever()


@functools.cache
def answerer_for(model: str) -> Answerer:
    """One Answerer per model, all sharing the index; built on first use and then reused."""
    return Answerer(shared_retriever(), OllamaChat(model))


def format_sources(answer: Answer) -> str:
    """Retrieved questions, with the cited ones marked by an asterisk."""
    lines = ["sources (* cited):"]
    for hit in answer.hits:
        mark = "*" if hit.id in answer.citations else " "
        lines.append(f"  {mark} Pergunta nº {hit.id:03d}  p. {hit.page}  {hit.title}")
    return "\n".join(lines)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Answer an IRPF question from the official guide.")
    parser.add_argument("question", nargs="+", help="the question, in Portuguese (quote it)")
    parser.add_argument("--model", default=ANSWER_MODEL, help=f"default: {ANSWER_MODEL}")
    parser.add_argument("-k", type=int, default=DEFAULT_K, help="passages given to the model")
    parser.add_argument("--think", action="store_true", help="let the model reason first (slower)")
    args = parser.parse_args(argv)

    try:
        answerer = Answerer(Retriever(), OllamaChat(args.model, think=args.think), k=args.k)
        answer = answerer.ask(" ".join(args.question))
    except ConnectionError:
        print("cannot reach Ollama; start it with `ollama serve`", file=sys.stderr)
        return 1
    except ollama.ResponseError as error:
        print(f"Ollama error: {error.error} (is {args.model} pulled?)", file=sys.stderr)
        return 1
    except ValueError as error:
        print(f"cannot search: {error}. Build the index with `uv run irpf-index`.", file=sys.stderr)
        return 1

    print(answer.text)
    print()
    print(format_sources(answer))
    print(
        f"{args.model} · retrieval {answer.retrieval_ms:.0f} ms · "
        f"generation {answer.generation_ms / 1000:.1f} s · {answer.reason}"
    )
    print(load_text("disclaimer.md"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
