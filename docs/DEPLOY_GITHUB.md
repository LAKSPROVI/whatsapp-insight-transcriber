# Deploy Seguro via GitHub

Este projeto esta preparado para deploy recorrente via GitHub Actions usando o workflow `/.github/workflows/deploy.yml`.

## Principios

- Nao versionar tokens, chaves privadas ou segredos em arquivos do repositorio.
- Armazenar credenciais apenas em `GitHub Secrets` ou `Environment Secrets` do ambiente `production`.
- Executar deploys apenas pelo workflow do GitHub, evitando acesso manual recorrente por SSH no chat.

## Secrets obrigatorios no GitHub

Configure no ambiente `production` do repositorio os seguintes secrets:

- `HETZNER_SSH_KEY`
- `ANTHROPIC_API_KEY`
- `ANTHROPIC_BASE_URL`
- `POSTGRES_USER`
- `POSTGRES_PASSWORD`
- `POSTGRES_DB`
- `REDIS_PASSWORD`
- `ELASTIC_PASSWORD`
- `GRAFANA_ADMIN_USER`
- `GRAFANA_ADMIN_PASSWORD`
- `SECRET_KEY`
- `JWT_SECRET_KEY`
- `ADMIN_USERNAME`
- `ADMIN_PASSWORD`
- `LETSENCRYPT_EMAIL`

## Token Hetzner

Se for necessario usar API token da Hetzner em automacoes futuras, armazene-o somente como secret no GitHub, por exemplo:

- `HETZNER_API_TOKEN`

Nao grave esse valor em README, docs versionados, workflow YAML ou arquivos `.env.example`.

## Fluxo de deploy

1. Push para `main` ou execucao manual de `workflow_dispatch`
2. GitHub Actions injeta secrets no workflow
3. Workflow sincroniza codigo para o servidor
4. Workflow recria `.env` remoto de forma idempotente
5. Workflow executa backup pre-deploy
6. Workflow sobe stack base
7. Workflow executa bootstrap HTTP -> emissao SSL -> troca para HTTPS
8. Workflow valida `nginx-health`, `/api/health` e disponibilidade publica

## Operacao futura

- Para novos deploys, atualize codigo e dispare o workflow do GitHub.
- Para rotacao de credenciais, altere apenas os secrets no GitHub.
- Para auditoria, consulte o historico do workflow no GitHub Actions.
