import pytest
from pydantic import ValidationError

from app.core.config import Settings


def test_settings_accept_expected_environment_and_hide_credentials() -> None:
    settings = Settings(
        _env_file=None,
        environment="development",
        database_url="postgresql://user:secret@localhost/db",
        redis_url=None,
    )

    assert settings.environment == "development"
    assert settings.database_url is not None
    assert "secret" not in repr(settings)


def test_settings_reject_unknown_environment() -> None:
    with pytest.raises(ValidationError):
        Settings(_env_file=None, environment="staging", database_url=None, redis_url=None)
