# 📖 Documentação Completa — WhatsApp Insight Transcriber

> **Versão:** 1.0.0  
> **Data:** 01/04/2026  
> **Stack:** FastAPI (Python 3.12) + Next.js 14 (React 18, TypeScript)  
> **IA:** Claude Opus 4.6 via Gameron API  
> **Banco:** SQLite (aiosqlite) assíncrono  
> **Deploy:** Docker Compose

---

## 📁 Estrutura do Projeto

```
TRANSCRIÇÃOWHATSAPP/
├── backend/                    # API FastAPI
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── run.py                  # Script dev local
│   ├── .env.example
│   └── app/
│       ├── __init__.py
│       ├── main.py             # App FastAPI + lifespan
│       ├── config.py           # Configuração centralizada (Pydantic Settings)
│       ├── database.py         # Engine async SQLAlchemy
│       ├── dependencies.py     # Singletons (ClaudeService, Orchestrator)
│       ├── models.py           # Modelos SQLAlchemy (Conversation, Message, etc.)
│       ├── schemas.py          # Schemas Pydantic (request/response)
│       ├── routers/
│       │   ├── conversations.py  # CRUD + upload + progress
│       │   ├── chat.py           # Chat RAG + analytics
│       │   └── export.py         # Exportação PDF/DOCX + serve media
│       └── services/
│           ├── claude_service.py           # Integração Claude API (transcrição, visão, RAG)
│           ├── agent_orchestrator.py       # 20 agentes paralelos com PriorityQueue
│           ├── conversation_processor.py   # Pipeline completo de processamento
│           ├── whatsapp_parser.py          # Parser de exportação WhatsApp (.zip)
│           ├── media_metadata.py           # Extrator de metadados (ffprobe, Pillow)
│           └── export_service.py           # Geração PDF (ReportLab) e DOCX
│
├── frontend/                   # UI Next.js 14
│   ├── Dockerfile
│   ├── next.config.mjs
│   ├── package.json
│   ├── tailwind.config.js
│   ├── tsconfig.json
│   └── src/
│       ├── app/
│       │   ├── layout.tsx      # RootLayout + metadata + viewport
│       │   ├── page.tsx        # Página principal (SPA)
│       │   └── globals.css     # Estilos globais + animações
│       ├── components/
│       │   ├── UploadZone.tsx        # Upload drag-and-drop
│       │   ├── ProcessingPanel.tsx   # Barra de progresso + agentes
│       │   ├── ConversationView.tsx  # Visualização da conversa
│       │   ├── MessageBubble.tsx     # Bolha de mensagem individual
│       │   ├── ChatPanel.tsx         # Chat RAG com streaming
│       │   ├── AnalyticsPanel.tsx    # Gráficos e análises
│       │   └── ExportPanel.tsx       # Exportação PDF/DOCX
│       ├── lib/
│       │   ├── api.ts          # Client HTTP (fetch nativo)
│       │   └── utils.ts        # Utilidades (formatação, cores, etc.)
│       └── types/
│           └── index.ts        # Tipos TypeScript completos
│
├── docker-compose.yml
├── .gitignore
└── README.md
```

---

## 🔧 Arquitetura

### Visão Geral
```
[Usuário] → [Frontend Next.js :3020] → [Backend FastAPI :8020] → [Claude API]
                                               ↓
                                        [SQLite DB]
                                        [Uploads/Media]
```

### Fluxo de Processamento
1. **Upload:** Usuário envia `.zip` do WhatsApp
2. **Extração:** ZIP descompactado, chat `.txt` localizado
3. **Parse:** Regex identifica mensagens, remetentes, timestamps, mídias
4. **Persistência:** Mensagens salvas no SQLite
5. **Processamento Paralelo:** 20 agentes de IA processam mídias:
   - Áudios → Whisper (se disponível) ou Claude
   - Imagens → Claude Vision (descrição + OCR)
   - Vídeos → ffmpeg (frames) + Claude Vision + transcrição
6. **Análise Avançada:** Resumo, sentimento, palavras-chave, contradições
7. **Resultado:** Conversa completa disponível para consulta, chat RAG, exportação

### Backend (FastAPI)

#### `config.py`
Usa `pydantic-settings` para carregar configuração de variáveis de ambiente e `.env`.
Cria diretórios de upload/media automaticamente via `model_post_init`.

#### `database.py`
Engine assíncrono SQLAlchemy com `aiosqlite`. SessionFactory com `expire_on_commit=False`.
`init_db()` cria as tabelas automaticamente no startup.

#### `models.py`
4 tabelas principais:
- **Conversation** — conversa completa com metadados, análises e status
- **Message** — mensagem individual com transcrição/descrição/OCR/sentimento
- **ChatMessage** — histórico do chat RAG
- **AgentJob** — registro de jobs dos agentes de IA

#### `dependencies.py`
Padrão Singleton para `ClaudeService` e `AgentOrchestrator`.
`get_orchestrator()` faz lazy init e retorna instância global.

#### Routers

**`conversations.py`** — CRUD + upload:
- `POST /api/conversations/upload` — recebe ZIP, inicia processamento background
- `GET /api/conversations/progress/{session_id}` — polling de progresso
- `GET /api/conversations/` — listar conversas
- `GET /api/conversations/{id}` — detalhes
- `GET /api/conversations/{id}/messages` — mensagens com filtros
- `DELETE /api/conversations/{id}` — remover

**`chat.py`** — Chat RAG + Analytics:
- `POST /api/chat/{id}/message` — streaming SSE com contexto da conversa
- `GET /api/chat/{id}/history` — histórico
- `DELETE /api/chat/{id}/history` — limpar
- `GET /api/chat/{id}/analytics` — estatísticas detalhadas

**`export.py`** — Exportação + Mídia:
- `POST /api/conversations/{id}/export` — gera PDF ou DOCX
- `GET /api/media/{id}/{filename}` — serve arquivos de mídia
- `GET /api/media/{id}/{filename}/info` — metadados do arquivo
- `GET /api/agents/status` — status dos 20 agentes

#### Services

**`claude_service.py`** — Integração com API Claude:
- `transcribe_audio()` — Whisper como primário, fallback textual
- `describe_image()` — Claude Vision com OCR + sentimento
- `transcribe_video()` — frames + áudio combinados
- `analyze_sentiment()` — análise emocional
- `generate_summary()` — resumo executivo
- `detect_contradictions()` — detecção de contradições
- `extract_keywords()` — palavras-chave e tópicos
- `chat_with_context()` — chat RAG com streaming

**`agent_orchestrator.py`** — Pool de 20 agentes:
- `AgentOrchestrator` gerencia fila com prioridade (`PriorityQueue`)
- Cada `AIAgent` processa jobs independentemente
- `submit_batch()` + `wait_for_jobs()` com callback de progresso
- Cleanup automático de resultados (evita memory leak)

**`conversation_processor.py`** — Pipeline completo:
- `process_upload()` orquestra todas as fases
- Processamento de mídia em paralelo com os 20 agentes
- Análise avançada (resumo, sentimento, keywords, contradições) em paralelo

**`whatsapp_parser.py`** — Parser robusto:
- 3 padrões regex para formatos Android, iOS e alternativo
- Detecção de mídias por extensão e padrão
- Suporte a AM/PM, múltiplos formatos de data
- Proteção contra path traversal em ZIPs

**`media_metadata.py`** — Extração de metadados:
- Imagens: Pillow (resolução, formato)
- Áudio/Vídeo: ffprobe (duração, codec, bitrate, fps)
- Formatação legível (tamanho, duração)

**`export_service.py`** — Geração de documentos:
- `PDFExporter` com ReportLab (layout profissional A4)
- `DOCXExporter` com python-docx (formatação Office)
- Sanitização de caracteres fora do BMP

### Frontend (Next.js 14)

#### `next.config.mjs`
- Output `standalone` para Docker
- Rewrites `/api/*` → backend via `BACKEND_URL`
- `remotePatterns` para imagens
- TypeScript/ESLint ignorados (TODO: corrigir)

#### `layout.tsx`
- Metadata com keywords, ícones
- Viewport separado com `themeColor`
- Background com efeitos de blur/glow
- Toaster para notificações

#### Componentes

**`page.tsx`** — SPA com 4 views:
- `home` — upload + histórico
- `processing` — acompanhamento em tempo real
- `conversation` — visualização completa
- `history` — lista de conversas anteriores

**`UploadZone.tsx`** — Drag-and-drop com react-dropzone, validação de ZIP.

**`ProcessingPanel.tsx`** — Progresso com polling, visualização de agentes ativos.

**`ConversationView.tsx`** — Exibição paginada de mensagens com filtros.

**`MessageBubble.tsx`** — Bolha estilizada por tipo de mídia com player de áudio/vídeo.

**`ChatPanel.tsx`** — Chat com streaming SSE, histórico, markdown rendering.

**`AnalyticsPanel.tsx`** — Gráficos Recharts (timeline, sentimento, participantes).

**`ExportPanel.tsx`** — Opções de exportação PDF/DOCX.

#### `api.ts`
Client HTTP usando `fetch` nativo. Funções tipadas para todas as rotas.
Streaming via `ReadableStream` para chat.

#### `utils.ts`
- `cn()` — classnames com tailwind-merge
- Formatação de datas com date-fns pt-BR
- Helpers de cores por remetente
- Helpers de sentimento (emoji, cores)

#### `types/index.ts`
Tipos TypeScript completos espelhando schemas Pydantic do backend.

---

## 🐳 Deploy com Docker

```bash
# Clonar
git clone <repo>
cd TRANSCRIÇÃOWHATSAPP

# Configurar
cp backend/.env.example backend/.env
# Editar backend/.env com sua ANTHROPIC_API_KEY

# Build e run
docker-compose up -d --build

# Acessar
# Frontend: http://localhost:3020
# Backend API: http://localhost:8020/api/docs
# Health: http://localhost:8020/api/health
```

### Portas
| Serviço | Container | Host |
|---------|-----------|------|
| Backend | 8000 | 8020 |
| Frontend | 3000 | 3020 |

### Volumes
- `wit_data` — persistência do SQLite + uploads + mídia

---

## 🔑 Variáveis de Ambiente

### Backend
| Variável | Descrição | Default |
|----------|-----------|---------|
| `ANTHROPIC_API_KEY` | API key do Claude | obrigatório |
| `ANTHROPIC_BASE_URL` | URL do proxy API | `https://api.gameron.me` |
| `CLAUDE_MODEL` | Modelo Claude | `claude-opus-4-6` |
| `MAX_AGENTS` | Agentes paralelos | `20` |
| `DATABASE_URL` | URL do SQLite | `sqlite+aiosqlite:///./whatsapp_insight.db` |
| `DEBUG` | Modo debug | `false` |
| `SECRET_KEY` | Chave secreta | `change-me-in-production...` |
| `ALLOWED_ORIGINS` | CORS origins | `["http://localhost:3000"]` |

### Frontend
| Variável | Descrição | Default |
|----------|-----------|---------|
| `NEXT_PUBLIC_API_URL` | URL pública da API | `http://77.42.68.212:8020` |
| `BACKEND_URL` | URL interna (rewrites) | `http://backend:8000` |

---

## 🧪 Testes Realizados

### Validação Estática
- ✅ Nenhuma dependência removida era importada no código (`axios`, `react-wordcloud`, `react-intersection-observer`, `next-themes`)
- ✅ `next.config.mjs` — rewrites com env var, `remotePatterns` correto
- ✅ `layout.tsx` — `Viewport` importado e exportado corretamente
- ✅ `globals.css` — keyframes `spin` e `pulse` definidos
- ✅ `package.json` — JSON válido, dependências consistentes
- ✅ Todos os imports entre módulos backend são válidos
- ✅ Schemas Pydantic espelham modelos SQLAlchemy
- ✅ Types TypeScript espelham schemas Pydantic
- ✅ `api.ts` usa fetch nativo (sem axios)
- ✅ Sem vulnerabilidades de path traversal no parser ZIP

### Validação de Arquitetura
- ✅ Padrão singleton para serviços de IA
- ✅ Processamento background com `BackgroundTasks`
- ✅ Streaming SSE para chat RAG
- ✅ Cleanup de recursos temporários (frames, áudio extraído)
- ✅ Retry com backoff exponencial na API Claude
- ✅ Semáforo para limitar chamadas simultâneas

---

## 🐛 Bugs Identificados e Status

### Corrigidos Nesta Sessão (Fix-7)
1. ✅ Rewrites com IP hardcoded → env var `BACKEND_URL`
2. ✅ `images.domains` deprecado → `remotePatterns`
3. ✅ `ignoreBuildErrors` sem TODO → comentário adicionado
4. ✅ Dependências não utilizadas → removidas
5. ✅ `themeColor` deprecado no Metadata → export `viewport`
6. ✅ Keyframes `spin`/`pulse` sem definição → adicionados

### Bugs Pré-existentes Identificados (Debug)
7. ⚠️ `conversation_processor.py:437` usa `datetime.utcnow()` deprecado no Python 3.12+ (deveria usar `datetime.now(timezone.utc)`)
8. ⚠️ `docker-compose.yml:22` — `ALLOWED_ORIGINS` como string JSON dentro de env pode falhar no parse do Pydantic
9. ⚠️ `claude_service.py:420-426` — extrai áudio com codec `mp3` mas extensão `.wav` (inconsistência)
10. ⚠️ `frontend/Dockerfile:10` — `NEXT_PUBLIC_API_URL=http://localhost:8000` hardcoded no build (deveria ser build arg)
11. ⚠️ `config.py:13` — API key hardcoded como default (risco de segurança se `.env` não configurado)
12. ⚠️ `chat.py:91-92` — response_text closure pode ter race condition em requests simultâneos
13. ⚠️ `utils.ts:41` — fallback para `http://localhost:8020` hardcoded
