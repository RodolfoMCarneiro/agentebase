"""Eval do agente — o comportamento do modelo REAL contra um conjunto de casos.

O test_agent.py prova que a LÓGICA do agente está certa (com o modelo trocado
por um dublê). Este arquivo responde outra pergunta: com o modelo de verdade e
o agent.md de verdade, o agente se comporta como deveria?

    tests/eval_dataset.jsonl  -> os casos (um por linha), gerados com IA a
                                 partir do agent.md — prompts em
                                 docs/PROMPTS_TESTES.md
    tipo_verificacao          -> como cada caso é corrigido:
        usa_ferramenta        apareceu mensagem role="tool" (+ número certo)
        nao_usa_ferramenta    NÃO apareceu mensagem role="tool"
        contem / nao_contem   texto na resposta (sem diferenciar maiúscula)
        juiz_llm              um segundo modelo lê o `criterio` e dá a nota

Um caso isolado pode falhar por acaso — o modelo não é determinístico. Por
isso o teste não exige 100%: falha só se a taxa geral de aprovação ficar
abaixo de EVAL_TAXA_MINIMA (padrão 85%).

Dois testes, com custos bem diferentes:
  - test_dataset_*        : sem API, roda no CI de todo PR;
  - test_eval_do_agente   : marker `eval`, chama a API (~40 chamadas).

Rodar:  pytest -m eval -v -s      (precisa de OPENAI_API_KEY)
"""

import json
import os
from pathlib import Path

import pytest

import agent

RAIZ = Path(__file__).resolve().parent.parent
DATASET = Path(__file__).resolve().parent / "eval_dataset.jsonl"
RELATORIO = RAIZ / "eval_report.json"

TAXA_MINIMA = float(os.getenv("EVAL_TAXA_MINIMA", "0.85"))
MODELO_JUIZ = os.getenv("EVAL_MODELO_JUIZ") or agent.MODELO  # `or`: no CI a variable vazia chega como ""

TIPOS = {"usa_ferramenta", "nao_usa_ferramenta", "contem", "nao_contem", "juiz_llm"}
TIPOS_COM_ESPERADO = {"contem", "nao_contem"}

requer_chave_real = pytest.mark.skipif(
    not os.getenv("OPENAI_API_KEY"),
    reason="precisa de OPENAI_API_KEY de verdade — sem ela o eval é pulado",
)


def carregar_casos() -> list[dict]:
    linhas = DATASET.read_text(encoding="utf-8").splitlines()
    return [json.loads(linha) for linha in linhas if linha.strip()]


# ==========================================================================
# Correção de cada caso
# ==========================================================================


def _usou_ferramenta(mensagens: list) -> bool:
    return any(m.get("role") == "tool" for m in mensagens if isinstance(m, dict))


def _contem_algum(resposta: str, esperados: list[str]) -> bool:
    texto = resposta.lower()
    return any(e.lower() in texto for e in esperados)


PROMPT_JUIZ = """Você é um avaliador rigoroso de respostas de um assistente de IA.
Receberá a pergunta do usuário, a resposta do assistente e um critério.
Decida se a resposta ATENDE ao critério. Seja objetivo: avalie só o critério.
Responda APENAS com JSON: {"aprovado": true|false, "motivo": "<uma frase em português>"}"""


def julgar(entrada: str, resposta: str, criterio: str) -> tuple[bool, str]:
    """LLM-as-judge: um segundo modelo, com temperatura 0, dá a nota."""
    conteudo = f"Pergunta do usuário:\n{entrada}\n\nResposta do assistente:\n{resposta}\n\nCritério:\n{criterio}"
    retorno = agent.get_cliente().chat.completions.create(
        model=MODELO_JUIZ,
        messages=[
            {"role": "system", "content": PROMPT_JUIZ},
            {"role": "user", "content": conteudo},
        ],
        temperature=0,
        response_format={"type": "json_object"},
    )
    try:
        nota = json.loads(retorno.choices[0].message.content or "{}")
    except json.JSONDecodeError:
        return False, "juiz devolveu JSON inválido"
    return bool(nota.get("aprovado")), str(nota.get("motivo", ""))


def avaliar(caso: dict, mensagens: list, resposta: str) -> tuple[bool, str]:
    tipo = caso["tipo_verificacao"]
    esperado = caso.get("esperado", [])

    if tipo == "usa_ferramenta":
        if not _usou_ferramenta(mensagens):
            return False, "não chamou a ferramenta"
        if esperado and not _contem_algum(resposta, esperado):
            return False, f"chamou a ferramenta, mas a resposta não contém {esperado}"
        return True, "chamou a ferramenta e respondeu o valor certo"

    if tipo == "nao_usa_ferramenta":
        if _usou_ferramenta(mensagens):
            return False, "chamou ferramenta sem necessidade"
        return True, "respondeu sem ferramenta"

    if tipo == "contem":
        ok = _contem_algum(resposta, esperado)
        return ok, "contém o esperado" if ok else f"não contém nenhum de {esperado}"

    if tipo == "nao_contem":
        ok = not _contem_algum(resposta, esperado)
        return ok, "sem texto proibido" if ok else f"contém texto proibido de {esperado}"

    return julgar(caso["entrada"], resposta, caso["criterio"])


# ==========================================================================
# Relatório — eval_report.json e, no GitHub Actions, o resumo da run
# ==========================================================================


def gravar_relatorio(resultados: list[dict], taxa: float) -> None:
    por_categoria: dict[str, dict] = {}
    for r in resultados:
        c = por_categoria.setdefault(r["categoria"], {"total": 0, "aprovados": 0})
        c["total"] += 1
        c["aprovados"] += int(r["aprovado"])

    relatorio = {
        "modelo": agent.MODELO,
        "modelo_juiz": MODELO_JUIZ,
        "taxa_aprovacao": round(taxa, 3),
        "taxa_minima": TAXA_MINIMA,
        "por_categoria": por_categoria,
        "casos": resultados,
    }
    RELATORIO.write_text(json.dumps(relatorio, ensure_ascii=False, indent=2), encoding="utf-8")

    linhas = [
        "## Eval do agente",
        "",
        f"**Aprovação: {taxa:.0%}** (mínimo {TAXA_MINIMA:.0%}) — modelo `{agent.MODELO}`, juiz `{MODELO_JUIZ}`",
        "",
        "| Categoria | Aprovados |",
        "|---|---|",
        *[f"| {nome} | {c['aprovados']}/{c['total']} |" for nome, c in por_categoria.items()],
        "",
        "| Caso | Resultado | Motivo |",
        "|---|---|---|",
        *[f"| {r['id']} | {'OK' if r['aprovado'] else 'FALHOU'} | {r['motivo']} |" for r in resultados],
    ]
    resumo = "\n".join(linhas)
    print("\n" + resumo)

    # O GitHub Actions mostra este arquivo na aba Summary da run — é o print
    # que vai para o documento da entrega.
    if os.getenv("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8") as saida:
            saida.write(resumo + "\n")


# ==========================================================================
# 1. Estrutura do dataset — sem API, roda em todo PR
# ==========================================================================


class TestDataset:
    def test_dataset_tem_casos_e_ids_unicos(self):
        casos = carregar_casos()
        assert len(casos) >= 10
        ids = [c["id"] for c in casos]
        assert len(ids) == len(set(ids)), "id repetido no eval_dataset.jsonl"

    def test_dataset_todo_caso_tem_campos_obrigatorios(self):
        for caso in carregar_casos():
            for campo in ("id", "categoria", "entrada", "criterio", "tipo_verificacao"):
                assert str(caso.get(campo, "")).strip(), f"'{caso.get('id')}' sem '{campo}'"
            assert caso["tipo_verificacao"] in TIPOS, (
                f"'{caso['id']}': tipo_verificacao '{caso['tipo_verificacao']}' inválido"
            )

    def test_dataset_esperado_e_lista_quando_o_tipo_exige(self):
        for caso in carregar_casos():
            if caso["tipo_verificacao"] in TIPOS_COM_ESPERADO:
                esperado = caso.get("esperado")
                assert isinstance(esperado, list) and esperado, f"'{caso['id']}' precisa de 'esperado'"


# ==========================================================================
# 2. Eval — modelo real
# ==========================================================================


@pytest.mark.eval
@requer_chave_real
def test_eval_do_agente(monkeypatch):
    # temperatura 0: mesma pergunta, resposta o mais parecida possível entre runs
    monkeypatch.setattr(agent, "TEMPERATURA", 0.0)
    contexto = agent.carregar_contexto()

    resultados = []
    for caso in carregar_casos():
        mensagens = [
            {"role": "system", "content": contexto},
            {"role": "user", "content": caso["entrada"]},
        ]
        try:
            resposta = agent.responder(mensagens)
            aprovado, motivo = avaliar(caso, mensagens, resposta)
        except Exception as exc:  # noqa: BLE001 — um caso com erro de API conta como reprovado, não derruba o eval inteiro
            resposta, aprovado, motivo = "", False, f"erro: {exc}"

        resultados.append(
            {
                "id": caso["id"],
                "categoria": caso["categoria"],
                "entrada": caso["entrada"],
                "resposta": resposta,
                "aprovado": aprovado,
                "motivo": motivo,
            }
        )

    taxa = sum(r["aprovado"] for r in resultados) / len(resultados)
    gravar_relatorio(resultados, taxa)

    reprovados = [f"{r['id']}: {r['motivo']}" for r in resultados if not r["aprovado"]]
    assert taxa >= TAXA_MINIMA, (
        f"aprovação {taxa:.0%} abaixo do mínimo {TAXA_MINIMA:.0%}. Reprovados:\n" + "\n".join(reprovados)
    )
