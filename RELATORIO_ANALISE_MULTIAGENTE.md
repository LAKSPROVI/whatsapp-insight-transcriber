# RELATÓRIO DE ANÁLISE MULTI-AGENTE — WhatsApp Insight Transcriber (WIT)

**Versão:** 1.0  
**Data:** 2026-04-03  
**Metodologia:** Análise Multi-Agente Cooperativa (24 agentes especializados)  
**Classificação:** Confidencial — Uso Interno

---

## ÍNDICE

1. [Sumário Executivo](#1-sumário-executivo)
2. [Metodologia Multi-Agente](#2-metodologia-multi-agente)
3. [Diagnóstico do Estado Atual](#3-diagnóstico-do-estado-atual)
4. [Lista de Funcionalidades Propostas](#4-lista-de-funcionalidades-propostas)
5. [Análise de Viabilidade Técnica e Econômica](#5-análise-de-viabilidade-técnica-e-econômica)
6. [Priorização (MoSCoW + RICE)](#6-priorização-moscow--rice)
7. [Backlog Priorizado](#7-backlog-priorizado)
8. [Especificações de Requisitos e Critérios de Aceitação](#8-especificações-de-requisitos-e-critérios-de-aceitação)
9. [Arquitetura de Alto Nível](#9-arquitetura-de-alto-nível)
10. [Plano de Implementação](#10-plano-de-implementação)
11. [Mapa de Riscos](#11-mapa-de-riscos)
12. [Plano de Testes](#12-plano-de-testes)
13. [Métricas de Sucesso](#13-métricas-de-sucesso)
14. [Limitações e Considerações](#14-limitações-e-considerações)
15. [Questionamentos Clarificadores](#15-questionamentos-clarificadores)

---

## 1. SUMÁRIO EXECUTIVO

### Contexto do Projeto

O **WhatsApp Insight Transcriber (WIT)** é uma plataforma web que processa exportações `.zip` do WhatsApp, transformando conversas brutas em transcrições enriquecidas por IA, com análise de sentimentos, detecção de contradições, chat RAG interativo e exportação multi-formato. O sistema atende profissionais jurídicos, equipes de RH, equipes comerciais, investigadores e pesquisadores.

### Stack Tecnológico Atual

| Camada | Tecnologia |
|--------|-----------|
| Backend | FastAPI (Python 3.12), SQLAlchemy Async, 20 agentes AI paralelos |
| Frontend | Next.js 14, React 18, TypeScript, Zustand, TanStack Query, Tailwind CSS |
| IA | Claude Opus 4.6 (via proxy Gameron), Whisper (local), FFmpeg |
| Banco de Dados | SQLite (dev) / PostgreSQL 16 (prod) |
| Cache | Redis 7 |
| Infraestrutura | Docker Compose (7 containers), Hetzner VPS, GitHub Actions CI/CD |
| Observabilidade | Fluent Bit + Elasticsearch + Kibana (logs apenas) |

### Descobertas Críticas

A análise multi-agente identificou:

- **3 vulnerabilidades CRÍTICAS de segurança** (IDOR, ausência de TLS, segredos hardcoded)
- **14 gaps de conformidade LGPD/GDPR** (sem consentimento, transferência internacional sem DPA)
- **64% de cobertura de testes** (4 módulos críticos sem testes)
- **30 novas funcionalidades propostas** por 6 agentes especializados
- **Estimativa de investimento total**: ~672h (~$50.400 a $75/h) para remediar gaps + implementar features prioritárias
- **Potencial de redução de 75% nos custos de API Claude** via estratégia de model fallback

### Recomendação Principal

**Antes de implementar novas funcionalidades, é imperativo resolver as 3 vulnerabilidades P0 de segurança (IDOR, TLS, segredos) e os gaps críticos de LGPD.** O custo estimado para estas correções é de ~$6.300 (84h) e devem ser concluídas em 2 semanas.

---

## 2. METODOLOGIA MULTI-AGENTE

### 2.1 Protocolo de Análise

Foram empregados **24 agentes especializados** organizados em **4 fases** de cooperação:

```
FASE 1 — COLETA DE DADOS (6 agentes, paralelo)
├── Agent 1:  Arquiteto Backend
├── Agent 2:  Arquiteto Frontend
├── Agent 3:  Engenheiro DevOps/Infra
├── Agent 4:  Analista de Documentação/Negócio
├── Agent 5:  Analista de QA/Testes
└── Agent 6:  Especialista em Segurança

FASE 2 — PROPOSTA DE FUNCIONALIDADES (6 agentes, paralelo)
├── Agent 7:  Analista de Negócios
├── Agent 8:  Engenheiro de Dados
├── Agent 9:  Designer UX
├── Agent 10: Especialista em Conformidade/Legal
├── Agent 11: Engenheiro AI/ML
└── Agent 12: Product Manager

FASE 3 — VIABILIDADE E RISCOS (6 agentes, paralelo)
├── Agent 13: Arquiteto de Viabilidade Técnica
├── Agent 14: Analista Econômico (CAPEX/OPEX)
├── Agent 15: Analista de Riscos
├── Agent 16: Engenheiro DevOps
├── Agent 17: Líder de Estratégia QA
└── Agent 18: Data Privacy Officer (DPO)

FASE 4 — ARQUITETURA E DESIGN (6 agentes, paralelo)
├── Agent 19: Arquiteto Multi-Tenancy
├── Agent 20: Arquiteto de Colaboração Real-Time
├── Agent 21: Arquiteto de Pipeline AI
├── Agent 22: Arquiteto de Integrações
├── Agent 23: Arquiteto de Observabilidade
└── Agent 24: Arquiteto de Segurança
```

### 2.2 Registro de Evidências

Cada agente leu e analisou diretamente o código-fonte do projeto:
- **Backend**: 22 arquivos Python (~5.000 linhas)
- **Frontend**: 18 arquivos TS/TSX (~8.000 linhas)
- **Infraestrutura**: docker-compose.yml, nginx.conf, deploy.yml, Dockerfiles, logging configs
- **Documentação**: 5 documentos MD, README, API docs
- **Testes**: 14 arquivos de teste (~3.500 linhas)

### 2.3 Controle de Qualidade

- Cross-validation entre agentes (ex: Agent 6/Segurança validou achados do Agent 3/DevOps)
- Cada proposta inclui: descrição, benefício, complexidade, esforço, dependências, riscos e KPIs
- Priorização via métodos RICE e MoSCoW com consenso entre agentes

---

## 3. DIAGNÓSTICO DO ESTADO ATUAL

### 3.1 Arquitetura Backend

**Pontos Fortes:**
- Pipeline de processamento robusto com 20 agentes AI paralelos (PriorityQueue)
- Hierarquia de exceções bem estruturada com Error Advisor (20+ erros catalogados)
- Sistema de logging estruturado (structlog) com redação de PII em duas camadas
- 6 formatos de exportação (PDF, DOCX, XLSX, CSV, HTML, JSON)
- Parser WhatsApp suportando 6 formatos regex (Android/iOS/Web) e multi-idioma
- Retry com backoff exponencial para API Claude (4 retries)
- Cache Redis com graceful degradation

**Pontos Fracos:**
- Fila de jobs em memória (`asyncio.PriorityQueue`) — perda de estado no restart
- Rate limiter em memória — incompatível com múltiplas instâncias
- Progress store em memória — efêmero
- Singletons globais (`_claude_service`, `_orchestrator`) — não escala horizontalmente
- Sem migrações de banco (usa `create_all` — risco de perda de dados em mudanças de schema)
- Sem multi-tenancy (IDOR: qualquer usuário autenticado vê todas as conversas)

### 3.2 Arquitetura Frontend

**Pontos Fortes:**
- SPA moderna com Next.js 14 App Router
- Gestão de estado dual: Zustand (client) + TanStack Query (server)
- Virtualização de listas para performance (@tanstack/react-virtual)
- Design futurista com glassmorfismo, animações Framer Motion
- PWA com Service Worker
- Sanitização XSS via DOMPurify
- Acessibilidade (ARIA labels, skip-nav, reduced-motion)
- WebSocket + HTTP polling para atualizações real-time

**Pontos Fracos:**
- Token JWT no localStorage (vulnerável a XSS)
- Sem testes frontend (zero Jest/Playwright)
- DevTools do Zustand habilitado incondicionalmente
- Fallback para `localhost:8020` hardcoded em utils.ts

### 3.3 Infraestrutura

**Pontos Fortes:**
- Containers com usuários non-root
- Healthchecks definidos para todos os serviços
- Multi-stage build no frontend (imagem otimizada)
- PostgreSQL e Redis sem ports expostos ao host

**Pontos Fracos CRÍTICOS:**
- **Nginx NÃO está no docker-compose.yml** — toda a configuração de rate limiting, headers de segurança e SSL é código morto
- **TLS/SSL totalmente comentado** — tráfego em cleartext incluindo JWT e credenciais
- **Segredos hardcoded** no docker-compose e CI/CD (`Admin@2024Secure!`, `changeme`, etc.)
- **Deploy como root** no servidor
- **docker compose down** antes de rebuild — downtime de 5-15 minutos por deploy
- **Sem backups** automatizados
- **Sem limites de recursos** nos containers
- **Elasticsearch/Kibana/FluentBit** com portas expostas publicamente
- **Docker socket montado** no Fluent Bit (risco de escape de container)

### 3.4 Segurança — Avaliação: **B- (Boa fundação, gaps críticos)**

| ID | Severidade | Achado |
|---|---|---|
| **AUTHZ-01** | **CRÍTICO** | IDOR: qualquer usuário autenticado acessa QUALQUER conversa. Sem `owner_id` no modelo |
| **HDR-01** | **CRÍTICO** | SSL/TLS não habilitado — credenciais e PII transmitidos em cleartext |
| **ENV-02** | **CRÍTICO** | Segredos com defaults previsíveis no docker-compose (JWT key, admin password, DB password) |
| **AUTH-02** | ALTO | Sem mecanismo de refresh token — JWT comprometido válido por 24h sem revogação |
| **MISC-01** | ALTO | Token JWT no localStorage — vulnerável a roubo via XSS |
| **DOCK-01** | ALTO | Docker socket montado no Fluent Bit — risco de escape |
| **VAL-01** | MÉDIO | Chat permite 10.000 chars enviados direto ao Claude — sem mitigação de prompt injection |
| **RATE-01** | MÉDIO | Rate limiter em memória — reseta no restart, não funciona com múltiplos workers |
| **WS-01** | MÉDIO | WebSocket sem validação de JWT na conexão |

### 3.5 Conformidade LGPD/GDPR — Avaliação: **ALTO RISCO**

| Requisito LGPD | Artigo | Status |
|---|---|---|
| Base legal para processamento | Art. 7 | **AUSENTE** — sem coleta de consentimento |
| Inventário de dados | Art. 37 | **AUSENTE** |
| Aviso de privacidade | Art. 9 | **AUSENTE** |
| Direito à exclusão | Art. 18-VI | **PARCIAL** — sem cascade para backups/logs/cache |
| Minimização de dados | Art. 6-III | **FALHA** — armazena texto completo + mídia permanentemente |
| Transferência internacional | Art. 33 | **VIOLAÇÃO** — PII enviado a Anthropic (EUA) sem salvaguardas |
| Medidas de segurança | Art. 46 | **FALHA** — sem TLS, IDOR, serviços expostos |

### 3.6 Testes — Cobertura: **64% dos módulos**

| Área | Cobertura | Gap |
|---|---|---|
| Modelos e Schemas | 80% | Baixo |
| Routers | 70% | Médio |
| Auth | 75% | Médio |
| Logging/Redação | 90% | Baixo |
| **claude_service.py** (1012 linhas) | **~0%** | **CRÍTICO** |
| **conversation_processor.py** | **~0%** | **CRÍTICO** |
| **agent_orchestrator.py** | **~0%** | **CRÍTICO** |
| **whatsapp_parser.py** | **~0%** | **CRÍTICO** |
| Frontend (Jest/Playwright) | **0%** | **CRÍTICO** |

---

## 4. LISTA DE FUNCIONALIDADES PROPOSTAS

### Classificação por Valor e Urgência

As 30 funcionalidades propostas pelos 6 agentes especializados (Agents 7-12), consolidadas e deduplicadas em **25 features** únicas:

#### SEGURANÇA E COMPLIANCE (Urgência: IMEDIATA)

| # | Feature | Agente | Valor | Complexidade |
|---|---------|--------|-------|-------------|
| F01 | **Multi-Tenancy com RLS (PostgreSQL Row-Level Security)** | Agent 19 | Crítico | Alta |
| F02 | **TLS/HTTPS via Let's Encrypt + Nginx no Docker Compose** | Agent 16 | Crítico | Baixa |
| F03 | **Suite de Conformidade LGPD** (consentimento, retenção, exclusão, DPA) | Agent 18 | Crítico | Alta |
| F04 | **Rotação de Segredos + Remoção de Defaults Hardcoded** | Agent 6 | Crítico | Baixa |
| F05 | **Auditoria de Acesso (Audit Trail)** | Agent 10 | Alto | Média |

#### INFRAESTRUTURA E CONFIABILIDADE (Urgência: ALTA)

| # | Feature | Agente | Valor | Complexidade |
|---|---------|--------|-------|-------------|
| F06 | **Fila de Jobs Persistente (Redis Streams)** | Agent 13 | Alto | Média |
| F07 | **Deploy Zero-Downtime (Blue-Green)** | Agent 16 | Alto | Média |
| F08 | **Backup Automatizado (pg_dump + off-site)** | Agent 16 | Alto | Baixa |
| F09 | **Migrações de Banco com Alembic** | Agent 13 | Alto | Baixa |
| F10 | **Stack de Observabilidade (Prometheus + Grafana + Alertas)** | Agent 23 | Alto | Média |

#### OTIMIZAÇÃO DE CUSTOS (Urgência: ALTA)

| # | Feature | Agente | Valor | Complexidade |
|---|---------|--------|-------|-------------|
| F11 | **Model Fallback Inteligente (Sonnet/Haiku para operações não-críticas)** | Agent 14 | Muito Alto | Baixa |
| F12 | **Prompt Caching (Anthropic Beta)** | Agent 14 | Alto | Baixa |

#### AI E DADOS (Urgência: MÉDIA)

| # | Feature | Agente | Valor | Complexidade |
|---|---------|--------|-------|-------------|
| F13 | **Busca Semântica com pgvector** | Agent 21 | Muito Alto | Alta |
| F14 | **Segmentação Automática de Tópicos** | Agent 21 | Alto | Alta |
| F15 | **Análise Cross-Conversation** | Agent 21 | Alto | Muito Alta |
| F16 | **Detecção de Padrões Comportamentais** | Agent 11 | Alto | Alta |

#### EXPERIÊNCIA DO USUÁRIO (Urgência: MÉDIA)

| # | Feature | Agente | Valor | Complexidade |
|---|---------|--------|-------|-------------|
| F17 | **Colaboração Real-Time (Workspaces, Anotações, Comentários)** | Agent 20 | Alto | Muito Alta |
| F18 | **Onboarding Interativo (Tour Guiado)** | Agent 9 | Médio | Baixa |
| F19 | **Dashboard de Custos/Uso por Tenant** | Agent 7 | Alto | Média |
| F20 | **Sistema de Notificações (Push/Email)** | Agent 9 | Médio | Média |

#### INTEGRAÇÕES E PLATAFORMA (Urgência: BAIXA)

| # | Feature | Agente | Valor | Complexidade |
|---|---------|--------|-------|-------------|
| F21 | **Importação Telegram/Signal** | Agent 22 | Alto | Média |
| F22 | **API Pública com API Keys** | Agent 22 | Muito Alto | Média |
| F23 | **Sistema de Webhooks** | Agent 22 | Alto | Média |
| F24 | **Export para Notion/Obsidian** | Agent 22 | Médio | Baixa |
| F25 | **OAuth2/OIDC via Keycloak** | Agent 24 | Alto | Alta |

---

## 5. ANÁLISE DE VIABILIDADE TÉCNICA E ECONÔMICA

### 5.1 Viabilidade Técnica

#### Capacidade da Arquitetura Atual

| Dimensão | Capacidade Atual | Limitação | Solução |
|---|---|---|---|
| Usuários simultâneos | ~50 | Único worker uvicorn | Adicionar workers ou horizontal scaling |
| Conversas processadas/dia | ~100 | 20 agentes + semáforo de 10 | Fila persistente + model fallback |
| Tamanho máximo de upload | 500MB | RAM do container | Streaming upload |
| Conexões WebSocket | ~100 | Event loop do Python | Redis Pub/Sub para broadcast |
| Armazenamento | Ilimitado (VPS) | Disco do Hetzner VPS | CDN + storage externo |

#### Estimativa de Infraestrutura por Escala

| Usuários | VPS | Custo Infra/mês | Custo Claude API/mês | Total/mês |
|---|---|---|---|---|
| **100** | CX31 (8 vCPU, 16GB) | ~$17 | ~$150 | **~$170** |
| **1.000** | CX41 (16 vCPU, 32GB) + DB separado | ~$50 | ~$1.500 | **~$1.550** |
| **10.000** | 3x CX41 + managed DB + LB | ~$200 | ~$15.000 | **~$15.200** |

> **O custo da API Claude domina em escala.** A infraestrutura representa <2% do custo total com 10K usuários.

### 5.2 Análise CAPEX/OPEX — Top 15 Features

| # | Feature | Horas Dev | CAPEX ($75/h) | OPEX Mensal | Impacto API Claude | Payback |
|---|---------|-----------|--------------|-------------|-------------------|---------|
| F01 | Multi-Tenancy (RLS) | 80h | $6.000 | $0 | Nenhum | Imediato (habilita receita) |
| F02 | TLS/HTTPS | 8h | $600 | $0 | Nenhum | Imediato (compliance) |
| F03 | LGPD Compliance | 80h | $6.000 | $0 | Nenhum | Imediato (evita multas) |
| F04 | Rotação de Segredos | 8h | $600 | $0 | Nenhum | Imediato |
| F05 | Audit Trail | 24h | $1.800 | $0 | Nenhum | 1 mês |
| F06 | Fila Redis Streams | 24h | $1.800 | $0 | Nenhum | 2 meses |
| F07 | Deploy Zero-Downtime | 16h | $1.200 | $0 | Nenhum | 1 mês |
| F08 | Backup Automatizado | 12h | $900 | $5/mês | Nenhum | Imediato (DR) |
| F09 | Alembic Migrations | 12h | $900 | $0 | Nenhum | 1 mês |
| F10 | Observabilidade | 48h | $3.600 | $0 | Nenhum | 2 meses |
| F11 | Model Fallback | 12h | $900 | $0 | **-70% a -90%** | <1 mês |
| F12 | Prompt Caching | 16h | $1.200 | $0 | **-40% a -60%** | 1 mês |
| F13 | Busca Semântica | 80h | $6.000 | $10/mês | -20% (menos contexto) | 3 meses |
| F22 | API Pública | 40h | $3.000 | $0 | +20% (uso externo) | 3 meses |
| F17 | Colaboração Real-Time | 80h | $6.000 | $5/mês | +10% | 6 meses |

### 5.3 Estratégia de Otimização de Custos Claude API

| Estratégia | Economia | Esforço |
|---|---|---|
| Usar **Sonnet** para sentimento/keywords/formatação | 70-80% nessas operações | 12h |
| Usar **Haiku** para classificação simples | 90% em classificação | 8h |
| **Prompt caching** (Anthropic beta) | 40-60% em contexto repetido | 16h |
| **Cache Redis agressivo** (TTL 24h atual) | 30-50% em queries repetidas | 4h |
| Truncar contexto mais agressivamente | 20-30% | 4h |
| **Combinado** | **~75% redução total** | **~44h ($3.300)** |

**ROI do Model Fallback**: Investimento de $3.300, economia de $500-$3.000/mês em escala. Payback em 1-2 meses.

---

## 6. PRIORIZAÇÃO (MoSCoW + RICE)

### 6.1 Classificação MoSCoW

#### MUST HAVE (Obrigatório — Sem isso o sistema não pode operar em produção)

| # | Feature | Justificativa |
|---|---------|--------------|
| F01 | Multi-Tenancy (RLS) | IDOR é vulnerabilidade ativa — qualquer usuário vê dados de todos |
| F02 | TLS/HTTPS | Credenciais e PII trafegam em cleartext |
| F03 | LGPD Compliance (fase 1) | Risco de multa ANPD (até 2% da receita / R$50M) |
| F04 | Rotação de Segredos | Senhas admin/JWT previsíveis hardcoded |
| F08 | Backup Automatizado | Zero backup = perda total possível |
| F09 | Alembic Migrations | `create_all` impede evolução segura do schema |

#### SHOULD HAVE (Deveria ter — Alto valor, mas não bloqueia operação)

| # | Feature | Justificativa |
|---|---------|--------------|
| F06 | Fila Redis Streams | Elimina perda de jobs no restart |
| F07 | Deploy Zero-Downtime | 5-15 min downtime por deploy é inaceitável |
| F10 | Observabilidade | Sem métricas/alertas, problemas passam despercebidos |
| F11 | Model Fallback | Redução de 70-90% em custos de API |
| F12 | Prompt Caching | Redução adicional de 40-60% |
| F05 | Audit Trail | Requisito para compliance e investigação |

#### COULD HAVE (Poderia ter — Valor incremental significativo)

| # | Feature | Justificativa |
|---|---------|--------------|
| F13 | Busca Semântica (pgvector) | Diferenciação de produto, melhora RAG |
| F14 | Segmentação de Tópicos | Valor para usuários jurídicos/investigativos |
| F19 | Dashboard de Custos | Visibilidade financeira por tenant |
| F21 | Importação Telegram/Signal | Expansão de mercado |
| F22 | API Pública | Habilita ecossistema e receita via API |

#### WON'T HAVE (Não terá agora — Futuro, pós-estabilização)

| # | Feature | Justificativa |
|---|---------|--------------|
| F15 | Análise Cross-Conversation | Requer pgvector + multi-tenancy maduro |
| F16 | Detecção de Padrões Comportamentais | Complexidade alta, valor incremental |
| F17 | Colaboração Real-Time | Requer multi-tenancy + workspaces |
| F25 | OAuth2/Keycloak | JWT atual funciona; migrar depois |
| F20 | Sistema de Notificações | Nice-to-have após features core |
| F18 | Onboarding Interativo | Baixa prioridade técnica |

### 6.2 Score RICE (Reach × Impact × Confidence / Effort)

| # | Feature | Reach (1-10) | Impact (1-3) | Confidence (%) | Effort (sem) | **RICE Score** |
|---|---------|-------------|-------------|----------------|-------------|----------------|
| F02 | TLS/HTTPS | 10 | 3 | 100% | 0.2 | **150.0** |
| F04 | Rotação de Segredos | 10 | 3 | 100% | 0.2 | **150.0** |
| F11 | Model Fallback | 10 | 3 | 90% | 0.3 | **90.0** |
| F08 | Backup Automatizado | 10 | 3 | 95% | 0.3 | **95.0** |
| F01 | Multi-Tenancy (RLS) | 10 | 3 | 85% | 2.0 | **12.8** |
| F09 | Alembic Migrations | 8 | 2 | 95% | 0.3 | **50.7** |
| F12 | Prompt Caching | 10 | 2 | 80% | 0.4 | **40.0** |
| F06 | Fila Redis Streams | 8 | 2 | 90% | 0.6 | **24.0** |
| F07 | Deploy Zero-Downtime | 10 | 2 | 85% | 0.4 | **42.5** |
| F05 | Audit Trail | 6 | 2 | 90% | 0.6 | **18.0** |
| F10 | Observabilidade | 8 | 2 | 85% | 1.2 | **11.3** |
| F03 | LGPD Compliance | 10 | 3 | 75% | 2.0 | **11.3** |
| F13 | Busca Semântica | 7 | 3 | 70% | 2.5 | **5.9** |
| F22 | API Pública | 5 | 3 | 70% | 1.0 | **10.5** |
| F21 | Importação Telegram | 4 | 2 | 80% | 1.0 | **6.4** |
| F14 | Segmentação Tópicos | 5 | 2 | 60% | 1.5 | **4.0** |
| F19 | Dashboard Custos | 6 | 1 | 80% | 1.0 | **4.8** |
| F23 | Webhooks | 4 | 2 | 75% | 1.0 | **6.0** |
| F24 | Export Notion/Obsidian | 3 | 1 | 85% | 0.5 | **5.1** |
| F17 | Colaboração Real-Time | 5 | 3 | 50% | 3.0 | **2.5** |
| F16 | Padrões Comportamentais | 4 | 2 | 50% | 2.0 | **2.0** |
| F25 | OAuth2/Keycloak | 6 | 2 | 60% | 3.5 | **2.1** |
| F15 | Cross-Conversation | 3 | 2 | 50% | 3.0 | **1.0** |
| F20 | Notificações | 4 | 1 | 70% | 1.0 | **2.8** |
| F18 | Onboarding | 3 | 1 | 80% | 0.5 | **4.8** |

---

## 7. BACKLOG PRIORIZADO

### Sprint 0 — EMERGÊNCIA DE SEGURANÇA (Semana 1-2)

| Prioridade | Item | Esforço | Responsável |
|---|---|---|---|
| P0 | F02: Habilitar TLS/HTTPS (Nginx + Let's Encrypt no Docker Compose) | 8h | DevOps |
| P0 | F04: Remover segredos hardcoded, rotacionar credenciais | 8h | DevOps |
| P0 | F01.1: Adicionar `owner_id` ao modelo Conversation + filtrar queries | 36h | Backend |
| P0 | F08: Configurar backup automatizado (pg_dump + Hetzner Storage Box) | 12h | DevOps |
| P0 | Fechar portas expostas (ES:9200, Kibana:5601, FluentBit:24224) | 4h | DevOps |
| | **Total Sprint 0** | **68h** | |

### Sprint 1 — FUNDAÇÃO (Semana 3-4)

| Prioridade | Item | Esforço | Responsável |
|---|---|---|---|
| P1 | F09: Implementar Alembic Migrations | 12h | Backend |
| P1 | F11: Model Fallback (Sonnet/Haiku para operações não-críticas) | 12h | Backend/AI |
| P1 | F12: Prompt Caching (Anthropic beta) | 16h | Backend/AI |
| P1 | F07: Deploy Zero-Downtime (blue-green script) | 16h | DevOps |
| P1 | F06: Migrar fila de jobs para Redis Streams | 24h | Backend |
| | **Total Sprint 1** | **80h** | |

### Sprint 2 — COMPLIANCE (Semana 5-8)

| Prioridade | Item | Esforço | Responsável |
|---|---|---|---|
| P1 | F03.1: Coleta de consentimento no upload (checkbox + timestamp) | 12h | Full-stack |
| P1 | F03.2: Política de privacidade (página frontend) | 8h | Frontend |
| P1 | F03.3: Política de retenção de dados + auto-purge | 16h | Backend |
| P1 | F03.4: Redação de PII antes de envio à API Claude | 16h | Backend |
| P1 | F03.5: DPA com Anthropic (template legal) | 8h | Legal |
| P1 | F05: Implementar Audit Trail | 24h | Backend |
| P1 | F01.2: RBAC completo (admin/owner/member/viewer) | 16h | Backend |
| | **Total Sprint 2** | **100h** | |

### Sprint 3 — QUALIDADE (Semana 9-12)

| Prioridade | Item | Esforço | Responsável |
|---|---|---|---|
| P1 | Testes unitários: claude_service.py, whatsapp_parser.py | 32h | QA |
| P1 | Testes unitários: conversation_processor.py, agent_orchestrator.py | 32h | QA |
| P1 | Testes de integração (pipeline completo) | 20h | QA |
| P1 | F10: Stack de Observabilidade (Prometheus + Grafana) | 48h | DevOps |
| P2 | Testes E2E com Playwright (fluxos críticos) | 24h | QA |
| | **Total Sprint 3** | **156h** | |

### Sprint 4 — AI AVANÇADA (Semana 13-18)

| Prioridade | Item | Esforço | Responsável |
|---|---|---|---|
| P2 | F13: Busca Semântica com pgvector | 80h | Backend/AI |
| P2 | F14: Segmentação Automática de Tópicos | 40h | AI |
| P2 | F19: Dashboard de Custos/Uso | 40h | Full-stack |
| | **Total Sprint 4** | **160h** | |

### Sprint 5 — PLATAFORMA (Semana 19-24)

| Prioridade | Item | Esforço | Responsável |
|---|---|---|---|
| P2 | F22: API Pública com API Keys | 40h | Backend |
| P2 | F21: Importação Telegram/Signal | 40h | Backend |
| P2 | F23: Sistema de Webhooks | 40h | Backend |
| P3 | F24: Export Notion/Obsidian | 20h | Backend |
| | **Total Sprint 5** | **140h** | |

### Sprint 6+ — COLABORAÇÃO (Semana 25+)

| Prioridade | Item | Esforço | Responsável |
|---|---|---|---|
| P3 | F17: Colaboração Real-Time (Workspaces + Anotações) | 80h | Full-stack |
| P3 | F15: Análise Cross-Conversation | 60h | AI |
| P3 | F16: Detecção de Padrões Comportamentais | 40h | AI |
| P3 | F25: OAuth2/OIDC (Keycloak) | 80h | Backend |
| P3 | F18: Onboarding Interativo | 20h | Frontend |
| P3 | F20: Sistema de Notificações | 40h | Full-stack |
| | **Total Sprint 6+** | **320h** | |

### Resumo do Backlog

| Sprint | Período | Horas | Custo ($75/h) | Foco |
|---|---|---|---|---|
| Sprint 0 | Sem 1-2 | 68h | $5.100 | Segurança crítica |
| Sprint 1 | Sem 3-4 | 80h | $6.000 | Fundação técnica |
| Sprint 2 | Sem 5-8 | 100h | $7.500 | LGPD Compliance |
| Sprint 3 | Sem 9-12 | 156h | $11.700 | Qualidade e observabilidade |
| Sprint 4 | Sem 13-18 | 160h | $12.000 | AI avançada |
| Sprint 5 | Sem 19-24 | 140h | $10.500 | Plataforma e integrações |
| Sprint 6+ | Sem 25+ | 320h | $24.000 | Colaboração e expansão |
| **TOTAL** | **~30 semanas** | **~1.024h** | **~$76.800** | |

---

## 8. ESPECIFICAÇÕES DE REQUISITOS E CRITÉRIOS DE ACEITAÇÃO

### F01 — Multi-Tenancy com RLS

**Descrição:** Implementar isolamento de dados por tenant usando PostgreSQL Row-Level Security, garantindo que cada usuário veja apenas suas próprias conversas.

**Requisitos Funcionais:**
- RF01.1: Adicionar campo `owner_id` (FK para users) na tabela `conversations`
- RF01.2: Adicionar campo `tenant_id` (FK para tenants) em todas as tabelas com dados de negócio
- RF01.3: Criar modelo `Tenant` com campos: id, name, slug, plan_id, is_active, settings
- RF01.4: Criar modelo `Plan` com quotas: max_conversations, max_storage_mb, max_ai_calls_per_day
- RF01.5: Habilitar RLS no PostgreSQL com policies por `tenant_id`
- RF01.6: Middleware de tenant que injeta `SET LOCAL app.tenant_id` a cada request

**Critérios de Aceitação:**
- [ ] Usuário A não consegue acessar conversas do Usuário B via API (GET, DELETE, EXPORT)
- [ ] Admin vê apenas dados do seu tenant (exceto superadmin)
- [ ] RLS policies ativas nas tabelas: conversations, messages, chat_messages, agent_jobs
- [ ] Teste de integração cobrindo IDOR em todos os endpoints
- [ ] Migração Alembic reversível criada
- [ ] Performance: overhead de RLS < 5ms por query

**Dependências:** F09 (Alembic)
**Riscos:** Migração de dados existentes (backfill de tenant_id); performance do RLS
**Estimativa:** 80h (2 semanas, 1 dev)

---

### F02 — TLS/HTTPS

**Descrição:** Habilitar comunicação criptografada adicionando Nginx como reverse proxy com certificados Let's Encrypt.

**Requisitos Funcionais:**
- RF02.1: Adicionar serviço `nginx` ao docker-compose.yml
- RF02.2: Configurar certbot para auto-renovação
- RF02.3: Redirecionar HTTP (80) para HTTPS (443)
- RF02.4: Aplicar headers de segurança da configuração nginx existente
- RF02.5: Habilitar HSTS com max-age=31536000

**Critérios de Aceitação:**
- [ ] Todas as requisições HTTP redirecionam para HTTPS
- [ ] Certificado SSL válido (verificável via `curl -v`)
- [ ] Headers de segurança presentes: X-Frame-Options, X-Content-Type-Options, CSP, HSTS
- [ ] WebSocket funciona via WSS
- [ ] SSL Labs score >= A
- [ ] Renovação automática do certificado configurada

**Dependências:** Nenhuma
**Riscos:** Configuração DNS do domínio
**Estimativa:** 8h

---

### F03 — Suite de Conformidade LGPD

**Descrição:** Implementar os controles mínimos exigidos pela LGPD para processamento de dados pessoais de conversas WhatsApp.

**Requisitos Funcionais:**
- RF03.1: Checkbox de consentimento obrigatório no upload com timestamp
- RF03.2: Página de política de privacidade acessível sem autenticação
- RF03.3: API de exclusão com cascade completo (DB + arquivos + cache + logs)
- RF03.4: Política de retenção configurável com auto-purge (default: 90 dias)
- RF03.5: Redação de PII (nomes, telefones) antes de envio à API Claude
- RF03.6: Registro de operações de processamento (ROPA)
- RF03.7: Endpoint de portabilidade (export JSON padronizado)

**Critérios de Aceitação:**
- [ ] Upload falha sem checkbox de consentimento marcado
- [ ] Timestamp de consentimento armazenado no DB
- [ ] DELETE em conversa remove: registros DB, arquivos de mídia, cache Redis, embeddings
- [ ] Conversas expiradas são removidas automaticamente pelo scheduler
- [ ] PII redacted nos payloads enviados à API Claude (verificável via logs)
- [ ] Página de privacidade acessível em `/privacidade`
- [ ] Export de dados pessoais gera JSON com todos os dados do usuário

**Dependências:** F01 (Multi-Tenancy), F09 (Alembic)
**Riscos:** Complexidade de cascade delete; impacto na qualidade de análise AI com PII redacted
**Estimativa:** 100h (fase completa)

---

### F11 — Model Fallback Inteligente

**Descrição:** Usar modelos Claude mais baratos (Sonnet/Haiku) para operações que não requerem Opus, reduzindo custos de API em 70-90%.

**Requisitos Funcionais:**
- RF11.1: Configuração de modelo por tipo de operação (sentimento, keywords, classificação, chat)
- RF11.2: Haiku para: classificação de tipo de mídia, detecção de idioma, formatação
- RF11.3: Sonnet para: sentimento, keywords, formatação de transcrição
- RF11.4: Opus apenas para: RAG chat, detecção de contradições, análise jurídica
- RF11.5: Fallback automático para modelo inferior em caso de rate limit

**Critérios de Aceitação:**
- [ ] Cada operação em `claude_service.py` usa o modelo configurado
- [ ] Configuração via env vars: `CLAUDE_MODEL_CHAT`, `CLAUDE_MODEL_ANALYSIS`, `CLAUDE_MODEL_SIMPLE`
- [ ] Rate limit no Opus faz fallback para Sonnet automaticamente
- [ ] Dashboard mostra custo por modelo e por operação
- [ ] Qualidade da análise verificada via testes comparativos (>90% de concordância com Opus)
- [ ] Redução verificável de >60% no custo total de API

**Dependências:** Nenhuma
**Riscos:** Degradação de qualidade em operações downgraded
**Estimativa:** 12h

---

### F13 — Busca Semântica com pgvector

**Descrição:** Substituir a busca full-text atual por busca semântica usando embeddings vetoriais armazenados no PostgreSQL via extensão pgvector.

**Requisitos Funcionais:**
- RF13.1: Instalar extensão pgvector no PostgreSQL
- RF13.2: Criar tabela `message_embeddings` com campo vector(1536)
- RF13.3: Pipeline de embedding: chunking (512 tokens, 50 overlap) → embedding API → pgvector
- RF13.4: Index HNSW para busca por similaridade coseno
- RF13.5: API de busca semântica: `/api/search/semantic?q=...`
- RF13.6: Integrar no RAG chat como fonte de contexto (substituir full-text truncado)
- RF13.7: Backfill de embeddings para conversas existentes

**Critérios de Aceitação:**
- [ ] Busca semântica retorna resultados relevantes para queries em linguagem natural
- [ ] Tempo de busca < 200ms para até 100K embeddings
- [ ] RAG chat usa contexto vetorial ao invés de full-text truncado
- [ ] Embeddings gerados automaticamente após processamento de conversa
- [ ] RLS aplicado na tabela de embeddings
- [ ] Comando de backfill para conversas existentes

**Dependências:** F01 (Multi-Tenancy/RLS), F09 (Alembic)
**Riscos:** Custo de embedding API; consumo de memória do índice HNSW
**Estimativa:** 80h

---

## 9. ARQUITETURA DE ALTO NÍVEL

### 9.1 Arquitetura Atual

```
                        ┌─────────────────┐
                        │    Internet      │
                        └────────┬────────┘
                                 │ HTTP (sem TLS!)
                    ┌────────────▼────────────┐
                    │   Hetzner VPS (único)    │
                    │                          │
                    │  ┌──────┐  ┌──────────┐  │
                    │  │Next.js│  │ FastAPI   │  │
                    │  │:3020  │  │ :8020     │  │
                    │  └──────┘  │ 20 agents │  │
                    │            │ Whisper   │  │
                    │            └─────┬─────┘  │
                    │                  │        │
                    │  ┌─────┐  ┌──────▼─────┐  │
                    │  │Redis│  │ PostgreSQL │  │
                    │  │:6379│  │ :5432      │  │
                    │  └─────┘  └────────────┘  │
                    │                           │
                    │  ┌────────────────────┐   │
                    │  │ FluentBit → ES → KB│   │
                    │  └────────────────────┘   │
                    └──────────────────────────┘
                                 │
                    ┌────────────▼────────────┐
                    │  api.gameron.me (proxy)  │
                    │  → Anthropic Claude API  │
                    └─────────────────────────┘
```

### 9.2 Arquitetura Proposta (Pós Sprint 0-3)

```
                        ┌─────────────────┐
                        │    Internet      │
                        └────────┬────────┘
                                 │ HTTPS (TLS 1.3)
                    ┌────────────▼────────────────────────────┐
                    │   Nginx (Reverse Proxy + WAF)            │
                    │   - Rate limiting (3 zonas)              │
                    │   - Security headers                     │
                    │   - Let's Encrypt auto-renew             │
                    │   - Gzip compression                     │
                    └────────────┬────────────────────────────┘
                                 │
                    ┌────────────▼────────────────────────────┐
                    │   Hetzner VPS                            │
                    │                                          │
                    │  ┌──────────┐  ┌───────────────────┐    │
                    │  │ Next.js  │  │ FastAPI            │    │
                    │  │ Frontend │  │ Backend            │    │
                    │  │ :3000    │  │ :8000              │    │
                    │  └──────────┘  │                    │    │
                    │                │ ┌────────────────┐ │    │
                    │                │ │ Agent Workers  │ │    │
                    │                │ │ (Redis Streams)│ │    │
                    │                │ └────────────────┘ │    │
                    │                │ ┌────────────────┐ │    │
                    │                │ │ Tenant Context │ │    │
                    │                │ │ (RLS enforced) │ │    │
                    │                │ └────────────────┘ │    │
                    │                └────────┬──────────┘    │
                    │                         │               │
                    │  ┌──────────┐  ┌────────▼──────────┐   │
                    │  │ Redis 7  │  │ PostgreSQL 16     │   │
                    │  │ - Cache  │  │ - RLS policies    │   │
                    │  │ - Queue  │  │ - pgvector        │   │
                    │  │ - PubSub │  │ - Audit logs      │   │
                    │  └──────────┘  └───────────────────┘   │
                    │                                         │
                    │  ┌─────────────────────────────────┐   │
                    │  │ Observability (rede interna)     │   │
                    │  │ Prometheus + Grafana + Tempo     │   │
                    │  │ FluentBit → ES → Kibana          │   │
                    │  │ Alertmanager → Telegram/Email    │   │
                    │  └─────────────────────────────────┘   │
                    │                                         │
                    │  ┌─────────────────────────────────┐   │
                    │  │ Backup (cron)                    │   │
                    │  │ pg_dump → Hetzner Storage Box    │   │
                    │  │ uploads rsync → off-site         │   │
                    │  └─────────────────────────────────┘   │
                    └────────────────────────────────────────┘
                                 │
                    ┌────────────▼──────────────────┐
                    │  Anthropic API (direto)        │
                    │  - Opus: RAG chat, contradições│
                    │  - Sonnet: sentimento, resumo  │
                    │  - Haiku: classificação        │
                    │  + Fallback: api.gameron.me     │
                    └───────────────────────────────┘
```

### 9.3 Diferenças Chave

| Aspecto | Atual | Proposto |
|---|---|---|
| TLS | Ausente | Nginx + Let's Encrypt |
| Isolamento de dados | Nenhum (IDOR) | RLS + tenant_id |
| Fila de jobs | In-memory (perde no restart) | Redis Streams (persistente) |
| Modelos AI | Apenas Opus ($$$) | Opus/Sonnet/Haiku por operação |
| Busca | Full-text ILIKE | Semântica (pgvector) |
| Observabilidade | Logs apenas | Metrics + Traces + Alerts |
| Backup | Nenhum | Automatizado + off-site |
| Deploy | 5-15min downtime | Blue-green zero-downtime |
| Portas expostas | ES, Kibana, FluentBit | Apenas 80/443 via Nginx |

---

## 10. PLANO DE IMPLEMENTAÇÃO

### 10.1 Timeline com Marcos

```
Sem 1-2:  ████████ Sprint 0 — Segurança Crítica
          Marco: TLS ativo, IDOR corrigido, backups funcionando

Sem 3-4:  ████████ Sprint 1 — Fundação Técnica
          Marco: Alembic, model fallback ativo, deploy zero-downtime

Sem 5-8:  ████████████████ Sprint 2 — Compliance LGPD
          Marco: Consentimento, retenção, audit trail, RBAC

Sem 9-12: ████████████████ Sprint 3 — Qualidade
          Marco: 90% cobertura testes, observabilidade completa

Sem 13-18:████████████████████████ Sprint 4 — AI Avançada
          Marco: Busca semântica, segmentação de tópicos

Sem 19-24:████████████████████████ Sprint 5 — Plataforma
          Marco: API pública, Telegram import, webhooks

Sem 25+:  ████████████████████████████████ Sprint 6+ — Expansão
          Marco: Colaboração real-time, cross-analysis
```

### 10.2 Recursos Necessários

| Papel | Sprint 0-3 | Sprint 4-5 | Sprint 6+ |
|---|---|---|---|
| Backend Engineer (Python/FastAPI) | 1 FTE | 1 FTE | 1 FTE |
| DevOps Engineer | 0.5 FTE | 0.25 FTE | 0.1 FTE |
| Frontend Engineer (React/Next.js) | 0.25 FTE | 0.5 FTE | 1 FTE |
| QA Engineer | 0.5 FTE | 0.25 FTE | 0.25 FTE |
| AI/ML Engineer | 0 | 0.5 FTE | 0.5 FTE |
| **Total** | **2.25 FTE** | **2.5 FTE** | **2.85 FTE** |

### 10.3 Marcos de Decisão (Gates)

| Gate | Semana | Critério de Passagem |
|---|---|---|
| G0: Segurança | Sem 2 | TLS ativo, IDOR corrigido, backups, zero segredos hardcoded |
| G1: Fundação | Sem 4 | Alembic funcional, model fallback com >60% economia, zero-downtime deploy |
| G2: Compliance | Sem 8 | LGPD: consentimento, retenção, PII redaction, audit trail |
| G3: Qualidade | Sem 12 | >85% cobertura testes, SLOs definidos, alertas configurados |
| G4: AI | Sem 18 | Busca semântica com <200ms latência, segmentação de tópicos funcional |
| G5: Plataforma | Sem 24 | API pública documentada, 2+ importers, webhooks funcionais |

---

## 11. MAPA DE RISCOS

### 11.1 Matriz de Riscos (Top 20)

| # | Risco | Categoria | Probabilidade | Impacto | Severidade | Mitigação |
|---|---|---|---|---|---|---|
| R01 | IDOR: qualquer usuário vê todas as conversas | Segurança | **100%** | Crítico | **P0** | F01: Multi-tenancy + RLS |
| R02 | Sem TLS: credenciais/PII em cleartext | Segurança | **100%** | Crítico | **P0** | F02: Nginx + Let's Encrypt |
| R03 | Segredos hardcoded previsíveis | Segurança | **100%** | Alto | **P0** | F04: Rotação + remoção defaults |
| R04 | Non-compliance LGPD (sem consentimento) | Compliance | 80% | Crítico | **P0** | F03: Suite LGPD |
| R05 | Single VPS: falha total em crash de hardware | Operacional | 15%/ano | Crítico | **P1** | F08: Backups + DR plan |
| R06 | Dependência proxy terceiro (api.gameron.me) | Vendor | 40% | Alto | **P1** | Fallback direto para Anthropic |
| R07 | Sem backup de banco de dados | Operacional | 30%/ano | Crítico | **P1** | F08: pg_dump automatizado |
| R08 | Perda de estado in-memory no redeploy | Técnico | **100%** | Médio | **P2** | F06: Redis Streams |
| R09 | Custo descontrolado de API Claude | Financeiro | 50% | Alto | **P2** | F11: Model fallback + budget caps |
| R10 | Sem Alembic: mudança de schema pode perder dados | Técnico | **100%** | Médio | **P2** | F09: Alembic migrations |
| R11 | ES/Kibana expostos publicamente | Segurança | 60% | Médio | **P2** | Remover port mapping |
| R12 | Whisper model consome RAM excessiva | Técnico | 60% | Médio | **P2** | Usar API externa ou worker separado |
| R13 | Prompt injection via chat (10K chars) | Segurança | 30% | Alto | **P2** | Sanitização + max tokens por usuário |
| R14 | DB pool exaurido (pool_size=10, overflow=20) | Performance | 40% | Médio | **P3** | Monitorar conexões; PgBouncer |
| R15 | Competidores com alternativas mais baratas | Mercado | 50% | Médio | **P3** | Diferenciar em vertical jurídica |
| R16 | Bus factor = 1 (único desenvolvedor) | Operacional | 70% | Alto | **P3** | Documentação; code reviews |
| R17 | Docker socket no FluentBit (escape risk) | Segurança | 10% | Crítico | **P3** | Usar socket proxy |
| R18 | Sem validação de mídia além de ZIP | Segurança | 30% | Médio | **P3** | MIME validation; ClamAV |
| R19 | Transferência internacional sem DPA | Compliance | 100% | Alto | **P1** | DPA com Anthropic |
| R20 | Sem auditoria (quem acessou quais dados) | Compliance | 100% | Médio | **P2** | F05: Audit Trail |

### 11.2 Heat Map

```
IMPACTO →   Baixo      Médio       Alto        Crítico
PROB ↓
Alta      |          | R08,R10,R20| R03,R09    | R01,R02,R04,R19
Média     |          | R11,R12    | R06,R07,R16| R05
Baixa     |          | R14,R18    | R13,R15    | R17
Rara      |          |            |            |
```

---

## 12. PLANO DE TESTES

### 12.1 Estratégia de Testes

| Tipo | Alvo | Cobertura Atual | Meta | Esforço |
|---|---|---|---|---|
| **Unitários (Backend)** | Serviços, modelos, routers | 64% módulos | 90% linhas | 92h |
| **Integração** | Pipeline upload→process→complete | 0% | 100% fluxos críticos | 40h |
| **E2E (Playwright)** | Fluxos completos do usuário | 0% | 6 cenários críticos | 40h |
| **Carga (Locust/k6)** | Concorrência e performance | 0% | Baseline definido | 16h |
| **Segurança (OWASP)** | Top 10 OWASP | 0% | Todas as categorias | 24h |
| **Total** | | | | **212h** |

### 12.2 Testes Prioritários por Módulo (P0)

| Módulo | Linhas | Criticidade | Testes Necessários |
|---|---|---|---|
| `whatsapp_parser.py` | ~400 | CRÍTICA | Formatos Android/iOS/Web, multi-idioma, edge cases |
| `claude_service.py` | ~1012 | CRÍTICA | Mock Anthropic client, retry, timeout, rate limit |
| `conversation_processor.py` | ~500 | CRÍTICA | Pipeline completo com mocks, transições de status |
| `agent_orchestrator.py` | ~350 | CRÍTICA | Concorrência, falha de agentes, retry, timeout |

### 12.3 Cenários E2E (Playwright)

| # | Cenário | Prioridade |
|---|---------|-----------|
| 1 | Login → Upload ZIP → Aguardar processamento → Visualizar resultados | P0 |
| 2 | Chat com conversa processada → Verificar streaming | P0 |
| 3 | Export em todos os formatos | P1 |
| 4 | Busca em conversas | P1 |
| 5 | Template analysis flow | P2 |
| 6 | Admin: criar/desativar usuário | P2 |

### 12.4 Testes de Segurança (OWASP Top 10)

| OWASP | Status Atual | Teste |
|---|---|---|
| A01: Broken Access Control | **VULNERÁVEL** (IDOR) | Testes automatizados de boundary auth |
| A02: Cryptographic Failures | Sem TLS | Verificação de TLS após deploy |
| A03: Injection | Mitigado (SQLAlchemy ORM) | Verificar todas as queries raw |
| A04: Insecure Design | Rate limiter em memória | Teste de eficácia do rate limiting |
| A05: Security Misconfiguration | Portas expostas | Port scan automatizado |
| A06: Vulnerable Components | Não verificado | `pip audit` + `npm audit` no CI |
| A07: Auth Failures | JWT sólido | Testes de brute force |
| A08: Data Integrity | Sem CSP ativo | Verificação de headers |
| A09: Logging Failures | Boa redação PII | Verificar que PII não vaza em logs |
| A10: SSRF | Path handling em exports | Testes de path traversal |

---

## 13. MÉTRICAS DE SUCESSO

### 13.1 KPIs Técnicos

| Métrica | Baseline Atual | Meta Sprint 3 | Meta Sprint 6 |
|---|---|---|---|
| Cobertura de testes (linhas) | ~30% | 85% | 90% |
| Cobertura de módulos | 64% | 95% | 100% |
| MTTR (tempo de recuperação) | Desconhecido | < 30 min | < 15 min |
| Uptime (disponibilidade) | Desconhecido | 99.5% | 99.9% |
| Deploy downtime | 5-15 min | 0 | 0 |
| Latência API p99 (excl. AI) | Desconhecido | < 2s | < 1s |
| Latência busca semântica | N/A | < 500ms | < 200ms |

### 13.2 KPIs de Segurança

| Métrica | Baseline | Meta |
|---|---|---|
| Vulnerabilidades CRÍTICAS abertas | 3 | 0 |
| Vulnerabilidades ALTAS abertas | 5 | 0 |
| SSL Labs Score | N/A (sem TLS) | A+ |
| OWASP compliance | ~50% | 100% |
| Tempo de detecção de incidente | Desconhecido | < 5 min |

### 13.3 KPIs de Negócio

| Métrica | Baseline | Meta Sprint 6 |
|---|---|---|
| Custo por conversa processada | ~$0.50-2.00 (Opus) | < $0.20 (model fallback) |
| Redução de custo API | 0% | 75% |
| Tenants ativos | 1 (compartilhado) | Multi-tenant isolado |
| Formatos de importação | 1 (WhatsApp) | 3 (+ Telegram, Signal) |
| LGPD compliance score | ~20% | 90% |

### 13.4 KPIs de Qualidade

| Métrica | Baseline | Meta |
|---|---|---|
| Bugs em produção/mês | Desconhecido | < 2 (P3+) |
| Qualidade análise AI (concordância Opus vs Sonnet) | N/A | > 90% |
| Testes E2E passando | 0 | 6 cenários P0 |
| Cache hit rate | Desconhecido | > 60% |

---

## 14. LIMITAÇÕES E CONSIDERAÇÕES

### 14.1 Limitações da Análise

- **Acesso ao ambiente**: Análise baseada exclusivamente no código-fonte; sem acesso ao ambiente de produção em execução
- **Dados de uso**: Sem telemetria de uso real (número de usuários, volume de conversas, padrões de acesso)
- **Validação de negócio**: As funcionalidades propostas não foram validadas com usuários finais reais
- **Estimativas de esforço**: Baseadas em complexidade de código e padrões de mercado; podem variar conforme experiência da equipe
- **Custos de API**: Estimativas baseadas em preços públicos da Anthropic; custos reais dependem do volume e modelo de precificação do proxy Gameron

### 14.2 Considerações de Privacidade

- **Dados sensíveis**: Conversas WhatsApp contêm PII (nomes, telefones, conteúdo pessoal, mídia)
- **Dados biométricos**: Gravações de áudio e imagens de pessoas podem ser considerados dados biométricos (LGPD Art. 5, XI)
- **Transferência internacional**: PII é enviado à Anthropic (EUA) sem DPA — violação LGPD Art. 33
- **Retenção indefinida**: Sem política de retenção — dados persistem indefinidamente
- **Recomendação**: Priorizar F03 (LGPD Compliance) como pré-requisito para operação comercial

### 14.3 Considerações de Ambiente

- **Single VPS**: Toda a infraestrutura em um único servidor Hetzner — ponto único de falha
- **Sem redundância**: Sem replicação de banco, sem failover, sem DR automatizado
- **Recursos limitados**: ~2-2.4GB RAM estimados para 7 containers — pouco espaço para adições (Prometheus, Grafana, etc.)

### 14.4 Reprodutibilidade

Este relatório foi gerado por análise direta do código-fonte e pode ser reproduzido:
1. Clonando o repositório na mesma versão (commit `48501f0`)
2. Executando os mesmos agentes de análise sobre o código
3. Aplicando os mesmos frameworks de priorização (MoSCoW + RICE)

---

## 15. QUESTIONAMENTOS CLARIFICADORES

As seguintes questões, se respondidas, permitiriam refinar as recomendações:

### Negócio
1. **Modelo de monetização**: O WIT será SaaS (multi-tenant com planos) ou on-premise (licenciado)? Isso impacta prioridade de F01/F19
2. **Público-alvo primário**: Qual vertical é prioritária (jurídica, RH, comercial)? Impacta templates e features específicas
3. **Volume esperado**: Quantos usuários e conversas/mês são esperados nos próximos 6-12 meses?

### Técnico
4. **Proxy Gameron**: Qual é a relação com api.gameron.me? É um serviço próprio ou terceiro? Existe DPA?
5. **Whisper local vs API**: O modelo Whisper local é mandatório ou pode ser substituído por OpenAI Whisper API?
6. **Orçamento de infraestrutura**: Qual é o budget mensal disponível para infraestrutura e API?

### Compliance
7. **Jurisdição**: O sistema processa dados de residentes brasileiros? Confirmar aplicabilidade da LGPD
8. **Setor regulado**: Algum cliente opera em setor regulado (saúde, financeiro)? Pode exigir compliance adicional
9. **DPO**: Há um Data Protection Officer designado ou disponível?

### Prioridades
10. **Urgência vs completude**: Preferência por entregar incrementalmente (MVP → iterate) ou completar cada feature antes de avançar?

---

## APÊNDICE A — AGENTES UTILIZADOS

| Agent | Role | Entregas |
|---|---|---|
| 1 | Arquiteto Backend | Estrutura completa, endpoints, modelos, padrões, dependências |
| 2 | Arquiteto Frontend | Componentes, estado, API client, design system |
| 3 | Engenheiro DevOps | Containers, CI/CD, Nginx, logging, deploy |
| 4 | Analista de Documentação | Contexto de negócio, features, issues, gaps |
| 5 | Analista QA | Cobertura de testes, gaps, recomendações |
| 6 | Especialista Segurança | 30+ vulnerabilidades, roadmap de remediação |
| 7 | Analista de Negócios | 5 features de valor de negócio |
| 8 | Engenheiro de Dados | 5 features de pipeline de dados |
| 9 | Designer UX | 5 features de experiência do usuário |
| 10 | Especialista Compliance | 5 features de conformidade legal |
| 11 | Engenheiro AI/ML | 5 features de AI avançada |
| 12 | Product Manager | 5 features de crescimento de plataforma |
| 13 | Arquiteto de Viabilidade | Análise de bottlenecks, custos por escala |
| 14 | Analista Econômico | CAPEX/OPEX das top 15 features, ROI |
| 15 | Analista de Riscos | Top 20 riscos com probabilidade e impacto |
| 16 | Engenheiro DevOps (design) | Zero-downtime, backup, DR, monitoring |
| 17 | Líder QA (estratégia) | Plano completo de testes, estimativa para 90% |
| 18 | DPO | Gap analysis LGPD/GDPR, roadmap de compliance |
| 19 | Arquiteto Multi-Tenancy | Design RLS, migrações, modelos, policies |
| 20 | Arquiteto Colaboração | WebSocket rooms, anotações, comentários |
| 21 | Arquiteto AI Pipeline | pgvector, embeddings, RAG, clustering |
| 22 | Arquiteto Integrações | Importers, API pública, webhooks, OAuth |
| 23 | Arquiteto Observabilidade | Prometheus, Grafana, Tempo, alertas, SLOs |
| 24 | Arquiteto Segurança | Keycloak, RBAC, encryption, WAF, SOC 2 |

---

## APÊNDICE B — GLOSSÁRIO

| Termo | Definição |
|---|---|
| **IDOR** | Insecure Direct Object Reference — acesso não autorizado a recursos por referência direta |
| **RLS** | Row-Level Security — política de PostgreSQL que filtra linhas por contexto |
| **LGPD** | Lei Geral de Proteção de Dados (Lei 13.709/2018) |
| **DPA** | Data Processing Agreement — acordo de processamento de dados |
| **RAG** | Retrieval-Augmented Generation — geração com recuperação de contexto |
| **pgvector** | Extensão PostgreSQL para armazenamento e busca de vetores |
| **HNSW** | Hierarchical Navigable Small World — algoritmo de indexação vetorial |
| **MoSCoW** | Must/Should/Could/Won't — método de priorização |
| **RICE** | Reach × Impact × Confidence / Effort — scoring de priorização |
| **SLO/SLI** | Service Level Objective / Indicator — metas de disponibilidade |
| **MTTR** | Mean Time To Recovery — tempo médio de recuperação |
| **CAPEX** | Capital Expenditure — investimento inicial |
| **OPEX** | Operational Expenditure — custo operacional recorrente |
| **FTE** | Full-Time Equivalent — equivalente a tempo integral |
| **DR** | Disaster Recovery — recuperação de desastres |

---

*Relatório gerado por análise multi-agente cooperativa com 24 agentes especializados.*
*Baseado no commit `48501f0` do repositório WhatsApp Insight Transcriber.*
*Data: 2026-04-03 | Versão: 1.0*
