import asyncio

import pytest

from kirtap.cogs.midi import restaurant_poll, restaurants_embed
from kirtap.lunch import LunchStore


def test_restaurant_list_is_ordered_and_can_be_reused() -> None:
    async def scenario() -> None:
        store = LunchStore(":memory:")
        await store.open()
        first = await store.add_restaurant(42, "Le Bistrot", "https://maps.google.com/?q=bistrot")
        second = await store.add_restaurant(42, "La Cantine", None)

        restaurants = await store.list_restaurants(42)
        assert [restaurant.name for restaurant in restaurants] == ["Le Bistrot", "La Cantine"]
        assert restaurants_embed(restaurants).description == (
            "1. [Le Bistrot](https://maps.google.com/?q=bistrot)\n2. La Cantine"
        )
        poll = restaurant_poll(restaurants, duration_hours=3)
        assert poll.duration.total_seconds() == 3 * 60 * 60
        assert [answer.text for answer in poll.answers] == [
            "Le Bistrot",
            "La Cantine",
        ]

        removed = await store.remove_restaurant(42, 1)
        assert removed == first
        assert [restaurant.position for restaurant in await store.list_restaurants(42)] == [1]

        await store.remove_restaurants(42, [second])
        assert await store.list_restaurants(42) == []
        await store.close()

    asyncio.run(scenario())


def test_restaurant_list_rejects_duplicates_and_more_than_ten_entries() -> None:
    async def scenario() -> None:
        store = LunchStore(":memory:")
        await store.open()
        await store.add_restaurant(42, "Le Bistrot", None)
        with pytest.raises(ValueError, match="déjà"):
            await store.add_restaurant(42, "le bistrot", None)
        for index in range(2, 11):
            await store.add_restaurant(42, f"Restaurant {index}", None)
        with pytest.raises(ValueError, match="limitée"):
            await store.add_restaurant(42, "Restaurant 11", None)
        await store.close()

    asyncio.run(scenario())
