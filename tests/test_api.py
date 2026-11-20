"""The HTTP layer, with a fake answerer: no Ollama and no index needed."""

import pytest
from fastapi.testclient import TestClient

from irpf_assistant.answer import Answer, load_text
from irpf_assistant.api import app, get_answerer_factory
from irpf_assistant.retrieve import Hit

HITS = (
    Hit(id=384, title="Quiropraxia", question="Q?", answer="R.", page=188, distance=0.231),
    Hit(
        id=373,
        title="Internação em residência",
        question="Q?",
        answer="R.",
        page=186,
        distance=0.302,
    ),
)
ANSWERED = Answer(
    text="Sim, se a sessão for feita por fisioterapeuta. (Pergunta nº 384)",
    found=True,
    citations=(384,),
    hits=HITS,
    reason="answered",
    retrieval_ms=40.04,
    generation_ms=8200.26,
)


class FakeAnswerer:
    def __init__(self, outcome: Answer | Exception) -> None:
        self.outcome = outcome
        self.questions: list[str] = []

    def ask(self, question: str) -> Answer:
        self.questions.append(question)
        if isinstance(self.outcome, Exception):
            raise self.outcome
        return self.outcome


@pytest.fixture
def serve():
    """Start a test client whose answerer returns (or raises) the given outcome."""

    def start(outcome: Answer | Exception):
        answerer = FakeAnswerer(outcome)
        models: list[str] = []

        def factory(model: str) -> FakeAnswerer:
            models.append(model)
            return answerer

        app.dependency_overrides[get_answerer_factory] = lambda: factory
        return TestClient(app), answerer, models

    yield start
    app.dependency_overrides.clear()


def test_ask_returns_the_answer_with_its_sources_and_the_disclaimer(serve) -> None:
    client, answerer, models = serve(ANSWERED)

    response = client.post("/ask", json={"question": "  Posso deduzir quiropraxia?  "})

    assert response.status_code == 200
    body = response.json()
    assert body["answer"] == ANSWERED.text
    assert (body["found"], body["citations"], body["reason"]) == (True, [384], "answered")
    assert body["sources"] == [
        {"id": 384, "title": "Quiropraxia", "page": 188, "similarity": 0.769, "cited": True},
        {
            "id": 373,
            "title": "Internação em residência",
            "page": 186,
            "similarity": 0.698,
            "cited": False,
        },
    ]
    assert (body["retrieval_ms"], body["generation_ms"]) == (40.0, 8200.3)
    assert body["disclaimer"] == load_text("disclaimer.md")
    assert body["model"] == "qwen3.5:9b"
    assert models == ["qwen3.5:9b"]
    assert answerer.questions == ["Posso deduzir quiropraxia?"]


def test_ask_can_use_the_fast_model(serve) -> None:
    client, _, models = serve(ANSWERED)
    payload = {"question": "Posso deduzir quiropraxia?", "model": "qwen3.5:4b"}
    assert client.post("/ask", json=payload).status_code == 200
    assert models == ["qwen3.5:4b"]


@pytest.mark.parametrize(
    "payload",
    [
        {"question": "   "},
        {"question": "ok"},
        {"question": "Posso deduzir quiropraxia?", "model": "gpt-4o"},
        {},
    ],
)
def test_ask_rejects_invalid_requests(serve, payload: dict) -> None:
    client, answerer, _ = serve(ANSWERED)
    assert client.post("/ask", json=payload).status_code == 422
    assert answerer.questions == []


def test_ask_reports_not_found_answers(serve) -> None:
    not_found = Answer(
        text=load_text("not_found.md"),
        found=False,
        citations=(),
        hits=HITS,
        reason="model_not_found",
        retrieval_ms=1.0,
        generation_ms=2.0,
    )
    client, _, _ = serve(not_found)

    body = client.post("/ask", json={"question": "Qual o prazo do IPVA?"}).json()

    assert (body["found"], body["citations"], body["reason"]) == (False, [], "model_not_found")
    assert not any(source["cited"] for source in body["sources"])


def test_ask_returns_503_when_ollama_is_down(serve) -> None:
    client, _, _ = serve(ConnectionError("connection refused"))
    response = client.post("/ask", json={"question": "Posso deduzir quiropraxia?"})
    assert response.status_code == 503
    assert "ollama serve" in response.json()["detail"]


def test_health_reports_ok() -> None:
    response = TestClient(app).get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "default_model": "qwen3.5:9b"}
