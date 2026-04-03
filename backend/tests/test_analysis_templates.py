"""
Testes unitários para o módulo analysis_templates.
Não requer banco de dados — testes puros de lógica.
"""
import pytest

from app.services.analysis_templates import (
    get_all_templates,
    get_template,
    get_template_prompts,
)

KNOWN_IDS = ["juridico", "comercial", "familiar", "rh", "geral"]


# ═══════════════════════════════════════════════════════════════════════════════
# 1. get_all_templates
# ═══════════════════════════════════════════════════════════════════════════════

class TestGetAllTemplates:

    def test_returns_non_empty_list(self):
        templates = get_all_templates()
        assert isinstance(templates, list)
        assert len(templates) > 0

    def test_each_template_has_required_keys(self):
        for t in get_all_templates():
            assert "id" in t
            assert "name" in t
            assert "description" in t
            assert "prompts" in t
            assert isinstance(t["prompts"], dict)

    @pytest.mark.parametrize("expected_id", KNOWN_IDS)
    def test_known_template_exists(self, expected_id):
        ids = [t["id"] for t in get_all_templates()]
        assert expected_id in ids


# ═══════════════════════════════════════════════════════════════════════════════
# 2. get_template
# ═══════════════════════════════════════════════════════════════════════════════

class TestGetTemplate:

    def test_returns_template_by_valid_id(self):
        result = get_template("juridico")
        assert result is not None
        assert result["id"] == "juridico"

    def test_returns_none_for_invalid_id(self):
        assert get_template("nonexistent_template_xyz") is None

    def test_returned_template_has_correct_structure(self):
        result = get_template("comercial")
        assert result is not None
        assert isinstance(result["name"], str)
        assert isinstance(result["description"], str)
        assert isinstance(result["prompts"], dict)
        # comercial template should have specific prompt keys
        assert "summary" in result["prompts"]


# ═══════════════════════════════════════════════════════════════════════════════
# 3. get_template_prompts
# ═══════════════════════════════════════════════════════════════════════════════

class TestGetTemplatePrompts:

    def test_returns_all_prompts_for_valid_template(self):
        prompts = get_template_prompts("geral")
        assert prompts is not None
        assert isinstance(prompts, dict)
        assert len(prompts) > 0
        # all values should be non-empty strings
        for key, val in prompts.items():
            assert isinstance(val, str)
            assert len(val) > 0

    def test_returns_filtered_prompts_when_keys_provided(self):
        prompts = get_template_prompts("geral", prompt_keys=["summary", "timeline"])
        assert prompts is not None
        assert set(prompts.keys()) == {"summary", "timeline"}

    def test_returns_none_for_invalid_template_id(self):
        assert get_template_prompts("does_not_exist") is None

    def test_empty_prompt_keys_returns_all_prompts(self):
        all_prompts = get_template_prompts("geral")
        empty_keys = get_template_prompts("geral", prompt_keys=[])
        # Empty list means no filter applied — returns all
        assert empty_keys == all_prompts
