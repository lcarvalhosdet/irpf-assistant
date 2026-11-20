# Data source

| Field | Value |
|---|---|
| Title | Perguntas e Respostas IRPF 2026 (Receita Federal) |
| Version | 1.00, dated 2026-04-23 |
| Coverage | 2026 return (exercício 2026), calendar year 2025 |
| Listing page | https://www.gov.br/receitafederal/pt-br/centrais-de-conteudo/publicacoes/perguntas-e-respostas/dirpf |
| File URL | https://www.gov.br/receitafederal/pt-br/centrais-de-conteudo/publicacoes/perguntas-e-respostas/dirpf/p-r-irpf-2026-v1-00-2026-04-23.pdf |
| Original filename | `P&R IRPF 2026 - v1.00 - 2026.04.23.pdf` |
| Local path | `data/raw/p-r-irpf-2026-v1-00-2026-04-23.pdf` (not versioned) |
| Size | 4,751,936 bytes, 340 pages |
| SHA-256 | `f3740385c07fa4dc52f8614d009dd5bd038fbeb8bd935f89da4e9bc26ed2a3b0` |
| Downloaded | 2026-11-20 |
| Reuse | The guide states (page 3): "É permitida a reprodução total ou parcial deste manual, desde que citada a fonte." The gov.br site states that its content is published under CC BY-ND 3.0. |

## Derived data

`data/processed/questions.jsonl` is generated from this PDF by `uv run irpf-ingest`
([ADR 0002](../docs/adr/0002-pdf-parser.md)) and is versioned so that CI can check the dataset
and evaluate retrieval without the PDF ([ADR 0003](../docs/adr/0003-version-parsed-dataset.md)).
Text is kept as published; only page numbers, the "Retorno ao sumário" navigation links and line
wraps are removed. This file is the attribution.

## Reproduce

```bash
curl -L -o data/raw/p-r-irpf-2026-v1-00-2026-04-23.pdf \
  "https://www.gov.br/receitafederal/pt-br/centrais-de-conteudo/publicacoes/perguntas-e-respostas/dirpf/p-r-irpf-2026-v1-00-2026-04-23.pdf"
shasum -a 256 data/raw/p-r-irpf-2026-v1-00-2026-04-23.pdf
```
