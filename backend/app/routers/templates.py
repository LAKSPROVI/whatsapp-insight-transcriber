"""
API Endpoints — Templates de Análise pré-configurados.

Permite listar, consultar detalhes e executar templates de análise pré-configurados
(jurídico, comercial, RH, etc.) sobre conversas transcritas usando IA.
"""
import logging
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.models import Conversation, Message, ProcessingStatus
from app.schemas import (
    TemplateResponse,
    TemplateListResponse,
    TemplateAnalysisRequest,
    TemplateAnalysisResponse,
)
from app.auth import get_current_user, UserInfo
from app.auth import apply_owner_filter, ensure_owner_access
from app.services.analysis_templates import get_all_templates, get_template, get_template_prompts
from app.dependencies import get_claude_service
from app.exceptions import ValidationError, ProcessingError

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/templates", tags=["templates"])


@router.get("", response_model=TemplateListResponse)
async def list_templates(
    current_user: UserInfo = Depends(get_current_user),
):
    """
    Lista todos os templates de análise disponíveis.

    Retorna a lista completa de templates pré-configurados para análise de conversas.
    Cada template contém um conjunto de prompts especializados para diferentes
    tipos de análise (jurídico, comercial, RH, etc.).

    **Headers necessários:**
    ```
    Authorization: Bearer <token>
    ```

    **Exemplo de response (200):**
    ```json
    {
        "templates": [
            {
                "id": "juridico",
                "name": "Análise Jurídica",
                "description": "Análise de evidências, cronologia e aspectos legais",
                "prompts": {
                    "summary": "Faça um resumo jurídico...",
                    "entities": "Identifique todas as partes...",
                    "timeline": "Monte uma cronologia..."
                }
            },
            {
                "id": "comercial",
                "name": "Análise Comercial",
                "description": "Análise de negociações e acordos comerciais",
                "prompts": {
                    "summary": "Resuma a negociação...",
                    "recommendations": "Sugira próximos passos..."
                }
            }
        ]
    }
    ```

    **Erros possíveis:**
    - **401 Unauthorized**: Token ausente ou inválido.
    """
    logger.info("Listando templates", extra={"user": current_user.username})
    templates = get_all_templates()
    return TemplateListResponse(
        templates=[TemplateResponse(**t) for t in templates]
    )


@router.get("/{template_id}", response_model=TemplateResponse)
async def get_template_detail(
    template_id: str,
    current_user: UserInfo = Depends(get_current_user),
):
    """
    Retorna detalhes de um template de análise específico.

    Inclui o nome, descrição e todos os prompts disponíveis no template.

    **Headers necessários:**
    ```
    Authorization: Bearer <token>
    ```

    **Exemplo de response (200):**
    ```json
    {
        "id": "juridico",
        "name": "Análise Jurídica",
        "description": "Análise de evidências, cronologia e aspectos legais",
        "prompts": {
            "summary": "Faça um resumo jurídico da conversa...",
            "entities": "Identifique todas as partes envolvidas...",
            "timeline": "Monte uma cronologia dos eventos...",
            "contradictions": "Identifique contradições..."
        }
    }
    ```

    **Erros possíveis:**
    - **404 Not Found**: Template não encontrado.
    - **401 Unauthorized**: Token ausente ou inválido.
    """
    logger.info(
        "Detalhe do template",
        extra={"template_id": template_id, "user": current_user.username},
    )
    template = get_template(template_id)
    if not template:
        raise HTTPException(404, f"Template '{template_id}' não encontrado")
    return TemplateResponse(**template)


@router.post("/{template_id}/analyze/{conversation_id}", response_model=TemplateAnalysisResponse)
async def analyze_with_template(
    template_id: str,
    conversation_id: str,
    request: Optional[TemplateAnalysisRequest] = None,
    db: AsyncSession = Depends(get_db),
    current_user: UserInfo = Depends(get_current_user),
):
    """
    Executa análise de uma conversa usando um template pré-configurado.

    Envia os prompts do template selecionado para a IA Claude, junto com o
    contexto completo da conversa. Pode executar todos os prompts do template
    ou apenas os especificados via `prompt_keys`.

    **⚠️ Esta operação pode levar alguns minutos** dependendo do tamanho da
    conversa e do número de prompts.

    **Headers necessários:**
    ```
    Authorization: Bearer <token>
    Content-Type: application/json
    ```

    **Exemplo de request (executar todos os prompts):**
    ```json
    {}
    ```

    **Exemplo de request (executar prompts específicos):**
    ```json
    {
        "prompt_keys": ["summary", "contradictions"]
    }
    ```

    **Exemplo de response (200):**
    ```json
    {
        "template_id": "juridico",
        "template_name": "Análise Jurídica",
        "conversation_id": "conv-abc123",
        "results": {
            "summary": "## Resumo Jurídico\\n\\nA conversa analisada...",
            "contradictions": "## Contradições Identificadas\\n\\n1. Em 15/01..."
        },
        "executed_prompts": ["summary", "contradictions"]
    }
    ```

    **Erros possíveis:**
    - **404 Not Found**: Template ou conversa não encontrados.
    - **400 Bad Request**: Conversa ainda está sendo processada.
    - **422 Unprocessable Entity**: Nenhum prompt válido para os keys fornecidos.
    - **401 Unauthorized**: Token ausente ou inválido.
    """
    logger.info(
        "Análise com template",
        extra={
            "template_id": template_id,
            "conversation_id": conversation_id,
            "user": current_user.username,
        },
    )

    # Validar template
    template = get_template(template_id)
    if not template:
        raise HTTPException(404, f"Template '{template_id}' não encontrado")

    # Buscar conversa
    stmt = apply_owner_filter(
        select(Conversation).where(Conversation.id == conversation_id),
        Conversation,
        current_user,
    )
    result = await db.execute(stmt)
    conv = result.scalar_one_or_none()
    ensure_owner_access(conv, current_user)
    if conv.status != ProcessingStatus.COMPLETED:
        raise HTTPException(400, "A conversa ainda está sendo processada")

    # Buscar mensagens para contexto
    msg_stmt = (
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(Message.sequence_number)
    )
    msg_result = await db.execute(msg_stmt)
    messages = msg_result.scalars().all()

    # Montar contexto da conversa
    context_lines = []
    context_lines.append(f"Conversa: {conv.conversation_name or 'Sem nome'}")
    context_lines.append(f"Participantes: {', '.join(conv.participants or [])}")
    context_lines.append(f"Período: {conv.date_start} a {conv.date_end}")
    context_lines.append(f"Total de mensagens: {conv.total_messages}")
    context_lines.append("")
    context_lines.append("--- MENSAGENS ---")

    for msg in messages[:500]:  # Limitar para não exceder contexto
        ts = msg.timestamp.strftime("%d/%m/%Y %H:%M") if msg.timestamp else "?"
        text = msg.original_text or ""
        if msg.transcription:
            text += f" [Transcrição: {msg.transcription}]"
        if msg.description:
            text += f" [Descrição: {msg.description}]"
        context_lines.append(f"[{ts}] {msg.sender}: {text}")

    conversation_context = "\n".join(context_lines)

    # Obter prompts do template
    prompt_keys = request.prompt_keys if request else None
    prompts = get_template_prompts(template_id, prompt_keys)
    if not prompts:
        raise ValidationError(
            detail="Nenhum prompt válido encontrado para os keys fornecidos",
            context={"template_id": template_id, "prompt_keys": prompt_keys},
        )

    # Executar cada prompt via Claude
    claude = get_claude_service()
    results = {}
    executed = []

    for key, prompt_text in prompts.items():
        try:
            full_prompt = (
                f"{prompt_text}\n\n"
                f"Contexto da conversa:\n{conversation_context}"
            )

            system_prompt = (
                f"Você é um analista especializado realizando uma {template['name']}. "
                f"Responda de forma estruturada, profissional e em português brasileiro."
            )

            # Usar _call_claude_with_retry do ClaudeService
            response = await claude._call_claude_with_retry(
                operation="template_analysis",
                model=claude.model,
                max_tokens=4000,
                system=system_prompt,
                messages=[{"role": "user", "content": full_prompt}],
            )
            result_text = response.content[0].text if response.content else ""
            results[key] = result_text
            executed.append(key)
            logger.info(f"Prompt '{key}' executado com sucesso para template '{template_id}'")

        except Exception as e:
            logger.error(
                f"Erro ao executar prompt '{key}' do template '{template_id}': {e}",
                exc_info=True,
            )
            results[key] = f"Erro ao processar: {str(e)}"
            executed.append(key)

    return TemplateAnalysisResponse(
        template_id=template_id,
        template_name=template["name"],
        conversation_id=conversation_id,
        results=results,
        executed_prompts=executed,
    )
