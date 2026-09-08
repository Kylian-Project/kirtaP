import asyncio
from unittest.mock import AsyncMock, Mock

import discord
import pytest
from discord.ext import commands
from discord.ext.commands.view import StringView

from kirtap.bot import KirtaPBot
from kirtap.cogs.crous import WeekMenuView
from kirtap.cogs.presence import Presence
from kirtap.cogs.presence_setup import PresenceSetupView
from kirtap.config import load_settings


@pytest.mark.parametrize(
    "environment, administrator, private_message, allowed",
    [
        ("development", False, False, False),
        ("development", True, False, True),
        ("development", False, True, False),
        ("production", False, False, True),
        ("production", True, False, True),
        ("production", False, True, True),
    ],
)
def test_access_for_prefix_slash_and_buttons(
    environment: str, administrator: bool, private_message: bool, allowed: bool
) -> None:
    async def scenario() -> None:
        bot = KirtaPBot(load_settings({"DISCORD_TOKEN": "token", "ENVIRONMENT": environment}))
        user = Mock(spec=discord.User if private_message else discord.Member)
        if not private_message:
            user.guild_permissions = discord.Permissions(administrator=administrator)

        @bot.command()
        async def example(context: commands.Context) -> None:
            await context.send("Executed")

        message = Mock(spec=discord.Message, author=user, attachments=[])
        context = commands.Context(
            message=message,
            bot=bot,
            view=StringView(""),
            prefix="!",
            invoked_with="example",
            command=example,
        )
        context.send = AsyncMock()
        bot.dispatch = Mock()
        interaction = Mock(user=user)
        interaction.response = Mock(send_message=AsyncMock(), defer=AsyncMock())

        await bot.invoke(context)
        if allowed:
            context.send.assert_awaited_once_with("Executed")
        else:
            context.send.assert_not_awaited()
            bot.dispatch.assert_not_called()

        assert await bot.tree.interaction_check(interaction) is allowed
        view = WeekMenuView(bot, Mock(), ["07-09-2026"])
        assert await view.interaction_check(interaction) is allowed
        interaction.response.send_message.assert_not_awaited()
        interaction.response.defer.assert_not_awaited()
        view.stop()
        await bot.close()

    asyncio.run(scenario())


def test_presence_setup_panel_is_persistent() -> None:
    async def synchronize(_: discord.Guild) -> int:
        return 0

    def topo(_: object) -> discord.Embed:
        return discord.Embed()

    bot = KirtaPBot(load_settings({"DISCORD_TOKEN": "token"}))
    panel = PresenceSetupView(bot, synchronize=synchronize, topo=topo, persistent=True)

    assert panel.is_persistent()
    bot.add_view(panel)
    asyncio.run(bot.close())


def test_presence_exposes_only_setup_and_consultation_commands() -> None:
    async def scenario() -> None:
        bot = KirtaPBot(load_settings({"DISCORD_TOKEN": "token"}))
        await bot.add_cog(Presence(bot))
        presence = bot.get_command("presence")

        assert isinstance(presence, commands.Group)
        assert {command.name for command in presence.commands} == {
            "classes",
            "setup",
            "statut",
            "topo",
        }
        await bot.close()

    asyncio.run(scenario())
