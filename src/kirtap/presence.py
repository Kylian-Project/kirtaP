from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path

import aiosqlite


@dataclass(frozen=True, slots=True)
class SchoolPeriod:
    start: date
    end: date

    def contains(self, target: date) -> bool:
        return self.start <= target <= self.end and target.weekday() < 5


@dataclass(frozen=True, slots=True)
class RotationSlot:
    week_start: date
    first_school_day: date


@dataclass(frozen=True, slots=True)
class PresenceClass:
    id: int
    name: str
    member_ids: tuple[int, ...]
    periods: tuple[SchoolPeriod, ...]
    channel_id: int | None = None


@dataclass(frozen=True, slots=True)
class PresenceAssignment:
    presence_class: PresenceClass
    holder_id: int
    slot: RotationSlot


class PresenceStore:
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
            PRAGMA foreign_keys = ON;

            CREATE TABLE IF NOT EXISTS presence_classes (
                id INTEGER PRIMARY KEY,
                guild_id INTEGER NOT NULL,
                name TEXT NOT NULL COLLATE NOCASE,
                channel_id INTEGER,
                UNIQUE(guild_id, name)
            );

            CREATE TABLE IF NOT EXISTS presence_members (
                class_id INTEGER NOT NULL REFERENCES presence_classes(id) ON DELETE CASCADE,
                user_id INTEGER NOT NULL,
                position INTEGER NOT NULL,
                PRIMARY KEY(class_id, user_id),
                UNIQUE(class_id, position)
            );

            CREATE TABLE IF NOT EXISTS presence_periods (
                id INTEGER PRIMARY KEY,
                class_id INTEGER NOT NULL REFERENCES presence_classes(id) ON DELETE CASCADE,
                start_date TEXT NOT NULL,
                end_date TEXT NOT NULL,
                UNIQUE(class_id, start_date, end_date)
            );

            CREATE TABLE IF NOT EXISTS presence_notifications (
                class_id INTEGER NOT NULL REFERENCES presence_classes(id) ON DELETE CASCADE,
                slot_date TEXT NOT NULL,
                PRIMARY KEY(class_id, slot_date)
            );

            CREATE TABLE IF NOT EXISTS presence_role_holders (
                class_id INTEGER PRIMARY KEY REFERENCES presence_classes(id) ON DELETE CASCADE,
                user_id INTEGER NOT NULL
            );
            """
        )
        cursor = await self._connection.execute("PRAGMA table_info(presence_classes)")
        columns = {str(row[1]) for row in await cursor.fetchall()}
        await cursor.close()
        if "channel_id" not in columns:
            await self._connection.execute(
                "ALTER TABLE presence_classes ADD COLUMN channel_id INTEGER"
            )
        await self._connection.commit()

    async def close(self) -> None:
        if self._connection is not None:
            await self._connection.close()
            self._connection = None

    async def ensure_class(self, guild_id: int, name: str) -> PresenceClass:
        connection = self._require_connection()
        normalized_name = name.strip()
        if not normalized_name:
            raise ValueError("Le nom de la classe ne peut pas être vide.")
        await connection.execute(
            "INSERT OR IGNORE INTO presence_classes (guild_id, name) VALUES (?, ?)",
            (guild_id, normalized_name),
        )
        await connection.commit()
        presence_class = await self.get_class(guild_id, normalized_name)
        if presence_class is None:
            raise RuntimeError("La classe vient d'être créée mais est introuvable.")
        return presence_class

    async def get_class(self, guild_id: int, name: str) -> PresenceClass | None:
        connection = self._require_connection()
        cursor = await connection.execute(
            "SELECT id, name, channel_id FROM presence_classes "
            "WHERE guild_id = ? AND name = ? COLLATE NOCASE",
            (guild_id, name.strip()),
        )
        row = await cursor.fetchone()
        await cursor.close()
        return await self._class_from_row(row) if row is not None else None

    async def get_class_by_id(self, guild_id: int, class_id: int) -> PresenceClass | None:
        connection = self._require_connection()
        cursor = await connection.execute(
            "SELECT id, name, channel_id FROM presence_classes WHERE guild_id = ? AND id = ?",
            (guild_id, class_id),
        )
        row = await cursor.fetchone()
        await cursor.close()
        return await self._class_from_row(row) if row is not None else None

    async def list_classes(self, guild_id: int) -> list[PresenceClass]:
        connection = self._require_connection()
        cursor = await connection.execute(
            "SELECT id, name, channel_id FROM presence_classes "
            "WHERE guild_id = ? ORDER BY name COLLATE NOCASE",
            (guild_id,),
        )
        rows = await cursor.fetchall()
        await cursor.close()
        return [await self._class_from_row(row) for row in rows]

    async def set_channel(self, presence_class: PresenceClass, channel_id: int) -> None:
        connection = self._require_connection()
        await connection.execute(
            "UPDATE presence_classes SET channel_id = ? WHERE id = ?",
            (channel_id, presence_class.id),
        )
        await connection.commit()

    async def delete_class(self, presence_class: PresenceClass) -> bool:
        connection = self._require_connection()
        cursor = await connection.execute(
            "DELETE FROM presence_classes WHERE id = ?", (presence_class.id,)
        )
        deleted = cursor.rowcount > 0
        await cursor.close()
        await connection.commit()
        return deleted

    async def add_member(self, presence_class: PresenceClass, user_id: int) -> bool:
        connection = self._require_connection()
        cursor = await connection.execute(
            "SELECT 1 FROM presence_members WHERE class_id = ? AND user_id = ?",
            (presence_class.id, user_id),
        )
        exists = await cursor.fetchone() is not None
        await cursor.close()
        if exists:
            return False

        cursor = await connection.execute(
            "SELECT COALESCE(MAX(position), 0) + 1 FROM presence_members WHERE class_id = ?",
            (presence_class.id,),
        )
        position = int((await cursor.fetchone())[0])
        await cursor.close()
        await connection.execute(
            "INSERT INTO presence_members (class_id, user_id, position) VALUES (?, ?, ?)",
            (presence_class.id, user_id, position),
        )
        await connection.commit()
        return True

    async def remove_member(self, presence_class: PresenceClass, user_id: int) -> bool:
        connection = self._require_connection()
        cursor = await connection.execute(
            "DELETE FROM presence_members WHERE class_id = ? AND user_id = ?",
            (presence_class.id, user_id),
        )
        deleted = cursor.rowcount > 0
        await cursor.close()
        await connection.commit()
        return deleted

    async def replace_periods(
        self, presence_class: PresenceClass, periods: Iterable[SchoolPeriod]
    ) -> None:
        connection = self._require_connection()
        normalized_periods = sorted(set(periods), key=lambda period: (period.start, period.end))
        await connection.execute(
            "DELETE FROM presence_periods WHERE class_id = ?", (presence_class.id,)
        )
        await connection.executemany(
            "INSERT INTO presence_periods (class_id, start_date, end_date) VALUES (?, ?, ?)",
            [
                (presence_class.id, period.start.isoformat(), period.end.isoformat())
                for period in normalized_periods
            ],
        )
        await connection.commit()

    async def notification_was_sent(
        self, presence_class: PresenceClass, slot: RotationSlot
    ) -> bool:
        connection = self._require_connection()
        cursor = await connection.execute(
            "SELECT 1 FROM presence_notifications WHERE class_id = ? AND slot_date = ?",
            (presence_class.id, slot.week_start.isoformat()),
        )
        sent = await cursor.fetchone() is not None
        await cursor.close()
        return sent

    async def mark_notification_sent(
        self, presence_class: PresenceClass, slot: RotationSlot
    ) -> None:
        connection = self._require_connection()
        await connection.execute(
            "INSERT OR IGNORE INTO presence_notifications (class_id, slot_date) VALUES (?, ?)",
            (presence_class.id, slot.week_start.isoformat()),
        )
        await connection.commit()

    async def role_holders(self, guild_id: int) -> set[int]:
        connection = self._require_connection()
        cursor = await connection.execute(
            """
            SELECT holder.user_id
            FROM presence_role_holders AS holder
            JOIN presence_classes AS class ON class.id = holder.class_id
            WHERE class.guild_id = ?
            """,
            (guild_id,),
        )
        holders = {int(row[0]) for row in await cursor.fetchall()}
        await cursor.close()
        return holders

    async def replace_role_holders(
        self, guild_id: int, assignments: Iterable[PresenceAssignment]
    ) -> None:
        connection = self._require_connection()
        await connection.execute(
            """
            DELETE FROM presence_role_holders
            WHERE class_id IN (SELECT id FROM presence_classes WHERE guild_id = ?)
            """,
            (guild_id,),
        )
        await connection.executemany(
            "INSERT INTO presence_role_holders (class_id, user_id) VALUES (?, ?)",
            [(assignment.presence_class.id, assignment.holder_id) for assignment in assignments],
        )
        await connection.commit()

    async def _class_from_row(self, row: aiosqlite.Row) -> PresenceClass:
        connection = self._require_connection()
        class_id = int(row["id"])
        member_cursor = await connection.execute(
            "SELECT user_id FROM presence_members WHERE class_id = ? ORDER BY position, user_id",
            (class_id,),
        )
        member_ids = tuple(int(member[0]) for member in await member_cursor.fetchall())
        await member_cursor.close()
        period_cursor = await connection.execute(
            "SELECT start_date, end_date FROM presence_periods WHERE class_id = ? ORDER BY start_date",
            (class_id,),
        )
        periods = tuple(
            SchoolPeriod(start=date.fromisoformat(period[0]), end=date.fromisoformat(period[1]))
            for period in await period_cursor.fetchall()
        )
        await period_cursor.close()
        return PresenceClass(
            id=class_id,
            name=str(row["name"]),
            member_ids=member_ids,
            periods=periods,
            channel_id=int(row["channel_id"]) if row["channel_id"] is not None else None,
        )

    def _require_connection(self) -> aiosqlite.Connection:
        if self._connection is None:
            raise RuntimeError("La base de présence n'est pas ouverte.")
        return self._connection


def parse_periods(value: str) -> list[SchoolPeriod]:
    periods: list[SchoolPeriod] = []
    for entry_number, entry in enumerate(value.split(), start=1):
        parts = [part.strip() for part in entry.split(",")]
        if len(parts) != 2:
            raise ValueError(f"Entrée {entry_number} : utilisez debut,fin au format AAAA-MM-JJ.")
        try:
            period = SchoolPeriod(
                start=date.fromisoformat(parts[0]), end=date.fromisoformat(parts[1])
            )
        except ValueError as error:
            raise ValueError(f"Entrée {entry_number} : date invalide.") from error
        if period.end < period.start:
            raise ValueError(f"Entrée {entry_number} : la fin doit suivre le début.")
        periods.append(period)

    if not periods:
        raise ValueError("Ajoutez au moins une période de formation.")
    return periods


def rotation_slots(periods: Iterable[SchoolPeriod]) -> list[RotationSlot]:
    first_days: dict[date, date] = {}
    for period in periods:
        current = period.start
        while current <= period.end:
            if current.weekday() < 5:
                week_start = current - timedelta(days=current.weekday())
                first_days.setdefault(week_start, current)
            current += timedelta(days=1)
    return [
        RotationSlot(week_start=week_start, first_school_day=first_days[week_start])
        for week_start in sorted(first_days)
    ]


def assignment_for_date(presence_class: PresenceClass, target: date) -> PresenceAssignment | None:
    if not presence_class.member_ids or not any(
        period.contains(target) for period in presence_class.periods
    ):
        return None

    week_start = target - timedelta(days=target.weekday())
    slots = rotation_slots(presence_class.periods)
    for position, slot in enumerate(slots):
        if slot.week_start == week_start:
            return PresenceAssignment(
                presence_class=presence_class,
                holder_id=presence_class.member_ids[position % len(presence_class.member_ids)],
                slot=slot,
            )
    return None


def next_assignment(presence_class: PresenceClass, target: date) -> PresenceAssignment | None:
    if not presence_class.member_ids:
        return None

    for position, slot in enumerate(rotation_slots(presence_class.periods)):
        if slot.first_school_day >= target:
            return PresenceAssignment(
                presence_class=presence_class,
                holder_id=presence_class.member_ids[position % len(presence_class.member_ids)],
                slot=slot,
            )
    return None
