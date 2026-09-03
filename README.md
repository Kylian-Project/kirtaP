# kirtaP

Bot Discord en Python des Master kirtaP ?

## Installation

Python 3.13 et [uv](https://docs.astral.sh/uv/) sont requis.

```bash
cp .env.example .env
uv sync
uv run kirtap
```

## Configuration

| Variable | Requise | Description |
| --- | --- | --- |
| `DISCORD_TOKEN` | Oui | Token du bot Discord. |
| `OWNER_ID` | Non | Identifiant Discord du propriétaire. |
| `COMMAND_PREFIX` | Non | Préfixe des commandes, `!` par défaut. |
| `LOG_LEVEL` | Non | `DEBUG`, `INFO`, `WARNING`, `ERROR` ou `CRITICAL`. |
| `ENVIRONMENT` | Non | `development` ou `production`. |
| `STATUS_MESSAGE` | Non | Statut affiché par le bot. |
| `CROUS_RESTAURANT_ID` | Non | Restaurant CROUS, `1392` par défaut. |
| `CROUS_CHANNEL_ID` | Non | Canal de publication automatique du menu à 08:00 Europe/Paris. |

## Menus CROUS

Les menus sont envoyés sous forme d'image directement générée par l'API CROUStillant. Les commandes disponibles sont `/menu [date]` et `/menu_semaine`.

## Développement

```bash
uv run ruff format .
uv run ruff check .
uv run pytest
```

## Docker

```bash
docker build -t kirtap .
docker run --rm --env-file .env kirtap
```
