"""
Templates pré-configurados de análise para diferentes contextos.
Cada template possui prompts específicos para análise via IA.
"""
import logging
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)

TEMPLATES: Dict[str, Dict[str, Any]] = {
    "juridico": {
        "name": "Análise Jurídica",
        "description": "Análise para fins legais — identifica fatos, entidades, linha do tempo e contradições relevantes juridicamente.",
        "prompts": {
            "summary": (
                "Analise esta conversa do WhatsApp identificando todos os fatos relevantes "
                "juridicamente. Foque em declarações que possam constituir provas, compromissos "
                "assumidos, ameaças, acordos verbais e qualquer conteúdo com potencial valor legal. "
                "Apresente de forma estruturada e objetiva."
            ),
            "entities": (
                "Identifique todas as entidades mencionadas nesta conversa: pessoas (com seus "
                "papéis/relações), empresas/organizações, datas relevantes, valores monetários, "
                "endereços, números de documentos e qualquer outra referência identificável. "
                "Organize em categorias."
            ),
            "timeline": (
                "Crie uma linha do tempo detalhada e cronológica dos eventos relevantes "
                "mencionados nesta conversa. Inclua datas (quando disponíveis), participantes "
                "envolvidos e descrição do evento. Foque em fatos com relevância jurídica."
            ),
            "contradictions": (
                "Identifique todas as contradições entre declarações dos participantes desta "
                "conversa. Para cada contradição encontrada, cite as mensagens conflitantes, "
                "os participantes envolvidos e a natureza da inconsistência. Isso é crucial "
                "para avaliação de credibilidade."
            ),
        },
    },
    "comercial": {
        "name": "Análise Comercial",
        "description": "Análise de negociações, vendas, propostas comerciais e relacionamento com clientes.",
        "prompts": {
            "summary": (
                "Analise esta conversa comercial identificando: produtos/serviços discutidos, "
                "valores e condições negociadas, objeções levantadas, compromissos de compra, "
                "prazos acordados e status final da negociação. Resuma de forma executiva."
            ),
            "entities": (
                "Extraia todas as informações comerciais: nomes de produtos/serviços, valores "
                "monetários, percentuais de desconto, prazos de entrega, condições de pagamento, "
                "nomes de empresas, contatos e qualquer dado relevante para follow-up comercial."
            ),
            "timeline": (
                "Monte a linha do tempo da negociação: primeiro contato, apresentação de proposta, "
                "contra-propostas, objeções, concessões e fechamento (ou não). Identifique o "
                "estágio atual do funil de vendas."
            ),
            "sentiment": (
                "Analise o sentimento ao longo da negociação. Identifique momentos de maior "
                "engajamento, frustração, entusiasmo ou hesitação do prospect/cliente. "
                "Sugira pontos de melhoria na abordagem comercial."
            ),
            "recommendations": (
                "Com base na conversa, forneça recomendações estratégicas: próximos passos, "
                "pontos de atenção, oportunidades de upsell/cross-sell e sugestões para "
                "melhorar o relacionamento comercial."
            ),
        },
    },
    "familiar": {
        "name": "Análise Familiar",
        "description": "Análise de dinâmica familiar, relacionamentos e padrões de comunicação.",
        "prompts": {
            "summary": (
                "Analise esta conversa familiar identificando os principais temas discutidos, "
                "decisões tomadas, conflitos identificados e momentos de união/apoio. "
                "Descreva a dinâmica geral da comunicação familiar."
            ),
            "entities": (
                "Identifique todos os membros da família mencionados, seus papéis/relações "
                "(pai, mãe, filho, etc.), eventos familiares citados (aniversários, reuniões, "
                "viagens), locais e datas relevantes."
            ),
            "timeline": (
                "Crie uma linha do tempo dos eventos e decisões familiares mencionados na "
                "conversa. Inclua planejamentos futuros, compromissos agendados e marcos "
                "importantes citados."
            ),
            "sentiment": (
                "Analise o tom emocional da conversa. Identifique padrões de comunicação "
                "entre os participantes: quem tende a mediar conflitos, quem expressa "
                "mais emoções, dinâmicas de poder e padrões recorrentes."
            ),
            "contradictions": (
                "Identifique divergências de opinião ou conflitos latentes entre os "
                "participantes. Analise como essas divergências são tratadas e se há "
                "padrões de resolução ou escalação."
            ),
        },
    },
    "rh": {
        "name": "Análise de RH",
        "description": "Análise de comunicação profissional, clima organizacional e relações de trabalho.",
        "prompts": {
            "summary": (
                "Analise esta conversa profissional identificando: temas discutidos, "
                "decisões tomadas, tarefas delegadas, prazos definidos, conflitos "
                "interpessoais e clima organizacional geral."
            ),
            "entities": (
                "Identifique: nomes de colaboradores e seus cargos/funções, departamentos "
                "mencionados, projetos, clientes, prazos, reuniões agendadas e qualquer "
                "referência a políticas ou processos da empresa."
            ),
            "timeline": (
                "Monte uma linha do tempo de decisões e compromissos profissionais: "
                "tarefas atribuídas com responsável e prazo, reuniões agendadas, "
                "entregas esperadas e marcos de projeto."
            ),
            "sentiment": (
                "Avalie o clima organizacional refletido na conversa. Identifique "
                "indicadores de satisfação/insatisfação, motivação, estresse, "
                "colaboração e possíveis sinais de burnout ou conflito."
            ),
            "recommendations": (
                "Com base na análise, sugira ações de RH: necessidade de mediação, "
                "oportunidades de desenvolvimento de equipe, ajustes de comunicação, "
                "reconhecimentos devidos e pontos de atenção para gestão de pessoas."
            ),
        },
    },
    "geral": {
        "name": "Análise Geral",
        "description": "Análise completa padrão — resumo abrangente com principais insights.",
        "prompts": {
            "summary": (
                "Faça um resumo executivo completo desta conversa do WhatsApp. Inclua: "
                "participantes, período, principais temas discutidos, decisões tomadas, "
                "pendências e tom geral da conversa."
            ),
            "entities": (
                "Extraia todas as entidades relevantes: pessoas, organizações, locais, "
                "datas, valores, links, números de telefone e qualquer referência "
                "identificável mencionada na conversa."
            ),
            "timeline": (
                "Crie uma linha do tempo dos principais eventos e marcos mencionados "
                "na conversa, em ordem cronológica."
            ),
            "sentiment": (
                "Analise o sentimento geral e por participante ao longo da conversa. "
                "Identifique mudanças de humor, momentos de tensão e de harmonia."
            ),
            "contradictions": (
                "Identifique quaisquer contradições, inconsistências ou mudanças "
                "de posição entre os participantes da conversa."
            ),
        },
    },
}


def get_all_templates() -> List[Dict[str, Any]]:
    """Retorna lista de todos os templates disponíveis."""
    result = []
    for template_id, template in TEMPLATES.items():
        result.append({
            "id": template_id,
            "name": template["name"],
            "description": template["description"],
            "prompts": template["prompts"],
        })
    return result


def get_template(template_id: str) -> Optional[Dict[str, Any]]:
    """Retorna um template específico pelo ID."""
    template = TEMPLATES.get(template_id)
    if not template:
        return None
    return {
        "id": template_id,
        "name": template["name"],
        "description": template["description"],
        "prompts": template["prompts"],
    }


def get_template_prompts(
    template_id: str,
    prompt_keys: Optional[List[str]] = None,
) -> Optional[Dict[str, str]]:
    """Retorna os prompts de um template, filtrados por keys se fornecido."""
    template = TEMPLATES.get(template_id)
    if not template:
        return None

    prompts = template["prompts"]
    if prompt_keys:
        return {k: v for k, v in prompts.items() if k in prompt_keys}
    return dict(prompts)
