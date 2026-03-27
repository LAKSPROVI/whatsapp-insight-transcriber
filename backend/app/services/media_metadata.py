"""
Extrator de metadados de arquivos de mídia
"""
import os
import mimetypes
import logging
from pathlib import Path
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)


def format_file_size(size_bytes: int) -> str:
    """Formata o tamanho do arquivo de forma legível"""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 ** 2:
        return f"{size_bytes / 1024:.1f} KB"
    elif size_bytes < 1024 ** 3:
        return f"{size_bytes / (1024**2):.1f} MB"
    else:
        return f"{size_bytes / (1024**3):.1f} GB"


def format_duration(seconds: float) -> str:
    """Formata duração em HH:MM:SS ou MM:SS"""
    if seconds < 60:
        return f"{int(seconds)}s"
    elif seconds < 3600:
        minutes = int(seconds // 60)
        secs = int(seconds % 60)
        return f"{minutes}:{secs:02d}"
    else:
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        return f"{hours}:{minutes:02d}:{secs:02d}"


class MediaMetadataExtractor:
    """Extrai metadados de arquivos de mídia usando múltiplas bibliotecas"""

    @staticmethod
    def extract(file_path: str) -> Dict[str, Any]:
        """Extrai todos os metadados disponíveis de um arquivo"""
        path = Path(file_path)

        if not path.exists():
            return {}

        metadata = {
            "file_size": path.stat().st_size,
            "file_size_formatted": format_file_size(path.stat().st_size),
            "format": path.suffix.lower().lstrip("."),
            "mime_type": mimetypes.guess_type(file_path)[0],
        }

        ext = path.suffix.lower()

        # Tentar extrair metadados específicos por tipo
        try:
            if ext in {".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp", ".tiff", ".heic"}:
                metadata.update(MediaMetadataExtractor._extract_image_metadata(file_path))
            elif ext in {".mp4", ".mov", ".avi", ".mkv", ".3gp", ".wmv", ".flv", ".webm"}:
                metadata.update(MediaMetadataExtractor._extract_video_metadata(file_path))
            elif ext in {".mp3", ".ogg", ".opus", ".aac", ".wav", ".m4a", ".flac", ".amr"}:
                metadata.update(MediaMetadataExtractor._extract_audio_metadata(file_path))
        except Exception as e:
            logger.warning(f"Erro ao extrair metadados de {file_path}: {e}")

        return metadata

    @staticmethod
    def _extract_image_metadata(file_path: str) -> Dict:
        """Extrai metadados de imagens"""
        try:
            from PIL import Image
            with Image.open(file_path) as img:
                width, height = img.size
                return {
                    "width": width,
                    "height": height,
                    "resolution": f"{width}x{height}",
                    "mode": img.mode,
                    "format": img.format or Path(file_path).suffix.lstrip(".").upper(),
                }
        except ImportError:
            logger.warning("Pillow não instalado, metadados de imagem limitados")
            return {}
        except Exception as e:
            logger.warning(f"Erro ao extrair metadados de imagem: {e}")
            return {}

    @staticmethod
    def _extract_video_metadata(file_path: str) -> Dict:
        """Extrai metadados de vídeo"""
        try:
            import subprocess
            import json

            cmd = [
                "ffprobe", "-v", "quiet",
                "-print_format", "json",
                "-show_streams", "-show_format",
                file_path
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)

            if result.returncode == 0:
                data = json.loads(result.stdout)
                meta = {}

                # Formato geral
                if "format" in data:
                    fmt = data["format"]
                    if "duration" in fmt:
                        duration = float(fmt["duration"])
                        meta["duration"] = duration
                        meta["duration_formatted"] = format_duration(duration)
                    if "bit_rate" in fmt:
                        meta["bitrate"] = int(fmt["bit_rate"])

                # Streams
                for stream in data.get("streams", []):
                    if stream.get("codec_type") == "video":
                        if "width" in stream:
                            meta["width"] = stream["width"]
                        if "height" in stream:
                            meta["height"] = stream["height"]
                        if "width" in stream and "height" in stream:
                            meta["resolution"] = f"{stream['width']}x{stream['height']}"
                        if "codec_name" in stream:
                            meta["codec"] = stream["codec_name"]
                        if "r_frame_rate" in stream:
                            fps_parts = stream["r_frame_rate"].split("/")
                            if len(fps_parts) == 2 and float(fps_parts[1]) > 0:
                                meta["fps"] = round(float(fps_parts[0]) / float(fps_parts[1]), 2)

                return meta
        except FileNotFoundError:
            logger.warning("ffprobe não encontrado, metadados de vídeo limitados")
        except Exception as e:
            logger.warning(f"Erro ao extrair metadados de vídeo: {e}")

        return {}

    @staticmethod
    def _extract_audio_metadata(file_path: str) -> Dict:
        """Extrai metadados de áudio"""
        try:
            import subprocess
            import json

            cmd = [
                "ffprobe", "-v", "quiet",
                "-print_format", "json",
                "-show_streams", "-show_format",
                file_path
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)

            if result.returncode == 0:
                data = json.loads(result.stdout)
                meta = {}

                if "format" in data:
                    fmt = data["format"]
                    if "duration" in fmt:
                        duration = float(fmt["duration"])
                        meta["duration"] = duration
                        meta["duration_formatted"] = format_duration(duration)
                    if "bit_rate" in fmt:
                        meta["bitrate"] = int(fmt["bit_rate"])

                for stream in data.get("streams", []):
                    if stream.get("codec_type") == "audio":
                        if "codec_name" in stream:
                            meta["codec"] = stream["codec_name"]
                        if "sample_rate" in stream:
                            meta["sample_rate"] = int(stream["sample_rate"])
                        if "channels" in stream:
                            meta["channels"] = stream["channels"]

                return meta
        except FileNotFoundError:
            logger.warning("ffprobe não encontrado, metadados de áudio limitados")
        except Exception as e:
            logger.warning(f"Erro ao extrair metadados de áudio: {e}")

        return {}
