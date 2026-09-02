import logging
from datetime import time
from typing import Any

import discord
from discord import app_commands
from discord.ext import commands, tasks

from ..bot import KirtaPBot
from ..crous import (
    PARIS_TIMEZONE,
    Category,
    CrousApi,
    Menu,
    categories_for_meal,
    category_dishes,
    find_menu,
    menu_meals,
    parse_menu_date,
    today_menu_date,
)

logger = logging.getLogger(__name__)

MAX_EMBED_FIELDS = 25
MAX_EMBED_LENGTH = 5800


class Crous(commands.Cog):
    def __init__(self, bot: KirtaPBot) -> None:
        if bot.http_session is None:
            raise RuntimeError("The HTTP session must be created before loading the CROUS cog.")
        self.bot = bot
        self.api = CrousApi(bot.http_session, bot.settings.crous_restaurant_id)
        if bot.settings.crous_channel_id is None:
            logger.info("Automatic CROUS posting is disabled because CROUS_CHANNEL_ID is not set")
        else:
            self.daily_menu_task.start()

    def cog_unload(self) -> None:
        self.daily_menu_task.cancel()

    @commands.hybrid_command(
        name="menu",
        aliases=["crous"],
        help="Affiche le menu CROUS du jour ou d'une date donnée.",
    )
    @app_commands.describe(date="Date au format JJ-MM-AAAA")
    async def menu(self, context: commands.Context[Any], date: str | None = None) -> None:
        try:
            target_date = parse_menu_date(date) if date else today_menu_date()
        except ValueError:
            await context.send(
                "❌ Format de date invalide. Utilisez JJ-MM-AAAA, par exemple 01-10-2025."
            )
            return

        if context.interaction:
            await context.defer()
            await self._send_menu(context, target_date)
        else:
            async with context.typing():
                await self._send_menu(context, target_date)

    @commands.hybrid_command(
        name="menu_semaine",
        aliases=["menus"],
        help="Liste les dates des menus CROUS disponibles.",
    )
    async def menu_semaine(self, context: commands.Context[Any]) -> None:
        if context.interaction:
            await context.defer()
            await self._send_available_dates(context)
        else:
            async with context.typing():
                await self._send_available_dates(context)

    async def _send_menu(self, context: commands.Context[Any], target_date: str) -> None:
        menus = await self._fetch_menus(context)
        if menus is None:
            return

        menu = find_menu(menus, target_date)
        if menu is None:
            embed = discord.Embed(
                title="📅 Pas de menu",
                description=f"Aucun menu trouvé pour le {target_date}.",
                color=discord.Color.orange(),
            )
            await context.send(embed=embed)
            return
        await context.send(embed=_menu_embed(menu))

    async def _send_available_dates(self, context: commands.Context[Any]) -> None:
        menus = await self._fetch_menus(context)
        if menus is None:
            return
        if not menus:
            await context.send("📅 Aucun menu disponible.")
            return

        dates = [str(menu.get("date", "Date inconnue")) for menu in menus[:10]]
        embed = discord.Embed(
            title="📅 Menus CROUS disponibles",
            description="Utilisez `/menu` ou la commande prefixe `menu` avec une date.",
            color=discord.Color.orange(),
        )
        embed.add_field(
            name="🗓️ Dates disponibles",
            value="\n".join(f"**{index}.** {date}" for index, date in enumerate(dates, start=1)),
            inline=False,
        )
        await context.send(embed=embed)

    async def _fetch_menus(self, context: commands.Context[Any]) -> list[Menu] | None:
        menus = await self.api.fetch_menus()
        if menus is not None:
            return menus
        embed = discord.Embed(
            title="❌ Erreur",
            description="Impossible de récupérer les menus CROUS.",
            color=discord.Color.red(),
        )
        await context.send(embed=embed)
        return None

    @tasks.loop(time=time(hour=8, tzinfo=PARIS_TIMEZONE))
    async def daily_menu_task(self) -> None:
        channel_id = self.bot.settings.crous_channel_id
        if channel_id is None:
            return

        channel = self.bot.get_channel(channel_id)
        if not isinstance(channel, discord.abc.Messageable):
            logger.warning("CROUS channel %s is unavailable", channel_id)
            return

        try:
            menus = await self.api.fetch_menus()
            if menus is None:
                return
            menu = find_menu(menus, today_menu_date())
            if menu is None:
                logger.info("No CROUS menu is available for today")
                return
            embed = _menu_embed(menu)
            embed.title = "🌅 Menu du jour — CROUS"
            await channel.send("🍽️ **Le menu du jour est arrivé !**", embed=embed)
            logger.info("Posted the automatic CROUS menu")
        except Exception:
            logger.exception("Unable to post the automatic CROUS menu")

    @daily_menu_task.before_loop
    async def wait_until_ready(self) -> None:
        await self.bot.wait_until_ready()


def _menu_embed(menu: Menu) -> discord.Embed:
    date = str(menu.get("date", "Date inconnue"))
    embed = discord.Embed(
        title="🍽️ Menu CROUS",
        description=f"📅 **{date}**",
        color=discord.Color.orange(),
        timestamp=discord.utils.utcnow(),
    )
    used_length = len(embed.title) + len(embed.description)
    hidden_categories = 0

    for meal in menu_meals(menu):
        meal_name = str(meal.get("type", "Repas")).capitalize()
        for category in categories_for_meal(meal):
            dishes = category_dishes(category)
            if not dishes:
                continue
            if len(embed.fields) >= MAX_EMBED_FIELDS:
                hidden_categories += 1
                continue

            name = _truncate(f"📋 {meal_name} — {_category_name(category)}", 256)
            remaining_length = MAX_EMBED_LENGTH - used_length - len(name)
            if remaining_length < 2:
                hidden_categories += 1
                continue
            value = _truncate(
                "\n".join(f"• {dish}" for dish in dishes), min(1024, remaining_length)
            )
            embed.add_field(name=name, value=value, inline=False)
            used_length += len(name) + len(value)

    footer = "🏫 Restaurant universitaire | Données via CROUStillantAPI"
    if hidden_categories:
        footer = f"{footer} | {hidden_categories} catégorie(s) non affichée(s)"
    embed.set_footer(text=footer)
    return embed


def _category_name(category: Category) -> str:
    label = str(category.get("libelle", "Catégorie"))
    return label.replace("Salle des ", "").replace(" - ", " | ")


def _truncate(value: str, limit: int) -> str:
    if len(value) <= limit:
        return value
    return f"{value[: limit - 1].rstrip()}…"


async def setup(bot: KirtaPBot) -> None:
    await bot.add_cog(Crous(bot))
