"""
Testes de autenticação — Login, Register, Token JWT e endpoint /me.
"""
import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from types import SimpleNamespace


class TestLogin:
    """Testes para POST /api/auth/login"""

    def test_login_success(self, client, auth_headers):
        """Login com credenciais válidas retorna token JWT."""
        fake_user = SimpleNamespace(
            username="admin", full_name="Admin", is_admin=True, is_active=True,
            hashed_password="fake"
        )
        with patch("app.routers.auth.AsyncSessionLocal") as mock_session_cls:
            mock_session = AsyncMock()
            mock_session.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session.__aexit__ = AsyncMock(return_value=False)
            mock_session_cls.return_value = mock_session
            with patch("app.routers.auth.authenticate_user", new_callable=AsyncMock, return_value=fake_user):
                response = client.post("/api/auth/login", json={
                    "username": "admin",
                    "password": "TestAdmin123",
                })
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"
        assert data["username"] == "admin"
        assert data["expires_in"] > 0

    def test_login_invalid_password(self, client):
        """Login com senha errada retorna 401."""
        with patch("app.routers.auth.AsyncSessionLocal") as mock_session_cls:
            mock_session = AsyncMock()
            mock_session.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session.__aexit__ = AsyncMock(return_value=False)
            mock_session_cls.return_value = mock_session
            with patch("app.routers.auth.authenticate_user", new_callable=AsyncMock, return_value=None):
                response = client.post("/api/auth/login", json={
                    "username": "admin",
                    "password": "SenhaErrada123",
                })
        assert response.status_code == 401
        assert "Credenciais inv\u00e1lidas" in response.json()["detail"]

    def test_login_invalid_username(self, client):
        """Login com usu\u00e1rio inexistente retorna 401."""
        with patch("app.routers.auth.AsyncSessionLocal") as mock_session_cls:
            mock_session = AsyncMock()
            mock_session.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session.__aexit__ = AsyncMock(return_value=False)
            mock_session_cls.return_value = mock_session
            with patch("app.routers.auth.authenticate_user", new_callable=AsyncMock, return_value=None):
                response = client.post("/api/auth/login", json={
                    "username": "usuario_inexistente",
                    "password": "QualquerSenha1",
                })
        assert response.status_code == 401

    def test_login_validation_error(self, client):
        """Login com dados inv\u00e1lidos retorna 422."""
        # Username muito curto
        response = client.post("/api/auth/login", json={
            "username": "ab",
            "password": "123456",
        })
        assert response.status_code == 422


class TestRegister:
    """Testes para POST /api/auth/register"""

    def _mock_async_session(self):
        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)
        mock_session.commit = AsyncMock()
        return mock_session

    def test_register_success(self, client):
        """Registro de novo usu\u00e1rio com dados v\u00e1lidos."""
        fake_user = SimpleNamespace(
            username="novo_usuario_test", full_name="Usu\u00e1rio de Teste",
            is_admin=False, is_active=True
        )
        mock_session = self._mock_async_session()
        with patch("app.routers.auth.AsyncSessionLocal", return_value=mock_session):
            with patch("app.routers.auth.get_user_by_username", new_callable=AsyncMock, return_value=None):
                with patch("app.routers.auth.create_user", new_callable=AsyncMock, return_value=fake_user):
                    response = client.post("/api/auth/register", json={
                        "username": "novo_usuario_test",
                        "password": "MinhaSenh4Forte",
                        "full_name": "Usu\u00e1rio de Teste",
                    })
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["username"] == "novo_usuario_test"

    def test_register_duplicate(self, client):
        """Registro de usu\u00e1rio duplicado retorna 409."""
        existing_user = SimpleNamespace(username="duplicado_test")
        mock_session = self._mock_async_session()
        with patch("app.routers.auth.AsyncSessionLocal", return_value=mock_session):
            with patch("app.routers.auth.get_user_by_username", new_callable=AsyncMock, return_value=existing_user):
                response = client.post("/api/auth/register", json={
                    "username": "duplicado_test",
                    "password": "MinhaSenh4Forte",
                    "full_name": "Teste",
                })
        assert response.status_code == 409
        assert "j\u00e1 existe" in response.json()["detail"]

    def test_register_weak_password(self, client):
        """Registro com senha fraca retorna 422."""
        # Sem letra mai\u00fascula
        response = client.post("/api/auth/register", json={
            "username": "weak_pass_user",
            "password": "senhafraca1",
            "full_name": "Teste",
        })
        assert response.status_code == 422

    def test_register_password_no_number(self, client):
        """Registro com senha sem n\u00famero retorna 422."""
        response = client.post("/api/auth/register", json={
            "username": "weak_pass_user2",
            "password": "SenhaSemNumero",
            "full_name": "Teste",
        })
        assert response.status_code == 422


class TestProtectedEndpoints:
    """Testes de acesso a endpoints protegidos."""

    def test_protected_endpoint_without_token(self, app, db_engine):
        """Acesso sem token retorna 401 ou 403."""
        from app.auth import get_current_user
        app.dependency_overrides.pop(get_current_user, None)
        from fastapi.testclient import TestClient
        with TestClient(app, raise_server_exceptions=False) as c:
            response = c.get("/api/auth/me")
            assert response.status_code in (401, 403)

    def test_protected_endpoint_with_invalid_token(self, app, db_engine):
        """Acesso com token inv\u00e1lido retorna 401."""
        from app.auth import get_current_user
        app.dependency_overrides.pop(get_current_user, None)
        from fastapi.testclient import TestClient
        with TestClient(app, raise_server_exceptions=False) as c:
            response = c.get("/api/auth/me", headers={
                "Authorization": "Bearer token-invalido-fake-123"
            })
            assert response.status_code == 401

    def test_me_endpoint(self, client, auth_headers):
        """GET /api/auth/me retorna dados do usu\u00e1rio autenticado."""
        response = client.get("/api/auth/me", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["username"] == "admin"
        assert "full_name" in data
        assert "is_admin" in data
