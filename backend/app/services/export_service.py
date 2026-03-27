"""
Serviço de exportação para PDF e DOCX
Gera relatórios profissionais formatados
"""
import io
import os
import logging
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Dict, Any

from app.models import Conversation, Message, MediaType, SentimentType

logger = logging.getLogger(__name__)


def _format_timestamp(dt: Optional[datetime]) -> str:
    if not dt:
        return "—"
    return dt.strftime("%d/%m/%Y às %H:%M:%S")


def _sentiment_label(sentiment: Optional[SentimentType]) -> str:
    labels = {
        SentimentType.POSITIVE: "😊 Positivo",
        SentimentType.NEGATIVE: "😔 Negativo",
        SentimentType.NEUTRAL: "😐 Neutro",
        SentimentType.MIXED: "🤔 Misto",
    }
    return labels.get(sentiment, "—") if sentiment else "—"


def _media_type_label(mtype: MediaType) -> str:
    labels = {
        MediaType.IMAGE: "🖼️ Imagem",
        MediaType.AUDIO: "🎵 Áudio",
        MediaType.VIDEO: "🎬 Vídeo",
        MediaType.DOCUMENT: "📄 Documento",
        MediaType.STICKER: "🎭 Sticker",
        MediaType.CONTACT: "👤 Contato",
        MediaType.LOCATION: "📍 Localização",
        MediaType.DELETED: "🗑️ Mensagem Deletada",
    }
    return labels.get(mtype, "📎 Mídia")


class PDFExporter:
    """Gera PDFs profissionais com ReportLab"""

    def generate(
        self,
        conversation: Conversation,
        messages: List[Message],
        options: Dict[str, bool] = None,
    ) -> bytes:
        """Gera o PDF e retorna como bytes"""
        try:
            from reportlab.lib.pagesizes import A4
            from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
            from reportlab.lib.units import mm, cm
            from reportlab.lib import colors
            from reportlab.platypus import (
                SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
                HRFlowable, PageBreak
            )
            from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT
        except ImportError:
            raise RuntimeError("ReportLab não instalado. Execute: pip install reportlab")

        opts = options or {}
        buffer = io.BytesIO()

        # ─── Configuração do documento ─────────────────────────────────
        doc = SimpleDocTemplate(
            buffer,
            pagesize=A4,
            rightMargin=2*cm,
            leftMargin=2*cm,
            topMargin=2*cm,
            bottomMargin=2*cm,
            title=f"Transcrição - {conversation.conversation_name or 'Conversa'}",
            author="WhatsApp Insight Transcriber",
        )

        # ─── Estilos ──────────────────────────────────────────────────
        styles = getSampleStyleSheet()
        BRAND_COLOR = colors.HexColor("#6C63FF")
        DARK_COLOR = colors.HexColor("#1a1a2e")
        ACCENT_COLOR = colors.HexColor("#00d4aa")
        LIGHT_BG = colors.HexColor("#f8f9ff")

        title_style = ParagraphStyle(
            "CustomTitle",
            parent=styles["Title"],
            fontSize=24,
            textColor=BRAND_COLOR,
            spaceAfter=6,
            fontName="Helvetica-Bold",
        )
        subtitle_style = ParagraphStyle(
            "Subtitle",
            parent=styles["Normal"],
            fontSize=11,
            textColor=colors.HexColor("#666666"),
            spaceAfter=2,
        )
        section_header_style = ParagraphStyle(
            "SectionHeader",
            parent=styles["Heading2"],
            fontSize=14,
            textColor=BRAND_COLOR,
            spaceBefore=12,
            spaceAfter=6,
            fontName="Helvetica-Bold",
        )
        sender_style = ParagraphStyle(
            "Sender",
            parent=styles["Normal"],
            fontSize=9,
            textColor=ACCENT_COLOR,
            fontName="Helvetica-Bold",
        )
        timestamp_style = ParagraphStyle(
            "Timestamp",
            parent=styles["Normal"],
            fontSize=8,
            textColor=colors.HexColor("#999999"),
            alignment=TA_RIGHT,
        )
        message_style = ParagraphStyle(
            "Message",
            parent=styles["Normal"],
            fontSize=10,
            textColor=DARK_COLOR,
            leading=14,
            spaceAfter=4,
        )
        media_style = ParagraphStyle(
            "Media",
            parent=styles["Normal"],
            fontSize=9,
            textColor=colors.HexColor("#444444"),
            leftIndent=10,
            leading=13,
        )
        metadata_style = ParagraphStyle(
            "Metadata",
            parent=styles["Normal"],
            fontSize=8,
            textColor=colors.HexColor("#888888"),
            leftIndent=10,
        )

        # ─── Construir conteúdo ───────────────────────────────────────
        story = []

        # Cabeçalho
        story.append(Paragraph("🔍 WhatsApp Insight Transcriber", title_style))
        story.append(Paragraph(
            f"Transcrição Completa da Conversa: <b>{conversation.conversation_name or 'Conversa'}</b>",
            subtitle_style
        ))
        story.append(Paragraph(
            f"Gerado em: {datetime.now().strftime('%d/%m/%Y às %H:%M:%S')}",
            subtitle_style
        ))
        story.append(HRFlowable(width="100%", thickness=2, color=BRAND_COLOR))
        story.append(Spacer(1, 10))

        # ─── Metadados da Conversa ────────────────────────────────────
        if opts.get("include_statistics", True):
            story.append(Paragraph("📊 Informações Gerais", section_header_style))

            participants_str = ", ".join(conversation.participants or []) or "—"
            date_range = f"{_format_timestamp(conversation.date_start)} → {_format_timestamp(conversation.date_end)}"

            info_data = [
                ["Campo", "Valor"],
                ["Participantes", participants_str],
                ["Período", date_range],
                ["Total de Mensagens", str(conversation.total_messages)],
                ["Arquivos de Mídia", str(conversation.total_media)],
                ["Sentimento Geral", _sentiment_label(conversation.sentiment_overall)],
            ]

            info_table = Table(info_data, colWidths=[5*cm, 12*cm])
            info_table.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), BRAND_COLOR),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#dddddd")),
                ("BACKGROUND", (0, 1), (-1, -1), LIGHT_BG),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, LIGHT_BG]),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("PADDING", (0, 0), (-1, -1), 6),
            ]))
            story.append(info_table)
            story.append(Spacer(1, 12))

        # ─── Resumo ───────────────────────────────────────────────────
        if opts.get("include_summary", True) and conversation.summary:
            story.append(Paragraph("📝 Resumo Executivo", section_header_style))
            story.append(Paragraph(conversation.summary, message_style))
            story.append(Spacer(1, 8))

            if conversation.topics:
                topics_str = " • ".join(conversation.topics)
                story.append(Paragraph(f"<b>Tópicos:</b> {topics_str}", metadata_style))
            story.append(Spacer(1, 12))

        # ─── Contradições ─────────────────────────────────────────────
        if conversation.contradictions and opts.get("include_sentiment_analysis", True):
            story.append(Paragraph("⚠️ Contradições Detectadas", section_header_style))
            for c in conversation.contradictions[:10]:
                story.append(Paragraph(
                    f"<b>{c.get('participant', '?')}:</b> {c.get('description', '')}",
                    media_style
                ))
            story.append(Spacer(1, 12))

        # ─── Linha do Tempo ───────────────────────────────────────────
        story.append(PageBreak())
        story.append(Paragraph("💬 Transcrição Completa", section_header_style))
        story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#eeeeee")))
        story.append(Spacer(1, 8))

        for msg in messages:
            ts = _format_timestamp(msg.timestamp)

            if msg.media_type == MediaType.TEXT:
                story.append(Paragraph(f"{msg.sender}", sender_style))
                story.append(Paragraph(ts, timestamp_style))
                story.append(Paragraph(msg.original_text or "—", message_style))

            elif msg.media_type == MediaType.DELETED:
                story.append(Paragraph(f"{msg.sender}", sender_style))
                story.append(Paragraph(ts, timestamp_style))
                story.append(Paragraph("<i>🗑️ Mensagem deletada</i>", metadata_style))

            else:
                story.append(Paragraph(f"{msg.sender}", sender_style))
                story.append(Paragraph(ts, timestamp_style))

                # Tipo de mídia
                story.append(Paragraph(
                    f"<b>{_media_type_label(msg.media_type)}</b> — {msg.media_filename or ''}",
                    media_style
                ))

                # Metadados da mídia
                if msg.media_metadata:
                    meta = msg.media_metadata
                    meta_parts = []
                    if meta.get("file_size_formatted"):
                        meta_parts.append(f"Tamanho: {meta['file_size_formatted']}")
                    if meta.get("duration_formatted"):
                        meta_parts.append(f"Duração: {meta['duration_formatted']}")
                    if meta.get("resolution"):
                        meta_parts.append(f"Resolução: {meta['resolution']}")
                    if meta.get("format"):
                        meta_parts.append(f"Formato: {meta['format'].upper()}")
                    if meta_parts:
                        story.append(Paragraph(" | ".join(meta_parts), metadata_style))

                # Transcrição/Descrição
                if msg.transcription:
                    story.append(Paragraph(f"<b>🎤 Transcrição:</b>", media_style))
                    story.append(Paragraph(msg.transcription, message_style))
                if msg.description:
                    story.append(Paragraph(f"<b>👁️ Descrição:</b>", media_style))
                    story.append(Paragraph(msg.description, message_style))
                if msg.ocr_text:
                    story.append(Paragraph(f"<b>📄 Texto (OCR):</b> {msg.ocr_text}", media_style))

            # Sentimento individual
            if opts.get("include_sentiment_analysis", True) and msg.sentiment:
                story.append(Paragraph(
                    f"<i>Sentimento: {_sentiment_label(msg.sentiment)}</i>",
                    metadata_style
                ))

            story.append(HRFlowable(
                width="100%", thickness=0.5,
                color=colors.HexColor("#eeeeee"),
                spaceAfter=6
            ))

        # Rodapé
        story.append(Spacer(1, 20))
        story.append(HRFlowable(width="100%", thickness=1, color=BRAND_COLOR))
        story.append(Paragraph(
            f"<i>Relatório gerado por WhatsApp Insight Transcriber v1.0 | {datetime.now().strftime('%d/%m/%Y')}</i>",
            metadata_style
        ))

        doc.build(story)
        buffer.seek(0)
        return buffer.getvalue()


class DOCXExporter:
    """Gera documentos Word profissionais"""

    def generate(
        self,
        conversation: Conversation,
        messages: List[Message],
        options: Dict[str, bool] = None,
    ) -> bytes:
        """Gera o DOCX e retorna como bytes"""
        try:
            from docx import Document
            from docx.shared import Pt, Cm, RGBColor
            from docx.enum.text import WD_ALIGN_PARAGRAPH
            from docx.oxml.ns import qn
            from docx.oxml import OxmlElement
        except ImportError:
            raise RuntimeError("python-docx não instalado. Execute: pip install python-docx")

        opts = options or {}
        doc = Document()

        # ─── Configuração de página ────────────────────────────────────
        section = doc.sections[0]
        section.page_height = Cm(29.7)
        section.page_width = Cm(21.0)
        section.left_margin = Cm(2.5)
        section.right_margin = Cm(2.5)
        section.top_margin = Cm(2.5)
        section.bottom_margin = Cm(2.5)

        # ─── Estilos ──────────────────────────────────────────────────
        def add_heading(text: str, level: int = 1):
            p = doc.add_heading(text, level=level)
            run = p.runs[0] if p.runs else p.add_run(text)
            run.font.color.rgb = RGBColor(108, 99, 255)
            return p

        def add_paragraph(text: str, bold: bool = False, italic: bool = False, color: str = None, size: int = 10):
            p = doc.add_paragraph()
            run = p.add_run(text)
            run.font.size = Pt(size)
            run.bold = bold
            run.italic = italic
            if color:
                r, g, b = int(color[0:2], 16), int(color[2:4], 16), int(color[4:6], 16)
                run.font.color.rgb = RGBColor(r, g, b)
            return p

        # ─── Cabeçalho ────────────────────────────────────────────────
        title_p = doc.add_paragraph()
        title_run = title_p.add_run("WhatsApp Insight Transcriber")
        title_run.font.size = Pt(22)
        title_run.font.bold = True
        title_run.font.color.rgb = RGBColor(108, 99, 255)
        title_p.alignment = WD_ALIGN_PARAGRAPH.CENTER

        sub_p = doc.add_paragraph()
        sub_run = sub_p.add_run(f"Transcrição: {conversation.conversation_name or 'Conversa'}")
        sub_run.font.size = Pt(14)
        sub_run.font.color.rgb = RGBColor(100, 100, 100)
        sub_p.alignment = WD_ALIGN_PARAGRAPH.CENTER

        doc.add_paragraph(f"Gerado em: {datetime.now().strftime('%d/%m/%Y às %H:%M')}")
        doc.add_paragraph()  # Espaço

        # ─── Informações Gerais ───────────────────────────────────────
        if opts.get("include_statistics", True):
            add_heading("📊 Informações Gerais", level=2)

            table = doc.add_table(rows=6, cols=2)
            table.style = "Table Grid"

            rows_data = [
                ("Participantes", ", ".join(conversation.participants or []) or "—"),
                ("Data Início", _format_timestamp(conversation.date_start)),
                ("Data Fim", _format_timestamp(conversation.date_end)),
                ("Total Mensagens", str(conversation.total_messages)),
                ("Arquivos de Mídia", str(conversation.total_media)),
                ("Sentimento", _sentiment_label(conversation.sentiment_overall)),
            ]

            for i, (label, value) in enumerate(rows_data):
                row = table.rows[i]
                row.cells[0].text = label
                row.cells[1].text = value
                # Formatar cabeçalho da célula
                for cell in row.cells:
                    for paragraph in cell.paragraphs:
                        for run in paragraph.runs:
                            run.font.size = Pt(9)

            doc.add_paragraph()

        # ─── Resumo ───────────────────────────────────────────────────
        if opts.get("include_summary", True) and conversation.summary:
            add_heading("📝 Resumo Executivo", level=2)
            add_paragraph(conversation.summary)
            if conversation.topics:
                add_paragraph("Tópicos: " + " • ".join(conversation.topics), italic=True, size=9)
            doc.add_paragraph()

        # ─── Transcrição ──────────────────────────────────────────────
        doc.add_page_break()
        add_heading("💬 Transcrição Completa", level=1)

        for msg in messages:
            ts = _format_timestamp(msg.timestamp)

            # Remetente e timestamp
            p = doc.add_paragraph()
            run_sender = p.add_run(f"{msg.sender}")
            run_sender.bold = True
            run_sender.font.color.rgb = RGBColor(0, 212, 170)
            run_sender.font.size = Pt(9)
            p.add_run(f"  {ts}")
            p.runs[-1].font.color.rgb = RGBColor(150, 150, 150)
            p.runs[-1].font.size = Pt(8)

            if msg.media_type == MediaType.TEXT:
                add_paragraph(msg.original_text or "—", size=10)

            elif msg.media_type == MediaType.DELETED:
                add_paragraph("🗑️ Mensagem deletada", italic=True, color="999999", size=9)

            else:
                # Tipo de mídia
                p_media = doc.add_paragraph()
                run_type = p_media.add_run(f"{_media_type_label(msg.media_type)}")
                run_type.bold = True
                run_type.font.size = Pt(9)
                if msg.media_filename:
                    p_media.add_run(f" — {msg.media_filename}")

                # Metadados
                if msg.media_metadata:
                    meta = msg.media_metadata
                    meta_parts = []
                    if meta.get("file_size_formatted"):
                        meta_parts.append(f"Tamanho: {meta['file_size_formatted']}")
                    if meta.get("duration_formatted"):
                        meta_parts.append(f"Duração: {meta['duration_formatted']}")
                    if meta.get("resolution"):
                        meta_parts.append(f"Resolução: {meta['resolution']}")
                    if meta_parts:
                        add_paragraph(" | ".join(meta_parts), italic=True, color="888888", size=8)

                # Transcrição/Descrição
                if msg.transcription:
                    add_paragraph("🎤 Transcrição:", bold=True, size=9)
                    add_paragraph(msg.transcription, size=10)
                if msg.description:
                    add_paragraph("👁️ Descrição:", bold=True, size=9)
                    add_paragraph(msg.description, size=10)
                if msg.ocr_text:
                    add_paragraph(f"📄 OCR: {msg.ocr_text}", italic=True, size=9)

            # Linha divisória
            doc.add_paragraph("─" * 60).runs[0].font.size = Pt(6)

        # Rodapé
        doc.add_paragraph()
        footer_p = doc.add_paragraph(
            f"Relatório gerado por WhatsApp Insight Transcriber v1.0 | {datetime.now().strftime('%d/%m/%Y')}"
        )
        for run in footer_p.runs:
            run.font.size = Pt(8)
            run.font.color.rgb = RGBColor(150, 150, 150)

        # Salvar para buffer
        buffer = io.BytesIO()
        doc.save(buffer)
        buffer.seek(0)
        return buffer.getvalue()
