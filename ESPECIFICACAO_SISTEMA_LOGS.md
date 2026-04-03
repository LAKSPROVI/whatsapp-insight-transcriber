# Especificacao Tecnica - Sistema de Logs Estruturados

> **Projeto:** WhatsApp Insight Transcriber  
> **Versao:** 1.0.0  
> **Data:** 2026-04-03  
> **Stack:** FastAPI (Python 3.12) + Next.js 14 + PostgreSQL + Redis + Docker  
> **Status:** Especificacao Aprovada para Implementacao

---

## 1. Objetivo e Escopo

### 1.1 Objetivo

Implantar um sistema de logging estruturado, centralizado e observavel que registre todas as acoes do sistema WhatsApp Insight Transcriber, cobrindo:

- Acoes de usuarios (upload, consulta, exportacao, chat RAG)
- Processamento de pipeline (parse, transcricao, analise IA)
- Comunicacao entre servicos (backend, frontend, Claude API, PostgreSQL, Redis)
- Eventos de seguranca (autenticacao, autorizacao, acessos)
- Erros, falhas e metricas de desempenho

### 1.2 Escopo

| Componente | Cobertura |
|---|---|
| Backend FastAPI | Todos os endpoints, servicos, middlewares, tarefas async |
| Frontend Next.js | Erros client-side, acoes de usuario, chamadas API |
| PostgreSQL | Queries lentas, erros de conexao, migracao |
| Redis | Cache hits/misses, expiracoes, falhas |
| Claude API | Chamadas, latencia, tokens, erros, retries |
| Nginx | Access logs, error logs, rate limiting |
| Docker/Infra | Health checks, restarts, uso de recursos |

### 1.3 Fora do Escopo

- Monitoramento de rede de baixo nivel (NetFlow, packet capture)
- Logs de sistema operacional nao relacionados a aplicacao
- Metricas de hardware (CPU/RAM/disco) - cobertos por ferramentas de infra separadas

---

## 2. Requisitos de Dados - Campos Capturados

### 2.1 Campos Obrigatorios

| Campo | Tipo | Descricao | Exemplo |
|---|---|---|---|
| `timestamp` | string (ISO 8601) | Data/hora UTC com microsegundos | `"2026-04-03T18:02:06.123456Z"` |
| `level` | string (enum) | Nivel do log | `"INFO"` |
| `service` | string | Nome do servico emissor | `"wit-backend"` |
| `event` | string | Identificador do evento | `"conversation.upload.completed"` |
| `message` | string | Descricao legivel | `"Upload processado com sucesso"` |
| `trace_id` | string (UUID v4) | ID de rastreamento distribuido | `"a1b2c3d4-e5f6-..."` |
| `span_id` | string (hex 16) | ID do span atual | `"1a2b3c4d5e6f7890"` |
| `request_id` | string (UUID v4) | ID unico da requisicao HTTP | `"f1e2d3c4-b5a6-..."` |
| `environment` | string | Ambiente de execucao | `"production"` |
| `version` | string | Versao da aplicacao | `"1.0.0"` |

### 2.2 Campos Contextuais (quando aplicaveis)

| Campo | Tipo | Descricao | Redacao |
|---|---|---|---|
| `user.id` | string | ID do usuario autenticado | Nao |
| `user.role` | string | Papel do usuario | Nao |
| `user.ip` | string | Endereco IP do cliente | Anonimizar ultimo octeto em producao |
| `user.session_id` | string | ID da sessao | Nao |
| `user.user_agent` | string | User-Agent do navegador | Truncar a 256 chars |
| `http.method` | string | Metodo HTTP | Nao |
| `http.url` | string | URL requisitada | Remover query params sensiveis |
| `http.status_code` | integer | Codigo de resposta HTTP | Nao |
| `http.duration_ms` | float | Duracao da requisicao em ms | Nao |
| `http.request_size` | integer | Tamanho do corpo da requisicao (bytes) | Nao |
| `http.response_size` | integer | Tamanho do corpo da resposta (bytes) | Nao |

### 2.3 Campos de Erro (quando `level` >= ERROR)

| Campo | Tipo | Descricao |
|---|---|---|
| `error.type` | string | Classe/tipo do erro |
| `error.code` | string | Codigo de erro interno |
| `error.message` | string | Mensagem do erro (redacao de dados sensiveis) |
| `error.stack_trace` | string | Stack trace completo (apenas DEBUG/dev) |
| `error.suggestion` | string | Recomendacao automatica de correcao |
| `error.severity` | string | `critical`, `high`, `medium`, `low` |
| `error.retry_count` | integer | Numero de tentativas realizadas |

### 2.4 Campos de Recurso/Operacao

| Campo | Tipo | Descricao |
|---|---|---|
| `resource.type` | string | Tipo de recurso (`conversation`, `message`, `media`, `export`) |
| `resource.id` | string | ID do recurso |
| `resource.action` | string | Acao executada (`create`, `read`, `update`, `delete`, `process`) |
| `operation.name` | string | Nome da operacao (`claude.transcribe`, `whatsapp.parse`) |
| `operation.duration_ms` | float | Duracao da operacao |
| `operation.status` | string | `success`, `failure`, `timeout`, `cancelled` |
| `operation.params` | object | Parametros da operacao (com redacao) |

### 2.5 Campos de IA/Claude API

| Campo | Tipo | Descricao |
|---|---|---|
| `ai.model` | string | Modelo utilizado |
| `ai.tokens_input` | integer | Tokens de entrada |
| `ai.tokens_output` | integer | Tokens de saida |
| `ai.latency_ms` | float | Latencia da chamada |
| `ai.cost_usd` | float | Custo estimado da chamada |
| `ai.agent_id` | string | ID do agente no orquestrador |

### 2.6 Regras de Redacao de Dados Sensiveis

| Dado | Regra | Exemplo |
|---|---|---|
| Senhas | Nunca logar | Campo omitido |
| Tokens JWT | Hash SHA-256 dos ultimos 8 chars | `"jwt_hash:a1b2c3d4"` |
| Numeros de telefone | Mascarar digitos centrais | `"+55 11 9****-1234"` |
| Conteudo de mensagens | Nao logar em producao | `"[REDACTED]"` |
| Nomes de participantes | Pseudonimizar | `"user_hash:x7y8z9"` |
| API Keys | Nunca logar | `"[REDACTED]"` |
| IPs em producao | Anonimizar ultimo octeto | `"192.168.1.xxx"` |
| Parametros de query | Remover `token`, `key`, `password`, `secret` | `"?token=[REDACTED]"` |
| Conteudo de arquivos | Hash + tamanho apenas | `"file_hash:abc123, size:1.2MB"` |

---

## 3. Formato e Estrutura de Logs

### 3.1 Formato

Todos os logs devem ser emitidos em **JSON estruturado**, uma linha por evento (JSON Lines / NDJSON). Sem logs multi-linha em producao.

### 3.2 Esquema de Log Definitivo (JSON Schema)

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "WIT Log Entry",
  "type": "object",
  "required": [
    "timestamp", "level", "service", "event", "message",
    "trace_id", "span_id", "request_id", "environment", "version"
  ],
  "properties": {
    "timestamp": {
      "type": "string",
      "format": "date-time",
      "description": "ISO 8601 UTC com microsegundos"
    },
    "level": {
      "type": "string",
      "enum": ["DEBUG", "INFO", "WARN", "ERROR"]
    },
    "service": {
      "type": "string",
      "enum": ["wit-backend", "wit-frontend", "wit-nginx", "wit-worker"]
    },
    "event": {
      "type": "string",
      "pattern": "^[a-z]+\\.[a-z_]+\\.[a-z_]+$",
      "description": "Formato: dominio.recurso.acao"
    },
    "message": { "type": "string", "maxLength": 1024 },
    "trace_id": { "type": "string", "format": "uuid" },
    "span_id": { "type": "string", "pattern": "^[a-f0-9]{16}$" },
    "request_id": { "type": "string", "format": "uuid" },
    "parent_span_id": { "type": ["string", "null"] },
    "environment": {
      "type": "string",
      "enum": ["development", "staging", "production"]
    },
    "version": { "type": "string" },
    "user": {
      "type": "object",
      "properties": {
        "id": { "type": "string" },
        "role": { "type": "string", "enum": ["admin", "user", "anonymous"] },
        "ip": { "type": "string" },
        "session_id": { "type": "string" },
        "user_agent": { "type": "string", "maxLength": 256 }
      }
    },
    "http": {
      "type": "object",
      "properties": {
        "method": { "type": "string" },
        "url": { "type": "string" },
        "status_code": { "type": "integer" },
        "duration_ms": { "type": "number" },
        "request_size": { "type": "integer" },
        "response_size": { "type": "integer" }
      }
    },
    "error": {
      "type": "object",
      "properties": {
        "type": { "type": "string" },
        "code": { "type": "string" },
        "message": { "type": "string" },
        "stack_trace": { "type": "string" },
        "suggestion": { "type": "string" },
        "severity": { "type": "string", "enum": ["critical", "high", "medium", "low"] },
        "retry_count": { "type": "integer" }
      }
    },
    "resource": {
      "type": "object",
      "properties": {
        "type": { "type": "string" },
        "id": { "type": "string" },
        "action": { "type": "string" }
      }
    },
    "operation": {
      "type": "object",
      "properties": {
        "name": { "type": "string" },
        "duration_ms": { "type": "number" },
        "status": { "type": "string", "enum": ["success", "failure", "timeout", "cancelled"] },
        "params": { "type": "object" }
      }
    },
    "ai": {
      "type": "object",
      "properties": {
        "model": { "type": "string" },
        "tokens_input": { "type": "integer" },
        "tokens_output": { "type": "integer" },
        "latency_ms": { "type": "number" },
        "cost_usd": { "type": "number" },
        "agent_id": { "type": "string" }
      }
    },
    "metadata": {
      "type": "object",
      "description": "Campos adicionais especificos do contexto",
      "additionalProperties": true
    }
  },
  "additionalProperties": false
}
```

### 3.3 Exemplos de Logs

#### Log de Sucesso - Upload de Conversa

```json
{
  "timestamp": "2026-04-03T18:02:06.123456Z",
  "level": "INFO",
  "service": "wit-backend",
  "event": "conversation.upload.completed",
  "message": "Upload de conversa processado com sucesso",
  "trace_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "span_id": "1a2b3c4d5e6f7890",
  "request_id": "f1e2d3c4-b5a6-7890-cdef-123456789abc",
  "parent_span_id": null,
  "environment": "production",
  "version": "1.0.0",
  "user": {
    "id": "usr_42",
    "role": "admin",
    "ip": "192.168.1.xxx",
    "session_id": "sess_abc123def456",
    "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
  },
  "http": {
    "method": "POST",
    "url": "/api/conversations/upload",
    "status_code": 200,
    "duration_ms": 2340.5,
    "request_size": 15728640,
    "response_size": 512
  },
  "resource": {
    "type": "conversation",
    "id": "conv_789",
    "action": "create"
  },
  "operation": {
    "name": "conversation.upload",
    "duration_ms": 2340.5,
    "status": "success",
    "params": {
      "file_hash": "sha256:abc123...",
      "file_size_bytes": 15728640,
      "file_type": "application/zip"
    }
  },
  "metadata": {
    "messages_count": 1542,
    "media_count": 87,
    "participants_count": 3
  }
}
```

#### Log de Erro - Falha na Claude API

```json
{
  "timestamp": "2026-04-03T18:05:12.789012Z",
  "level": "ERROR",
  "service": "wit-backend",
  "event": "ai.transcription.failed",
  "message": "Falha na transcricao de audio via Claude API",
  "trace_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "span_id": "2b3c4d5e6f708901",
  "request_id": "f1e2d3c4-b5a6-7890-cdef-123456789abc",
  "parent_span_id": "1a2b3c4d5e6f7890",
  "environment": "production",
  "version": "1.0.0",
  "user": {
    "id": "usr_42",
    "role": "admin",
    "ip": "192.168.1.xxx",
    "session_id": "sess_abc123def456"
  },
  "resource": {
    "type": "media",
    "id": "media_456",
    "action": "process"
  },
  "operation": {
    "name": "claude.transcribe_audio",
    "duration_ms": 30000,
    "status": "timeout",
    "params": {
      "media_type": "audio/ogg",
      "media_size_bytes": 524288
    }
  },
  "ai": {
    "model": "claude-opus-4-6",
    "tokens_input": 0,
    "tokens_output": 0,
    "latency_ms": 30000,
    "cost_usd": 0.0,
    "agent_id": "agent_07"
  },
  "error": {
    "type": "TimeoutError",
    "code": "AI_TIMEOUT_001",
    "message": "Claude API nao respondeu dentro do timeout de 30s",
    "severity": "high",
    "retry_count": 3,
    "suggestion": "Verificar status da API Claude em status.anthropic.com. Considerar aumentar timeout ou reduzir tamanho do payload. Verificar conectividade com api.gameron.me."
  }
}
```

#### Log DEBUG - Cache Redis

```json
{
  "timestamp": "2026-04-03T18:02:06.100000Z",
  "level": "DEBUG",
  "service": "wit-backend",
  "event": "cache.redis.miss",
  "message": "Cache miss para chave de conversa",
  "trace_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "span_id": "3c4d5e6f70890123",
  "request_id": "f1e2d3c4-b5a6-7890-cdef-123456789abc",
  "parent_span_id": "1a2b3c4d5e6f7890",
  "environment": "development",
  "version": "1.0.0",
  "operation": {
    "name": "redis.get",
    "duration_ms": 1.2,
    "status": "success",
    "params": {
      "key_pattern": "conv:*:summary",
      "ttl_seconds": 3600
    }
  }
}
```

#### Log WARN - Rate Limiting

```json
{
  "timestamp": "2026-04-03T18:10:00.000000Z",
  "level": "WARN",
  "service": "wit-backend",
  "event": "security.rate_limit.exceeded",
  "message": "Rate limit excedido para usuario",
  "trace_id": "b2c3d4e5-f6a7-8901-bcde-f12345678901",
  "span_id": "4d5e6f7089012345",
  "request_id": "e2d3c4b5-a6f7-8901-cdef-234567890abc",
  "parent_span_id": null,
  "environment": "production",
  "version": "1.0.0",
  "user": {
    "id": "usr_99",
    "role": "user",
    "ip": "10.0.1.xxx",
    "session_id": "sess_xyz789"
  },
  "http": {
    "method": "POST",
    "url": "/api/chat",
    "status_code": 429,
    "duration_ms": 5.0
  },
  "metadata": {
    "limit": 60,
    "window_seconds": 60,
    "current_count": 61
  }
}
```

---

## 4. Niveis de Log e Regras de Roteamento

### 4.1 Definicao de Niveis

| Nivel | Uso | Exemplos |
|---|---|---|
| **DEBUG** | Informacao detalhada para desenvolvimento. Desabilitado em producao por padrao. | Cache miss, query SQL executada, parsing de mensagem individual |
| **INFO** | Eventos operacionais normais. Registro de acoes bem-sucedidas. | Upload concluido, usuario autenticado, exportacao gerada |
| **WARN** | Situacao anormal que nao impede operacao, mas requer atencao. | Rate limit proximo, retry em andamento, deprecation, disco >80% |
| **ERROR** | Falha que impede conclusao de uma operacao. Requer acao. | Falha na API Claude, erro de banco, arquivo corrompido |

### 4.2 Regras de Roteamento por Ambiente

| Destino | Development | Staging | Production |
|---|---|---|---|
| **stdout/console** | DEBUG+ (colorido, pretty-print) | INFO+ (JSON) | INFO+ (JSON) |
| **Arquivo local** | Nao | WARN+ (rotacao diaria) | INFO+ (rotacao diaria, 7 dias) |
| **SIEM** | Nao | ERROR+ | WARN+ |
| **Data Lake** | Nao | INFO+ (batch 5min) | INFO+ (batch 1min) |
| **Cloud Logging** | Nao | INFO+ | INFO+ (streaming) |
| **Alerta imediato** | Nao | ERROR (Slack) | ERROR (PagerDuty + Slack) |

### 4.3 Regras de Roteamento por Tipo de Evento

| Tipo de Evento | Destinos Adicionais |
|---|---|
| `security.*` | SIEM (tempo real), arquivo de auditoria separado |
| `error.*` com severity=critical | PagerDuty, Slack #incidents, email de plantao |
| `ai.*` | Data Lake para analise de custo e performance |
| `http.*` com duration_ms > 5000 | Dashboard de performance, alerta WARN |
| `conversation.upload.*` | Metricas de negocio, analytics |

---

## 5. Correlacao entre Servicos Distribuidos

### 5.1 Padrao de Propagacao

```
[Nginx] --trace_id, span_id--> [FastAPI] --trace_id, child_span_id--> [Claude API]
                                    |
                                    +--trace_id, child_span_id--> [PostgreSQL]
                                    |
                                    +--trace_id, child_span_id--> [Redis]
```

### 5.2 Regras de Geracao e Propagacao

| Campo | Gerado por | Propagado via |
|---|---|---|
| `trace_id` | Primeiro servico que recebe a requisicao (Nginx ou Backend) | Header `X-Trace-ID` |
| `span_id` | Cada servico/operacao gera o seu | Header `X-Span-ID` |
| `parent_span_id` | Span do chamador | Header `X-Parent-Span-ID` |
| `request_id` | Middleware do Backend | Header `X-Request-ID` |

### 5.3 Implementacao - Middleware FastAPI

```python
# app/middleware/tracing.py
import uuid
import time
from contextvars import ContextVar
from starlette.middleware.base import BaseHTTPMiddleware

trace_id_var: ContextVar[str] = ContextVar("trace_id", default="")
span_id_var: ContextVar[str] = ContextVar("span_id", default="")
request_id_var: ContextVar[str] = ContextVar("request_id", default="")

class TracingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        trace_id = request.headers.get("X-Trace-ID", str(uuid.uuid4()))
        span_id = uuid.uuid4().hex[:16]
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))

        trace_id_var.set(trace_id)
        span_id_var.set(span_id)
        request_id_var.set(request_id)

        start_time = time.perf_counter()
        response = await call_next(request)
        duration_ms = (time.perf_counter() - start_time) * 1000

        response.headers["X-Trace-ID"] = trace_id
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Duration-Ms"] = f"{duration_ms:.2f}"

        return response
```

### 5.4 Idempotencia de Logs

Para acoes repetidas (retries, reprocessamento), o log deve conter:

| Campo | Descricao |
|---|---|
| `idempotency_key` | Chave unica da operacao original |
| `error.retry_count` | Numero da tentativa atual |
| `metadata.is_retry` | `true` se for uma nova tentativa |
| `metadata.original_request_id` | `request_id` da primeira tentativa |

Regras:
- Cada retry gera um novo `span_id` mas mantém o mesmo `trace_id`
- O campo `idempotency_key` e composto por `{user_id}:{resource_type}:{resource_id}:{action}:{hash_params}`
- Logs duplicados exatos (mesmo `request_id` + `event`) sao descartados pelo coletor

---

## 6. Arquitetura do Pipeline de Logs

### 6.1 Visao Geral

```
+-------------------+     +-------------------+     +-------------------+
|   FONTES DE LOG   |     |   COLETA/ENVIO    |     |   ARMAZENAMENTO   |
+-------------------+     +-------------------+     +-------------------+
|                   |     |                   |     |                   |
| FastAPI (structlog)---->| Fluent Bit        |---->| Elasticsearch     |
| Next.js (pino)   ----->| (sidecar/DaemonSet)|    | (hot: 7d)         |
| Nginx (JSON)     ----->|                   |---->| S3/MinIO           |
| PostgreSQL       ----->| Buffer em disco   |     | (warm: 90d)       |
| Redis            ----->| Compressao gzip   |---->| Glacier/Archive    |
| Docker daemon    ----->| TLS em transito   |     | (cold: 365d+)     |
|                   |     |                   |     |                   |
+-------------------+     +-------------------+     +-------------------+
                                                           |
                                                    +------+------+
                                                    |  CONSUMO    |
                                                    +-------------+
                                                    | Kibana      |
                                                    | Grafana     |
                                                    | AlertManager|
                                                    | Analytics   |
                                                    +-------------+
```

### 6.2 Componentes Detalhados

#### Fontes de Log

| Fonte | Biblioteca | Formato de Saida |
|---|---|---|
| FastAPI | `structlog` + `python-json-logger` | JSON para stdout |
| Next.js | `pino` | JSON para stdout |
| Nginx | `log_format json_combined` | JSON para arquivo + stdout |
| PostgreSQL | `log_destination = 'csvlog'` | CSV convertido para JSON pelo coletor |
| Redis | `logfile` padrao | Texto convertido para JSON pelo coletor |

#### Coletor/Shipper

**Fluent Bit** (recomendado) - agente leve (<5MB RAM por container):

```ini
# fluent-bit.conf
[SERVICE]
    Flush        1
    Log_Level    warn
    Parsers_File parsers.conf
    HTTP_Server  On
    HTTP_Listen  0.0.0.0
    HTTP_Port    2020

[INPUT]
    Name         forward
    Listen       0.0.0.0
    Port         24224
    Tag          wit.*

[INPUT]
    Name         tail
    Path         /var/log/containers/wit_*.log
    Parser       docker
    Tag          docker.*
    Refresh_Interval 5
    Mem_Buf_Limit 10MB

[FILTER]
    Name         modify
    Match        *
    Add          cluster wit-production
    Add          collected_at ${HOSTNAME}

[FILTER]
    Name         lua
    Match        *
    Script       redact.lua
    Call         redact_sensitive

[OUTPUT]
    Name         es
    Match        *
    Host         elasticsearch
    Port         9200
    Index        wit-logs-%Y.%m.%d
    TLS          On
    TLS.Verify   On
    Retry_Limit  5
    Buffer_Size  10MB

[OUTPUT]
    Name         s3
    Match        *
    Bucket       wit-logs-archive
    Region       sa-east-1
    Total_file_size 50M
    Upload_timeout  10m
    Use_put_object  On
    Compression  gzip
```

#### Transporte Seguro

- TLS 1.3 obrigatorio entre todos os componentes
- mTLS entre Fluent Bit e Elasticsearch em producao
- Certificados gerenciados via cert-manager ou Let's Encrypt
- Sem transmissao de logs em texto plano em nenhum cenario

### 6.3 Arquitetura de Armazenamento

#### Camadas de Armazenamento

| Camada | Tecnologia | Retencao | Dados | Indice |
|---|---|---|---|---|
| **Hot** | Elasticsearch (SSD) | 7 dias | Todos os niveis | Completo, busca full-text |
| **Warm** | Elasticsearch (HDD) | 90 dias | INFO+ | Reduzido, campos principais |
| **Cold** | S3/MinIO (gzip) | 365 dias | WARN+ | Apenas metadados no catalogo |
| **Archive** | S3 Glacier / tape | 5+ anos | Auditoria e seguranca | Nenhum (sob demanda) |

#### Particionamento

```
wit-logs-{ambiente}-{YYYY.MM.DD}
  |-- shard por service (backend, frontend, nginx)
  |-- rollover automatico quando indice > 50GB ou > 7 dias
```

#### Backup

- Snapshot diario do Elasticsearch para S3
- Retencao de snapshots: 30 dias
- Teste de restauracao mensal automatizado
- RPO (Recovery Point Objective): 1 hora
- RTO (Recovery Time Objective): 4 horas

#### Escalabilidade

- Elasticsearch cluster minimo: 3 nos (1 master, 2 data)
- Fluent Bit escala horizontalmente (1 por container/host)
- S3 escala infinitamente
- Auto-scaling de nos Elasticsearch baseado em volume de ingestao

---

## 7. Governanca de Dados

### 7.1 Mascaramento e Redacao

Implementado em duas camadas:

**Camada 1 - Aplicacao (antes de logar):**
```python
# app/logging/redaction.py
import re
import hashlib

REDACTION_PATTERNS = {
    "phone": (r"\+?\d{2}\s?\d{2}\s?\d{4,5}[-\s]?\d{4}", lambda m: mask_phone(m.group())),
    "email": (r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}", lambda m: hash_email(m.group())),
    "cpf": (r"\d{3}\.\d{3}\.\d{3}-\d{2}", lambda m: "***.***.***-**"),
    "jwt": (r"eyJ[a-zA-Z0-9_-]+\.eyJ[a-zA-Z0-9_-]+\.[a-zA-Z0-9_-]+", lambda m: "[REDACTED_JWT]"),
    "api_key": (r"(sk-|ak-|key-)[a-zA-Z0-9]{20,}", lambda m: "[REDACTED_KEY]"),
}

def mask_phone(phone: str) -> str:
    digits = re.sub(r"\D", "", phone)
    if len(digits) >= 8:
        return f"+{digits[:4]}****{digits[-4:]}"
    return "[REDACTED_PHONE]"

def hash_email(email: str) -> str:
    h = hashlib.sha256(email.encode()).hexdigest()[:8]
    return f"email_hash:{h}"

def redact(text: str) -> str:
    for name, (pattern, replacer) in REDACTION_PATTERNS.items():
        text = re.sub(pattern, replacer, text)
    return text
```

**Camada 2 - Pipeline (Fluent Bit Lua filter):**
```lua
-- redact.lua
function redact_sensitive(tag, timestamp, record)
    local modified = false
    -- Redact em campos conhecidos
    if record["http"] and record["http"]["url"] then
        local url = record["http"]["url"]
        url = url:gsub("([?&])(token|key|password|secret)=[^&]*", "%1%2=[REDACTED]")
        if url ~= record["http"]["url"] then
            record["http"]["url"] = url
            modified = true
        end
    end
    if modified then
        return 1, timestamp, record
    end
    return 0, timestamp, record
end
```

### 7.2 Minimizacao de Dados

| Regra | Descricao |
|---|---|
| Nao logar corpos de request/response | Apenas tamanho e hash |
| Conteudo de mensagens WhatsApp | Nunca presente em logs |
| Arquivos de midia | Apenas hash, tamanho, tipo MIME |
| Dados de participantes | Pseudonimizados por hash |
| Query params sensiveis | Removidos antes de logar |

### 7.3 Politicas de Descarte Seguro

| Tipo de Dado | Retencao | Metodo de Descarte |
|---|---|---|
| Logs operacionais (INFO) | 90 dias | Delete automatico via ILM |
| Logs de erro (ERROR) | 365 dias | Delete automatico via ILM |
| Logs de seguranca | 5 anos | Crypto-shredding + delete |
| Logs de auditoria | 5 anos (ou conforme regulacao) | Crypto-shredding + delete |
| Logs de debug | 7 dias | Delete automatico |
| PII residual em logs | 90 dias max | Anonimizacao retroativa + delete |

---

## 8. Seguranca e Privacidade

### 8.1 Criptografia

| Contexto | Requisito |
|---|---|
| Em transito | TLS 1.3 obrigatorio. Sem fallback para versoes anteriores. |
| Em repouso (Elasticsearch) | Encryption-at-rest habilitado. Chaves gerenciadas via KMS ou Vault. |
| Em repouso (S3/MinIO) | SSE-S3 ou SSE-KMS. Bucket policy com deny para acesso sem TLS. |
| Backups | Criptografados com chave separada da operacional. |
| Chaves de criptografia | Rotacao a cada 90 dias. Armazenadas em HSM/Vault. |

### 8.2 Controle de Acesso (RBAC)

| Papel | Permissoes em Logs |
|---|---|
| **log-admin** | CRUD completo, gestao de indices, politicas de retencao |
| **log-analyst** | Leitura de todos os logs, criacao de dashboards, queries |
| **developer** | Leitura de logs INFO+DEBUG do ambiente de desenvolvimento/staging |
| **security-auditor** | Leitura de logs de seguranca e auditoria, sem acesso a dados de debug |
| **support** | Leitura de logs INFO+WARN, filtrados por `trace_id` especifico |
| **automated-system** | Write-only para ingestao, read de metricas agregadas |

#### Auditoria de Acesso aos Logs

Todo acesso aos logs (leitura, busca, exportacao) gera um log de auditoria:

```json
{
  "timestamp": "2026-04-03T18:30:00.000000Z",
  "level": "INFO",
  "service": "wit-log-audit",
  "event": "audit.log_access.read",
  "message": "Consulta de logs executada",
  "user": {
    "id": "analyst_01",
    "role": "log-analyst",
    "ip": "10.0.0.xxx"
  },
  "metadata": {
    "query": "service:wit-backend AND level:ERROR",
    "time_range": "last 24h",
    "results_count": 42,
    "indices_accessed": ["wit-logs-production-2026.04.03"]
  }
}
```

### 8.3 Integridade de Logs

| Mecanismo | Implementacao |
|---|---|
| **Hashing sequencial** | Cada log inclui `metadata.prev_hash` = SHA-256 do log anterior no mesmo stream |
| **Assinatura digital** | Lote de logs assinado a cada 1 minuto com chave do servico |
| **Imutabilidade** | Indices Elasticsearch configurados como append-only (write-once) |
| **Deteccao de tampering** | Job diario que valida cadeia de hashes |
| **Write-Ahead Log** | Fluent Bit persiste em disco antes de enviar |

### 8.4 Protecao contra Logs Maliciosos

| Ameaca | Mitigacao |
|---|---|
| **Log injection** | Sanitizacao de todos os campos de input do usuario. Escape de caracteres especiais JSON. Validacao contra schema. |
| **Log overflow/DoS** | Rate limiting de logs por servico (max 10.000 logs/min por container). Alerta se ultrapassar 80% do limite. |
| **Stack trace leak** | Stack traces completos apenas em ambientes nao-producao. Em producao, hash do stack + referencia para lookup interno. |
| **Header injection** | Validacao e sanitizacao de headers HTTP antes de incluir em logs. Whitelist de headers permitidos. |
| **Oversized payloads** | Truncamento de campos string a `maxLength` definido no schema. Rejeicao de logs > 64KB. |

### 8.5 Conformidade LGPD/GDPR

| Requisito | Implementacao |
|---|---|
| **Base legal** | Legitimo interesse para logs operacionais. Obrigacao legal para logs de seguranca. |
| **Consentimento** | Nao necessario para logs operacionais/seguranca (base: legitimo interesse). Necessario para analytics de comportamento. |
| **Minimizacao** | Apenas dados estritamente necessarios. Revisao trimestral de campos logados. |
| **Anonimizacao** | IPs anonimizados. Dados pessoais pseudonimizados. Impossibilidade de re-identificacao sem chave. |
| **Direito ao esquecimento** | Procedimento de exclusao de logs vinculados a `user.id` sob demanda. SLA: 30 dias. |
| **Portabilidade** | Exportacao de logs vinculados a um usuario em formato JSON. |
| **Retencao por tipo** | Definida na Secao 7.3. Automatizada via ILM. |
| **DPO** | Notificacao automatica ao DPO para acessos a logs com PII. |
| **DPIA** | Avaliacao de impacto realizada antes da implantacao. Revisao anual. |
| **Incidentes** | Procedimento na Secao 12 (Playbooks). Notificacao a ANPD em 72h para violacoes. |

### 8.6 Retencao por Tipo de Dado

| Categoria | Retencao | Base Legal | Descarte |
|---|---|---|---|
| Logs operacionais sem PII | 90 dias | Legitimo interesse | Delete automatico |
| Logs operacionais com PII pseudonimizada | 90 dias | Legitimo interesse | Delete automatico |
| Logs de seguranca/autenticacao | 5 anos | Obrigacao legal (Marco Civil da Internet) | Crypto-shredding |
| Logs de auditoria financeira | 5 anos | Obrigacao legal | Crypto-shredding |
| Logs de consentimento | Duracao do consentimento + 5 anos | Obrigacao legal (LGPD) | Crypto-shredding |
| Logs de debug com dados de teste | 7 dias | Legitimo interesse | Delete automatico |

---

## 9. Debugging Automatico e Deteccao de Falhas

### 9.1 Sistema de Deteccao

```
[Logs Ingeridos] --> [Motor de Regras] --> [Classificador] --> [Recomendador]
                          |                      |                    |
                     Regras estaticas      ML anomaly          Base de conhecimento
                     Thresholds            detection           de erros conhecidos
                     Pattern matching      Clustering          Runbooks automaticos
```

### 9.2 Regras de Deteccao

| Regra | Condicao | Severidade | Acao |
|---|---|---|---|
| Error rate spike | >5% de requests com ERROR em janela de 5min | critical | PagerDuty + auto-scale |
| Latencia elevada | p95 > 5s por 3 min consecutivos | high | Alerta Slack + dashboard |
| Claude API down | 3 erros consecutivos em 1min | critical | Circuit breaker + alerta |
| Database connection pool | >80% conexoes em uso | high | Alerta + log detalhado |
| Disco >90% | Metricas de host | critical | Alerta + rotacao emergencial |
| Auth failures spike | >10 falhas de auth de mesmo IP em 5min | high | Block IP temporario + alerta |
| Memory leak | RSS crescente monotonicamente por 30min | medium | Alerta + heap dump |

### 9.3 Recomendacoes Automaticas de Correcao

O campo `error.suggestion` e preenchido automaticamente com base em um mapeamento de erros conhecidos:

```python
# app/logging/error_advisor.py
ERROR_KNOWLEDGE_BASE = {
    "AI_TIMEOUT_001": {
        "suggestion": "Verificar status da API Claude. Considerar aumentar timeout ou reduzir payload.",
        "runbook": "https://wiki.internal/runbooks/claude-timeout",
        "auto_action": "circuit_breaker"
    },
    "DB_CONN_001": {
        "suggestion": "Verificar pool de conexoes PostgreSQL. Considerar aumentar max_connections.",
        "runbook": "https://wiki.internal/runbooks/db-connection-pool",
        "auto_action": "pool_reset"
    },
    "REDIS_CONN_001": {
        "suggestion": "Verificar saude do Redis. Fallback para operacao sem cache.",
        "runbook": "https://wiki.internal/runbooks/redis-failure",
        "auto_action": "cache_bypass"
    },
    "PARSE_ERR_001": {
        "suggestion": "Formato de exportacao WhatsApp nao reconhecido. Verificar versao do app.",
        "runbook": "https://wiki.internal/runbooks/parser-error",
        "auto_action": None
    },
    "AUTH_INVALID_001": {
        "suggestion": "Token JWT invalido ou expirado. Cliente deve re-autenticar.",
        "runbook": "https://wiki.internal/runbooks/auth-failure",
        "auto_action": None
    },
    "MEDIA_CORRUPT_001": {
        "suggestion": "Arquivo de midia corrompido. Tentar re-download ou marcar como indisponivel.",
        "runbook": "https://wiki.internal/runbooks/media-corruption",
        "auto_action": "mark_unavailable"
    }
}

def get_suggestion(error_code: str) -> dict:
    return ERROR_KNOWLEDGE_BASE.get(error_code, {
        "suggestion": "Erro desconhecido. Consultar logs detalhados e escalar para engenharia.",
        "runbook": "https://wiki.internal/runbooks/unknown-error",
        "auto_action": None
    })
```

### 9.4 Rastreamento de Falhas End-to-End

Para cada falha ERROR, o sistema:

1. Coleta todos os logs com o mesmo `trace_id`
2. Reconstroi a timeline da requisicao (spans)
3. Identifica o ponto exato de falha
4. Gera um "failure report" automatico:

```json
{
  "failure_report": {
    "trace_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
    "root_cause": "Claude API timeout apos 30s",
    "affected_user": "usr_42",
    "affected_resource": "conv_789",
    "timeline": [
      {"span_id": "1a...", "operation": "http.request", "status": "in_progress", "at": "T18:02:06.123Z"},
      {"span_id": "2b...", "operation": "conversation.parse", "status": "success", "at": "T18:02:07.500Z"},
      {"span_id": "3c...", "operation": "claude.transcribe", "status": "timeout", "at": "T18:02:37.500Z"}
    ],
    "suggestion": "Verificar status da API Claude.",
    "auto_actions_taken": ["circuit_breaker_activated"],
    "requires_human": true
  }
}
```

---

## 10. Observabilidade e Confiabilidade

### 10.1 Dashboards

| Dashboard | Metricas | Ferramenta |
|---|---|---|
| **Operacional** | Requests/s, latencia p50/p95/p99, error rate, status codes | Grafana |
| **Pipeline de Logs** | Ingestao/s, latencia de entrega, backpressure, drops | Grafana |
| **Seguranca** | Auth failures, rate limits, IPs bloqueados, acessos a logs | Kibana |
| **IA/Claude** | Chamadas/min, tokens, custo, latencia, erros, circuit breaker status | Grafana |
| **Negocio** | Uploads/dia, conversas processadas, exportacoes, usuarios ativos | Grafana |

### 10.2 Alertas

| Alerta | Condicao | Canal | SLA Resposta |
|---|---|---|---|
| Pipeline down | Ingestao = 0 por 5min | PagerDuty P1 | 15min |
| Error rate critical | >10% requests com ERROR | PagerDuty P1 | 15min |
| Error rate elevated | >5% requests com ERROR | Slack #alerts | 1h |
| Latencia degradada | p95 > 5s por 5min | Slack #alerts | 1h |
| Disco logs >85% | Metricas de host | Slack #infra | 4h |
| Claude API circuit open | Circuit breaker ativado | PagerDuty P2 + Slack | 30min |
| Integridade comprometida | Hash chain quebrada | PagerDuty P1 + Security | 15min |

### 10.3 Metricas do Pipeline

| Metrica | Alvo | Alerta |
|---|---|---|
| Ingestao (logs/s) | Suportar 10x pico normal | Alerta se > 80% capacidade |
| Latencia de entrega (log emitido -> disponivel para busca) | < 30 segundos | Alerta se > 60s |
| Taxa de perda de logs | < 0.01% | Alerta se > 0.1% |
| Disponibilidade do pipeline | 99.9% | Alerta se indisponivel > 5min |
| Tempo de busca (query) | < 5s para queries comuns | Alerta se > 10s |

### 10.4 Testes de Estresse e Resiliencia

| Teste | Descricao | Frequencia |
|---|---|---|
| **Load test** | Injetar 100x volume normal de logs por 30min | Trimestral |
| **Chaos: kill Fluent Bit** | Derrubar coletor e validar buffer/recuperacao | Mensal |
| **Chaos: Elasticsearch down** | Derrubar cluster ES e validar buffer em disco | Mensal |
| **Chaos: network partition** | Simular falha de rede entre coletor e storage | Trimestral |
| **Recovery test** | Restaurar indices de backup e validar integridade | Mensal |
| **Retention test** | Validar que ILM esta deletando dados conforme politica | Semanal |

### 10.5 Requisitos de Desempenho

| Metrica | Limite |
|---|---|
| Overhead de instrumentacao no request | < 5ms adicionais (p99) |
| Uso de CPU pelo logging | < 2% do total do container |
| Uso de memoria pelo logging | < 50MB por container |
| Impacto na latencia do request | < 1% de aumento |
| Tamanho medio de log entry | < 2KB |
| Throughput minimo do pipeline | 50.000 logs/min |

### 10.6 Failover e Redundancia

| Componente | Estrategia |
|---|---|
| Fluent Bit | Buffer em disco (1GB). Retry com backoff exponencial. Failover para arquivo local se destino indisponivel. |
| Elasticsearch | Cluster com replicas. Minimo 1 replica por shard. Snapshot automatico. |
| S3/MinIO | Replicacao cross-region (se multi-region). Versionamento habilitado. |
| Certificados TLS | Renovacao automatica 30 dias antes da expiracao. Alerta 7 dias antes. |

### 10.7 Recuperacao apos Falhas

1. **Fluent Bit reinicia**: Le buffer de disco pendente e reenvia
2. **Elasticsearch indisponivel**: Fluent Bit acumula em buffer local (1GB max). Alerta apos 10min.
3. **Perda de indice**: Restaurar snapshot mais recente. Reprocessar logs do buffer S3 para preencher gap.
4. **Corrupção de dados**: Detectada por validacao de hash chain. Isolamento do segmento corrompido. Restauracao do backup.

---

## 11. Recomendacoes de Stack/Ferramentas

### 11.1 Comparativo por Cenario

#### On-Premises

| Componente | Recomendacao | Alternativa | Pros | Cons |
|---|---|---|---|---|
| Coleta | Fluent Bit | Filebeat | Leve, flexivel, plugins | Menos integracao nativa com ES |
| Transporte | Kafka | Redis Streams | Alta durabilidade, replay | Complexidade operacional |
| Armazenamento | Elasticsearch (OpenSearch) | Loki + S3 | Busca full-text, maduro | Custo de hardware, operacao |
| Visualizacao | Grafana + Kibana | Graylog | Flexivel, open source | Duas ferramentas para manter |
| Alertas | AlertManager + Grafana | ElastAlert | Integracao Prometheus | Configuracao adicional |

#### Cloud Hibrido (recomendado para WIT)

| Componente | Recomendacao | Custo Estimado |
|---|---|---|
| Coleta | Fluent Bit (sidecar Docker) | Gratuito (OSS) |
| Buffer | Disco local + Redis (ja existente) | Incluso na infra atual |
| Armazenamento Hot | Elasticsearch 8 (self-hosted, 3 nos) | ~$150-300/mes (VMs) |
| Armazenamento Cold | S3-compatible (MinIO ou AWS S3) | ~$5-20/mes |
| Visualizacao | Grafana Cloud (free tier) + Kibana | Gratuito ate 10GB/mes |
| Alertas | Grafana Alerting + Slack webhook | Gratuito |

#### Multi-Cloud

| Componente | AWS | GCP | Azure |
|---|---|---|---|
| Coleta | CloudWatch Agent + Fluent Bit | Cloud Logging Agent | Azure Monitor Agent |
| Armazenamento | CloudWatch Logs + S3 | Cloud Logging + GCS | Log Analytics + Blob |
| Busca | OpenSearch Service | BigQuery | Azure Data Explorer |
| Visualizacao | CloudWatch Dashboards | Looker | Azure Workbooks |
| Custo (1TB/mes) | ~$500 | ~$400 | ~$450 |

### 11.2 Stack Recomendada para WIT (Producao Atual)

Considerando a infra atual (Docker Compose, single host, PostgreSQL, Redis):

```
Fase 1 (MVP):
  - structlog (Python) + pino (Node.js) --> stdout JSON
  - Docker logging driver json-file --> Fluent Bit --> Elasticsearch single-node
  - Kibana para busca e dashboards basicos

Fase 2 (Escala):
  - Fluent Bit com buffer Redis
  - Elasticsearch cluster (3 nos)
  - Grafana para dashboards e alertas
  - S3/MinIO para arquivo

Fase 3 (Enterprise):
  - Kafka como transporte central
  - Elasticsearch cluster dedicado
  - SIEM integration
  - ML anomaly detection
```

---

## 12. Playbooks de Incidentes

### 12.1 Playbook: Pipeline de Logs Indisponivel

```
SEVERIDADE: P1 - Critico
SLA: 15 minutos para resposta

DETECCAO:
  - Alerta: "Log ingestion rate = 0 for > 5min"
  - Dashboard: Grafana > Pipeline > Ingestion Rate

DIAGNOSTICO:
  1. Verificar status do Fluent Bit:
     $ docker logs wit_fluentbit --tail 100
     $ curl http://localhost:2020/api/v1/health
  
  2. Verificar status do Elasticsearch:
     $ curl -k https://elasticsearch:9200/_cluster/health
     $ curl -k https://elasticsearch:9200/_cat/indices?v
  
  3. Verificar espaco em disco:
     $ df -h /var/lib/docker
     $ docker system df
  
  4. Verificar conectividade:
     $ docker exec wit_fluentbit ping elasticsearch

RESOLUCAO:
  A. Fluent Bit down:
     $ docker restart wit_fluentbit
     Verificar se buffer em disco esta sendo reprocessado
  
  B. Elasticsearch sem espaco:
     $ curl -X POST 'elasticsearch:9200/wit-logs-*-2026.03.*/_forcemerge?max_num_segments=1'
     $ curl -X DELETE 'elasticsearch:9200/wit-logs-development-*'
     Ajustar ILM policy se necessario
  
  C. Elasticsearch cluster red:
     $ curl -k https://elasticsearch:9200/_cluster/allocation/explain
     Resolver shard allocation issues

VALIDACAO:
  - Confirmar ingestao restaurada no Grafana
  - Verificar que logs acumulados no buffer foram entregues
  - Confirmar integridade com spot check de trace_id recente

POSTMORTEM:
  - Documento de postmortem em 48h
  - Action items para prevenir recorrencia
```

### 12.2 Playbook: Error Rate Elevado (>5%)

```
SEVERIDADE: P2 - Alto
SLA: 1 hora para resposta

DETECCAO:
  - Alerta: "Error rate > 5% in 5min window"
  - Dashboard: Grafana > Operacional > Error Rate

DIAGNOSTICO:
  1. Identificar tipo de erro predominante:
     Kibana: level:ERROR | top 10 error.code
  
  2. Verificar se e um servico especifico:
     Kibana: level:ERROR | breakdown by service
  
  3. Verificar se ha trace_id comum (falha em cascata):
     Kibana: level:ERROR | unique trace_id count
  
  4. Verificar dependencias externas:
     - Claude API: verificar status.anthropic.com
     - PostgreSQL: $ docker exec wit_postgres pg_isready
     - Redis: $ docker exec wit_redis redis-cli ping

RESOLUCAO:
  A. Claude API com problemas:
     - Ativar circuit breaker se nao automatico
     - Retornar resposta degradada ao usuario
     - Monitorar restauracao
  
  B. Database connection exhaustion:
     - $ docker restart wit_backend (se pool corrupted)
     - Aumentar pool_size se necessario
     - Verificar queries lentas: SELECT * FROM pg_stat_activity WHERE state='active'
  
  C. Erro de parsing (volume de uploads):
     - Identificar arquivo problematico via trace_id
     - Isolar e marcar para analise manual
     - Nao bloqueia outros processamentos

VALIDACAO:
  - Error rate volta abaixo de 1%
  - Nenhum usuario impactado sem resposta adequada
```

### 12.3 Playbook: Vazamento de Dados Pessoais em Logs

```
SEVERIDADE: P1 - Critico (LGPD)
SLA: IMEDIATO

DETECCAO:
  - Alerta automatico de scanner de PII
  - Report manual de equipe
  - Auditoria periodica

RESPOSTA IMEDIATA (< 1 hora):
  1. Identificar escopo do vazamento:
     - Quais campos contem PII?
     - Quais indices/datas afetados?
     - Quantos registros?
  
  2. Isolar dados:
     - Bloquear acesso de leitura aos indices afetados (exceto security team)
     - Nao deletar imediatamente (preservar para investigacao)
  
  3. Notificar:
     - DPO imediatamente
     - CISO imediatamente
     - Equipe juridica em 4h

CORRECAO (< 24 horas):
  1. Corrigir a fonte do vazamento no codigo
  2. Deploy de hotfix
  3. Adicionar regra de redacao no pipeline
  4. Testar que novos logs nao contem PII

REMEDIACAO (< 72 horas):
  1. Anonimizar retroativamente os logs afetados
  2. Atualizar indices e backups
  3. Se necessario, notificar ANPD (dentro de 72h conforme LGPD)
  4. Se necessario, notificar usuarios afetados
  5. Documentar incidente completo

POSTMORTEM:
  - Root cause analysis
  - Atualizar regras de redacao
  - Atualizar testes de privacidade
  - Treinamento da equipe
```

---

## 13. Roteiro de Implementacao

### Fase 1 - Fundacao (Semanas 1-3)

| Entregavel | Descricao | Esforco | Criterio de Aceitacao | Dependencias |
|---|---|---|---|---|
| Biblioteca de logging | `structlog` configurado no backend com JSON output | 3 dias | Todos os logs do backend em JSON para stdout | Nenhuma |
| Middleware de tracing | `TracingMiddleware` com trace_id, span_id, request_id | 2 dias | Headers propagados, contextvars funcionando | Biblioteca de logging |
| Redacao de dados | Modulo de redacao com patterns definidos | 2 dias | Testes passando para todos os patterns | Biblioteca de logging |
| Log de requests HTTP | Middleware que loga todas as requests/responses | 1 dia | Todos os campos HTTP capturados | Middleware de tracing |
| Log de erros | Exception handler global com campos de erro | 2 dias | Todos os erros 4xx/5xx logados com detalhes | Biblioteca de logging |
| Testes unitarios | Testes para redacao, formato, campos | 2 dias | >90% cobertura do modulo de logging | Todos acima |

**Criterios de aceitacao da Fase 1:**
- [ ] Todos os logs do backend emitidos em JSON estruturado
- [ ] trace_id propagado em todas as requests
- [ ] Dados sensiveis redactados (validar com 10 cenarios)
- [ ] Zero logs com PII em texto plano
- [ ] Testes unitarios passando

### Fase 2 - Pipeline (Semanas 4-6)

| Entregavel | Descricao | Esforco | Criterio de Aceitacao | Dependencias |
|---|---|---|---|---|
| Fluent Bit config | Container Fluent Bit no docker-compose | 2 dias | Logs coletados de todos os containers | Fase 1 |
| Elasticsearch setup | Container ES no docker-compose + ILM | 3 dias | Indices criados, ILM configurado | Fluent Bit |
| Kibana setup | Container Kibana com index patterns | 1 dia | Busca de logs funcional | Elasticsearch |
| Frontend logging | `pino` configurado no Next.js | 2 dias | Erros client-side capturados | Nenhuma |
| Nginx JSON logs | Configuracao de log format JSON | 1 dia | Access logs em JSON | Nenhuma |
| Integracao completa | Todos os componentes conectados | 2 dias | Log de uma request visivel end-to-end | Todos acima |

**Criterios de aceitacao da Fase 2:**
- [ ] Logs de todos os servicos visiveis no Kibana
- [ ] Busca por trace_id retorna timeline completa
- [ ] ILM rodando (indices antigos movidos/deletados)
- [ ] Latencia de entrega < 30s

### Fase 3 - Observabilidade (Semanas 7-9)

| Entregavel | Descricao | Esforco | Criterio de Aceitacao | Dependencias |
|---|---|---|---|---|
| Dashboards Grafana | 5 dashboards definidos na Secao 10.1 | 3 dias | Metricas atualizadas em tempo real | Fase 2 |
| Alertas | Regras de alerta da Secao 10.2 | 2 dias | Alertas disparando em Slack para testes | Dashboards |
| Error advisor | Modulo de recomendacao automatica | 3 dias | Erros conhecidos com suggestion preenchida | Fase 1 |
| Failure reports | Geracao automatica de reports por trace_id | 3 dias | Report gerado para cada ERROR | Fase 2 |
| Metricas do pipeline | Monitoramento do proprio pipeline | 2 dias | Dashboard de saude do pipeline | Fase 2 |

**Criterios de aceitacao da Fase 3:**
- [ ] Dashboards operacionais funcionais
- [ ] Alertas testados (fire drill)
- [ ] Error advisor respondendo para codigos conhecidos
- [ ] Failure report automatico para erros criticos

### Fase 4 - Seguranca e Compliance (Semanas 10-12)

| Entregavel | Descricao | Esforco | Criterio de Aceitacao | Dependencias |
|---|---|---|---|---|
| RBAC | Roles configurados no ES/Kibana | 2 dias | Cada papel com acesso correto | Fase 2 |
| Auditoria de acesso | Log de acesso aos logs | 2 dias | Todo acesso a logs auditado | RBAC |
| Integridade de logs | Hash chain + validacao | 3 dias | Job de validacao rodando diariamente | Fase 2 |
| Scanner de PII | Scan automatico de PII residual | 3 dias | Alerta se PII detectada em logs | Fase 2 |
| Criptografia e-2-e | TLS entre componentes, encryption at rest | 2 dias | Nenhuma transmissao em texto plano | Fase 2 |
| Documentacao LGPD | DPIA, politicas, procedimentos | 3 dias | Documentos aprovados pelo DPO | Todas |

**Criterios de aceitacao da Fase 4:**
- [ ] Pentest do pipeline de logs sem findings criticos
- [ ] Audit trail completo e imutavel
- [ ] Scanner de PII sem falsos negativos em dataset de teste
- [ ] DPIA aprovada

### Fase 5 - Hardening e Producao (Semanas 13-14)

| Entregavel | Descricao | Esforco | Criterio de Aceitacao | Dependencias |
|---|---|---|---|---|
| Load test | Teste com 100x volume | 2 dias | Pipeline suporta sem perda | Fase 3 |
| Chaos testing | Cenarios da Secao 10.4 | 2 dias | Recuperacao automatica em todos | Fase 3 |
| Playbooks | Documentacao de resposta a incidentes | 2 dias | Equipe treinada | Fase 3 |
| Backup/restore test | Validacao de recuperacao | 1 dia | Restore em < 4h (RTO) | Fase 2 |
| Go-live | Deploy em producao | 1 dia | Pipeline operacional | Todas |

---

## 14. Plano de Migracao de Sistemas Legados

### 14.1 Estado Atual

O WIT atualmente usa logging basico do Python (`logging` module) com output em texto nao estruturado para stdout, sem correlacao entre servicos, sem centralizacao.

### 14.2 Estrategia de Coexistencia

```
Fase A (Semana 1-2): Dual-write
  - Novo sistema de logging ativado em paralelo
  - Logs antigos continuam funcionando
  - Ambos escrevem para stdout (Docker captura ambos)
  - Fluent Bit filtra e roteia apenas JSON valido

Fase B (Semana 3-4): Migração progressiva
  - Modulo por modulo migrado para structlog
  - Ordem: middleware -> routers -> services -> tasks
  - Cada modulo migrado: PR com testes, review, merge
  - Rollback: revert PR se problemas

Fase C (Semana 5): Cutover
  - Remover logging antigo
  - Validar que 100% dos logs estao estruturados
  - Desabilitar fallback de texto plano no Fluent Bit

Fase D (Semana 6): Cleanup
  - Remover codigo de compatibilidade
  - Documentar nova API de logging para desenvolvedores
```

### 14.3 Minimizacao de Impacto

| Risco | Mitigacao |
|---|---|
| Perda de logs durante migracao | Dual-write garante que ambos os sistemas capturam |
| Performance degradada | Benchmark antes/depois de cada modulo migrado |
| Bugs no novo sistema | Feature flag para desabilitar novo logging instantaneamente |
| Equipe nao familiarizada | Sessao de treinamento de 2h antes da Fase B |
| Rollback necessario | Cada modulo e um PR independente, revert isolado |

### 14.4 Feature Flags

```python
# app/config.py
class Settings(BaseSettings):
    # Logging
    LOG_STRUCTURED: bool = True          # Ativar JSON estruturado
    LOG_LEGACY_COMPAT: bool = False      # Manter formato legado em paralelo
    LOG_REDACTION_ENABLED: bool = True   # Ativar redacao de dados sensiveis
    LOG_TRACING_ENABLED: bool = True     # Ativar trace_id/span_id
    LOG_ERROR_ADVISOR: bool = True       # Ativar recomendacoes automaticas
    LOG_INTEGRITY_CHECK: bool = False    # Ativar hash chain (Fase 4)
    LOG_PII_SCANNER: bool = False        # Ativar scanner de PII (Fase 4)
```

---

## 15. Casos de Uso e Exemplos Adicionais

### 15.1 Upload de Conversa (Fluxo Completo)

```json
// 1. Request recebida
{"timestamp":"2026-04-03T18:00:00.000Z","level":"INFO","service":"wit-backend","event":"http.request.received","message":"POST /api/conversations/upload","trace_id":"t1","span_id":"s1","request_id":"r1","environment":"production","version":"1.0.0","user":{"id":"usr_1","role":"admin","ip":"192.168.1.xxx"},"http":{"method":"POST","url":"/api/conversations/upload","request_size":15000000}}

// 2. Parse iniciado
{"timestamp":"2026-04-03T18:00:01.000Z","level":"INFO","service":"wit-backend","event":"conversation.parse.started","message":"Iniciando parse da exportacao WhatsApp","trace_id":"t1","span_id":"s2","request_id":"r1","parent_span_id":"s1","environment":"production","version":"1.0.0","resource":{"type":"conversation","id":"conv_1","action":"create"}}

// 3. Parse concluido
{"timestamp":"2026-04-03T18:00:03.000Z","level":"INFO","service":"wit-backend","event":"conversation.parse.completed","message":"Parse concluido: 1542 mensagens, 87 midias","trace_id":"t1","span_id":"s2","request_id":"r1","parent_span_id":"s1","environment":"production","version":"1.0.0","operation":{"name":"whatsapp.parse","duration_ms":2000,"status":"success"},"metadata":{"messages_count":1542,"media_count":87}}

// 4. Processamento de midia (por agente)
{"timestamp":"2026-04-03T18:00:04.000Z","level":"INFO","service":"wit-backend","event":"ai.media.processing","message":"Agente 07 processando audio","trace_id":"t1","span_id":"s3","request_id":"r1","parent_span_id":"s1","environment":"production","version":"1.0.0","resource":{"type":"media","id":"media_45","action":"process"},"ai":{"model":"claude-opus-4-6","agent_id":"agent_07"},"operation":{"name":"claude.transcribe_audio","status":"success","duration_ms":5200},"metadata":{"media_type":"audio/ogg","media_size_bytes":524288}}

// 5. Request concluida
{"timestamp":"2026-04-03T18:01:30.000Z","level":"INFO","service":"wit-backend","event":"http.request.completed","message":"Upload processado com sucesso","trace_id":"t1","span_id":"s1","request_id":"r1","environment":"production","version":"1.0.0","http":{"method":"POST","url":"/api/conversations/upload","status_code":200,"duration_ms":90000,"response_size":1024},"operation":{"name":"conversation.upload","duration_ms":90000,"status":"success"}}
```

### 15.2 Autenticacao Falhada

```json
{"timestamp":"2026-04-03T19:00:00.000Z","level":"WARN","service":"wit-backend","event":"security.auth.failed","message":"Tentativa de login com credenciais invalidas","trace_id":"t2","span_id":"s10","request_id":"r2","environment":"production","version":"1.0.0","user":{"ip":"45.33.xxx.xxx","user_agent":"curl/7.88.1"},"http":{"method":"POST","url":"/api/auth/login","status_code":401,"duration_ms":150},"error":{"type":"AuthenticationError","code":"AUTH_INVALID_001","message":"Credenciais invalidas","severity":"medium","suggestion":"Verificar se usuario existe e senha esta correta. Monitorar tentativas repetidas do mesmo IP."},"metadata":{"username_hash":"sha256:abc123","attempt_number":3,"lockout_threshold":5}}
```

### 15.3 Exportacao PDF

```json
{"timestamp":"2026-04-03T20:00:00.000Z","level":"INFO","service":"wit-backend","event":"export.pdf.completed","message":"Exportacao PDF gerada com sucesso","trace_id":"t3","span_id":"s20","request_id":"r3","environment":"production","version":"1.0.0","user":{"id":"usr_1","role":"admin"},"resource":{"type":"export","id":"exp_99","action":"create"},"operation":{"name":"export.generate_pdf","duration_ms":3500,"status":"success","params":{"format":"pdf","conversation_id":"conv_1","pages":45,"include_media":true}},"metadata":{"file_size_bytes":2500000,"file_hash":"sha256:def456"}}
```

### 15.4 Health Check

```json
{"timestamp":"2026-04-03T18:00:00.000Z","level":"DEBUG","service":"wit-backend","event":"system.health.check","message":"Health check executado","trace_id":"t4","span_id":"s30","request_id":"r4","environment":"production","version":"1.0.0","http":{"method":"GET","url":"/api/health","status_code":200,"duration_ms":12},"metadata":{"postgres":"healthy","redis":"healthy","disk_usage_pct":45,"memory_usage_pct":62,"active_agents":3,"queue_size":0}}
```

---

## 16. Criterios de Validacao e Aceitacao

### 16.1 Testes de Privacidade

| Teste | Metodo | Criterio de Aprovacao |
|---|---|---|
| Redacao de PII | Injetar dados pessoais conhecidos em todos os campos de input | Nenhum dado pessoal presente em logs de saida |
| Anonimizacao de IP | Verificar todos os logs com campo `user.ip` | Ultimo octeto sempre mascarado em producao |
| Conteudo de mensagens | Processar conversas e buscar conteudo em logs | Zero conteudo de mensagens em logs |
| Tokens/API Keys | Buscar patterns de tokens em todo o indice | Zero tokens em texto plano |
| Direito ao esquecimento | Solicitar exclusao de user_id e verificar | Zero logs com user_id apos procedimento |

### 16.2 Testes de Desempenho

| Teste | Metodo | Criterio de Aprovacao |
|---|---|---|
| Overhead de instrumentacao | Benchmark request com/sem logging | < 5ms adicional (p99) |
| Throughput do pipeline | Injetar 50.000 logs/min por 1h | Zero perda, latencia < 30s |
| Busca em volume | Query em indice com 100M+ logs | Resposta < 5s |
| Impacto em producao | A/B test com 50% de trafego | Nenhuma degradacao mensuravel |

### 16.3 Testes de Escalabilidade

| Teste | Metodo | Criterio de Aprovacao |
|---|---|---|
| Volume 10x | Simular 10x trafego normal por 24h | Pipeline estavel, sem perda |
| Storage growth | Projetar crescimento de storage por 12 meses | Plano de capacidade aprovado |
| Indice rollover | Validar rollover automatico apos 50GB | Novo indice criado, queries transparentes |

### 16.4 Testes de Seguranca

| Teste | Metodo | Criterio de Aprovacao |
|---|---|---|
| Log injection | Injetar payloads maliciosos via input de usuario | Payloads sanitizados, sem execucao |
| RBAC | Tentar acesso com roles incorretos | Acesso negado em todos os cenarios |
| TLS | Scan de portas e interceptacao | Nenhuma transmissao em texto plano |
| Integridade | Modificar log e rodar validacao | Deteccao de tampering em < 24h |
| Overflow | Enviar 1M logs/min por 10min | Rate limiting ativo, sem crash |

### 16.5 Testes de Conformidade

| Teste | Metodo | Criterio de Aprovacao |
|---|---|---|
| LGPD compliance | Checklist ANPD + auditoria externa | 100% conformidade |
| Retencao | Verificar que dados expirados foram deletados | Zero dados alem da retencao definida |
| Audit trail | Rastrear todas as acoes de um usuario por 30 dias | Timeline completa reconstituivel |
| Incidente simulado | Drill de resposta a vazamento | SLA de resposta cumprido |

---

## 17. Glossario

| Termo | Definicao |
|---|---|
| **trace_id** | Identificador unico de uma cadeia de operacoes distribuidas |
| **span_id** | Identificador de uma unidade de trabalho dentro de um trace |
| **ILM** | Index Lifecycle Management - gestao automatica do ciclo de vida de indices |
| **Crypto-shredding** | Destruicao da chave de criptografia para tornar dados irrecuperaveis |
| **Circuit breaker** | Padrao que interrompe chamadas a servico degradado para evitar cascata |
| **SIEM** | Security Information and Event Management |
| **PII** | Personally Identifiable Information - dados pessoais identificaveis |
| **DPIA** | Data Protection Impact Assessment - avaliacao de impacto a protecao de dados |
| **DPO** | Data Protection Officer - encarregado de protecao de dados |
| **ANPD** | Autoridade Nacional de Protecao de Dados |
| **ILM** | Index Lifecycle Management |
| **mTLS** | Mutual TLS - autenticacao mutua entre cliente e servidor |
| **RPO** | Recovery Point Objective - ponto maximo de perda de dados aceitavel |
| **RTO** | Recovery Time Objective - tempo maximo para restauracao do servico |
| **NDJSON** | Newline Delimited JSON - formato de uma linha JSON por registro |

---

## Apendice A - docker-compose.yml Parcial (Servicos de Logging)

```yaml
# Adicionar ao docker-compose.yml existente

  # ─── Fluent Bit ─────────────────────────────────────────────
  fluentbit:
    image: fluent/fluent-bit:3.0
    container_name: wit_fluentbit
    restart: unless-stopped
    volumes:
      - ./logging/fluent-bit.conf:/fluent-bit/etc/fluent-bit.conf:ro
      - ./logging/parsers.conf:/fluent-bit/etc/parsers.conf:ro
      - ./logging/redact.lua:/fluent-bit/etc/redact.lua:ro
      - fluentbit_buffer:/fluent-bit/buffer
    ports:
      - "2020:2020"   # Metricas
      - "24224:24224"  # Forward input
    depends_on:
      - elasticsearch
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:2020/api/v1/health"]
      interval: 15s
      timeout: 5s
      retries: 3

  # ─── Elasticsearch ──────────────────────────────────────────
  elasticsearch:
    image: docker.elastic.co/elasticsearch/elasticsearch:8.13.0
    container_name: wit_elasticsearch
    restart: unless-stopped
    environment:
      - discovery.type=single-node
      - xpack.security.enabled=true
      - xpack.security.http.ssl.enabled=false
      - ELASTIC_PASSWORD=${ELASTIC_PASSWORD:-wit_elastic_2024}
      - "ES_JAVA_OPTS=-Xms512m -Xmx512m"
    volumes:
      - wit_esdata:/usr/share/elasticsearch/data
    ports:
      - "9200:9200"
    healthcheck:
      test: ["CMD-SHELL", "curl -s -u elastic:${ELASTIC_PASSWORD:-wit_elastic_2024} http://localhost:9200/_cluster/health | grep -q '\"status\":\"green\\|yellow\"'"]
      interval: 30s
      timeout: 10s
      retries: 5
      start_period: 60s

  # ─── Kibana ─────────────────────────────────────────────────
  kibana:
    image: docker.elastic.co/kibana/kibana:8.13.0
    container_name: wit_kibana
    restart: unless-stopped
    environment:
      - ELASTICSEARCH_HOSTS=http://elasticsearch:9200
      - ELASTICSEARCH_USERNAME=elastic
      - ELASTICSEARCH_PASSWORD=${ELASTIC_PASSWORD:-wit_elastic_2024}
    ports:
      - "5601:5601"
    depends_on:
      elasticsearch:
        condition: service_healthy

volumes:
  wit_esdata:
    driver: local
  fluentbit_buffer:
    driver: local
```

## Apendice B - Configuracao structlog (Python)

```python
# app/logging/config.py
import structlog
import logging
import sys
from app.config import get_settings

def setup_logging():
    settings = get_settings()
    
    shared_processors = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.UnicodeDecoder(),
    ]
    
    if settings.LOG_REDACTION_ENABLED:
        from app.logging.redaction import redact_processor
        shared_processors.append(redact_processor)
    
    if settings.DEBUG:
        # Development: pretty-print colorido
        renderer = structlog.dev.ConsoleRenderer()
    else:
        # Production: JSON estruturado
        renderer = structlog.processors.JSONRenderer()
    
    structlog.configure(
        processors=[
            *shared_processors,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )
    
    formatter = structlog.stdlib.ProcessorFormatter(
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            renderer,
        ],
    )
    
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)
    
    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.addHandler(handler)
    root_logger.setLevel(logging.DEBUG if settings.DEBUG else logging.INFO)
    
    # Silenciar loggers ruidosos
    for noisy in ["uvicorn.access", "httpcore", "httpx"]:
        logging.getLogger(noisy).setLevel(logging.WARNING)

def get_logger(name: str = None):
    return structlog.get_logger(name)
```

---

**Fim do documento.**

> Este documento deve ser revisado trimestralmente ou apos incidentes significativos.  
> Proxima revisao programada: 2026-07-03  
> Responsavel: Equipe de Engenharia / SRE
