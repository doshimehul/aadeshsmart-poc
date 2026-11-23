from app.core.config import Settings


def test_settings_parse_database_url_and_cors_origins():
    settings = Settings(
        database_url="postgresql+psycopg://user:pass@localhost:5432/appdb",
        cors_origins="http://localhost:3000, http://127.0.0.1:3000",
    )
    assert str(settings.database_url) == "postgresql+psycopg://user:pass@localhost:5432/appdb"
    assert settings.cors_origins == ["http://localhost:3000", "http://127.0.0.1:3000"]
