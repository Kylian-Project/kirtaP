import logging
from datetime import datetime
from io import BytesIO
from typing import Any

import discord
from discord.ext import commands

from ..ade import PARIS_TIMEZONE, AdeApi, AdeApiError
from ..ade_image import render_week_schedule, schedule_image_filename
from ..bot import KirtaPBot

logger = logging.getLogger(__name__)


class Fugue(commands.Cog):
    def __init__(self, bot: KirtaPBot) -> None:
        if bot.http_session is None:
            raise RuntimeError("The HTTP session must be created before loading the Fugue cog.")
        self.bot = bot
        self.api = (
            AdeApi(bot.http_session, bot.settings.ade_ical_url)
            if bot.settings.ade_ical_url
            else None
        )

    @commands.hybrid_command(name="fugue", help="Mouahahahahahaha !!")
    async def fugue(self, context: commands.Context[Any]) -> None:
        if self.api is None:
            await context.send(embed=_configuration_embed())
            return
        if context.interaction:
            await context.defer()
            await self._send_week(context)
        else:
            async with context.typing():
                await self._send_week(context)

    async def _send_week(self, context: commands.Context[Any]) -> None:
        try:
            events = await self.api.fetch_events()
        except AdeApiError:
            logger.warning("Unable to fetch ADE iCalendar feed", exc_info=True)
            await context.send(embed=_error_embed())
            return
        reference = datetime.now(PARIS_TIMEZONE).date()
        await context.send(
            file=discord.File(
                BytesIO(render_week_schedule(events, reference=reference)),
                filename=schedule_image_filename(reference=reference),
                description="Mouahahahahahaha !!",
            )
        )


def _configuration_embed() -> discord.Embed:
    return discord.Embed(
        title="Planning indisponible",
        description="Le calendrier ADE n'est pas configuré.",
        color=discord.Color.red(),
    )


def _error_embed() -> discord.Embed:
    return discord.Embed(
        title="Planning indisponible",
        description="Impossible de récupérer le calendrier ADE. Réessayez plus tard.",
        color=discord.Color.red(),
    )


async def setup(bot: KirtaPBot) -> None:
    await bot.add_cog(Fugue(bot))
