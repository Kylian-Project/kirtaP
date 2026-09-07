import asyncio
from datetime import date

import aiosqlite
import pytest

from kirtap.presence import (
    PresenceClass,
    PresenceStore,
    SchoolPeriod,
    assignment_for_date,
    next_assignment,
    parse_periods,
    rotation_slots,
)


def test_period_import_accepts_spaces_or_newlines_between_periods() -> None:
    periods = parse_periods("2026-09-07,2026-09-25 2026-10-12,2026-10-16")

    assert periods == [
        SchoolPeriod(start=date(2026, 9, 7), end=date(2026, 9, 25)),
        SchoolPeriod(start=date(2026, 10, 12), end=date(2026, 10, 16)),
    ]

    with pytest.raises(ValueError, match="Entrée 1"):
        parse_periods("07-09-2026,25-09-2026")


def test_rotation_creates_one_slot_for_each_school_week() -> None:
    slots = rotation_slots([SchoolPeriod(start=date(2026, 9, 7), end=date(2026, 9, 25))])

    assert [slot.first_school_day for slot in slots] == [
        date(2026, 9, 7),
        date(2026, 9, 14),
        date(2026, 9, 21),
    ]


def test_assignment_cycles_members_and_skips_company_days() -> None:
    presence_class = PresenceClass(
        id=1,
        name="M2 SIL",
        member_ids=(101, 202),
        periods=(SchoolPeriod(start=date(2026, 9, 7), end=date(2026, 9, 25)),),
    )

    first = assignment_for_date(presence_class, date(2026, 9, 7))
    second = assignment_for_date(presence_class, date(2026, 9, 14))
    third = assignment_for_date(presence_class, date(2026, 9, 21))

    assert first is not None and first.holder_id == 101
    assert second is not None and second.holder_id == 202
    assert third is not None and third.holder_id == 101
    assert assignment_for_date(presence_class, date(2026, 9, 26)) is None


def test_next_assignment_uses_the_next_school_slot() -> None:
    presence_class = PresenceClass(
        id=1,
        name="M2 SIL",
        member_ids=(101, 202),
        periods=(SchoolPeriod(start=date(2026, 9, 7), end=date(2026, 9, 25)),),
    )

    assignment = next_assignment(presence_class, date(2026, 9, 12))

    assert assignment is not None
    assert assignment.holder_id == 202
    assert assignment.slot.first_school_day == date(2026, 9, 14)


def test_store_keeps_a_class_roster_and_periods() -> None:
    async def scenario() -> PresenceClass:
        store = PresenceStore(":memory:")
        await store.open()
        try:
            presence_class = await store.ensure_class(42, "M2 SIL")
            assert await store.add_member(presence_class, 101)
            assert await store.add_member(presence_class, 202)
            await store.set_channel(presence_class, 987)
            await store.replace_periods(
                presence_class,
                [SchoolPeriod(start=date(2026, 9, 7), end=date(2026, 9, 25))],
            )
            loaded = await store.get_class(42, "m2 sil")
            assert loaded is not None
            return loaded
        finally:
            await store.close()

    loaded = asyncio.run(scenario())

    assert loaded.member_ids == (101, 202)
    assert loaded.channel_id == 987
    assert loaded.periods == (SchoolPeriod(start=date(2026, 9, 7), end=date(2026, 9, 25)),)


def test_store_migrates_existing_database_with_class_channels(tmp_path) -> None:
    async def scenario() -> None:
        database_path = tmp_path / "presence.db"
        connection = await aiosqlite.connect(database_path)
        await connection.executescript(
            """
            CREATE TABLE presence_classes (
                id INTEGER PRIMARY KEY,
                guild_id INTEGER NOT NULL,
                name TEXT NOT NULL COLLATE NOCASE,
                UNIQUE(guild_id, name)
            );
            INSERT INTO presence_classes (guild_id, name) VALUES (42, 'M2 SIL');
            """
        )
        await connection.close()

        store = PresenceStore(str(database_path))
        await store.open()
        try:
            presence_class = await store.get_class(42, "M2 SIL")
            assert presence_class is not None
            assert presence_class.channel_id is None
            await store.set_channel(presence_class, 987)
            updated = await store.get_class(42, "M2 SIL")
            assert updated is not None
            assert updated.channel_id == 987
        finally:
            await store.close()

    asyncio.run(scenario())
