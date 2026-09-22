from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

import aiosqlite

MAX_RESTAURANTS = 10
MAX_RESTAURANT_NAME_LENGTH = 55


@dataclass(frozen=True, slots=True)
class Restaurant:
    id: int
    name: str
    link: str | None
    position: int


class LunchStore:
    def __init__(self, database_path: str) -> None:
        self._database_path = database_path
        self._connection: aiosqlite.Connection | None = None

    async def open(self) -> None:
        if self._database_path != ":memory:":
            Path(self._database_path).parent.mkdir(parents=True, exist_ok=True)
        self._connection = await aiosqlite.connect(self._database_path)
        self._connection.row_factory = aiosqlite.Row
        await self._connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS lunch_restaurants (
                id INTEGER PRIMARY KEY,
                guild_id INTEGER NOT NULL,
                name TEXT NOT NULL COLLATE NOCASE,
                link TEXT,
                position INTEGER NOT NULL,
                UNIQUE(guild_id, name),
                UNIQUE(guild_id, position)
            );
            """
        )
        await self._connection.commit()

    async def close(self) -> None:
        if self._connection is not None:
            await self._connection.close()
            self._connection = None

    async def list_restaurants(self, guild_id: int) -> list[Restaurant]:
        connection = self._require_connection()
        cursor = await connection.execute(
            "SELECT id, name, link, position FROM lunch_restaurants "
            "WHERE guild_id = ? ORDER BY position",
            (guild_id,),
        )
        rows = await cursor.fetchall()
        await cursor.close()
        return [self._restaurant_from_row(row) for row in rows]

    async def add_restaurant(self, guild_id: int, name: str, link: str | None) -> Restaurant:
        connection = self._require_connection()
        normalized_name = self._normalize_name(name)
        normalized_link = self._normalize_link(link)
        restaurants = await self.list_restaurants(guild_id)
        if len(restaurants) >= MAX_RESTAURANTS:
            raise ValueError(f"La liste est limitée à {MAX_RESTAURANTS} restaurants.")
        try:
            cursor = await connection.execute(
                "INSERT INTO lunch_restaurants (guild_id, name, link, position) "
                "VALUES (?, ?, ?, ?)",
                (guild_id, normalized_name, normalized_link, len(restaurants) + 1),
            )
        except aiosqlite.IntegrityError as error:
            raise ValueError("Ce restaurant est déjà dans la liste.") from error
        await connection.commit()
        restaurant_id = cursor.lastrowid
        await cursor.close()
        if restaurant_id is None:
            raise RuntimeError("Le restaurant créé est introuvable.")
        return Restaurant(
            id=restaurant_id,
            name=normalized_name,
            link=normalized_link,
            position=len(restaurants) + 1,
        )

    async def remove_restaurant(self, guild_id: int, position: int) -> Restaurant | None:
        restaurants = await self.list_restaurants(guild_id)
        restaurant = next((item for item in restaurants if item.position == position), None)
        if restaurant is None:
            return None
        connection = self._require_connection()
        await connection.execute(
            "DELETE FROM lunch_restaurants WHERE guild_id = ? AND id = ?",
            (guild_id, restaurant.id),
        )
        await self._resequence(guild_id)
        await connection.commit()
        return restaurant

    async def clear_restaurants(self, guild_id: int) -> bool:
        connection = self._require_connection()
        cursor = await connection.execute(
            "DELETE FROM lunch_restaurants WHERE guild_id = ?", (guild_id,)
        )
        cleared = cursor.rowcount > 0
        await cursor.close()
        await connection.commit()
        return cleared

    async def _resequence(self, guild_id: int) -> None:
        connection = self._require_connection()
        cursor = await connection.execute(
            "SELECT id FROM lunch_restaurants WHERE guild_id = ? ORDER BY position", (guild_id,)
        )
        rows = await cursor.fetchall()
        await cursor.close()
        await connection.execute(
            "UPDATE lunch_restaurants SET position = position + 1000 WHERE guild_id = ?",
            (guild_id,),
        )
        await connection.executemany(
            "UPDATE lunch_restaurants SET position = ? WHERE id = ?",
            [(position, int(row[0])) for position, row in enumerate(rows, start=1)],
        )

    def _require_connection(self) -> aiosqlite.Connection:
        if self._connection is None:
            raise RuntimeError("La base des restaurants n'est pas ouverte.")
        return self._connection

    @staticmethod
    def _restaurant_from_row(row: aiosqlite.Row) -> Restaurant:
        return Restaurant(
            id=int(row["id"]),
            name=str(row["name"]),
            link=str(row["link"]) if row["link"] is not None else None,
            position=int(row["position"]),
        )

    @staticmethod
    def _normalize_name(name: str) -> str:
        normalized_name = name.strip()
        if not normalized_name:
            raise ValueError("Le nom du restaurant ne peut pas être vide.")
        if len(normalized_name) > MAX_RESTAURANT_NAME_LENGTH:
            raise ValueError(f"Le nom est limité à {MAX_RESTAURANT_NAME_LENGTH} caractères.")
        return normalized_name

    @staticmethod
    def _normalize_link(link: str | None) -> str | None:
        if link is None or not link.strip():
            return None
        normalized_link = link.strip()
        parsed = urlparse(normalized_link)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("Le lien doit être une URL http:// ou https:// valide.")
        return normalized_link
