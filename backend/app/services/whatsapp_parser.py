"""
Parser de arquivos de exportação do WhatsApp
Suporta formatos Android e iOS, múltiplos idiomas, mensagens encaminhadas,
citadas, reações, edições, formatação rica e mensagens de sistema adicionais.
"""
import re
import zipfile
import os
import shutil
from datetime import datetime
from pathlib import Path
from typing import List, Tuple, Optional, Dict
from dataclasses import dataclass, field

from app.exceptions import ParserError
from app.logging import get_logger

logger = get_logger(__name__)

# ─── Padrões de Data/Hora WhatsApp ───────────────────────────────────────────
# Suporta Android, iOS e Web com formatos internacionais
PATTERNS = [
    # Android PT-BR: 26/03/2025 23:10:15 - Nome: mensagem
    re.compile(
        r"^(\d{1,2}/\d{1,2}/\d{2,4}),?\s+(\d{1,2}:\d{2}(?::\d{2})?)\s*(?:AM|PM|am|pm)?\s*[-–]\s*([^:]+):\s*(.+)$",
        re.MULTILINE | re.DOTALL,
    ),
    # iOS: [26/03/2025, 23:10:15] Nome: mensagem
    re.compile(
        r"^\[(\d{1,2}/\d{1,2}/\d{2,4}),\s+(\d{1,2}:\d{2}(?::\d{2})?)\s*(?:AM|PM|am|pm)?\]\s+([^:]+):\s*(.+)$",
        re.MULTILINE | re.DOTALL,
    ),
    # Formato alternativo com traço (sem vírgula)
    re.compile(
        r"^(\d{1,2}/\d{1,2}/\d{2,4})\s+(\d{1,2}:\d{2}(?::\d{2})?)\s*[-–]\s*([^:]+):\s*(.+)$",
        re.MULTILINE | re.DOTALL,
    ),
    # ISO yyyy-mm-dd HH:MM - Nome: mensagem
    re.compile(
        r"^(\d{4}-\d{2}-\d{2}),?\s+(\d{1,2}:\d{2}(?::\d{2})?)\s*(?:AM|PM|am|pm)?\s*[-–]\s*([^:]+):\s*(.+)$",
        re.MULTILINE | re.DOTALL,
    ),
    # Formato com ponto: dd.mm.yyyy, HH:MM - Nome: mensagem (alemão, etc.)
    re.compile(
        r"^(\d{1,2}\.\d{1,2}\.\d{2,4}),?\s+(\d{1,2}:\d{2}(?::\d{2})?)\s*[-–]\s*([^:]+):\s*(.+)$",
        re.MULTILINE | re.DOTALL,
    ),
    # Mensagens de sistema com data (sem remetente): dd/mm/yyyy HH:MM - mensagem
    re.compile(
        r"^(\d{1,2}/\d{1,2}/\d{2,4}),?\s+(\d{1,2}:\d{2}(?::\d{2})?)\s*(?:AM|PM|am|pm)?\s*[-–]\s*(.+)$",
        re.MULTILINE | re.DOTALL,
    ),
]

# Padrão separado para mensagens de sistema (sem sender:)
SYSTEM_MESSAGE_PATTERN = re.compile(
    r"^(?:\[)?(\d{1,2}[/.\-]\d{1,2}[/.\-]\d{2,4})[,\]]?\s+(\d{1,2}:\d{2}(?::\d{2})?)\s*(?:AM|PM|am|pm)?\s*(?:\])?\s*[-–]\s*(.+)$",
    re.MULTILINE,
)

# Padrões de mídia
MEDIA_PATTERNS = {
    "omitted": re.compile(r"<(.*?)\s+(?:omitted|omitido|anexado|attached)>", re.IGNORECASE),
    "filename": re.compile(
        r"^(?:(?:IMG|VID|AUD|STK|PTT|DOC|WAV|MP4|AAC|OGG|OPUS|JPEG|JPG|PNG|PDF|MOV|AVI|MKV|WEBP|MP3)-?\d+[-_\w]*\.\w{2,5})$",
        re.IGNORECASE,
    ),
}

DELETED_PATTERNS = [
    "esta mensagem foi apagada",
    "you deleted this message",
    "this message was deleted",
    "mensagem apagada",
    "message deleted",
    "this message was deleted by admin",
    "esta mensagem foi apagada pelo administrador",
]

# ─── Mensagens de Sistema (expandido) ────────────────────────────────────────
SYSTEM_PATTERNS = [
    re.compile(r"^Messages and calls are end-to-end encrypted", re.IGNORECASE),
    re.compile(r"^As mensagens e as chamadas são protegidas", re.IGNORECASE),
    re.compile(r"^As mensagens e ligações são protegidas", re.IGNORECASE),
    re.compile(r"^\w+ added \w+", re.IGNORECASE),
    re.compile(r"^\w+ adicionou \w+", re.IGNORECASE),
    re.compile(r"^\w+ removed \w+", re.IGNORECASE),
    re.compile(r"^\w+ removeu \w+", re.IGNORECASE),
    re.compile(r"^\w+ foi removido", re.IGNORECASE),
    re.compile(r"^\w+ left", re.IGNORECASE),
    re.compile(r"^\w+ saiu", re.IGNORECASE),
    re.compile(r"changed the subject", re.IGNORECASE),
    re.compile(r"changed this group", re.IGNORECASE),
    re.compile(r"changed the group", re.IGNORECASE),
    re.compile(r"alterou o assunto", re.IGNORECASE),
    re.compile(r"alterou a descrição do grupo", re.IGNORECASE),
    re.compile(r"alterou a imagem do grupo", re.IGNORECASE),
    re.compile(r"changed the group description", re.IGNORECASE),
    re.compile(r"changed the group icon", re.IGNORECASE),
    re.compile(r"Security code changed", re.IGNORECASE),
    re.compile(r"O código de segurança .+ mudou", re.IGNORECASE),
    re.compile(r"You're now an admin", re.IGNORECASE),
    re.compile(r"Agora você é um administrador", re.IGNORECASE),
    re.compile(r"entrou usando o link de convite", re.IGNORECASE),
    re.compile(r"joined using this group's invite link", re.IGNORECASE),
    re.compile(r"criou este grupo", re.IGNORECASE),
    re.compile(r"created this group", re.IGNORECASE),
    re.compile(r"^\w+ foi adicionado", re.IGNORECASE),
    re.compile(r"^\w+ was added", re.IGNORECASE),
    re.compile(r"number changed", re.IGNORECASE),
    re.compile(r"mudou o número", re.IGNORECASE),
    re.compile(r"Waiting for this message", re.IGNORECASE),
    re.compile(r"Aguardando esta mensagem", re.IGNORECASE),
    re.compile(r"disappearing messages", re.IGNORECASE),
    re.compile(r"mensagens temporárias", re.IGNORECASE),
    re.compile(r"Your security code with .+ changed", re.IGNORECASE),
    re.compile(r"Seu código de segurança com .+ mudou", re.IGNORECASE),
    re.compile(r"You changed this group's settings", re.IGNORECASE),
    re.compile(r"Você alterou as configurações", re.IGNORECASE),
    re.compile(r"pinned a message", re.IGNORECASE),
    re.compile(r"fixou uma mensagem", re.IGNORECASE),
    re.compile(r"started a call", re.IGNORECASE),
    re.compile(r"ligação perdida", re.IGNORECASE),
    re.compile(r"missed .+ call", re.IGNORECASE),
    re.compile(r"Poll:", re.IGNORECASE),
    re.compile(r"Enquete:", re.IGNORECASE),
]

# ─── Padrões de Encaminhamento ────────────────────────────────────────────────
FORWARDED_PATTERNS = [
    re.compile(r"^\u200e?⁣?\[?Forwarded\]?", re.IGNORECASE),
    re.compile(r"^\u200e?⁣?\[?Encaminhada\]?", re.IGNORECASE),
    re.compile(r"^\u200e?⁣?Forwarded$", re.IGNORECASE),
    re.compile(r"^\u200e?⁣?Encaminhada$", re.IGNORECASE),
]

# ─── Padrões de Edição ───────────────────────────────────────────────────────
EDITED_PATTERNS = [
    re.compile(r"<This message was edited>", re.IGNORECASE),
    re.compile(r"<Esta mensagem foi editada>", re.IGNORECASE),
    re.compile(r"\u200e?<edited>", re.IGNORECASE),
    re.compile(r"\u200e?<editada>", re.IGNORECASE),
]

# ─── Padrões de Formatação Rica ──────────────────────────────────────────────
RICH_FORMAT_PATTERNS = {
    "bold": re.compile(r"\*([^*\n]+)\*"),       # *negrito*
    "italic": re.compile(r"_([^_\n]+)_"),       # _itálico_
    "strikethrough": re.compile(r"~([^~\n]+)~"),  # ~tachado~
    "monospace": re.compile(r"```([^`]+)```"),   # ```monospace```
    "inline_code": re.compile(r"`([^`\n]+)`"),  # `inline code`
}


@dataclass
class ParsedMessage:
    timestamp: datetime
    sender: str
    text: str
    media_filename: Optional[str] = None
    media_type: str = "text"
    is_deleted: bool = False
    is_system: bool = False
    is_forwarded: bool = False
    is_edited: bool = False
    is_quoted: bool = False
    quoted_text: Optional[str] = None
    reaction: Optional[str] = None
    rich_formatting: Dict[str, List[str]] = field(default_factory=dict)
    sequence: int = 0


class WhatsAppParser:
    """Parser completo para exportações do WhatsApp com suporte avançado."""

    MEDIA_EXTENSIONS = {
        "image": {".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp", ".tiff", ".heic"},
        "video": {".mp4", ".mov", ".avi", ".mkv", ".3gp", ".wmv", ".flv", ".webm"},
        "audio": {".mp3", ".ogg", ".opus", ".aac", ".wav", ".m4a", ".flac", ".amr"},
        "document": {".pdf", ".doc", ".docx", ".xls", ".xlsx", ".txt", ".ppt", ".pptx"},
        "sticker": set(),
    }

    def __init__(self):
        self.messages: List[ParsedMessage] = []
        self.participants: set = set()
        self.media_files: Dict[str, str] = {}  # filename -> full_path
        self._date_format: Optional[str] = None  # formato detectado

    def extract_zip(self, zip_path: str, extract_dir: str) -> Tuple[str, List[str]]:
        """
        Extrai o arquivo ZIP do WhatsApp.
        Retorna: (caminho do arquivo .txt, lista de arquivos de mídia)
        """
        try:
            extract_path = Path(extract_dir)
            extract_path.mkdir(parents=True, exist_ok=True)

            chat_file = None
            media_files = []

            with zipfile.ZipFile(zip_path, "r") as zf:
                # Validar contra path traversal
                for member in zf.namelist():
                    member_path = os.path.normpath(member)
                    if member_path.startswith("..") or os.path.isabs(member_path):
                        raise ParserError(
                            detail=f"Caminho suspeito no ZIP (path traversal): {member}",
                            context={"file": member, "zip_path": zip_path},
                        )
                zf.extractall(extract_path)

            # Localizar arquivo de chat e mídias
            for file_path in extract_path.rglob("*"):
                if file_path.is_file():
                    name_lower = file_path.name.lower()
                    if name_lower.endswith(".txt") and (
                        "chat" in name_lower
                        or "whatsapp" in name_lower
                        or "_chat" in name_lower
                    ):
                        chat_file = str(file_path)
                    elif any(
                        name_lower.endswith(ext)
                        for exts in self.MEDIA_EXTENSIONS.values()
                        for ext in exts
                    ):
                        media_files.append(str(file_path))
                        self.media_files[file_path.name] = str(file_path)

            # Fallback: pegar qualquer .txt
            if not chat_file:
                for file_path in extract_path.rglob("*.txt"):
                    chat_file = str(file_path)
                    break

            if not chat_file:
                raise ParserError(
                    detail="Nenhum arquivo de chat encontrado no ZIP",
                    context={"zip_path": zip_path, "extracted_files": len(list(extract_path.rglob("*")))},
                )

            logger.info(
                "zip_extracted",
                event="parser.zip.extracted",
                files_count=len(list(extract_path.rglob("*"))),
                media_count=len(media_files),
                chat_file=chat_file,
            )

            return chat_file, media_files

        except ParserError:
            raise
        except zipfile.BadZipFile as e:
            raise ParserError(
                detail="Arquivo ZIP inválido ou corrompido",
                context={"zip_path": zip_path, "original_error": str(e)},
            )
        except Exception as e:
            raise ParserError(
                detail=f"Erro ao extrair arquivo ZIP: {str(e)}",
                context={"zip_path": zip_path, "original_error": str(e)},
            )

    def parse_file(self, chat_file: str) -> List[ParsedMessage]:
        """Parse completo do arquivo de chat"""
        # Reset de estado mutável
        self.participants = set()
        self.messages = []
        self._date_format = None

        try:
            with open(chat_file, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()
        except (IOError, OSError) as e:
            raise ParserError(
                detail=f"Erro ao ler arquivo de chat: {str(e)}",
                context={"chat_file": chat_file},
            )

        if not content.strip():
            raise ParserError(
                detail="Arquivo de chat está vazio",
                context={"chat_file": chat_file},
            )

        # Detectar formato de data automaticamente
        self._detect_date_format(content)

        # Dividir em blocos de mensagens
        lines = self._split_into_messages(content)
        messages = []
        sequence = 0

        for line in lines:
            line = line.strip()
            if not line:
                continue

            parsed = self._parse_line(line, sequence)
            if parsed:
                sequence += 1
                messages.append(parsed)

        self.messages = messages
        date_start, date_end = self.get_date_range()
        logger.info(
            "chat_parsed",
            event="parser.chat.parsed",
            messages_count=len(messages),
            participants_count=len(self.participants),
            date_range=f"{date_start} - {date_end}" if date_start else None,
            date_format=self._date_format or "auto",
        )
        return messages

    def _detect_date_format(self, content: str) -> None:
        """
        Detecta automaticamente o formato de data usado no arquivo.
        Analisa as primeiras linhas para determinar se é dd/mm ou mm/dd.
        """
        # Extrair as primeiras datas encontradas
        date_pattern = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{2,4})")
        matches = date_pattern.findall(content[:5000])

        if not matches:
            # Tentar formato ISO
            if re.search(r"\d{4}-\d{2}-\d{2}", content[:5000]):
                self._date_format = "iso"
                return
            # Tentar formato com ponto
            if re.search(r"\d{1,2}\.\d{1,2}\.\d{2,4}", content[:5000]):
                self._date_format = "dot_dmy"
                return
            return

        # Heurística: se algum primeiro campo > 12, é dd/mm
        # Se algum segundo campo > 12, é mm/dd
        first_vals = [int(m[0]) for m in matches]
        second_vals = [int(m[1]) for m in matches]

        if any(v > 12 for v in first_vals):
            self._date_format = "dmy"  # dd/mm/yyyy
        elif any(v > 12 for v in second_vals):
            self._date_format = "mdy"  # mm/dd/yyyy
        else:
            # Ambíguo — usar dd/mm como padrão (mais comum fora dos EUA)
            self._date_format = "dmy"

        logger.debug(f"Formato de data detectado: {self._date_format}")

    def _split_into_messages(self, content: str) -> List[str]:
        """Divide o conteúdo em blocos de mensagens individuais, preservando multi-linha."""
        # Padrão genérico que detecta início de mensagem (data no começo)
        line_pattern = re.compile(
            r"^(?:\[)?"
            r"(?:\d{1,2}[/.\-]\d{1,2}[/.\-]\d{2,4}"  # dd/mm/yyyy, mm/dd/yyyy, dd.mm.yyyy
            r"|\d{4}-\d{2}-\d{2})",                     # yyyy-mm-dd
            re.MULTILINE,
        )

        parts = []
        current = []

        for line in content.splitlines():
            stripped = line.strip()
            if line_pattern.match(stripped) or (stripped.startswith("[") and re.match(r"\[\d", stripped)):
                if current:
                    parts.append("\n".join(current))
                current = [line]
            else:
                if current:
                    current.append(line)
                else:
                    # Linha órfã antes da primeira mensagem — guardar como está
                    parts.append(line)

        if current:
            parts.append("\n".join(current))

        return parts if parts else content.splitlines()

    def _parse_line(self, line: str, sequence: int) -> Optional[ParsedMessage]:
        """Faz o parse de uma linha/bloco individual"""
        # Limpar caracteres de controle Unicode (LTR/RTL markers, etc.)
        cleaned = line.strip().replace("\u200e", "").replace("\u200f", "").replace("\u202a", "").replace("\u202c", "")

        # Verificar se é mensagem de sistema (sem remetente)
        if self._is_system_message(cleaned):
            return None

        # Tentar todos os padrões (os 5 primeiros têm sender, o 6o é sistema)
        for i, pattern in enumerate(PATTERNS[:-1]):  # Excluir o último padrão (sistema)
            match = pattern.match(cleaned)
            if match:
                groups = match.groups()
                date_str = groups[0]
                time_str = groups[1]
                sender = groups[2].strip()
                text = groups[3].strip() if len(groups) > 3 else ""

                timestamp = self._parse_datetime(date_str, time_str)
                if not timestamp:
                    continue

                # Checar se sender parece ser uma mensagem de sistema
                if self._is_system_sender(sender):
                    return None

                self.participants.add(sender)

                # Detectar propriedades especiais da mensagem
                is_deleted = any(p in text.lower() for p in DELETED_PATTERNS)
                is_forwarded = self._detect_forwarded(text)
                is_edited = self._detect_edited(text)
                is_quoted, quoted_text = self._detect_quoted(text)
                reaction = self._detect_reaction(text)
                rich_formatting = self._detect_rich_formatting(text)

                # Limpar marcadores do texto
                clean_text = self._clean_message_text(text, is_forwarded, is_edited)

                # Detectar mídia
                media_type, media_filename = self._detect_media(clean_text)

                return ParsedMessage(
                    timestamp=timestamp,
                    sender=sender,
                    text=clean_text,
                    media_filename=media_filename,
                    media_type=media_type,
                    is_deleted=is_deleted,
                    is_system=False,
                    is_forwarded=is_forwarded,
                    is_edited=is_edited,
                    is_quoted=is_quoted,
                    quoted_text=quoted_text,
                    reaction=reaction,
                    rich_formatting=rich_formatting,
                    sequence=sequence,
                )

        return None

    def _is_system_message(self, text: str) -> bool:
        """Verifica se o texto é uma mensagem de sistema."""
        for sys_pattern in SYSTEM_PATTERNS:
            if sys_pattern.search(text):
                return True
        return False

    def _is_system_sender(self, sender: str) -> bool:
        """Verifica se o remetente parece ser sistema/notificação."""
        system_senders = {
            "system", "sistema", "whatsapp", "you", "você",
        }
        # Mensagens de sistema geralmente não têm nome de pessoa
        lower = sender.lower().strip()
        if lower in system_senders:
            return True
        # Mensagens de sistema com texto longo como "sender"
        if len(sender) > 100:
            return True
        return False

    def _detect_forwarded(self, text: str) -> bool:
        """Detecta se a mensagem é encaminhada."""
        for pattern in FORWARDED_PATTERNS:
            if pattern.search(text):
                return True
        return False

    def _detect_edited(self, text: str) -> bool:
        """Detecta se a mensagem foi editada."""
        for pattern in EDITED_PATTERNS:
            if pattern.search(text):
                return True
        return False

    def _detect_quoted(self, text: str) -> Tuple[bool, Optional[str]]:
        """
        Detecta se a mensagem contém citação/resposta.
        WhatsApp Web/Android mostra citações de formas diferentes.
        """
        # Padrão iOS: começa com caractere especial de citação
        quote_match = re.match(r"^\u200e?⁣?\u200e?(.+?)\n(.+)$", text, re.DOTALL)
        if quote_match:
            potential_quote = quote_match.group(1).strip()
            # Verificar se parece uma citação (geralmente curta)
            if len(potential_quote) < 200 and "\n" not in potential_quote:
                return True, potential_quote

        # Padrão alternativo: texto entre aspas angulares
        quote_match2 = re.match(r"^[>»]\s*(.+?)(?:\n|$)(.*)$", text, re.DOTALL)
        if quote_match2:
            return True, quote_match2.group(1).strip()

        return False, None

    def _detect_reaction(self, text: str) -> Optional[str]:
        """
        Detecta reações em mensagens.
        WhatsApp mostra reações como emojis associados a mensagens.
        """
        # Padrão de reação: mensagem curta que é apenas emoji(s)
        stripped = text.strip()
        # Verificar se é apenas emojis (caracteres em blocos Unicode de emojis)
        emoji_pattern = re.compile(
            r"^[\U0001F600-\U0001F64F\U0001F300-\U0001F5FF\U0001F680-\U0001F6FF"
            r"\U0001F900-\U0001F9FF\U0001FA00-\U0001FA6F\U0001FA70-\U0001FAFF"
            r"\U00002702-\U000027B0\U0000FE00-\U0000FE0F\U0000200D"
            r"\U00002600-\U000026FF\U00002700-\U000027BF\u200d\ufe0f]+$"
        )
        if emoji_pattern.match(stripped) and len(stripped) <= 8:
            return stripped

        return None

    def _detect_rich_formatting(self, text: str) -> Dict[str, List[str]]:
        """Detecta formatação rica do WhatsApp no texto."""
        found = {}
        for fmt_name, pattern in RICH_FORMAT_PATTERNS.items():
            matches = pattern.findall(text)
            if matches:
                found[fmt_name] = matches
        return found

    def _clean_message_text(self, text: str, is_forwarded: bool, is_edited: bool) -> str:
        """Remove marcadores especiais do texto mantendo o conteúdo."""
        cleaned = text

        # Remover marcador de encaminhamento
        if is_forwarded:
            for pattern in FORWARDED_PATTERNS:
                cleaned = pattern.sub("", cleaned).strip()

        # Remover marcador de edição
        if is_edited:
            for pattern in EDITED_PATTERNS:
                cleaned = pattern.sub("", cleaned).strip()

        # Remover caracteres de controle Unicode residuais
        cleaned = cleaned.replace("\u200e", "").replace("\u200f", "").strip()

        return cleaned if cleaned else text

    def _parse_datetime(self, date_str: str, time_str: str) -> Optional[datetime]:
        """Parse de data e hora em múltiplos formatos com detecção automática."""
        # Converter AM/PM para 24h
        if "PM" in time_str.upper() or "AM" in time_str.upper():
            is_pm = "PM" in time_str.upper()
            time_str = time_str.upper().replace("AM", "").replace("PM", "").strip()
            parts = time_str.split(":")
            hour = int(parts[0])
            if is_pm and hour != 12:
                hour += 12
            elif not is_pm and hour == 12:
                hour = 0
            parts[0] = str(hour)
            time_str = ":".join(parts)

        # Tratar segundos opcionais
        if time_str.count(":") == 1:
            time_str += ":00"

        datetime_str = f"{date_str} {time_str}"

        # Formatos baseados na detecção automática
        if self._date_format == "iso":
            formats = [
                "%Y-%m-%d %H:%M:%S",
                "%Y-%m-%d %H:%M",
            ]
        elif self._date_format == "mdy":
            formats = [
                "%m/%d/%Y %H:%M:%S",
                "%m/%d/%y %H:%M:%S",
                "%m/%d/%Y %H:%M",
                "%m/%d/%y %H:%M",
            ]
        elif self._date_format == "dot_dmy":
            formats = [
                "%d.%m.%Y %H:%M:%S",
                "%d.%m.%y %H:%M:%S",
                "%d.%m.%Y %H:%M",
                "%d.%m.%y %H:%M",
            ]
        else:
            # Padrão: dd/mm (mais comum)
            formats = [
                "%d/%m/%Y %H:%M:%S",
                "%d/%m/%y %H:%M:%S",
                "%d/%m/%Y %H:%M",
                "%d/%m/%y %H:%M",
            ]

        # Tentar formatos detectados primeiro
        for fmt in formats:
            try:
                return datetime.strptime(datetime_str, fmt)
            except ValueError:
                continue

        # Fallback: tentar todos os formatos possíveis
        all_formats = [
            "%d/%m/%Y %H:%M:%S",
            "%d/%m/%y %H:%M:%S",
            "%m/%d/%Y %H:%M:%S",
            "%m/%d/%y %H:%M:%S",
            "%Y-%m-%d %H:%M:%S",
            "%d.%m.%Y %H:%M:%S",
            "%d.%m.%y %H:%M:%S",
            "%d/%m/%Y %H:%M",
            "%d/%m/%y %H:%M",
            "%m/%d/%Y %H:%M",
            "%m/%d/%y %H:%M",
        ]
        for fmt in all_formats:
            try:
                return datetime.strptime(datetime_str, fmt)
            except ValueError:
                continue

        logger.debug(f"Não foi possível parsear data: {datetime_str}")
        return None

    def _detect_media(self, text: str) -> Tuple[str, Optional[str]]:
        """Detecta o tipo de mídia na mensagem"""
        # Padrão: arquivo omitido/anexado
        omit_match = MEDIA_PATTERNS["omitted"].search(text)
        if omit_match:
            file_desc = omit_match.group(1).lower()
            if any(ext in file_desc for ext in [".jpg", ".jpeg", ".png", ".webp", ".gif", ".heic"]):
                return "image", None
            elif any(ext in file_desc for ext in [".mp4", ".mov", ".avi", ".3gp"]):
                return "video", None
            elif any(ext in file_desc for ext in [".mp3", ".ogg", ".opus", ".aac", ".wav", ".m4a", ".amr"]):
                return "audio", None
            elif "audio" in file_desc or "voice" in file_desc or "ptt" in file_desc:
                return "audio", None
            elif "sticker" in file_desc or "adesivo" in file_desc or "figurinha" in file_desc:
                return "sticker", None
            elif "image" in file_desc or "imagem" in file_desc or "foto" in file_desc or "photo" in file_desc:
                return "image", None
            elif "video" in file_desc or "vídeo" in file_desc:
                return "video", None
            elif "document" in file_desc or "documento" in file_desc:
                return "document", None
            elif "contact" in file_desc or "contato" in file_desc:
                return "contact", None
            elif "gif" in file_desc:
                return "image", None
            return "document", None

        # Verificar se o texto é um nome de arquivo de mídia
        text_stripped = text.strip()
        if MEDIA_PATTERNS["filename"].match(text_stripped):
            ext = Path(text_stripped).suffix.lower()
            for mtype, exts in self.MEDIA_EXTENSIONS.items():
                if ext in exts:
                    return mtype, text_stripped

        # Verificar padrões específicos de PTT (push to talk = áudio)
        if re.match(r"^PTT-\d{8}-WA\d+\.(ogg|opus|mp3|m4a|aac)", text_stripped, re.IGNORECASE):
            return "audio", text_stripped

        # Verificar outros padrões de arquivo
        for mtype, exts in self.MEDIA_EXTENSIONS.items():
            for ext in exts:
                if text_stripped.endswith(ext):
                    return mtype, text_stripped

        # Localização
        if re.match(r"^https?://maps\.google", text_stripped):
            return "location", None
        if re.match(r"^https?://maps\.apple", text_stripped):
            return "location", None
        # WhatsApp location sharing
        if "location:" in text_stripped.lower() or "localização:" in text_stripped.lower():
            return "location", None

        # Contato compartilhado
        if text_stripped.endswith(".vcf"):
            return "contact", text_stripped

        return "text", None

    def get_media_path(self, filename: str) -> Optional[str]:
        """Retorna o caminho completo de um arquivo de mídia"""
        if filename in self.media_files:
            return self.media_files[filename]
        # Busca case-insensitive
        for key, path in self.media_files.items():
            if key.lower() == filename.lower():
                return path
        return None

    def get_participants(self) -> List[str]:
        return sorted(list(self.participants))

    def get_date_range(self) -> Tuple[Optional[datetime], Optional[datetime]]:
        if not self.messages:
            return None, None
        timestamps = [m.timestamp for m in self.messages]
        return min(timestamps), max(timestamps)

    def get_stats(self) -> Dict:
        """Retorna estatísticas detalhadas do parsing."""
        if not self.messages:
            return {}

        total = len(self.messages)
        forwarded = sum(1 for m in self.messages if m.is_forwarded)
        edited = sum(1 for m in self.messages if m.is_edited)
        deleted = sum(1 for m in self.messages if m.is_deleted)
        quoted = sum(1 for m in self.messages if m.is_quoted)
        media = sum(1 for m in self.messages if m.media_type != "text")
        with_formatting = sum(1 for m in self.messages if m.rich_formatting)

        return {
            "total_messages": total,
            "participants": self.get_participants(),
            "forwarded": forwarded,
            "edited": edited,
            "deleted": deleted,
            "quoted": quoted,
            "media": media,
            "with_rich_formatting": with_formatting,
            "date_format_detected": self._date_format,
        }
