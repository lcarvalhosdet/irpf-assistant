# irpf-assistant — Assistente de dúvidas do IRPF

Projeto de portfólio de engenharia de IA. É um assistente que responde dúvidas sobre o Imposto de Renda da Pessoa Física e cita sempre o guia oficial da Receita Federal "Perguntas e Respostas IRPF 2026". O guia tem 745 perguntas e cobre a declaração de 2026, ano-calendário 2025.

Funcionar não basta: o projeto precisa mostrar engenharia de IA bem feita. Isso inclui:

- busca medida;
- respostas com fonte;
- uma ferramenta chamada pelo modelo;
- avaliação que pode ser repetida;
- testes automáticos.

O README é a vitrine para recrutadores, então resultados e decisões precisam estar visíveis.

## Restrições

- Tudo roda localmente num MacBook Pro M4 (Apple Silicon), sem APIs pagas.
- Planejar para 16 GB de memória: sobram cerca de 12,5 GB para modelos. Não adotar modelo que não caiba nisso.
- O assistente responde em português. Código, nomes, commits e README ficam em inglês. O README tem um resumo em português.
- Toda resposta cita o número da pergunta oficial usada, no formato "(Pergunta nº X)".
- Se não houver trecho relevante, o assistente diz que não encontrou e sugere consultar a Receita ou um contador. Nunca inventar regra, valor ou prazo.
- Aviso fixo na interface: conteúdo informativo, que não substitui um contador nem a legislação.

## Stack inicial

Mudanças relevantes viram um ADR curto em `docs/adr/`.

- Linguagem e ferramentas: Python 3.12, gerenciado com `uv`. `ruff` para lint e formatação, `pytest` para testes.
- LLM: Qwen3.5 via Ollama, que roda no próprio Mac em `localhost:11434`.
  - `qwen3.5:9b` quando a prioridade for qualidade;
  - `qwen3.5:4b` quando a prioridade for velocidade.
- Embeddings: `granite-embedding:278m` via Ollama (multilíngue, inclui português).
- Banco vetorial: LanceDB, em arquivo local, sem servidor.
- Leitura do PDF: PyMuPDF ou Docling. Escolher o que preservar melhor a numeração e a divisão das perguntas. Decidido: PyMuPDF (ADR 0002).
- API e interface: FastAPI e Gradio.
- CI: GitHub Actions com lint, testes e avaliação da busca. O CI não chama o LLM.

## Dados

- Fonte: o PDF oficial "Perguntas e Respostas IRPF 2026", no site da Receita Federal (gov.br/receitafederal). Registrar em `data/SOURCE.md` a URL, a versão do PDF e a data do download.
- `data/raw/`: o PDF original. Não editar e não versionar no git.
- `data/processed/questions.jsonl`: uma linha por pergunta, com `id` (número oficial), `chapter`, `title`, `question`, `answer` e `page`. Versionado no git (ADR 0003).
- Conferência: devem sair 745 perguntas. Se o número for outro, investigar antes de seguir.

## Estrutura planejada

```
src/irpf_assistant/
  ingest.py      # PDF -> questions.jsonl
  index.py       # embeddings + LanceDB
  retrieve.py    # busca (vetorial; depois híbrida)
  answer.py      # prompt + LLM + citações
  tools.py       # ferramentas determinísticas (semana 2)
  prompts/       # prompts versionados em arquivo
  api.py         # FastAPI (POST /ask)
  ui.py          # Gradio
evals/
  questions_paraphrased.jsonl   # pergunta reescrita + id oficial esperado
  run_eval.py
  results/                      # um CSV por experimento
tests/
docs/adr/
```

## Plano

### Semana 1: fazer funcionar

1. Criar a estrutura com uv, ruff e pytest, um `.gitignore` adequado e um teste simples passando.
2. Escrever `ingest.py`, que transforma o PDF em `questions.jsonl`. Testes:
   - total de 745 perguntas;
   - ids únicos e na ordem;
   - nenhuma pergunta ou resposta vazia.
3. Escrever `index.py`, que gera os embeddings e grava no LanceDB. Comparar duas formas de indexar: só a pergunta, ou pergunta e resposta juntas. Resultado: pergunta + resposta (ADR 0004).
4. Escrever `retrieve.py`, que devolve os k trechos mais parecidos. Incluir um comando de terminal para testar uma pergunta e ver os resultados.
5. Escrever `answer.py`, que monta o prompt com os trechos e pede uma resposta curta em português, citando o número da pergunta. Sem trecho relevante, devolve a resposta de "não encontrei".
6. Escrever `api.py` e `ui.py`: o endpoint `POST /ask` e uma tela de chat simples.

### Semana 2: medir

1. Conjunto de avaliação em `evals/`: cerca de 100 perguntas oficiais reescritas como um contribuinte perguntaria, cada uma com o id oficial esperado. Parte escrita à mão e parte por LLM, todas revisadas.
2. Métricas:
   - busca: hit@3, hit@5 e MRR;
   - resposta: concordância com a resposta oficial, avaliada por um LLM juiz e revisada à mão numa amostra;
   - citação correta e recusa correta;
   - tempo de resposta p50/p95.
3. Experimentos, com uma linha por configuração em `evals/results/`:
   - divisão por pergunta × tamanho fixo;
   - modelo 4b × 9b;
   - com e sem reordenação dos resultados (reranker);
   - valores diferentes de k.
4. Ferramenta com função determinística baseada na tabela oficial do ano. Exemplo: comparar o desconto simplificado com as deduções legais. O modelo chama a função via tool calling.
   - Os valores da tabela ficam num arquivo de dados, com a fonte citada.
   - Testes usam exemplos conferidos.
   - Medir se o modelo chama a ferramenta quando deve, e só quando deve.
5. CI e README: CI no GitHub Actions. README com arquitetura, tabela de resultados, limitações e GIF da demonstração.

## Como trabalhar neste repositório

- Trabalhar em passos pequenos. Para cada passo: propor o plano, implementar, rodar os testes e fazer o commit.
- Antes de qualquer coisa demorada, como reindexar tudo ou rodar a avaliação completa, avisar e perguntar.
- Toda mudança de modelo, prompt ou parâmetro de busca roda a avaliação e registra o resultado.
- Prompts ficam em `src/irpf_assistant/prompts/`, nunca espalhados pelo código.
- Não commitar segredos, o PDF nem arquivos gerados (índice, cache, modelos). Exceção: o `questions.jsonl` (ADR 0003).

## Comandos

- Setup: `uv sync` (cria o `.venv` com Python 3.12 e as ferramentas de desenvolvimento)
- Ingestão: `uv run irpf-ingest` (PDF → `data/processed/questions.jsonl`; `-v` lista as divergências do sumário). O PDF precisa estar em `data/raw/` (ver `data/SOURCE.md`).
- Testes: `uv run pytest`
- Lint: `uv run ruff check .`
- Formatação: `uv run ruff format .` (só conferir, sem alterar: `uv run ruff format --check .`)
- Índice: `uv run irpf-index` (grava as tabelas `question` e `question_answer` em `data/index/`; precisa do Ollama com `granite-embedding:278m`; `--limit N` testa numa amostra)
- Busca no terminal: `uv run irpf-search "pergunta"` (mostra as perguntas oficiais mais próximas; `-k`, `--mode question`, `--answers`)
- Resposta no terminal: `uv run irpf-ask "pergunta"` (padrão `qwen3.5:9b`; `--model qwen3.5:4b` para velocidade; `-k`, `--think`)
- Avaliação da busca: `uv run python evals/run_eval.py --name <experimento>` (grava um CSV em `evals/results/`; rodar com a árvore limpa para o CSV registrar o commit)
- API e interface: preencher conforme os passos forem implementados.
