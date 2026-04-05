"""
Testes de autenticacao — Login, Register, Token JWT e endpoint /me.
"""
import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from types import SimpleNamespace


class TestLogin:
    """Testes para POST /api/auth/login"""

    async def test_login_success(self, client, auth_headers):
        """Login com credenciais validas retorna token JWT."""
        fake_user = SimpleNamespace(
            username="admin", full_name="Admin", is_admin=True, is_active=True,
            hashed_password="fake"
        )
        with patch("app.routers.auth.authenticate_user", new_callable=AsyncMock, return_value=fake_user):
            response = await client.post("/api/auth/login", json={
                "username": "admin",
                "password": "TestAdmin123",
            })
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"
        assert data["username"] == "admin"
        assert data["expires_in"] > 0

    async def test_login_invalid_password(self, client):
        """Login com senha errada retorna 401."""
        with patch("app.routers.auth.authenticate_user", new_callable=AsyncMock, return_value=None):
            response = await client.post("/api/auth/login", json={
                "username": "admin",
                "password": "SenhaErrada123",
            })
        assert response.status_code == 401
        assert "Credenciais" in response.json()["detail"]

    async def test_login_invalid_username(self, client):
        """Login com usuario inexistente retorna 401."""
        with patch("app.routers.auth.authenticate_user", new_callable=AsyncMock, return_value=None):
            response = await client.post("/api/auth/login", json={
                "username": "usuario_inexistente",
                "password": "QualquerSenha1",
            })
        assert response.status_code == 401

    async def test_login_validation_error(self, client):
        """Login com dados invalidos retorna 422."""
        response = await client.post("/api/auth/login", json={
            "username": "ab",
            "password": "123456",
        })
        assert response.status_code == 422


class TestRegister:
    """Testes para POST /api/auth/register"""

    async def test_register_success(self, client):
        """Registro de novo usuario com dados validos."""
        fake_user = SimpleNamespace(
            username="novo_usuario_test", full_name="Usuario de Teste",
            is_admin=False, is_active=True
        )
        with patch("app.routers.auth.get_user_by_username", new_callable=AsyncMock, return_value=None):
            with patch("app.routers.auth.create_user", new_callable=AsyncMock, return_value=fake_user):
                response = await client.post("/api/auth/register", json={
                    "username": "novo_usuario_test",
                    "password": "MinhaSenh4Forte",
                    "full_name": "Usuario de Teste",
                })
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["username"] == "novo_usuario_test"

    async def test_register_duplicate(self, client):
        """Registro de usuario duplicado retorna 409."""
        existing_user = SimpleNamespace(username="duplicado_test")
        with patch("app.routers.auth.get_user_by_username", new_callable=AsyncMock, return_value=existing_user):
            response = await client.post("/api/auth/register", json={
                "username": "duplicado_test",
                "password": "MinhaSenh4Forte",
                "full_name": "Teste",
            })
        assert response.status_code == 409

    async def test_register_weak_password(self, client):
        """Registro com senha fraca retorna 422."""
        response = await client.post("/api/auth/register", json={
            "username": "weak_pass_user",
            "password": "senhafraca1",
            "full_name": "Teste",
        })
        assert response.status_code == 422

    async def test_register_password_no_number(self, client):
        """Registro com senha sem numero retorna 422."""
        response = await client.post("/api/auth/register", json={
            "username": "weak_pass_user2",
            "password": "SenhaSemNumero",
            "full_name": "Teste",
        })
        assert response.status_code == 422


class TestProtectedEndpoints:
    """Testes de acesso a endpoints protegidos."""

    async def test_protected_endpoint_without_token(self, app, db_engine):
        """Acesso sem token retorna 401 ou 403."""
        from app.auth import get_current_user, get_current_user_or_token
        app.dependency_overrides.pop(get_current_user, None)
        app.dependency_overrides.pop(get_current_user_or_token, None)
        import httpx
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as c:
            response = await c.get("/api/auth/me")
            assert response.status_code in (401, 403)

    async def test_protected_endpoint_with_invalid_token(self, app, db_engine):
        """Acesso com token invalido retorna 401."""
        from app.auth import get_current_user, get_current_user_or_token
        app.dependency_overrides.pop(get_current_user, None)
        app.dependency_overrides.pop(get_current_user_or_token, None)
        import httpx
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as c:
            response = await c.get("/api/auth/me", headers={
                "Authorization": "Bearer token-invalido-fake-123"
            })
            assert response.status_code == 401

    async def test_me_endpoint(self, client, auth_headers):
        """GET /api/auth/me retorna dados do usuario autenticado."""
        response = await client.get("/api/auth/me", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["username"] == "admin"
        assert "full_name" in data
        assert "is_admin" in data
