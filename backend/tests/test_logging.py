"""
Comprehensive unit tests for the logging system.

Covers:
- Tracing context (context.py)
- Redaction / masking (redaction.py)
- Error advisor (error_advisor.py)
"""
import hashlib
import re
import uuid

import pytest

from app.logging.context import (
    bind_trace_context,
    generate_request_id,
    generate_span_id,
    generate_trace_id,
    get_trace_context,
    new_span,
    parent_span_id_var,
    request_id_var,
    span_id_var,
    trace_id_var,
)
from app.logging.error_advisor import (
    ERROR_KNOWLEDGE_BASE,
    ErrorAdvisor,
    ErrorSuggestion,
    get_error_suggestion,
)
from app.logging.redaction import (
    BLACKLISTED_FIELDS,
    MASKED_FIELDS,
    RedactionFilter,
    _hash_email,
    _mask_ip,
    _mask_phone,
    _redact_cpf,
    _redact_jwt,
    _redact_key,
    redact,
    redact_processor,
)


# =====================================================================
# 1. Tracing Context
# =====================================================================


class TestGenerateTraceId:
    """Tests for generate_trace_id()."""

    def test_returns_valid_uuid(self):
        tid = generate_trace_id()
        # Should not raise
        parsed = uuid.UUID(tid, version=4)
        assert str(parsed) == tid

    def test_unique_each_call(self):
        ids = {generate_trace_id() for _ in range(100)}
        assert len(ids) == 100


class TestGenerateSpanId:
    """Tests for generate_span_id()."""

    def test_returns_16_char_hex(self):
        sid = generate_span_id()
        assert len(sid) == 16
        assert re.fullmatch(r"[0-9a-f]{16}", sid)

    def test_unique_each_call(self):
        ids = {generate_span_id() for _ in range(100)}
        assert len(ids) == 100


class TestGenerateRequestId:
    """Tests for generate_request_id()."""

    def test_returns_valid_uuid(self):
        rid = generate_request_id()
        parsed = uuid.UUID(rid, version=4)
        assert str(parsed) == rid


class TestBindTraceContext:
    """Tests for bind_trace_context()."""

    def test_sets_contextvars_correctly(self):
        ctx = bind_trace_context(
            trace_id="trace-abc",
            span_id="span-def",
            request_id="req-ghi",
            parent_span_id="parent-jkl",
        )
        assert trace_id_var.get() == "trace-abc"
        assert span_id_var.get() == "span-def"
        assert request_id_var.get() == "req-ghi"
        assert parent_span_id_var.get() == "parent-jkl"
        assert ctx["trace_id"] == "trace-abc"
        assert ctx["span_id"] == "span-def"
        assert ctx["request_id"] == "req-ghi"
        assert ctx["parent_span_id"] == "parent-jkl"

    def test_generates_ids_if_not_provided(self):
        ctx = bind_trace_context()
        # All three ids should be generated automatically
        assert ctx["trace_id"]
        assert ctx["span_id"]
        assert ctx["request_id"]
        # trace_id should be valid uuid
        uuid.UUID(ctx["trace_id"], version=4)
        # span_id should be 16-char hex
        assert len(ctx["span_id"]) == 16
        # request_id should be valid uuid
        uuid.UUID(ctx["request_id"], version=4)
        # parent_span_id defaults to None when not provided
        assert ctx["parent_span_id"] is None

    def test_partial_ids_provided(self):
        ctx = bind_trace_context(trace_id="my-trace")
        assert ctx["trace_id"] == "my-trace"
        # span_id and request_id should be auto-generated
        assert len(ctx["span_id"]) == 16
        uuid.UUID(ctx["request_id"], version=4)


class TestGetTraceContext:
    """Tests for get_trace_context()."""

    def test_returns_all_fields(self):
        bind_trace_context(
            trace_id="t1",
            span_id="s1",
            request_id="r1",
            parent_span_id="p1",
        )
        ctx = get_trace_context()
        assert ctx == {
            "trace_id": "t1",
            "span_id": "s1",
            "request_id": "r1",
            "parent_span_id": "p1",
        }

    def test_returns_defaults_when_unset(self):
        # Reset vars to defaults
        trace_id_var.set("")
        span_id_var.set("")
        request_id_var.set("")
        parent_span_id_var.set(None)

        ctx = get_trace_context()
        assert ctx["trace_id"] == ""
        assert ctx["span_id"] == ""
        assert ctx["request_id"] == ""
        assert ctx["parent_span_id"] is None


class TestNewSpan:
    """Tests for the new_span() context manager."""

    def test_creates_child_span_with_parent(self):
        bind_trace_context(trace_id="trace-1", span_id="original-span")

        with new_span("test.operation") as span_ctx:
            assert span_ctx["trace_id"] == "trace-1"
            assert span_ctx["parent_span_id"] == "original-span"
            assert span_ctx["operation"] == "test.operation"
            # child span should be different from original
            assert span_ctx["span_id"] != "original-span"
            assert len(span_ctx["span_id"]) == 16
            # contextvars should reflect the child span
            assert span_id_var.get() == span_ctx["span_id"]
            assert parent_span_id_var.get() == "original-span"

    def test_restores_original_span_on_exit(self):
        bind_trace_context(
            trace_id="trace-2",
            span_id="outer-span",
            parent_span_id="grandparent",
        )

        with new_span("inner.op"):
            # Inside span: different values
            assert span_id_var.get() != "outer-span"

        # After exiting: restored
        assert span_id_var.get() == "outer-span"
        assert parent_span_id_var.get() == "grandparent"

    def test_restores_on_exception(self):
        bind_trace_context(span_id="safe-span")
        with pytest.raises(ValueError):
            with new_span("failing.op"):
                raise ValueError("boom")
        assert span_id_var.get() == "safe-span"

    def test_nested_spans(self):
        bind_trace_context(trace_id="t", span_id="span-0")

        with new_span("level1") as s1:
            assert s1["parent_span_id"] == "span-0"
            with new_span("level2") as s2:
                assert s2["parent_span_id"] == s1["span_id"]
            # After level2 exits, back to level1
            assert span_id_var.get() == s1["span_id"]
        # After level1 exits, back to original
        assert span_id_var.get() == "span-0"


# =====================================================================
# 2. Redaction
# =====================================================================


class TestMaskPhone:
    """Tests for _mask_phone()."""

    def test_brazilian_mobile(self):
        result = _mask_phone("+5511999991234")
        assert result == "+5511****1234"

    def test_short_number(self):
        result = _mask_phone("1234")
        assert result == "[REDACTED_PHONE]"

    def test_formatted_phone(self):
        result = _mask_phone("+55 (11) 99999-1234")
        # Digits: 5511999991234 -> +5511****1234
        assert result == "+5511****1234"


class TestHashEmail:
    """Tests for _hash_email()."""

    def test_returns_hash_format(self):
        result = _hash_email("test@example.com")
        assert result.startswith("email_hash:")
        assert len(result) == len("email_hash:") + 8

    def test_deterministic(self):
        r1 = _hash_email("test@example.com")
        r2 = _hash_email("test@example.com")
        assert r1 == r2

    def test_case_insensitive(self):
        r1 = _hash_email("Test@Example.COM")
        r2 = _hash_email("test@example.com")
        assert r1 == r2

    def test_different_emails_different_hash(self):
        r1 = _hash_email("a@b.com")
        r2 = _hash_email("c@d.com")
        assert r1 != r2


class TestRedactCpf:
    """Tests for _redact_cpf()."""

    def test_masks_completely(self):
        assert _redact_cpf("123.456.789-00") == "***.***.***-**"


class TestRedactJwt:
    """Tests for _redact_jwt()."""

    def test_replaces_token(self):
        token = "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.abc123signature"
        result = _redact_jwt(token)
        assert result.startswith("jwt_hash:")
        assert token not in result


class TestRedactKey:
    """Tests for _redact_key()."""

    def test_api_key_redaction(self):
        result = _redact_key("sk-abc123def456ghi789")
        assert result == "sk-...[REDACTED]"

    def test_preserves_prefix(self):
        result = _redact_key("key-longenoughtobeakey")
        assert result.startswith("key")
        assert "[REDACTED]" in result


class TestMaskIp:
    """Tests for _mask_ip()."""

    def test_ipv4(self):
        assert _mask_ip("192.168.1.100") == "192.168.1.xxx"

    def test_ipv4_other(self):
        assert _mask_ip("10.0.0.1") == "10.0.0.xxx"

    def test_ipv6_hashed(self):
        result = _mask_ip("::1")
        assert result.startswith("ipv6_hash:")

    def test_non_ip_passthrough(self):
        assert _mask_ip("localhost") == "localhost"


class TestRedactFunction:
    """Tests for redact()."""

    def test_preserves_short_strings(self):
        assert redact("hi") == "hi"
        assert redact("abc") == "abc"
        assert redact("1234") == "1234"

    def test_preserves_non_string(self):
        assert redact(123) == 123  # type: ignore[arg-type]

    def test_redacts_phone_in_text(self):
        text = "Call me at +5511999991234 please"
        result = redact(text)
        assert "+5511999991234" not in result
        assert "****" in result

    def test_redacts_email_in_text(self):
        text = "Send to user@example.com ok"
        result = redact(text)
        assert "user@example.com" not in result
        assert "email_hash:" in result

    def test_redacts_cpf_in_text(self):
        text = "CPF: 123.456.789-00"
        result = redact(text)
        assert "123.456.789-00" not in result
        assert "***.***.***-**" in result

    def test_redacts_jwt_in_text(self):
        jwt = "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.abcdefghijklmnop"
        text = f"Token: {jwt}"
        result = redact(text)
        assert jwt not in result
        assert "jwt_hash:" in result

    def test_redacts_api_key_in_text(self):
        text = "key is sk-abcdef1234567890extra"
        result = redact(text)
        assert "sk-abcdef1234567890extra" not in result
        assert "[REDACTED]" in result

    def test_redact_url_params(self):
        url = "https://api.example.com/v1?token=secret123&name=john&password=pass123"
        result = redact(url)
        assert "secret123" not in result
        assert "pass123" not in result
        assert "token=[REDACTED]" in result
        assert "password=[REDACTED]" in result
        # non-sensitive param preserved
        assert "name=john" in result

    def test_multiple_patterns_in_one_string(self):
        text = "User user@test.com with CPF 111.222.333-44 called from +5521988887777"
        result = redact(text)
        assert "user@test.com" not in result
        assert "111.222.333-44" not in result
        assert "+5521988887777" not in result


class TestBlacklistedFields:
    """Tests for blacklisted fields being fully redacted."""

    def test_password_redacted(self):
        filt = RedactionFilter()
        assert filt.process_value("password", "supersecret") == "[REDACTED]"

    def test_api_key_redacted(self):
        filt = RedactionFilter()
        assert filt.process_value("api_key", "sk-something") == "[REDACTED]"

    def test_token_redacted(self):
        filt = RedactionFilter()
        assert filt.process_value("token", "abc123") == "[REDACTED]"

    def test_authorization_redacted(self):
        filt = RedactionFilter()
        assert filt.process_value("authorization", "Bearer xyz") == "[REDACTED]"

    def test_all_blacklisted_fields(self):
        filt = RedactionFilter()
        for field_name in BLACKLISTED_FIELDS:
            result = filt.process_value(field_name, "some_value")
            assert result == "[REDACTED]", f"Field '{field_name}' was not redacted"


class TestMaskedFields:
    """Tests for masked fields being partially visible."""

    def test_ip_masked(self):
        filt = RedactionFilter()
        result = filt.process_value("ip", "192.168.1.100")
        assert result == "192.168.1.xxx"

    def test_email_masked(self):
        filt = RedactionFilter()
        result = filt.process_value("email", "test@example.com")
        assert result.startswith("email_hash:")

    def test_phone_masked(self):
        filt = RedactionFilter()
        result = filt.process_value("phone", "+5511999991234")
        assert "****" in result

    def test_cpf_masked(self):
        filt = RedactionFilter()
        result = filt.process_value("cpf", "123.456.789-00")
        assert result == "***.***.***-**"

    def test_client_ip_masked(self):
        filt = RedactionFilter()
        result = filt.process_value("client_ip", "10.0.0.5")
        assert result == "10.0.0.xxx"


class TestRedactProcessor:
    """Tests for redact_processor (structlog processor)."""

    def test_processes_event_dict(self):
        event_dict = {
            "event": "user login",
            "password": "secret123",
            "email": "user@test.com",
            "ip": "192.168.1.50",
            "user_id": 42,
        }
        result = redact_processor(None, "info", event_dict)

        assert result["password"] == "[REDACTED]"
        assert result["email"].startswith("email_hash:")
        assert result["ip"] == "192.168.1.xxx"
        assert result["user_id"] == 42
        assert result["event"] == "user login"

    def test_preserves_underscore_fields(self):
        event_dict = {
            "_record": "some_internal",
            "_logger": "mylogger",
            "password": "secret",
        }
        result = redact_processor(None, "info", event_dict)
        assert result["_record"] == "some_internal"
        assert result["_logger"] == "mylogger"
        assert result["password"] == "[REDACTED]"

    def test_processes_nested_dict(self):
        event_dict = {
            "event": "request",
            "headers": {
                "authorization": "Bearer token123",
                "content_type": "application/json",
            },
        }
        result = redact_processor(None, "info", event_dict)
        assert result["headers"]["authorization"] == "[REDACTED]"
        assert result["headers"]["content_type"] == "application/json"


class TestRedactionFilterNestedDict:
    """Tests for RedactionFilter.process_dict with nested structures."""

    def test_nested_dict(self):
        filt = RedactionFilter()
        data = {
            "user": {
                "email": "nested@test.com",
                "password": "hidden",
                "name": "John",
            },
            "ip": "1.2.3.4",
        }
        result = filt.process_dict(data)
        assert result["user"]["email"].startswith("email_hash:")
        assert result["user"]["password"] == "[REDACTED]"
        assert result["user"]["name"] == "John"
        assert result["ip"] == "1.2.3.xxx"

    def test_list_values(self):
        filt = RedactionFilter()
        data = {
            "tokens": ["abc", "def"],
        }
        # "tokens" is not blacklisted, items are strings processed by redact()
        result = filt.process_dict(data)
        # short strings should pass through
        assert result["tokens"] == ["abc", "def"]

    def test_deeply_nested(self):
        filt = RedactionFilter()
        data = {
            "level1": {
                "level2": {
                    "secret": "should_be_redacted",
                }
            }
        }
        result = filt.process_dict(data)
        assert result["level1"]["level2"]["secret"] == "[REDACTED]"


# =====================================================================
# 3. Error Advisor
# =====================================================================


class TestErrorAdvisorGetByCode:
    """Tests for ErrorAdvisor.get_by_code()."""

    def test_returns_correct_suggestion(self):
        advisor = ErrorAdvisor()
        suggestion = advisor.get_by_code("AI_TIMEOUT_001")
        assert suggestion is not None
        assert suggestion.code == "AI_TIMEOUT_001"
        assert suggestion.severity == "high"
        assert "timeout" in suggestion.suggestion.lower() or "timeout" in suggestion.suggestion

    def test_returns_none_for_unknown_code(self):
        advisor = ErrorAdvisor()
        assert advisor.get_by_code("DOES_NOT_EXIST") is None

    def test_all_codes_in_knowledge_base(self):
        advisor = ErrorAdvisor()
        for code in ERROR_KNOWLEDGE_BASE:
            suggestion = advisor.get_by_code(code)
            assert suggestion is not None
            assert suggestion.code == code


class TestErrorAdvisorGetByException:
    """Tests for ErrorAdvisor.get_by_exception()."""

    def test_timeout_returns_ai_timeout(self):
        advisor = ErrorAdvisor()
        exc = TimeoutError("request timed out")
        suggestion = advisor.get_by_exception(exc)
        assert suggestion is not None
        assert suggestion.code == "AI_TIMEOUT_001"

    def test_connection_error_returns_redis_conn(self):
        advisor = ErrorAdvisor()
        exc = ConnectionError("connection refused")
        suggestion = advisor.get_by_exception(exc)
        assert suggestion is not None
        # ConnectionError maps to REDIS_CONN_001 in _exception_map
        assert suggestion.code == "REDIS_CONN_001"

    def test_connection_refused_error_returns_db_conn(self):
        advisor = ErrorAdvisor()
        exc = ConnectionRefusedError("refused")
        suggestion = advisor.get_by_exception(exc)
        assert suggestion is not None
        assert suggestion.code == "DB_CONN_001"

    def test_bad_zip_by_message(self):
        """BadZipFile class may not be importable; test via message matching."""
        advisor = ErrorAdvisor()
        # Simulate unknown exception with "bad zip" in message
        exc = Exception("bad zip file encountered")
        suggestion = advisor.get_by_exception(exc)
        assert suggestion is not None
        assert suggestion.code == "PARSE_ZIP_002"

    def test_unicode_decode_error(self):
        advisor = ErrorAdvisor()
        exc = UnicodeDecodeError("utf-8", b"", 0, 1, "invalid")
        suggestion = advisor.get_by_exception(exc)
        assert suggestion is not None
        assert suggestion.code == "PARSE_ENCODING_003"

    def test_permission_error(self):
        advisor = ErrorAdvisor()
        exc = PermissionError("access denied")
        suggestion = advisor.get_by_exception(exc)
        assert suggestion is not None
        assert suggestion.code == "AUTH_FORBIDDEN_002"

    def test_file_not_found_error(self):
        advisor = ErrorAdvisor()
        exc = FileNotFoundError("no such file")
        suggestion = advisor.get_by_exception(exc)
        assert suggestion is not None
        assert suggestion.code == "MEDIA_CORRUPT_001"


class TestErrorAdvisorMatchByMessage:
    """Tests for _match_by_message pattern matching."""

    def test_rate_limit_pattern(self):
        advisor = ErrorAdvisor()
        exc = Exception("API rate limit exceeded")
        suggestion = advisor.get_by_exception(exc)
        assert suggestion is not None
        assert suggestion.code == "AI_RATE_LIMIT_002"

    def test_429_pattern(self):
        advisor = ErrorAdvisor()
        exc = Exception("HTTP 429 Too Many Requests")
        suggestion = advisor.get_by_exception(exc)
        assert suggestion is not None
        assert suggestion.code == "AI_RATE_LIMIT_002"

    def test_disk_pattern(self):
        advisor = ErrorAdvisor()
        exc = Exception("disk full error")
        suggestion = advisor.get_by_exception(exc)
        assert suggestion is not None
        assert suggestion.code == "INFRA_DISK_001"

    def test_memory_pattern(self):
        advisor = ErrorAdvisor()
        exc = Exception("out of memory allocation failed")
        suggestion = advisor.get_by_exception(exc)
        assert suggestion is not None
        assert suggestion.code == "INFRA_MEMORY_002"

    def test_overloaded_pattern(self):
        advisor = ErrorAdvisor()
        exc = Exception("service overloaded 529")
        suggestion = advisor.get_by_exception(exc)
        assert suggestion is not None
        assert suggestion.code == "AI_OVERLOAD_004"

    def test_ffmpeg_pattern(self):
        advisor = ErrorAdvisor()
        exc = Exception("ffmpeg failed with exit code 1")
        suggestion = advisor.get_by_exception(exc)
        assert suggestion is not None
        assert suggestion.code == "MEDIA_FFMPEG_003"


class TestUnknownError:
    """Tests for unknown error fallback."""

    def test_returns_unknown_000(self):
        advisor = ErrorAdvisor()
        result = advisor.get_suggestion_dict(exc=Exception("something completely unique xyz"))
        assert result["error_code"] == "UNKNOWN_000"
        assert result["severity"] == "medium"
        assert result["auto_action"] is None


class TestGetSuggestionDict:
    """Tests for get_suggestion_dict() format."""

    def test_returns_dict_with_all_expected_keys(self):
        advisor = ErrorAdvisor()
        result = advisor.get_suggestion_dict(error_code="AI_TIMEOUT_001")
        expected_keys = {"error_code", "suggestion", "severity", "runbook", "auto_action"}
        assert set(result.keys()) == expected_keys

    def test_by_code(self):
        advisor = ErrorAdvisor()
        result = advisor.get_suggestion_dict(error_code="DB_CONN_001")
        assert result["error_code"] == "DB_CONN_001"
        assert result["severity"] == "high"

    def test_by_exception(self):
        advisor = ErrorAdvisor()
        result = advisor.get_suggestion_dict(exc=TimeoutError("oops"))
        assert result["error_code"] == "AI_TIMEOUT_001"

    def test_unknown_returns_expected_keys(self):
        result = get_error_suggestion(exc=Exception("never seen before xyz abc 999"))
        expected_keys = {"error_code", "suggestion", "severity", "runbook", "auto_action"}
        assert set(result.keys()) == expected_keys
        assert result["error_code"] == "UNKNOWN_000"


class TestAllErrorCodesHaveSuggestions:
    """Validate the ERROR_KNOWLEDGE_BASE integrity."""

    def test_all_entries_are_error_suggestions(self):
        for code, suggestion in ERROR_KNOWLEDGE_BASE.items():
            assert isinstance(suggestion, ErrorSuggestion), f"{code} is not ErrorSuggestion"

    def test_all_codes_match_keys(self):
        for code, suggestion in ERROR_KNOWLEDGE_BASE.items():
            assert suggestion.code == code, f"Key {code} != suggestion.code {suggestion.code}"

    def test_all_have_required_fields(self):
        for code, suggestion in ERROR_KNOWLEDGE_BASE.items():
            assert suggestion.suggestion, f"{code} missing suggestion text"
            assert suggestion.severity in (
                "critical", "high", "medium", "low"
            ), f"{code} has invalid severity: {suggestion.severity}"

    def test_knowledge_base_not_empty(self):
        assert len(ERROR_KNOWLEDGE_BASE) > 0


class TestGetErrorSuggestionConvenience:
    """Tests for the module-level get_error_suggestion() function."""

    def test_by_code(self):
        result = get_error_suggestion(error_code="REDIS_CONN_001")
        assert result["error_code"] == "REDIS_CONN_001"

    def test_by_exception(self):
        result = get_error_suggestion(exc=TimeoutError("timeout"))
        assert result["error_code"] == "AI_TIMEOUT_001"

    def test_no_args_returns_unknown(self):
        result = get_error_suggestion()
        assert result["error_code"] == "UNKNOWN_000"
