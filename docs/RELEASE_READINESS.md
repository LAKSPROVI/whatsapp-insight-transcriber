# Release Readiness

Este checklist resume o que precisa estar pronto para executar releases com seguranca.

## GitHub

- Environment `production` criado
- Secrets configurados no ambiente `production`
- Workflow `/.github/workflows/deploy.yml` habilitado
- Branch `main` protegida conforme politica da equipe

## Secrets obrigatorios

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

## Servidor

- Docker e Docker Compose instalados
- DNS do dominio apontando para o servidor
- Porta 80 liberada para bootstrap ACME
- Porta 443 liberada para trafego HTTPS
- Porta 22 restrita conforme politica de acesso

## Aplicacao

- `.env` remoto gerado apenas pelo workflow
- `docker-compose.yml` sincronizado com o servidor
- `nginx/nginx.conf` e `nginx/nginx-http.conf` presentes
- `scripts/init-ssl.sh` presente e executavel
- `scripts/backup.sh` presente e revisado

## Validacoes pos-deploy

- `https://transcriber.jurislaw.com.br/nginx-health`
- `https://transcriber.jurislaw.com.br/api/health`
- `https://transcriber.jurislaw.com.br/api/docs`
- `/metrics` disponivel internamente para Prometheus
- Containers `backend`, `frontend`, `nginx`, `postgres`, `redis` saudaveis
- Frontend resolvendo WebSocket e API por same-origin ou `NEXT_PUBLIC_API_URL` coerente
- Mídias protegidas carregando com autenticacao conforme contrato frontend/backend

## Seguranca

- Nenhum segredo versionado em arquivos do repositorio
- Tokens e chaves apenas em GitHub Secrets
- Workflow usando `environment: production`
- Sem deploy manual recorrente via segredos enviados no chat
