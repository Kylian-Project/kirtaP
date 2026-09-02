# kirtaP

Bot Discord en Python pour les commandes générales, la modération, les menus CROUS et la commande `caillou`.

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

Les commandes prefixe nécessitent l'intent privilégié **Message Content**, à activer aussi dans le portail développeur Discord. La commande `clear` requiert `Gérer les messages` pour l'utilisateur et le bot ; `caillou` requiert les droits administrateur.

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
