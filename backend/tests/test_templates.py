"""
Testes para endpoints de templates de análise.
"""
import pytest


class TestTemplates:
    """Testes para GET /api/templates."""

    def test_list_templates(self, client, auth_headers):
        """GET /api/templates retorna lista de templates."""
        response = client.get("/api/templates", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert "templates" in data
        assert isinstance(data["templates"], list)
        assert len(data["templates"]) > 0
        # Cada template deve ter id, name, description, prompts
        for t in data["templates"]:
            assert "id" in t
            assert "name" in t
            assert "description" in t
            assert "prompts" in t

    def test_get_template(self, client, auth_headers):
        """GET /api/templates/{id} retorna detalhes do template."""
        # Primeiro, listar templates para pegar um ID válido
        list_response = client.get("/api/templates", headers=auth_headers)
        templates = list_response.json()["templates"]
        assert len(templates) > 0

        template_id = templates[0]["id"]
        response = client.get(f"/api/templates/{template_id}", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == template_id
        assert "name" in data
        assert "prompts" in data
        assert isinstance(data["prompts"], dict)

    def test_get_template_not_found(self, client, auth_headers):
        """GET /api/templates/xxx retorna 404."""
        response = client.get("/api/templates/template_inexistente_xyz", headers=auth_headers)
        assert response.status_code == 404

    def test_list_templates_unauthorized(self, app):
        """GET /api/templates sem autenticação retorna erro."""
        from app.auth import get_current_user
        app.dependency_overrides.pop(get_current_user, None)
        from fastapi.testclient import TestClient
        with TestClient(app, raise_server_exceptions=False) as c:
            response = c.get("/api/templates")
            assert response.status_code in (401, 403)  # HTTPBearer returns 401 or 403
