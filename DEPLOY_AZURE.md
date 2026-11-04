# Deploy no Azure — guia para alunos

Este guia coloca **a sua própria cópia** do agente no ar, em um Azure Web
App só seu, com deploy automático a cada `git push` via GitHub Actions.

O workflow (`.github/workflows/deploy-azure.yml`) já existe no repositório.
Ele não faz nada sozinho — precisa que você configure o Azure e os secrets
do seu fork, nos passos abaixo.

---

## Passo 1 — Fork

Faça um fork deste repositório para a sua conta do GitHub e clone o fork
(não o original).

## Passo 2 — Criar o Azure Web App

No [Azure Portal](https://portal.azure.com):

1. **Create a resource → Web App**
2. Runtime stack: **Python 3.11**
3. Operating System: **Linux**
4. Pricing plan: **Free F1** (suficiente para uma demo)
5. Criar

## Passo 3 — Configurar variáveis do app

No recurso criado, vá em **Configuration → Application settings** e
adicione:

| Nome | Valor |
|---|---|
| `OPENAI_API_KEY` | sua chave da OpenAI (nunca vai para o Git) |
| `SCM_DO_BUILD_DURING_DEPLOYMENT` | `true` |

A segunda é o que faz o Azure instalar o `requirements.txt` automaticamente
a cada deploy (via Oryx).

## Passo 4 — Configurar o Startup Command

Ainda em **Configuration → General settings**, campo **Startup Command**:

```
python -m streamlit run app.py --server.port 8000 --server.address 0.0.0.0
```

Sem isso o Azure não sabe como iniciar um app Streamlit.

## Passo 5 — Baixar o Publish Profile

Na página **Overview** do Web App, clique em **Download publish profile**.
Guarde o arquivo — você vai colar o conteúdo dele no próximo passo.

## Passo 6 — Configurar secrets no seu fork

No GitHub, no seu fork: **Settings → Secrets and variables → Actions → New
repository secret**. Crie dois:

| Nome do secret | Valor |
|---|---|
| `AZURE_WEBAPP_NAME` | o nome que você deu ao Web App |
| `AZURE_WEBAPP_PUBLISH_PROFILE` | conteúdo completo do arquivo baixado no passo 5 |

Para o **eval** do agente rodar no pipeline, crie também:

| Nome do secret | Valor |
|---|---|
| `OPENAI_API_KEY` | a mesma chave da OpenAI do passo 3 (o GitHub não enxerga os Application Settings da Azure) |

Detalhes em [docs/PROMPTS_TESTES.md](docs/PROMPTS_TESTES.md).

## Passo 7 — Deploy

Dê um `git push` na sua `main` (qualquer commit). O **CI** roda primeiro
(build, testes e eval) e, se passar, dispara o **Deploy Azure**, que publica
e confere se o app respondeu. Para publicar sem esperar o CI, vá na aba
**Actions** e rode o workflow **Deploy Azure** manualmente (`Run workflow`).

## Passo 8 — Acessar

```
https://<nome-do-seu-app>.azurewebsites.net
```

---

## Problemas comuns

| Sintoma | Causa provável |
|---|---|
| Tela em branco / erro genérico do Azure | Faltou configurar o Startup Command (passo 4) |
| `OPENAI_API_KEY não encontrada` na tela do app | Faltou o Application Setting `OPENAI_API_KEY` (passo 3), ou o nome está escrito errado |
| Deploy "pulado" com aviso nos logs da Action | Secrets `AZURE_WEBAPP_NAME`/`AZURE_WEBAPP_PUBLISH_PROFILE` não configurados no seu fork (passo 6) |
| Build falha nos logs do Azure, pacotes não encontrados | Faltou `SCM_DO_BUILD_DURING_DEPLOYMENT=true` (passo 3) |
| Erro 401 dentro do app | Chave da OpenAI inválida ou expirada |
| Erro 429 dentro do app | Limite de cota da sua conta OpenAI — normal em uso intenso de aula |
