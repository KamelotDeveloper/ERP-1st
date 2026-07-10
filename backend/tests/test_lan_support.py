"""
Tests for Multi-PC LAN support (PR #1 — Backend).

Covers:
- Task 1.1 / 4.1: WAL pragmas applied on SQLite connect
- Task 1.2 / 4.2: Health endpoint returns LAN IP info
- Task 1.3 / 4.3: CORS allows wildcard origin
"""

import os
import sqlite3
import tempfile
from unittest.mock import patch

import pytest
from sqlalchemy import create_engine, event, text


# ---------------------------------------------------------------------------
# Task 4.1 — WAL pragmas on connect
# ---------------------------------------------------------------------------

class TestWalPragmas:
    """Verify that SQLite connections get WAL, busy_timeout, and synchronous pragmas."""

    def _make_engine_with_listener(self, listen_fn):
        """Create a file-based SQLite engine and register a connect listener.

        In-memory SQLite databases cannot use WAL mode, so we use a temp file.
        """
        tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        tmp.close()
        self._db_path = tmp.name
        eng = create_engine(f"sqlite:///{tmp.name}", connect_args={"check_same_thread": False})
        event.listen(eng, "connect", listen_fn)
        self._engine = eng
        return eng

    def teardown_method(self):
        """Clean up temp database files."""
        # Dispose the engine to release file locks before unlinking
        if hasattr(self, "_engine"):
            self._engine.dispose()
        if not hasattr(self, "_db_path"):
            return
        for ext in ("", "-wal", "-shm"):
            path = self._db_path + ext
            if os.path.exists(path):
                try:
                    os.unlink(path)
                except PermissionError:
                    pass  # Windows may still hold lock briefly

    def test_journal_mode_is_wal(self):
        """PRAGMA journal_mode must be WAL after connect."""
        from database import apply_sqlite_pragmas

        eng = self._make_engine_with_listener(apply_sqlite_pragmas)
        with eng.connect() as conn:
            result = conn.execute(text("PRAGMA journal_mode"))
            assert result.scalar() == "wal"

    def test_busy_timeout_is_5000(self):
        """PRAGMA busy_timeout must be 5000 ms."""
        from database import apply_sqlite_pragmas

        eng = self._make_engine_with_listener(apply_sqlite_pragmas)
        with eng.connect() as conn:
            result = conn.execute(text("PRAGMA busy_timeout"))
            assert result.scalar() == 5000

    def test_synchronous_is_normal(self):
        """PRAGMA synchronous must be NORMAL (1)."""
        from database import apply_sqlite_pragmas

        eng = self._make_engine_with_listener(apply_sqlite_pragmas)
        with eng.connect() as conn:
            result = conn.execute(text("PRAGMA synchronous"))
            # NORMAL = 1 in SQLite
            assert result.scalar() == 1

    def test_pragmas_applied_via_raw_dbapi(self):
        """Listener must work with raw DB-API connections (not just SQLAlchemy)."""
        from database import apply_sqlite_pragmas

        tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        tmp.close()
        try:
            conn = sqlite3.connect(tmp.name)
            apply_sqlite_pragmas(conn, None)

            cursor = conn.execute("PRAGMA journal_mode")
            assert cursor.fetchone()[0] == "wal"

            cursor = conn.execute("PRAGMA busy_timeout")
            assert cursor.fetchone()[0] == 5000

            cursor = conn.execute("PRAGMA synchronous")
            assert cursor.fetchone()[0] == 1

            conn.close()
        finally:
            for ext in ("", "-wal", "-shm"):
                path = tmp.name + ext
                if os.path.exists(path):
                    os.unlink(path)


# ---------------------------------------------------------------------------
# Task 4.2 — Enhanced health endpoint
# ---------------------------------------------------------------------------

class TestHealthEndpoint:
    """GET /health must return LAN IP info alongside status and version."""

    @pytest.fixture(autouse=True)
    def _client(self):
        """Create a TestClient for the FastAPI app."""
        from fastapi.testclient import TestClient
        from main import app

        self.client = TestClient(app)

    def test_health_returns_status_ok(self):
        resp = self.client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"

    def test_health_returns_version(self):
        resp = self.client.get("/health")
        data = resp.json()
        assert "version" in data
        assert isinstance(data["version"], str)

    def test_health_returns_lan_ip(self):
        resp = self.client.get("/health")
        data = resp.json()
        assert "lan_ip" in data
        assert isinstance(data["lan_ip"], str)
        # Must be a valid-looking IP (not empty, not None)
        assert len(data["lan_ip"]) > 0

    def test_health_returns_port(self):
        resp = self.client.get("/health")
        data = resp.json()
        assert "port" in data
        assert data["port"] == 8000

    def test_health_returns_sharing_url(self):
        resp = self.client.get("/health")
        data = resp.json()
        assert "sharing_url" in data
        assert data["sharing_url"].startswith("http://")
        assert ":8000" in data["sharing_url"]

    def test_health_returns_db_field(self):
        resp = self.client.get("/health")
        data = resp.json()
        assert "db" in data
        assert data["db"] in ("wal", "delete")


# ---------------------------------------------------------------------------
# Task 4.3 — CORS wildcard
# ---------------------------------------------------------------------------

class TestCorsWildcard:
    """CORS must allow any origin with Access-Control-Allow-Origin: *."""

    @pytest.fixture(autouse=True)
    def _client(self):
        from fastapi.testclient import TestClient
        from main import app

        self.client = TestClient(app)

    def test_cors_allows_arbitrary_origin(self):
        """Preflight from any LAN origin must return wildcard ACAO header."""
        resp = self.client.options(
            "/health",
            headers={
                "Origin": "http://192.168.1.99:5173",
                "Access-Control-Request-Method": "GET",
            },
        )
        # CORS middleware should respond with 200 and wildcard header
        assert resp.status_code in (200, 405)
        acao = resp.headers.get("access-control-allow-origin", "")
        assert acao == "*"

    def test_cors_allows_localhost_origin(self):
        """Even localhost origin gets wildcard (not a specific list)."""
        resp = self.client.options(
            "/health",
            headers={
                "Origin": "http://127.0.0.1:5173",
                "Access-Control-Request-Method": "GET",
            },
        )
        acao = resp.headers.get("access-control-allow-origin", "")
        assert acao == "*"

    def test_cors_get_includes_acao_header(self):
        """A regular GET response must include ACAO: * header."""
        resp = self.client.get("/health", headers={"Origin": "http://10.0.0.1:3000"})
        acao = resp.headers.get("access-control-allow-origin", "")
        assert acao == "*"
