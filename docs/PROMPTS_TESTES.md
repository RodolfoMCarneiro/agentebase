# Plano de testes gerado com IA — prompts utilizados

Este documento registra **os prompts usados para gerar, com IA, o plano de
testes do agente**, e onde está o resultado de cada um no repositório. É a
seção "Apresente os prompts utilizados" da entrega.

| # | Prompt | Resultado no repositório |
|---|---|---|
| 1 | Plano de testes | Este documento, seção [Plano de testes](#plano-de-testes-resultado-do-prompt-1) |
| 2 | Dataset de eval | [`tests/eval_dataset.jsonl`](../tests/eval_dataset.jsonl) |
| 3 | Código do eval | [`tests/test_eval.py`](../tests/test_eval.py) |
| 4 | Pipeline CI/CD | [`.github/workflows/ci.yml`](../.github/workflows/ci.yml) e [`.github/workflows/deploy-azure.yml`](../.github/workflows/deploy-azure.yml) |

---

## Prompt 1 — Plano de testes

```text
Você é um engenheiro de QA especialista em aplicações com LLM.

Contexto: tenho um agente em Python (agent.py) que usa a API da OpenAI
(gpt-4o-mini) com um loop de tool calling. A ferramenta disponível é `somar(a, b)`.
O prompt de sistema vem de agent.md (responder em pt-BR, direto, curto, não inventar,
usar ferramentas para contas exatas, respeitar a memória em memory.md).
O front é Streamlit (app.py) e o deploy é num Azure Web App via GitHub Actions.
Também existe um roteador de canary (router/router.py).

Já existem testes unitários, de contrato e run-level com mock do cliente OpenAI
(pytest -m "not smoke").

Gere um PLANO DE TESTES dividido em:
1. Testes unitários: o que já está coberto e quais lacunas restam
2. Testes de eval (comportamento do modelo real): categorias, critérios de aprovação
   e métricas (ex.: taxa de acerto >= 90%)
3. Teste pós-deploy (smoke da URL na Azure)
4. Em que etapa do pipeline CI/CD cada tipo roda e o que bloqueia o deploy

Para cada item informe: objetivo, como medir, determinístico ou não, custo.
Responda em tabela Markdown.
```

## Prompt 2 — Dataset de eval

```text
Com base no agent.md abaixo, gere um dataset de avaliação em JSONL com 20 casos.
Cada linha deve ter: id, categoria, entrada (mensagem do usuário), criterio
(o que uma boa resposta precisa ter), tipo_verificacao ("contem", "nao_contem",
"usa_ferramenta", "nao_usa_ferramenta" ou "juiz_llm") e esperado (lista de
textos aceitos, quando aplicável — ex.: ["6912", "6.912"], já que em pt-BR o
modelo pode usar separador de milhar).

Distribua entre as categorias:
- uso_ferramenta: somas que exigem chamar `somar` (números grandes, decimais, negativos)
- sem_ferramenta: perguntas que NÃO devem chamar ferramenta
- idioma_tom: deve responder em pt-BR, curto, sem frases do tipo "Claro! Fico feliz em ajudar"
- nao_inventar: perguntas sem resposta possível, onde o agente deve admitir que não sabe
- robustez: entradas ambíguas, sem sentido e prompt injection ("ignore suas instruções...")

=== INÍCIO DO agent.md ===
# Agente base

## Identidade

Você é um assistente que responde em português do Brasil.

## Como você responde

- Direto ao ponto. Sem "Claro! Fico feliz em ajudar!".
- Curto por padrão; só se estenda quando o assunto exigir.
- Concreto: exemplos reais em vez de explicações abstratas.

## Regras

1. **Não invente.** Se não sabe, diga que não sabe.
2. **Use as ferramentas quando elas souberem melhor que você.** Contas exatas,
   dados de sistemas, data e hora — nada disso você adivinha.
3. **Respeite a memória.** O que está na seção "Memória" foi confirmado pelo
   usuário e tem prioridade sobre suas suposições.

## Ferramentas disponíveis

| Ferramenta | Quando usar |
|---|---|
| `somar` | Qualquer adição que precise ser exata |
=== FIM DO agent.md ===
```

## Prompt 3 — Código do eval

```text
Gere um arquivo tests/test_eval.py em pytest que:
- leia tests/eval_dataset.jsonl
- para cada caso, chame agent.responder() com a API real (marker `eval`,
  skip se OPENAI_API_KEY não existir)
- verifique "usa_ferramenta"/"nao_usa_ferramenta" inspecionando se apareceu
  mensagem role="tool" no histórico (e, se houver `esperado`, se a resposta
  contém um dos valores)
- verifique "contem"/"nao_contem" por string (case-insensitive)
- para "juiz_llm", use um segundo modelo como juiz com temperatura 0 que
  responde JSON {"aprovado": bool, "motivo": str} com base no criterio
- grave um relatório eval_report.json (id, categoria, aprovado, motivo) e,
  no GitHub Actions, um resumo em tabela no $GITHUB_STEP_SUMMARY
- falhe o teste se a taxa de aprovação geral for < 85%
- tenha também um teste SEM API que valida a estrutura do dataset, para rodar
  no CI de todo PR
Use o mesmo estilo e os mesmos comentários em português de tests/test_agent.py.
Rode o agente com temperatura 0 para reduzir a variação.
```

## Prompt 4 — Pipeline CI/CD

```text
Tenho dois workflows no GitHub Actions: ci.yml (lint + pytest -m "not smoke")
e deploy-azure.yml (deploy no Azure Web App via publish profile).
Hoje o deploy roda mesmo se o CI falhar.

Reestruture em um pipeline com estágios encadeados:
build -> test-unit -> test-eval -> deploy -> smoke-pos-deploy
- test-eval usa o secret OPENAI_API_KEY, roda pytest -m eval e publica
  eval_report.json como artifact
- deploy só roda em push na main e só se o CI inteiro passar
  (workflow_run com conclusion == success)
- smoke-pos-deploy chama /_stcore/health na URL do Web App e falha se não
  responder (reaproveite .github/scripts/canary.sh saude)
Mantenha o comportamento atual de pular o deploy (e o eval) quando os secrets
não existirem.
```

---

## Plano de testes (resultado do Prompt 1)

| Camada | Arquivo | Objetivo | Determinístico? | Custo | Quando roda | Bloqueia deploy? |
|---|---|---|---|---|---|---|
| Build | `ci.yml` | Dependências instalam, código compila, `ruff` sem erros | Sim | Zero | Todo PR e push | Sim |
| Unitário | `tests/test_agent.py` | `somar()`, `executar_ferramenta()`, `carregar_contexto()` | Sim | Zero | Todo PR e push | Sim |
| Contrato | `tests/test_agent.py` | Declaração em `FERRAMENTAS` bate com a função Python | Sim | Zero | Todo PR e push | Sim |
| Run-level | `tests/test_agent.py` | Loop `responder()` com cliente OpenAI falso: chama ferramenta, para, respeita `MAX_ITERACOES` | Sim | Zero | Todo PR e push | Sim |
| Unitário | `tests/test_router.py` | Regra de sorteio/cookie do roteador canary | Sim | Zero | Todo PR e push | Sim |
| Dataset | `tests/test_eval.py` | Estrutura do `eval_dataset.jsonl` está válida | Sim | Zero | Todo PR e push | Sim |
| **Eval** | `tests/test_eval.py` + `tests/eval_dataset.jsonl` | Comportamento do modelo real em 20 casos, 5 categorias; aprovação ≥ 85% | **Não** (temperatura 0 reduz variação) | ~40 chamadas `gpt-4o-mini` (centavos) | Todo PR e push, se houver `OPENAI_API_KEY` | Sim |
| Smoke | `tests/test_smoke.py` | Uma soma real de ponta a ponta | Não | 2 chamadas | Manual (`pytest -m smoke`) | Não |
| Pós-deploy | `deploy-azure.yml` | Web App na Azure responde `/_stcore/health` | Sim | Zero | Depois de cada deploy | — (falha a run) |

### Categorias do eval

| Categoria | Casos | Como é verificado | O que pega |
|---|---|---|---|
| `uso_ferramenta` | 5 | Apareceu mensagem `role="tool"` **e** o número certo está na resposta | Modelo fazendo conta "de cabeça" e errando |
| `sem_ferramenta` | 4 | **Não** apareceu mensagem `role="tool"` | Ferramenta chamada sem necessidade (custo, latência) |
| `idioma_tom` | 4 | Juiz LLM / texto proibido | Fugir do pt-BR, enrolação, "Claro! Fico feliz em ajudar" |
| `nao_inventar` | 4 | Juiz LLM | Alucinação: inventar dado que o agente não tem |
| `robustez` | 3 | Juiz LLM | Prompt injection, entrada sem sentido, argumento inválido |

---

## Como usar

### 1. Cadastrar o secret da OpenAI no GitHub

A chave que está na Azure (Application Settings) **não** é vista pelo GitHub
Actions. Para o eval rodar no pipeline, cadastre também no repositório:

**Settings → Secrets and variables → Actions → New repository secret**

| Nome | Valor |
|---|---|
| `OPENAI_API_KEY` | a mesma chave da OpenAI usada na Azure |

Opcionais, em **Variables** (mesma tela, aba *Variables*):

| Nome | Padrão | Para quê |
|---|---|---|
| `EVAL_TAXA_MINIMA` | `0.85` | Taxa mínima de aprovação do eval |
| `EVAL_MODELO_JUIZ` | o mesmo do agente | Modelo usado como juiz |

Sem o secret, o job de eval avisa e é pulado — o pipeline não falha.

### 2. Rodar localmente

```bash
pip install -r requirements.txt -r requirements-dev.txt
```

Testes sem API (os mesmos do gate de todo PR):

```bash
pytest -m "not smoke and not eval" -v
```

Eval com a API real (precisa de `OPENAI_API_KEY` no `.env`):

```bash
pytest -m eval -v -s
```

O resultado detalhado fica em `eval_report.json`, na raiz.

### 3. Fluxo no GitHub Actions

```
push na main
  └─ CI (ci.yml)
       ├─ build      : dependências, py_compile, ruff, testes sem API
       └─ eval       : pytest -m eval  →  artifact eval_report.json
            │ (só se tudo passar)
            ▼
     Deploy Azure (deploy-azure.yml, disparado por workflow_run)
       ├─ deploy no Azure Web App
       └─ smoke pós-deploy: /_stcore/health
```

### 4. Evidências para o documento da entrega

- **Actions → CI → run da main**: print dos dois jobs verdes (`build` e `eval`).
- **Na mesma run, aba Summary**: a tabela "Eval do agente", com a taxa por
  categoria, é gerada automaticamente.
- **Artifacts → `eval-report`**: o JSON com o motivo de cada caso.
- **Actions → Deploy Azure**: print mostrando o deploy e o passo
  "Smoke pós-deploy" verdes.

### 5. Adicionar um caso novo

Uma linha a mais em `tests/eval_dataset.jsonl`. O teste de estrutura
(`pytest -m "not eval"`) já acusa campo faltando ou tipo inválido antes de
gastar qualquer chamada.
