"""Tests for app.services.media_metadata module."""
import os
import tempfile

from app.services.media_metadata import (
    format_file_size,
    format_duration,
    MediaMetadataExtractor,
)


# ---------- format_file_size ----------

def test_format_file_size_bytes():
    assert format_file_size(500) == "500 B"


def test_format_file_size_kilobytes():
    assert format_file_size(2048) == "2.0 KB"


def test_format_file_size_megabytes():
    # 5 MB = 5 * 1024^2
    assert format_file_size(5 * 1024 ** 2) == "5.0 MB"


def test_format_file_size_gigabytes():
    # 3 GB = 3 * 1024^3
    assert format_file_size(3 * 1024 ** 3) == "3.0 GB"


def test_format_file_size_zero():
    assert format_file_size(0) == "0 B"


# ---------- format_duration ----------

def test_format_duration_seconds_only():
    assert format_duration(45) == "45s"


def test_format_duration_minutes_and_seconds():
    # 2 minutes 30 seconds = 150s
    assert format_duration(150) == "2:30"


def test_format_duration_hours_minutes_seconds():
    # 1h 5m 9s = 3909s
    assert format_duration(3909) == "1:05:09"


def test_format_duration_exactly_60_seconds():
    assert format_duration(60) == "1:00"


# ---------- MediaMetadataExtractor.extract ----------

def test_extract_nonexistent_file():
    result = MediaMetadataExtractor.extract("/nonexistent/path/file.xyz")
    assert result == {}


def test_extract_existing_file():
    with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as f:
        f.write(b"test content")
        f.flush()
        path = f.name
    try:
        meta = MediaMetadataExtractor.extract(path)
        assert meta["file_size"] > 0
        assert meta["format"] == "txt"
        assert "file_size_formatted" in meta
    finally:
        os.unlink(path)


def test_extract_file_size_correct():
    content = b"hello world 1234567890"
    with tempfile.NamedTemporaryFile(suffix=".dat", delete=False) as f:
        f.write(content)
        f.flush()
        path = f.name
    try:
        meta = MediaMetadataExtractor.extract(path)
        assert meta["file_size"] == len(content)
        assert meta["mime_type"] is None or isinstance(meta["mime_type"], str)
    finally:
        os.unlink(path)
