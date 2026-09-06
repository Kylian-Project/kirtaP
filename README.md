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
| `PRESENCE_CHANNEL_ID` | Oui pour les fiches de présence | Salon textuel des notifications. |
| `PRESENCE_CARRIER_ROLE_ID` | Oui pour les fiches de présence | Rôle attribué au porteur actuel. |
| `PRESENCE_ACCESS_ROLE_ID` | Oui pour les fiches de présence | Rôle autorisé à gérer les rotations. |
| `PRESENCE_DATABASE_PATH` | Non | Base SQLite, `data/presence.db` par défaut. |

## Menus CROUS

Les menus sont envoyés sous forme d'image directement générée par l'API CROUStillant. Les commandes disponibles sont `/menu [date]` et `/menu_semaine`.

## Fiches de présence

Les commandes `/presence` sont réservées au rôle configuré dans `PRESENCE_ACCESS_ROLE_ID`.

1. Crée une classe avec `/presence classe_creer`.
2. Ajoute les élèves dans l'ordre de rotation avec `/presence membre_ajouter`.
3. Remplace son calendrier avec `/presence periodes_definir` en collant les périodes `AAAA-MM-JJ,AAAA-MM-JJ`, séparées par des espaces ou des retours à la ligne.
4. Utilise `/presence sync` pour tester le rôle et la notification, puis `/presence statut` pour contrôler le résultat.

Le bot publie à 08:00 le premier jour de chaque semaine de formation, attribue le rôle au porteur et le retire aux précédents porteurs.

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
