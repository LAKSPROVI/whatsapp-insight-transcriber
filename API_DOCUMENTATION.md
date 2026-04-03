# 📖 API Documentation — WhatsApp Insight Transcriber

> Documentação completa da API REST do WhatsApp Insight Transcriber.

**Base URL:** `https://seu-servidor.com/api`  
**Swagger UI:** `https://seu-servidor.com/api/docs`  
**ReDoc:** `https://seu-servidor.com/api/redoc`  
**Versão:** 1.0.0  

---

## 📋 Índice

- [Visão Geral](#visão-geral)
- [Autenticação](#autenticação)
- [Endpoints](#endpoints)
  - [Auth](#auth---autenticação)
  - [Conversations](#conversations---conversas)
  - [Chat RAG](#chat---chat-rag)
  - [Export](#export---exportação)
  - [Search](#search---pesquisa)
  - [Templates](#templates---templates-de-análise)
  - [Health](#health---monitoramento)
- [Códigos de Erro](#códigos-de-erro)
- [Rate Limiting](#rate-limiting)
- [Fluxo Completo](#fluxo-completo-de-uso)

---

## Visão Geral

O WhatsApp Insight Transcriber é uma plataforma avançada que permite:

| Funcionalidade | Descrição |
|---|---|
| 📤 **Upload** | Upload de arquivos ZIP exportados do WhatsApp |
| 🤖 **20 Agentes IA** | Processamento paralelo com múltiplos agentes Claude |
| 🎵 **Transcrição** | Transcrição automática de áudios |
| 🖼️ **Visão Computacional** | Descrição de imagens + OCR |
| 🎬 **Análise de Vídeo** | Extração de frames + transcrição |
| 💬 **Chat RAG** | Chat inteligente sobre a conversa |
| 📊 **Analytics** | Sentimento, palavras-chave, tópicos |
| 📄 **Exportação** | PDF, DOCX, Excel, CSV, HTML, JSON |
| 🔍 **Pesquisa** | Full-text com regex, filtros e highlighting |
| 📋 **Templates** | Análises pré-configuradas (jurídico, comercial, RH) |

---

## Autenticação

A API usa **JWT Bearer Token** para autenticação.

### Como obter o token

```bash
curl -X POST https://seu-servidor.com/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "SuaSenha123"}'
```

**Response:**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "expires_in": 86400,
  "username": "admin"
}
```

### Como usar o token

Inclua o token no header `Authorization` de todas as requisições:

```bash
curl -X GET https://seu-servidor.com/api/conversations \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
```

### Expiração

- Tokens expiram em **24 horas** (configurável)
- Após expiração, faça login novamente para obter novo token

---

## Endpoints

### Auth — Autenticação

#### `POST /api/auth/login`

Autentica o usuário e retorna um token JWT.

**Request Body:**
```json
{
  "username": "admin",
  "password": "SuaSenha123"
}
```

**Response (200):**
```json
{
  "access_token": "eyJhbGciOi...",
  "token_type": "bearer",
  "expires_in": 86400,
  "username": "admin"
}
```

**Erros:**
| Código | Descrição |
|--------|-----------|
| 401 | Credenciais inválidas |
| 422 | Dados de entrada inválidos |

**curl:**
```bash
curl -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"SuaSenha123"}'
```

---

#### `POST /api/auth/register`

Registra um novo usuário (se habilitado).

**Request Body:**
```json
{
  "username": "novo_usuario",
  "password": "MinhaSenh4Forte",
  "full_name": "João da Silva"
}
```

**Requisitos de senha:** mínimo 8 caracteres, 1 maiúscula, 1 número.

**Response (200):**
```json
{
  "access_token": "eyJhbGciOi...",
  "token_type": "bearer",
  "expires_in": 86400,
  "username": "novo_usuario"
}
```

**Erros:**
| Código | Descrição |
|--------|-----------|
| 403 | Registro desabilitado |
| 409 | Username já existe |
| 422 | Dados inválidos (senha fraca, etc.) |

---

#### `GET /api/auth/me`

Retorna informações do usuário autenticado.

**Headers:** `Authorization: Bearer <token>`

**Response (200):**
```json
{
  "username": "admin",
  "full_name": "Administrador",
  "is_admin": true
}
```

---

### Conversations — Conversas

#### `POST /api/conversations/upload`

Faz upload de arquivo ZIP do WhatsApp e inicia processamento.

**Headers:**
```
Authorization: Bearer <token>
Content-Type: multipart/form-data
```

**Request:** arquivo `.zip` no campo `file`

**Response (200):**
```json
{
  "session_id": "550e8400-e29b-41d4-a716-446655440000",
  "conversation_id": "conv-abc123",
  "message": "Upload realizado com sucesso. Processamento iniciado.",
  "status": "uploading"
}
```

**Erros:**
| Código | Descrição |
|--------|-----------|
| 400 | Não é .zip, ZIP corrompido, zip bomb |
| 413 | Arquivo muito grande |
| 401 | Não autenticado |

**curl:**
```bash
curl -X POST http://localhost:8000/api/conversations/upload \
  -H "Authorization: Bearer <token>" \
  -F "file=@WhatsApp_Chat_Grupo.zip"
```

---

#### `GET /api/conversations/progress/{session_id}`

Acompanha o progresso do processamento.

**Response (200):**
```json
{
  "session_id": "550e8400-...",
  "status": "processing",
  "progress": 0.45,
  "progress_message": "Transcrevendo áudios (45/100)...",
  "total_messages": 500
}
```

**Status possíveis:** `uploading`, `parsing`, `processing`, `analyzing`, `completed`, `failed`

**curl:**
```bash
curl http://localhost:8000/api/conversations/progress/550e8400-... \
  -H "Authorization: Bearer <token>"
```

---

#### `GET /api/conversations`

Lista conversas com paginação.

**Query Parameters:**
| Parâmetro | Tipo | Default | Descrição |
|-----------|------|---------|-----------|
| skip | int | 0 | Offset |
| limit | int | 20 | Itens por página |

**Response (200):**
```json
[
  {
    "id": "conv-abc123",
    "session_id": "550e8400-...",
    "original_filename": "WhatsApp Chat - Grupo.zip",
    "status": "completed",
    "progress": 1.0,
    "conversation_name": "Grupo da Família",
    "total_messages": 1500,
    "total_media": 200,
    "date_start": "2026-01-01T00:00:00Z",
    "date_end": "2026-03-31T23:59:00Z",
    "created_at": "2026-04-01T10:00:00Z"
  }
]
```

---

#### `GET /api/conversations/{conversation_id}`

Retorna detalhes completos de uma conversa.

**Response (200):** Objeto completo com resumo, sentimento, keywords, tópicos, etc.

---

#### `GET /api/conversations/{conversation_id}/messages`

Retorna mensagens com filtros e paginação.

**Query Parameters:**
| Parâmetro | Tipo | Default | Descrição |
|-----------|------|---------|-----------|
| skip | int | 0 | Offset |
| limit | int | 100 | Mensagens por página |
| media_only | bool | false | Apenas mensagens com mídia |
| sender | string | null | Filtrar por remetente |

**curl:**
```bash
curl "http://localhost:8000/api/conversations/conv-abc123/messages?limit=50&media_only=true" \
  -H "Authorization: Bearer <token>"
```

---

#### `DELETE /api/conversations/{conversation_id}`

Remove conversa e todos os dados (irreversível).

**Response (200):**
```json
{"message": "Conversa removida com sucesso"}
```

---

### Chat — Chat RAG

#### `POST /api/chat/{conversation_id}/message`

Envia pergunta sobre a conversa via Chat RAG (streaming SSE).

**Request Body:**
```json
{
  "conversation_id": "conv-abc123",
  "message": "Quais foram os principais tópicos discutidos?",
  "include_context": true
}
```

**Response:** Server-Sent Events (streaming)
```
data: Os principais
data:  tópicos foram
data:  trabalho e
data:  férias.
data: [DONE]
```

**curl:**
```bash
curl -N -X POST http://localhost:8000/api/chat/conv-abc123/message \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"conversation_id":"conv-abc123","message":"Resumo da conversa"}'
```

---

#### `GET /api/chat/{conversation_id}/history`

Retorna histórico completo do chat RAG.

**Response (200):**
```json
{
  "conversation_id": "conv-abc123",
  "messages": [
    {"id": "msg-1", "role": "user", "content": "Quem participou?", "created_at": "..."},
    {"id": "msg-2", "role": "assistant", "content": "João, Maria e Pedro.", "created_at": "..."}
  ]
}
```

---

#### `DELETE /api/chat/{conversation_id}/history`

Limpa o histórico do chat RAG.

---

#### `GET /api/chat/{conversation_id}/analytics`

Retorna analytics detalhados: estatísticas por participante, timeline, sentimento, nuvem de palavras, etc.

---

### Export — Exportação

#### `POST /api/conversations/{conversation_id}/export`

Exporta transcrição em múltiplos formatos.

**Formatos:** `pdf`, `docx`, `xlsx`, `csv`, `html`, `json`

**Request Body:**
```json
{
  "format": "pdf",
  "include_media_descriptions": true,
  "include_sentiment_analysis": true,
  "include_summary": true,
  "include_statistics": true
}
```

**Response:** Arquivo binário para download.

**curl:**
```bash
curl -X POST http://localhost:8000/api/conversations/conv-abc123/export \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"format":"pdf"}' \
  --output transcricao.pdf
```

---

#### `GET /api/media/{conversation_id}/{filename}`

Serve arquivo de mídia original.

---

#### `GET /api/media/{conversation_id}/{filename}/info`

Retorna metadados de uma mídia (tipo, transcrição, descrição, OCR).

---

#### `GET /api/agents/status`

Retorna status dos agentes de IA.

---

### Search — Pesquisa

#### `GET /api/search/messages`

Busca full-text em mensagens.

**Query Parameters:**
| Parâmetro | Tipo | Default | Descrição |
|-----------|------|---------|-----------|
| q | string | *obrigatório* | Texto para buscar (1-500 chars) |
| conversation_id | string | null | Filtrar por conversa |
| sender | string | null | Filtrar por remetente |
| date_from | datetime | null | Data/hora inicial (ISO 8601) |
| date_to | datetime | null | Data/hora final |
| type | string | null | Tipo de mídia |
| regex | bool | false | Interpretar q como regex |
| offset | int | 0 | Offset para paginação |
| limit | int | 50 | Resultados por página (max 200) |
| sort_by | string | "relevance" | `relevance` ou `chronological` |

**Response (200):**
```json
{
  "query": "reunião",
  "total": 25,
  "offset": 0,
  "limit": 50,
  "results": [
    {
      "message_id": "msg-001",
      "conversation_id": "conv-abc",
      "conversation_name": "Grupo Trabalho",
      "timestamp": "2026-01-15T14:30:00Z",
      "sender": "João",
      "text": "Vamos marcar a reunião",
      "highlighted_text": "Vamos marcar a **reunião**",
      "media_type": "text",
      "score": 15.0
    }
  ]
}
```

**curl:**
```bash
curl "http://localhost:8000/api/search/messages?q=reunião&sort_by=relevance&limit=20" \
  -H "Authorization: Bearer <token>"
```

---

#### `GET /api/search/conversations`

Busca em nomes de conversas.

**Query Parameters:**
| Parâmetro | Tipo | Descrição |
|-----------|------|-----------|
| q | string | Texto para buscar no nome da conversa |

---

### Templates — Templates de Análise

#### `GET /api/templates`

Lista todos os templates disponíveis (jurídico, comercial, RH, etc.).

**Response (200):**
```json
{
  "templates": [
    {
      "id": "juridico",
      "name": "Análise Jurídica",
      "description": "Análise de evidências e aspectos legais",
      "prompts": {"summary": "...", "entities": "...", "timeline": "..."}
    }
  ]
}
```

---

#### `GET /api/templates/{template_id}`

Retorna detalhes de um template específico.

---

#### `POST /api/templates/{template_id}/analyze/{conversation_id}`

Executa análise com template sobre uma conversa.

**Request Body (opcional):**
```json
{
  "prompt_keys": ["summary", "contradictions"]
}
```

**Response (200):**
```json
{
  "template_id": "juridico",
  "template_name": "Análise Jurídica",
  "conversation_id": "conv-abc123",
  "results": {
    "summary": "## Resumo Jurídico\n\nA conversa...",
    "contradictions": "## Contradições\n\n1. Em 15/01..."
  },
  "executed_prompts": ["summary", "contradictions"]
}
```

---

### Health — Monitoramento

#### `GET /api/health`

Health check básico (sem autenticação).

**Response (200):**
```json
{
  "status": "healthy",
  "app": "WhatsApp Insight Transcriber",
  "version": "1.0.0",
  "model": "claude-opus-4-6",
  "max_agents": 20,
  "cache_connected": true
}
```

---

#### `GET /api/health/detailed`

Health check com verificações completas de infraestrutura.

---

#### `GET /api/cache/stats`

Estatísticas do cache Redis.

---

## Códigos de Erro

| Código | Nome | Descrição |
|--------|------|-----------|
| 400 | Bad Request | Dados inválidos, ZIP corrompido, etc. |
| 401 | Unauthorized | Token ausente, inválido ou expirado |
| 403 | Forbidden | Sem permissão (ex.: registro desabilitado) |
| 404 | Not Found | Recurso não encontrado |
| 409 | Conflict | Conflito (ex.: usuário duplicado) |
| 413 | Payload Too Large | Arquivo excede tamanho máximo |
| 422 | Unprocessable Entity | Erro de validação nos dados |
| 429 | Too Many Requests | Rate limit excedido |
| 500 | Internal Server Error | Erro interno do servidor |

**Formato padrão de erro:**
```json
{
  "error": "NomeDoErro",
  "detail": "Descrição legível do erro",
  "status_code": 400,
  "context": {}
}
```

---

## Rate Limiting

O rate limiting é configurado no nginx reverse proxy:

- **Geral:** 30 requests/segundo por IP
- **Upload:** 5 requests/minuto por IP
- **Chat IA:** 10 requests/minuto por IP
- **Exportação:** 5 requests/minuto por IP

Quando excedido, retorna HTTP 429 com header `Retry-After`.

---

## Fluxo Completo de Uso

### 1. Autenticação

```bash
# Login
TOKEN=$(curl -s -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"SuaSenha123"}' | jq -r .access_token)

echo "Token: $TOKEN"
```

### 2. Upload e Processamento

```bash
# Upload do ZIP
UPLOAD=$(curl -s -X POST http://localhost:8000/api/conversations/upload \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@WhatsApp_Chat.zip")

SESSION_ID=$(echo $UPLOAD | jq -r .session_id)
CONV_ID=$(echo $UPLOAD | jq -r .conversation_id)

echo "Session: $SESSION_ID, Conversation: $CONV_ID"
```

### 3. Acompanhar Progresso

```bash
# Polling de progresso
while true; do
  PROGRESS=$(curl -s "http://localhost:8000/api/conversations/progress/$SESSION_ID" \
    -H "Authorization: Bearer $TOKEN")
  
  STATUS=$(echo $PROGRESS | jq -r .status)
  PERCENT=$(echo $PROGRESS | jq -r .progress)
  MSG=$(echo $PROGRESS | jq -r .progress_message)
  
  echo "[$STATUS] ${PERCENT}% - $MSG"
  
  if [ "$STATUS" = "completed" ] || [ "$STATUS" = "failed" ]; then
    break
  fi
  
  sleep 2
done
```

### 4. Explorar Conversa

```bash
# Detalhes da conversa
curl -s "http://localhost:8000/api/conversations/$CONV_ID" \
  -H "Authorization: Bearer $TOKEN" | jq .

# Mensagens (primeiras 50)
curl -s "http://localhost:8000/api/conversations/$CONV_ID/messages?limit=50" \
  -H "Authorization: Bearer $TOKEN" | jq .

# Analytics
curl -s "http://localhost:8000/api/chat/$CONV_ID/analytics" \
  -H "Authorization: Bearer $TOKEN" | jq .
```

### 5. Chat IA

```bash
# Perguntar sobre a conversa
curl -N -X POST "http://localhost:8000/api/chat/$CONV_ID/message" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d "{\"conversation_id\":\"$CONV_ID\",\"message\":\"Faça um resumo da conversa\"}"
```

### 6. Pesquisa

```bash
# Buscar mensagens
curl -s "http://localhost:8000/api/search/messages?q=reunião&sort_by=relevance" \
  -H "Authorization: Bearer $TOKEN" | jq .
```

### 7. Análise com Template

```bash
# Listar templates
curl -s "http://localhost:8000/api/templates" \
  -H "Authorization: Bearer $TOKEN" | jq .

# Executar análise jurídica
curl -s -X POST "http://localhost:8000/api/templates/juridico/analyze/$CONV_ID" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"prompt_keys":["summary","contradictions"]}' | jq .
```

### 8. Exportar

```bash
# Exportar para PDF
curl -X POST "http://localhost:8000/api/conversations/$CONV_ID/export" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"format":"pdf","include_summary":true}' \
  --output transcricao.pdf

# Exportar para Excel
curl -X POST "http://localhost:8000/api/conversations/$CONV_ID/export" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"format":"xlsx"}' \
  --output transcricao.xlsx
```

---

## Notas Adicionais

- Todos os timestamps são retornados em **UTC (ISO 8601)**
- O tamanho máximo de upload é configurável (padrão: 100MB)
- Conversas são processadas em background com até 20 agentes IA paralelos
- O cache Redis é opcional — a aplicação funciona sem ele (com degradação de performance)
- A documentação interativa (Swagger UI) está disponível em `/api/docs`
