import os
from collections.abc import Mapping
from dataclasses import dataclass

from dotenv import load_dotenv


class ConfigurationError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class Settings:
    discord_token: str
    owner_id: int | None
    command_prefix: str
    log_level: str
    environment: str
    status_message: str
    crous_restaurant_id: int
    crous_channel_id: int | None
    presence_carrier_role_id: int | None
    presence_access_role_id: int | None
    presence_database_path: str


def load_settings(values: Mapping[str, str] | None = None) -> Settings:
    if values is None:
        load_dotenv()
        values = os.environ

    token = _required(values, "DISCORD_TOKEN")
    prefix = values.get("COMMAND_PREFIX", "!").strip()
    if not prefix:
        raise ConfigurationError("COMMAND_PREFIX ne peut pas être vide.")

    log_level = values.get("LOG_LEVEL", "INFO").upper()
    if log_level not in {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}:
        raise ConfigurationError("LOG_LEVEL doit être DEBUG, INFO, WARNING, ERROR ou CRITICAL.")

    environment = values.get("ENVIRONMENT", "development").lower()
    if environment not in {"development", "production"}:
        raise ConfigurationError("ENVIRONMENT doit être development ou production.")

    status_message = values.get("STATUS_MESSAGE", f"En développement | {prefix}help").strip()
    if not status_message:
        raise ConfigurationError("STATUS_MESSAGE ne peut pas être vide.")

    presence_database_path = values.get("PRESENCE_DATABASE_PATH", "data/presence.db").strip()
    if not presence_database_path:
        raise ConfigurationError("PRESENCE_DATABASE_PATH ne peut pas être vide.")

    return Settings(
        discord_token=token,
        owner_id=_optional_id(values, "OWNER_ID"),
        command_prefix=prefix,
        log_level=log_level,
        environment=environment,
        status_message=status_message,
        crous_restaurant_id=_required_id(values, "CROUS_RESTAURANT_ID", default="1392"),
        crous_channel_id=_optional_id(values, "CROUS_CHANNEL_ID"),
        presence_carrier_role_id=_optional_id(values, "PRESENCE_CARRIER_ROLE_ID"),
        presence_access_role_id=_optional_id(values, "PRESENCE_ACCESS_ROLE_ID"),
        presence_database_path=presence_database_path,
    )


def _required(values: Mapping[str, str], name: str) -> str:
    value = values.get(name, "").strip()
    if not value:
        raise ConfigurationError(f"{name} est requis.")
    return value


def _required_id(values: Mapping[str, str], name: str, *, default: str) -> int:
    return _parse_id(name, values.get(name, default))


def _optional_id(values: Mapping[str, str], name: str) -> int | None:
    value = values.get(name, "").strip()
    return _parse_id(name, value) if value else None


def _parse_id(name: str, value: str) -> int:
    try:
        identifier = int(value)
    except ValueError as error:
        raise ConfigurationError(f"{name} doit être un entier positif.") from error

    if identifier <= 0:
        raise ConfigurationError(f"{name} doit être un entier positif.")
    return identifier
