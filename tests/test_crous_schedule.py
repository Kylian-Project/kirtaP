import asyncio
from unittest.mock import AsyncMock, Mock

import discord
import pytest

from kirtap.cogs.crous import Crous
from kirtap.crous import Restaurant


@pytest.mark.parametrize(
    "menu_date, weekend",
    [
        ("04-09-2026", False),
        ("05-09-2026", True),
        ("06-09-2026", True),
        ("07-09-2026", False),
    ],
)
@pytest.mark.parametrize("is_open", [False, True])
def test_daily_menu_only_posts_on_weekdays(
    monkeypatch: pytest.MonkeyPatch, menu_date: str, weekend: bool, is_open: bool
) -> None:
    monkeypatch.setattr("kirtap.cogs.crous.today_menu_date", lambda: menu_date)
    bot = Mock()
    bot.settings.crous_channel_id = None
    cog = Crous(bot)
    bot.settings.crous_channel_id = 123
    channel = Mock(spec=discord.abc.Messageable)
    channel.send = AsyncMock()
    bot.get_channel.return_value = channel
    cog.api = Mock(
        fetch_restaurant=AsyncMock(return_value=Restaurant(name="Restaurant")),
        fetch_is_open=AsyncMock(return_value=is_open),
        fetch_menu_image=AsyncMock(return_value=b"PNG"),
    )

    async def scenario() -> None:
        await cog.daily_menu_task()
        await cog.daily_menu_task()

    asyncio.run(scenario())

    if weekend:
        bot.get_channel.assert_not_called()
        cog.api.fetch_restaurant.assert_not_awaited()
        cog.api.fetch_is_open.assert_not_awaited()
        cog.api.fetch_menu_image.assert_not_awaited()
        channel.send.assert_not_awaited()
        assert cog._daily_menu_posted is None
    else:
        channel.send.assert_awaited_once()
        assert cog._daily_menu_posted == menu_date
        assert cog.api.fetch_menu_image.await_count == int(is_open)
