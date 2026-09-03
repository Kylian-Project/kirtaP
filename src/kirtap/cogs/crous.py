import logging
from datetime import time
from io import BytesIO
from typing import Any

import discord
from discord import app_commands
from discord.ext import commands, tasks

from ..bot import KirtaPBot
from ..crous import (
    PARIS_TIMEZONE,
    CrousApi,
    CrousApiError,
    format_menu_date,
    menu_image_filename,
    next_menu_dates,
    parse_menu_date,
    today_menu_date,
)

logger = logging.getLogger(__name__)


class MenuDateButton(discord.ui.Button[discord.ui.View]):
    def __init__(self, api: CrousApi, menu_date: str) -> None:
        self._api = api
        self._menu_date = menu_date
        super().__init__(
            label=format_menu_date(menu_date).capitalize(), style=discord.ButtonStyle.secondary
        )

    async def callback(self, interaction: discord.Interaction[Any]) -> None:
        await interaction.response.defer(ephemeral=True, thinking=True)
        try:
            image = await self._api.fetch_menu_image(self._menu_date)
        except CrousApiError:
            logger.warning("Unable to fetch CROUS menu image for weekly menu", exc_info=True)
            await interaction.followup.send(
                "❌ Impossible de récupérer ce menu CROUS.", ephemeral=True
            )
            return

        if image is None:
            await interaction.followup.send(
                "📅 Aucun menu n'est disponible pour cette date.", ephemeral=True
            )
            return

        await interaction.followup.send(
            embed=_menu_embed(self._menu_date),
            file=_menu_file(self._menu_date, image),
            ephemeral=True,
        )


class WeekMenuView(discord.ui.View):
    def __init__(self, api: CrousApi, menu_dates: list[str]) -> None:
        super().__init__(timeout=900)
        for menu_date in menu_dates:
            self.add_item(MenuDateButton(api, menu_date))


class Crous(commands.Cog):
    def __init__(self, bot: KirtaPBot) -> None:
        if bot.http_session is None:
            raise RuntimeError("The HTTP session must be created before loading the CROUS cog.")
        self.bot = bot
        self.api = CrousApi(bot.http_session, bot.settings.crous_restaurant_id)
        self._daily_menu_posted: str | None = None
        if bot.settings.crous_channel_id is None:
            logger.info("Automatic CROUS posting is disabled because CROUS_CHANNEL_ID is not set")
        else:
            self.daily_menu_task.start()

    def cog_unload(self) -> None:
        self.daily_menu_task.cancel()

    @commands.hybrid_command(
        name="menu",
        help="Affiche l'image du menu CROUS du jour ou d'une date donnée.",
    )
    @app_commands.describe(date="Date au format JJ-MM-AAAA")
    async def menu(self, context: commands.Context[Any], date: str | None = None) -> None:
        await self._handle_menu_command(context, date)

    @commands.hybrid_command(
        name="menu_semaine",
        help="Affiche les menus CROUS disponibles cette semaine.",
    )
    async def menu_semaine(self, context: commands.Context[Any]) -> None:
        await self._handle_week_command(context)

    async def _handle_menu_command(
        self, context: commands.Context[Any], requested_date: str | None
    ) -> None:
        try:
            menu_date = parse_menu_date(requested_date) if requested_date else today_menu_date()
        except ValueError:
            await context.send(
                "❌ Format de date invalide. Utilisez JJ-MM-AAAA, par exemple 01-10-2025."
            )
            return

        if context.interaction:
            await context.defer()
            await self._send_menu(context, menu_date)
        else:
            async with context.typing():
                await self._send_menu(context, menu_date)

    async def _handle_week_command(self, context: commands.Context[Any]) -> None:
        if context.interaction:
            await context.defer()
            await self._send_week(context)
        else:
            async with context.typing():
                await self._send_week(context)

    async def _send_menu(self, context: commands.Context[Any], menu_date: str) -> None:
        try:
            image = await self.api.fetch_menu_image(menu_date)
        except CrousApiError:
            logger.warning("Unable to fetch CROUS menu image", exc_info=True)
            await context.send(embed=_error_embed())
            return

        if image is None:
            await context.send(embed=_no_menu_embed(menu_date))
            return

        await context.send(embed=_menu_embed(menu_date), file=_menu_file(menu_date, image))

    async def _send_week(self, context: commands.Context[Any]) -> None:
        try:
            restaurant = await self.api.fetch_restaurant()
            available_dates = await self.api.fetch_menu_dates()
        except CrousApiError:
            logger.warning("Unable to fetch CROUS weekly menus", exc_info=True)
            await context.send(embed=_error_embed())
            return

        menu_dates = next_menu_dates(available_dates)
        if not menu_dates:
            await context.send(
                "📅 Aucun menu n'est encore disponible pour les cinq prochains jours."
            )
            return

        embed = discord.Embed(
            title=f"🍽️ {restaurant.name} - 5 prochains menus",
            description="Choisissez un jour pour recevoir l'image du menu.",
            color=discord.Color.orange(),
        )
        embed.add_field(
            name="📅 Menus disponibles",
            value="\n".join(
                f"• {format_menu_date(menu_date).capitalize()}" for menu_date in menu_dates
            ),
            inline=False,
        )
        embed.set_footer(text="Menus fournis par CROUStillant.menu")
        await context.send(embed=embed, view=WeekMenuView(self.api, menu_dates))

    @tasks.loop(
        time=(
            time(hour=8, tzinfo=PARIS_TIMEZONE),
            time(hour=9, minute=5, tzinfo=PARIS_TIMEZONE),
        )
    )
    async def daily_menu_task(self) -> None:
        menu_date = today_menu_date()
        if self._daily_menu_posted == menu_date:
            return

        channel_id = self.bot.settings.crous_channel_id
        if channel_id is None:
            return

        channel = self.bot.get_channel(channel_id)
        if not isinstance(channel, discord.abc.Messageable):
            logger.warning("CROUS channel %s is unavailable", channel_id)
            return

        try:
            restaurant = await self.api.fetch_restaurant()
            if not await self.api.fetch_is_open():
                await channel.send(embed=_closed_embed(restaurant.name, menu_date))
                self._daily_menu_posted = menu_date
                logger.info("Posted closed CROUS notice")
                return

            image = await self.api.fetch_menu_image(menu_date)
            if image is None:
                logger.info("No CROUS menu at %s; it will be retried at 09:05", menu_date)
                return

            await channel.send(
                embed=_daily_menu_embed(restaurant.name, menu_date),
                file=_menu_file(menu_date, image),
            )
            self._daily_menu_posted = menu_date
            logger.info("Posted the automatic CROUS menu")
        except (CrousApiError, discord.HTTPException):
            logger.exception("Unable to post the automatic CROUS menu")

    @daily_menu_task.before_loop
    async def wait_until_ready(self) -> None:
        await self.bot.wait_until_ready()


def _menu_file(menu_date: str, image: bytes) -> discord.File:
    return discord.File(BytesIO(image), filename=menu_image_filename(menu_date))


def _menu_embed(menu_date: str) -> discord.Embed:
    filename = menu_image_filename(menu_date)
    embed = discord.Embed(
        title=f"🍽️ Menu CROUS - {format_menu_date(menu_date).capitalize()}",
        color=discord.Color.orange(),
    )
    embed.set_image(url=f"attachment://{filename}")
    embed.set_footer(text="Menu fourni par CROUStillant.menu")
    return embed


def _daily_menu_embed(restaurant_name: str, menu_date: str) -> discord.Embed:
    embed = _menu_embed(menu_date)
    embed.title = f"🍽️ CROUS - {format_menu_date(menu_date).capitalize()}"
    embed.description = f"🟢 **{restaurant_name}**\nOuvert aujourd'hui."
    return embed


def _closed_embed(restaurant_name: str, menu_date: str) -> discord.Embed:
    return discord.Embed(
        title=f"🍽️ CROUS - {format_menu_date(menu_date).capitalize()}",
        description=f"🔴 **{restaurant_name}** est fermé aujourd'hui.",
        color=discord.Color.red(),
    )


def _no_menu_embed(menu_date: str) -> discord.Embed:
    return discord.Embed(
        title="📅 Pas de menu",
        description=f"Aucun menu n'est disponible pour le {format_menu_date(menu_date)}.",
        color=discord.Color.orange(),
    )


def _error_embed() -> discord.Embed:
    return discord.Embed(
        title="❌ Erreur CROUS",
        description="Impossible de récupérer les informations CROUS. Réessayez un peu plus tard.",
        color=discord.Color.red(),
    )


async def setup(bot: KirtaPBot) -> None:
    await bot.add_cog(Crous(bot))
