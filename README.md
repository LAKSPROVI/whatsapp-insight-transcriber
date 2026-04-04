# 🔍 WhatsApp Insight Transcriber

> **Plataforma avançada de transcrição e análise de conversas do WhatsApp com IA**  
> 20 agentes paralelos • Claude Opus 4.6 • Visão Computacional • RAG • Análise de Sentimento

---

## 📋 Índice

- [Visão Geral](#visão-geral)
- [Arquitetura Técnica](#arquitetura-técnica)
- [Funcionalidades](#funcionalidades)
- [Instalação Rápida](#instalação-rápida)
- [Deploy](#deploy)
- [Configuração](#configuração)
- [Como Usar](#como-usar)
- [Estrutura do Projeto](#estrutura-do-projeto)
- [API Reference](#api-reference)
- [Infraestrutura de Agentes](#infraestrutura-de-agentes)

---

## 🎯 Visão Geral

O **WhatsApp Insight Transcriber** é uma plataforma web de última geração que recebe exportações `.zip` do WhatsApp e produz uma transcrição completa e enriquecida com IA — incluindo áudios, vídeos, imagens — além de análises avançadas como sentimento, contradições, nuvem de palavras e um chat interativo RAG.

### Stack Técnica (Justificativa)

| Componente | Tecnologia | Por Quê |
|------------|-----------|---------|
| **Backend** | Python + FastAPI | Assíncrono nativo, excelente para orquestração de IA com `asyncio`, ecosystem IA maduro |
| **Frontend** | Next.js 14 + TypeScript | SSR, DX superior, ecosystem React robusto |
| **Banco** | SQLite (dev) / PostgreSQL (prod) via SQLAlchemy async | Simples para iniciar, escalável |
| **IA** | Claude Opus 4.6 via Anthropic SDK | Melhor modelo multimodal disponível |
| **Agentes** | asyncio.Queue + PriorityQueue | Paralelismo nativo, sem overhead de frameworks externos |

---

## 🏗️ Arquitetura Técnica

```
┌─────────────────────────────────────────────────────────┐
│                    FRONTEND (Next.js)                    │
│  Upload Zone → Processing Panel → Conversation View      │
│  Chat RAG → Analytics Dashboard → Export PDF/DOCX        │
└─────────────────────┬───────────────────────────────────┘
                      │ HTTP / SSE (Streaming)
┌─────────────────────▼───────────────────────────────────┐
│                   BACKEND (FastAPI)                      │
│                                                          │
│  POST /upload → Background Task → ConversationProcessor  │
│                                                          │
│  ┌─────────────────────────────────────────────────┐    │
│  │           AgentOrchestrator                      │    │
│  │  ┌────┐ ┌────┐ ┌────┐ ... ┌────┐ (20 agentes)  │    │
│  │  │ 01 │ │ 02 │ │ 03 │     │ 20 │               │    │
│  │  └──┬─┘ └──┬─┘ └──┬─┘     └──┬─┘               │    │
│  │     └──────┴──────┴───────────┘                  │    │
│  │              PriorityQueue                        │    │
│  └─────────────────────────────────────────────────┘    │
│                                                          │
│  ClaudeService ──→ Anthropic API (gameron proxy)         │
│  WhatsAppParser ──→ Parse ZIP + Mensagens                 │
│  MediaMetadataExtractor ──→ ffprobe + Pillow             │
│  ExportService ──→ ReportLab (PDF) + python-docx (DOCX)  │
└─────────────────────────────────────────────────────────┘
                      │
               ┌──────▼──────┐
               │   Database   │
               │  (SQLite /   │
               │  PostgreSQL) │
               └─────────────┘
```

### Fluxo de Processamento

1. **Upload** → Arquivo `.zip` enviado pelo usuário
2. **Extract** → ZIP descompactado, chat `.txt` e mídias separados
3. **Parse** → Parser identifica mensagens, timestamps, remetentes, tipos de mídia
4. **DB Save** → Mensagens salvas no banco com metadados
5. **Agent Dispatch** → 20 agentes recebem jobs em paralelo:
   - Áudios → `TRANSCRIBE_AUDIO`
   - Imagens → `DESCRIBE_IMAGE` (visão + OCR)
   - Vídeos → `TRANSCRIBE_VIDEO` (frames + áudio)
6. **Advanced Analysis** → Resumo, sentimento, contradições, keywords (paralelo)
7. **Complete** → UI atualizada, usuário pode interagir

---

## ✨ Funcionalidades

### 🎵 Processamento de Mídias
- **Áudios**: Transcrição completa via Claude + Whisper (fallback)
- **Imagens**: Descrição detalhada + OCR de texto presente
- **Vídeos**: Extração de frames + transcrição do áudio
- **Documentos**: Indexação e referência
- **Metadados**: Tamanho, resolução, duração, codec, bitrate para cada arquivo

### 🤖 Sistema de Agentes
- **20 agentes assíncronos** processando em paralelo
- **Fila com prioridade** — jobs críticos processados primeiro
- **Balanceamento automático** — próximo agente livre pega o job
- **Retry e error handling** — falhas isoladas, conversa continua

### 📊 Análises Avançadas
- **Análise de Sentimento** por mensagem e geral da conversa
- **Resumo Executivo** gerado por IA
- **Detecção de Contradições** e mudanças de posição
- **Nuvem de Palavras** com frequência real
- **Linha do Tempo** de atividade e sentimento
- **Momentos-Chave** identificados automaticamente
- **Estatísticas por Participante**

### 💬 Chat RAG
- Converse com a IA sobre a conversa transcrita
- **Streaming** — respostas em tempo real
- Histórico de chat persistido
- Sugestões de perguntas rápidas

### 📄 Exportação Profissional
- **PDF** formatado com ReportLab (capa, índice, tabelas)
- **DOCX** compatível com Word
- Opções configuráveis: incluir sentimento, mídias, resumo, estatísticas

### 🎨 UI/UX Futurista
- Design dark com glassmorphism e gradientes
- Animações Framer Motion
- Timeline visual da conversa com avatares coloridos
- Preview inline de imagens
- Botões **Visualizar** e **Baixar** em cada mídia

---

## 🚀 Instalação Rápida

### Pré-requisitos
- Python 3.11+
- Node.js 18+
- `ffmpeg` (para processamento de vídeo/áudio)
- gameron rodando localmente na porta 1337

### Backend

```bash
cd backend

# Criar ambiente virtual
python -m venv venv
source venv/bin/activate  # Linux/Mac
# ou
venv\Scripts\activate  # Windows

# Instalar dependências
pip install -r requirements.txt

# Configurar variáveis de ambiente
cp .env.example .env
# Editar .env e adicionar sua ANTHROPIC_API_KEY

# Iniciar servidor
python run.py
```

O backend estará disponível em `http://localhost:8000`  
Documentação Swagger: `http://localhost:8000/api/docs`

### Frontend

```bash
cd frontend

# Instalar dependências
npm install

# Iniciar servidor de desenvolvimento
npm run dev
```

O frontend estará disponível em `http://localhost:3000`

### Docker (Recomendado para produção)

```bash
# Copiar e configurar variáveis
cp backend/.env.example .env

# Subir toda a stack
docker-compose up -d

# Ver logs
docker-compose logs -f
```

## Deploy

### Deploy recorrente via GitHub Actions

O projeto esta preparado para deploy automatizado no ambiente `production` por meio do workflow `/.github/workflows/deploy.yml`.

- Configure os secrets do ambiente `production` no GitHub
- Use `push` para `main` ou `workflow_dispatch`
- Nao armazene tokens, chaves privadas ou segredos no repositorio

Documentacao operacional:

- `docs/DEPLOY_GITHUB.md`

---

## ⚙️ Configuração

### Variáveis de Ambiente (Backend)

| Variável | Padrão | Descrição |
|----------|--------|-----------|
| `ANTHROPIC_API_KEY` | — | **Obrigatória** — Chave da API Anthropic |
| `ANTHROPIC_BASE_URL` | `http://localhost:1337` | URL do proxy gameron |
| `CLAUDE_MODEL` | `claude-opus-4-6` | Modelo Claude a utilizar |
| `MAX_AGENTS` | `20` | Número de agentes paralelos |
| `MAX_UPLOAD_SIZE` | `524288000` | Tamanho máximo de upload (bytes, 500MB) |
| `DATABASE_URL` | SQLite | URL do banco de dados |
| `UPLOAD_DIR` | `uploads/` | Diretório de uploads |
| `MEDIA_DIR` | `media/` | Diretório de mídias extraídas |

### Configuração do gameron

O sistema usa o **gameron** como proxy local para coletar os dados na máquina e enviá-los à API Claude. Configure o gameron para:

1. Escutar na porta `1337` (padrão)
2. Rotear requisições para `https://api.anthropic.com`
3. Aplicar sua API key automaticamente

Altere `ANTHROPIC_BASE_URL` no `.env` se usar porta diferente.

---

## 📱 Como Usar

### 1. Exportar conversa do WhatsApp

**Android:**
1. Abra a conversa
2. Toque nos 3 pontos (⋮)
3. "Mais" → "Exportar conversa"
4. Escolha "Incluir mídia" para processar arquivos
5. Salve o `.zip`

**iPhone:**
1. Abra a conversa
2. Toque no nome do contato/grupo
3. "Exportar conversa"
4. Escolha "Incluir mídia"
5. Salve o `.zip`

### 2. Upload na Plataforma

1. Acesse `http://localhost:3000`
2. Arraste o arquivo `.zip` ou clique para selecionar
3. Aguarde o processamento (barra de progresso em tempo real)
4. A transcrição abre automaticamente ao concluir

### 3. Navegando na Transcrição

- **Barra de pesquisa**: busca em textos, transcrições e OCR
- **Filtro por participante**: filtra mensagens por remetente
- **Expandir mídias**: clique em "Ver conteúdo da IA" para ver transcrição completa
- **Botões Visualizar/Baixar**: acessar mídia original diretamente da linha do tempo

### 4. Análises

Clique em "Análises" (ícone de gráfico) para ver:
- Visão geral com gráficos interativos
- Linha do tempo de sentimento
- Distribuição de mídias
- Insights: resumo, momentos-chave, contradições

### 5. Chat com IA

Clique em "Chat IA" para abrir o painel de chat RAG:
- Faça perguntas sobre qualquer aspecto da conversa
- Respostas em streaming (aparecem em tempo real)
- Use as sugestões rápidas ou formule sua própria pergunta

### 6. Exportar Relatório

Clique em "Exportar" para gerar PDF ou DOCX:
- Selecione formato (PDF ou Word)
- Configure o que incluir
- Clique em "Exportar" — download inicia automaticamente

---

## 🗂️ Estrutura do Projeto

```
TRANSCRIÇÃOWHATSAPP/
├── backend/
│   ├── app/
│   │   ├── main.py              # Entrada FastAPI + Lifespan
│   │   ├── config.py            # Configurações centralizadas
│   │   ├── models.py            # SQLAlchemy ORM models
│   │   ├── schemas.py           # Pydantic schemas
│   │   ├── database.py          # Engine async + sessões
│   │   ├── dependencies.py      # Dependency Injection
│   │   ├── routers/
│   │   │   ├── conversations.py # Upload, progresso, listagem
│   │   │   ├── chat.py          # Chat RAG + Analytics
│   │   │   └── export.py        # PDF/DOCX + Servir mídias
│   │   └── services/
│   │       ├── whatsapp_parser.py       # Parser ZIP + chat
│   │       ├── media_metadata.py        # Extração de metadados
│   │       ├── agent_orchestrator.py    # 20 agentes paralelos
│   │       ├── claude_service.py        # Integração Claude API
│   │       ├── conversation_processor.py # Pipeline completo
│   │       └── export_service.py        # PDF + DOCX
│   ├── requirements.txt
│   ├── Dockerfile
│   ├── run.py
│   └── .env.example
│
├── frontend/
│   ├── src/
│   │   ├── app/
│   │   │   ├── layout.tsx       # Root layout com providers
│   │   │   ├── page.tsx         # Página principal
│   │   │   └── globals.css      # Estilos globais (futurista)
│   │   ├── components/
│   │   │   ├── UploadZone.tsx           # Drag & drop upload
│   │   │   ├── ProcessingPanel.tsx      # Status do processamento
│   │   │   ├── ConversationView.tsx     # Visualizador principal
│   │   │   ├── MessageBubble.tsx        # Bubble de mensagem
│   │   │   ├── ChatPanel.tsx            # Chat RAG (streaming)
│   │   │   ├── AnalyticsPanel.tsx       # Dashboards e gráficos
│   │   │   └── ExportPanel.tsx          # Exportação PDF/DOCX
│   │   ├── lib/
│   │   │   ├── api.ts           # Todos os calls de API
│   │   │   └── utils.ts         # Funções auxiliares
│   │   └── types/
│   │       └── index.ts         # TypeScript types
│   ├── package.json
│   ├── tailwind.config.js
│   ├── next.config.ts
│   └── Dockerfile
│
├── docker-compose.yml
└── README.md
```

---

## 🔌 API Reference

### Endpoints Principais

| Método | Endpoint | Descrição |
|--------|----------|-----------|
| `POST` | `/api/conversations/upload` | Upload do ZIP |
| `GET` | `/api/conversations/progress/{session_id}` | Progresso em tempo real |
| `GET` | `/api/conversations/` | Listar conversas |
| `GET` | `/api/conversations/{id}` | Detalhes da conversa |
| `GET` | `/api/conversations/{id}/messages` | Mensagens paginadas |
| `POST` | `/api/chat/{id}/message` | Chat RAG (SSE streaming) |
| `GET` | `/api/chat/{id}/analytics` | Analytics completo |
| `POST` | `/api/conversations/{id}/export` | Gerar PDF/DOCX |
| `GET` | `/api/media/{conv_id}/{filename}` | Servir mídia original |
| `GET` | `/api/health` | Health check |

Documentação interativa completa: `http://localhost:8000/api/docs`

---

## 🤖 Infraestrutura de Agentes

### Como os 20 Agentes Funcionam

```python
# Orquestrador cria 20 agentes na inicialização
orchestrator = AgentOrchestrator(claude_service, max_agents=20)
await orchestrator.start()  # 20 workers asyncio rodando

# Para processar uma conversa com 150 mídias:
jobs = [AgentJob(type=TRANSCRIBE_AUDIO, payload={"file": "..."}), ...]
job_ids = await orchestrator.submit_batch(jobs)  # Todos na fila

# Agentes pegam jobs da PriorityQueue automaticamente
# 20 agentes em paralelo = 150 mídias processadas ~7x mais rápido
results = await orchestrator.wait_for_jobs(job_ids)
```

### Tipos de Jobs

| Job Type | Agente faz | Resultado |
|----------|-----------|-----------|
| `TRANSCRIBE_AUDIO` | Claude transcreve o áudio | `transcription` |
| `DESCRIBE_IMAGE` | Claude descreve + OCR | `description`, `ocr_text` |
| `TRANSCRIBE_VIDEO` | Frames + áudio combinados | `description`, `transcription` |
| `ANALYZE_SENTIMENT` | Claude analisa sentimento | `sentiment`, `score` |
| `GENERATE_SUMMARY` | Resumo executivo | `summary`, `topics` |
| `DETECT_CONTRADICTIONS` | Análise de inconsistências | `contradictions` |
| `EXTRACT_KEYWORDS` | Keywords e entidades | `keywords`, `word_frequency` |

---

## 🛠️ Melhorias Proativas Implementadas

Além do escopo inicial, implementamos:

1. **🏷️ Detecção de Momentos-Chave** — IA identifica automaticamente pontos de inflexão
2. **⚠️ Análise de Contradições** — Detecta mudanças de posição e inconsistências
3. **📊 Dashboard de Atividade** — Gráficos temporais de mensagens e sentimento
4. **🔍 Busca Full-Text** — Pesquisa em todos os campos (texto, transcrições, OCR)
5. **👤 Filtro por Participante** — Visualizar mensagens de um remetente específico
6. **🎭 Stickers Processados** — Incluídos na análise visual
7. **📍 Localizações** — Registradas na timeline
8. **🔄 Carregamento Paginado** — Para conversas muito longas
9. **🎨 Cores por Remetente** — Identificação visual imediata
10. **⭐ Marcação de Momentos-Chave** — Destacados na timeline

---

## 📝 Licença

MIT License - Veja [LICENSE](LICENSE) para detalhes.

---

*Desenvolvido com ❤️ usando Claude Opus 4.6 e 20 agentes de IA paralelos.*
