import pytest

from kirtap.config import ConfigurationError, load_settings


def environment(**overrides: str) -> dict[str, str]:
    values = {
        "DISCORD_TOKEN": "token",
        "ENVIRONMENT": "development",
    }
    values.update(overrides)
    return values


def test_loads_defaults() -> None:
    settings = load_settings(environment())

    assert settings.command_prefix == "!"
    assert settings.log_level == "INFO"
    assert settings.crous_restaurant_id == 1392
    assert settings.crous_channel_id is None
    assert settings.ade_ical_url is None
    assert settings.presence_carrier_role_id is None
    assert settings.presence_access_role_id is None
    assert settings.presence_database_path == "data/presence.db"


def test_requires_discord_token() -> None:
    with pytest.raises(ConfigurationError, match="DISCORD_TOKEN"):
        load_settings({"ENVIRONMENT": "development"})


@pytest.mark.parametrize(
    "name, value",
    [
        ("OWNER_ID", "none"),
        ("CROUS_CHANNEL_ID", "0"),
        ("PRESENCE_CARRIER_ROLE_ID", "0"),
        ("PRESENCE_ACCESS_ROLE_ID", "-1"),
    ],
)
def test_rejects_invalid_optional_ids(name: str, value: str) -> None:
    with pytest.raises(ConfigurationError, match=name):
        load_settings(environment(**{name: value}))


@pytest.mark.parametrize(
    "name, value",
    [
        ("COMMAND_PREFIX", " "),
        ("LOG_LEVEL", "VERBOSE"),
        ("ENVIRONMENT", "staging"),
        ("ADE_ICAL_URL", "ftp://ade.example/planning"),
        ("ADE_ICAL_URL", "https://"),
    ],
)
def test_rejects_invalid_settings(name: str, value: str) -> None:
    with pytest.raises(ConfigurationError, match=name):
        load_settings(environment(**{name: value}))
