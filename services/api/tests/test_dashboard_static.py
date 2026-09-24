from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import app.main as main_module
from app.core.config import Settings


def test_built_dashboard_can_be_served_without_hiding_health_routes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    dashboard = tmp_path / "dashboard"
    dashboard.mkdir()
    (dashboard / "index.html").write_text(
        "<!doctype html><html><body>CODEFLUX DEPLOYMENT</body></html>",
        encoding="utf-8",
    )

    settings = Settings(
        _env_file=None,
        app_env="test",
        dashboard_root=dashboard,
        database_url="sqlite+pysqlite:///:memory:",
    )
    monkeypatch.setattr(main_module, "get_settings", lambda: settings)

    app = main_module.create_app()
    with TestClient(app) as client:
        root = client.get("/")
        health = client.get("/health")

    assert root.status_code == 200
    assert "CODEFLUX DEPLOYMENT" in root.text
    assert health.status_code == 200
    assert health.json() == {"status": "ok"}


def test_configured_dashboard_root_requires_index(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = Settings(
        _env_file=None,
        app_env="test",
        dashboard_root=tmp_path / "missing-dashboard",
        database_url="sqlite+pysqlite:///:memory:",
    )
    monkeypatch.setattr(main_module, "get_settings", lambda: settings)

    with pytest.raises(RuntimeError, match="index.html is missing"):
        main_module.create_app()


@pytest.mark.parametrize(
    ("raw_url", "expected"),
    [
        (
            "postgres://user:password@postgres.railway.internal:5432/codeflux",
            "postgresql+psycopg://user:password@postgres.railway.internal:5432/codeflux",
        ),
        (
            "postgresql://user:password@postgres.railway.internal:5432/codeflux",
            "postgresql+psycopg://user:password@postgres.railway.internal:5432/codeflux",
        ),
        (
            "postgresql+psycopg://user:password@postgres.railway.internal:5432/codeflux",
            "postgresql+psycopg://user:password@postgres.railway.internal:5432/codeflux",
        ),
    ],
)
def test_standard_postgres_urls_use_installed_psycopg_driver(
    raw_url: str,
    expected: str,
) -> None:
    settings = Settings(
        _env_file=None,
        app_env="test",
        database_url=raw_url,
    )

    assert settings.database_url == expected
