from datetime import timedelta
from typing import Any

import discord
from discord import app_commands
from discord.ext import commands

from ..bot import KirtaPBot
from ..lunch import Restaurant

POLL_DURATION = timedelta(hours=1)


class Midi(commands.Cog):
    def __init__(self, bot: KirtaPBot) -> None:
        self.bot = bot

    @commands.hybrid_group(
        name="midi", invoke_without_command=True, help="Organise le choix du midi."
    )
    async def midi(self, context: commands.Context[Any]) -> None:
        await _reply(
            context, "Utilisez `midi ajouter`, `midi liste`, `midi retirer` ou `midi lancer`."
        )

    @midi.command(name="ajouter", help="Ajoute un restaurant à la liste.")
    @app_commands.describe(nom="Nom du restaurant", lien="Lien Google Maps ou site du restaurant")
    async def ajouter(
        self, context: commands.Context[Any], nom: str, lien: str | None = None
    ) -> None:
        guild = _require_guild(context)
        if guild is None:
            return
        try:
            restaurant = await self.bot.lunch_store.add_restaurant(guild.id, nom, lien)
        except ValueError as error:
            await _reply(context, str(error))
            return
        await _reply(context, f"Ajouté : {restaurant.name}")

    @midi.command(name="liste", help="Affiche les restaurants proposés.")
    async def liste(self, context: commands.Context[Any]) -> None:
        guild = _require_guild(context)
        if guild is None:
            return
        restaurants = await self.bot.lunch_store.list_restaurants(guild.id)
        if not restaurants:
            await _reply(context, "La liste est vide.")
            return
        await _reply(context, embed=restaurants_embed(restaurants))

    @midi.command(name="retirer", help="Retire un restaurant de la liste.")
    @app_commands.describe(numero="Numéro affiché par /midi liste")
    async def retirer(self, context: commands.Context[Any], numero: int) -> None:
        guild = _require_guild(context)
        if guild is None:
            return
        restaurant = await self.bot.lunch_store.remove_restaurant(guild.id, numero)
        if restaurant is None:
            await _reply(context, "Restaurant introuvable.")
            return
        await _reply(context, f"Retiré : {restaurant.name}")

    @midi.command(name="lancer", help="Lance le vote dans ce salon.")
    @commands.bot_has_permissions(send_polls=True)
    @app_commands.checks.bot_has_permissions(send_polls=True)
    async def lancer(self, context: commands.Context[Any]) -> None:
        guild = _require_guild(context)
        if guild is None:
            return
        restaurants = await self.bot.lunch_store.list_restaurants(guild.id)
        if len(restaurants) < 2:
            await _reply(context, "Ajoutez au moins deux restaurants avant de lancer le vote.")
            return
        await context.send(poll=restaurant_poll(restaurants))
        await self.bot.lunch_store.remove_restaurants(guild.id, restaurants)


def restaurants_embed(restaurants: list[Restaurant]) -> discord.Embed:
    lines = []
    for restaurant in restaurants:
        name = f"[{restaurant.name}]({restaurant.link})" if restaurant.link else restaurant.name
        lines.append(f"{restaurant.position}. {name}")
    return discord.Embed(title="Restaurants proposés", description="\n".join(lines))


def restaurant_poll(restaurants: list[Restaurant]) -> discord.Poll:
    poll = discord.Poll(question="On mange où ?", duration=POLL_DURATION, multiple=False)
    for restaurant in restaurants:
        poll.add_answer(text=restaurant.name)
    return poll


async def _reply(
    context: commands.Context[Any],
    content: str | None = None,
    *,
    embed: discord.Embed | None = None,
) -> None:
    if context.interaction is not None:
        await context.send(content, embed=embed, ephemeral=True)
    else:
        await context.send(content, embed=embed, delete_after=20)


def _require_guild(context: commands.Context[Any]) -> discord.Guild | None:
    if context.guild is not None:
        return context.guild
    return None


async def setup(bot: KirtaPBot) -> None:
    await bot.add_cog(Midi(bot))
