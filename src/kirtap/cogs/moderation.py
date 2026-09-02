from typing import Any

import discord
from discord import app_commands
from discord.ext import commands


class Moderation(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @commands.hybrid_command(
        name="clear",
        aliases=["purge"],
        help="Supprime entre 1 et 100 messages.",
    )
    @commands.has_permissions(manage_messages=True)
    @commands.bot_has_permissions(manage_messages=True)
    @app_commands.default_permissions(manage_messages=True)
    @app_commands.checks.has_permissions(manage_messages=True)
    @app_commands.checks.bot_has_permissions(manage_messages=True)
    @app_commands.describe(amount="Nombre de messages à supprimer (1 à 100)")
    async def clear(self, context: commands.Context[Any], amount: int = 1) -> None:
        if not 1 <= amount <= 100:
            await context.send(
                "❌ Le nombre doit être compris entre 1 et 100.",
                ephemeral=context.interaction is not None,
            )
            return

        command_message_count = 0 if context.interaction else 1
        try:
            deleted = await context.channel.purge(limit=amount + command_message_count)
        except discord.Forbidden:
            await context.send("❌ Je n'ai pas la permission de supprimer des messages.")
            return
        except discord.HTTPException:
            await context.send("❌ Erreur lors de la suppression des messages.")
            return

        deleted_count = max(0, len(deleted) - command_message_count)
        embed = discord.Embed(
            title="🧹 Messages supprimés",
            description=f"{deleted_count} messages ont été supprimés par {context.author.mention}.",
            color=discord.Color.green(),
        )
        if context.interaction:
            await context.send(embed=embed, ephemeral=True)
        else:
            await context.send(embed=embed, delete_after=5)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Moderation(bot))
