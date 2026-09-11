from typing import Any

import discord
from discord.ext import commands

from ..aura import AuraMove, random_aura_move


class Aura(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @commands.hybrid_command(name="aura", help="Tire un move aléatoire de battle d'aura.")
    async def aura(self, context: commands.Context[Any]) -> None:
        await context.send(embed=aura_embed(random_aura_move()))


def aura_embed(move: AuraMove) -> discord.Embed:
    embed = discord.Embed(
        title="Battle d'aura",
        description=f"**{move.name}**\n{move.description}",
        color=discord.Color.from_rgb(85, 118, 242),
    )
    embed.add_field(name="Aura gagnée", value=f"+{move.points}", inline=True)
    embed.set_footer(text="/aura pour tirer un autre move")
    return embed


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Aura(bot))
