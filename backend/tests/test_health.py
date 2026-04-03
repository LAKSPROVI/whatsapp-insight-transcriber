"""
Testes de health check.
"""
import pytest


class TestHealthCheck:
    """Testes para endpoints de health check."""

    def test_health_basic(self, client):
        """GET /api/health retorna status healthy."""
        response = client.get("/api/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "app" in data
        assert "version" in data
        assert "model" in data
        assert "max_agents" in data

    def test_health_detailed(self, client):
        """GET /api/health/detailed retorna verificações detalhadas."""
        response = client.get("/api/health/detailed")
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert data["status"] in ("healthy", "degraded")
        assert "checks" in data
        checks = data["checks"]
        assert "database" in checks
        assert "disk" in checks
        assert "config" in checks
        assert "storage" in checks
        assert "timestamp" in data
        assert "python_version" in data

    def test_health_basic_response_shape(self, client):
        """Verifica a estrutura completa do health check básico."""
        response = client.get("/api/health")
        data = response.json()
        expected_keys = {"status", "app", "version", "model", "max_agents", "cache_connected"}
        assert expected_keys.issubset(set(data.keys()))

    def test_cache_stats(self, client):
        """GET /api/cache/stats retorna estatísticas."""
        response = client.get("/api/cache/stats")
        assert response.status_code == 200
