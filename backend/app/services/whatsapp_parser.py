"""
Parser de arquivos de exportação do WhatsApp
Suporta formatos Android e iOS, múltiplos idiomas
"""
import re
import zipfile
import os
import shutil
import logging
from datetime import datetime
from pathlib import Path
from typing import List, Tuple, Optional, Dict
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# ─── Padrões de Data/Hora WhatsApp ───────────────────────────────────────────
# Android: [DD/MM/YYYY HH:MM:SS] Nome: mensagem
# iOS: [DD/MM/YYYY, HH:MM:SS] Nome: mensagem
# US format: [M/D/YY, H:MM AM/PM] Name: message
PATTERNS = [
    # Android PT-BR: 26/03/2025 23:10:15 - Nome: mensagem
    re.compile(
        r"^(\d{1,2}/\d{1,2}/\d{2,4}),?\s+(\d{1,2}:\d{2}(?::\d{2})?)\s*(?:AM|PM)?\s*[-–]\s*([^:]+):\s*(.+)$",
        re.MULTILINE
    ),
    # iOS: [26/03/2025, 23:10:15] Nome: mensagem
    re.compile(
        r"^\[(\d{1,2}/\d{1,2}/\d{2,4}),\s+(\d{1,2}:\d{2}(?::\d{2})?)\s*(?:AM|PM)?\]\s+([^:]+):\s*(.+)$",
        re.MULTILINE
    ),
    # Formato alternativo com traço
    re.compile(
        r"^(\d{1,2}/\d{1,2}/\d{2,4})\s+(\d{1,2}:\d{2}(?::\d{2})?)\s*[-–]\s*([^:]+):\s*(.+)$",
        re.MULTILINE
    ),
]

# Padrões de mídia
MEDIA_PATTERNS = {
    "omitted": re.compile(r"<(.*?)\s+(?:omitted|omitido|anexado|attached)>", re.IGNORECASE),
    "filename": re.compile(
        r"^(?:(?:IMG|VID|AUD|STK|PTT|DOC|WAV|MP4|AAC|OGG|OPUS|JPEG|JPG|PNG|PDF|MOV|AVI|MKV|WEBP|MP3)-?\d+[-_\w]*\.\w{2,5})$",
        re.IGNORECASE
    ),
}

DELETED_PATTERNS = [
    "esta mensagem foi apagada",
    "you deleted this message",
    "this message was deleted",
    "mensagem apagada",
    "message deleted",
]

SYSTEM_PATTERNS = [
    re.compile(r"^Messages and calls are end-to-end encrypted", re.IGNORECASE),
    re.compile(r"^As mensagens e as chamadas são protegidas", re.IGNORECASE),
    re.compile(r"^\w+ added \w+", re.IGNORECASE),
    re.compile(r"^\w+ removed \w+", re.IGNORECASE),
    re.compile(r"^\w+ left", re.IGNORECASE),
    re.compile(r"changed the subject", re.IGNORECASE),
    re.compile(r"changed this group", re.IGNORECASE),
    re.compile(r"changed the group", re.IGNORECASE),
    re.compile(r"Security code changed", re.IGNORECASE),
    re.compile(r"You're now an admin", re.IGNORECASE),
]


@dataclass
class ParsedMessage:
    timestamp: datetime
    sender: str
    text: str
    media_filename: Optional[str] = None
    media_type: str = "text"
    is_deleted: bool = False
    is_system: bool = False
    sequence: int = 0


class WhatsAppParser:
    """Parser completo para exportações do WhatsApp"""

    MEDIA_EXTENSIONS = {
        "image": {".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp", ".tiff", ".heic"},
        "video": {".mp4", ".mov", ".avi", ".mkv", ".3gp", ".wmv", ".flv", ".webm"},
        "audio": {".mp3", ".ogg", ".opus", ".aac", ".wav", ".m4a", ".flac", ".amr"},
        "document": {".pdf", ".doc", ".docx", ".xls", ".xlsx", ".txt", ".ppt", ".pptx"},
        "sticker": {".webp"},
    }

    def __init__(self):
        self.messages: List[ParsedMessage] = []
        self.participants: set = set()
        self.media_files: Dict[str, str] = {}  # filename -> full_path

    def extract_zip(self, zip_path: str, extract_dir: str) -> Tuple[str, List[str]]:
        """
        Extrai o arquivo ZIP do WhatsApp.
        Retorna: (caminho do arquivo .txt, lista de arquivos de mídia)
        """
        extract_path = Path(extract_dir)
        extract_path.mkdir(parents=True, exist_ok=True)

        chat_file = None
        media_files = []

        with zipfile.ZipFile(zip_path, 'r') as zf:
            zf.extractall(extract_path)

        # Localizar arquivo de chat e mídias
        for file_path in extract_path.rglob("*"):
            if file_path.is_file():
                name_lower = file_path.name.lower()
                if name_lower.endswith(".txt") and ("chat" in name_lower or "whatsapp" in name_lower or "_chat" in name_lower):
                    chat_file = str(file_path)
                elif any(name_lower.endswith(ext) for exts in self.MEDIA_EXTENSIONS.values() for ext in exts):
                    media_files.append(str(file_path))
                    self.media_files[file_path.name] = str(file_path)

        # Fallback: pegar qualquer .txt
        if not chat_file:
            for file_path in extract_path.rglob("*.txt"):
                chat_file = str(file_path)
                break

        if not chat_file:
            raise ValueError("Nenhum arquivo de chat encontrado no ZIP")

        logger.info(f"Arquivo de chat encontrado: {chat_file}")
        logger.info(f"Arquivos de mídia encontrados: {len(media_files)}")

        return chat_file, media_files

    def parse_file(self, chat_file: str) -> List[ParsedMessage]:
        """Parse completo do arquivo de chat"""
        with open(chat_file, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()

        # Tentar detectar o formato
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
        logger.info(f"Total de mensagens parseadas: {len(messages)}")
        return messages

    def _split_into_messages(self, content: str) -> List[str]:
        """Divide o conteúdo em blocos de mensagens individuais"""
        # Primeiro tentar split por qualquer padrão de data no início da linha
        date_start = re.compile(
            r"(?=^\d{1,2}/\d{1,2}/\d{2,4}[,\s]|\^\[\d{1,2}/\d{1,2}/\d{2,4})",
            re.MULTILINE
        )

        # Método mais robusto: split nas linhas que começam com data
        line_pattern = re.compile(
            r"^(?:\[)?(\d{1,2}/\d{1,2}/\d{2,4})",
            re.MULTILINE
        )

        parts = []
        current = []

        for line in content.splitlines():
            if line_pattern.match(line.strip()) or (line.strip().startswith("[") and re.match(r"\[\d", line.strip())):
                if current:
                    parts.append(" ".join(current))
                current = [line]
            else:
                if current:
                    current.append(line)
                else:
                    parts.append(line)

        if current:
            parts.append(" ".join(current))

        return parts if parts else content.splitlines()

    def _parse_line(self, line: str, sequence: int) -> Optional[ParsedMessage]:
        """Faz o parse de uma linha individual"""
        # Verificar mensagens de sistema
        for sys_pattern in SYSTEM_PATTERNS:
            if sys_pattern.search(line):
                return None  # Ignorar mensagens de sistema

        # Tentar todos os padrões
        for pattern in PATTERNS:
            match = pattern.match(line.strip())
            if match:
                groups = match.groups()
                date_str = groups[0]
                time_str = groups[1]
                sender = groups[2].strip()
                text = groups[3].strip() if len(groups) > 3 else ""

                timestamp = self._parse_datetime(date_str, time_str)
                if not timestamp:
                    continue

                self.participants.add(sender)

                # Detectar se é mensagem deletada
                is_deleted = any(p in text.lower() for p in DELETED_PATTERNS)

                # Detectar mídia
                media_type, media_filename = self._detect_media(text)

                return ParsedMessage(
                    timestamp=timestamp,
                    sender=sender,
                    text=text,
                    media_filename=media_filename,
                    media_type=media_type,
                    is_deleted=is_deleted,
                    is_system=False,
                    sequence=sequence,
                )

        return None

    def _parse_datetime(self, date_str: str, time_str: str) -> Optional[datetime]:
        """Parse de data e hora em múltiplos formatos"""
        # Normalizar
        time_str = time_str.replace("AM", "").replace("PM", "").strip()

        # Tratar segundos opcionais
        if time_str.count(":") == 1:
            time_str += ":00"

        formats = [
            f"%d/%m/%Y %H:%M:%S",
            f"%d/%m/%y %H:%M:%S",
            f"%m/%d/%Y %H:%M:%S",
            f"%m/%d/%y %H:%M:%S",
            f"%d/%m/%Y %H:%M",
            f"%d/%m/%y %H:%M",
        ]

        datetime_str = f"{date_str} {time_str}"

        for fmt in formats:
            try:
                return datetime.strptime(datetime_str, fmt)
            except ValueError:
                continue

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
            elif "sticker" in file_desc or "adesivo" in file_desc:
                return "sticker", None
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
