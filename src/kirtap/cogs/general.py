import platform
import time
from typing import Any

import discord
from discord.ext import commands


class General(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @commands.hybrid_command(name="ping", help="Affiche la latence du bot.")
    async def ping(self, context: commands.Context[Any]) -> None:
        started_at = time.perf_counter()
        message = await context.send("🏓 Pong !")
        message_latency = round((time.perf_counter() - started_at) * 1000)
        api_latency = round(self.bot.latency * 1000)

        embed = discord.Embed(title="🏓 Pong !", color=discord.Color.green())
        embed.add_field(name="Latence du message", value=f"{message_latency} ms")
        embed.add_field(name="Latence API", value=f"{api_latency} ms")
        await message.edit(content=None, embed=embed)

    @commands.hybrid_command(
        name="info",
        aliases=["botinfo"],
        help="Affiche les informations du bot.",
    )
    async def info(self, context: commands.Context[Any]) -> None:
        owner_id = self.bot.settings.owner_id
        user = self.bot.user
        embed = discord.Embed(title="📊 Informations du bot", color=discord.Color.blue())
        embed.add_field(name="👑 Développeur", value=f"<@{owner_id}>" if owner_id else "Non défini")
        embed.add_field(name="📊 Serveurs", value=str(len(self.bot.guilds)))
        embed.add_field(
            name="👥 Utilisateurs",
            value=str(sum(guild.member_count or 0 for guild in self.bot.guilds)),
        )
        embed.add_field(name="🐍 Version Python", value=platform.python_version())
        embed.add_field(name="📚 Version discord.py", value=discord.__version__)
        if user is not None:
            embed.set_footer(text=f"Bot ID : {user.id}")
            if user.avatar is not None:
                embed.set_thumbnail(url=user.avatar.url)
        await context.send(embed=embed)

    @commands.command(name="help", help="Affiche l'aide des commandes.")
    async def help_command(
        self, context: commands.Context[Any], *, command_name: str | None = None
    ) -> None:
        if command_name:
            command = self.bot.get_command(command_name)
            if command is None:
                embed = discord.Embed(
                    title="❌ Erreur",
                    description=f"La commande `{command_name}` n'existe pas.",
                    color=discord.Color.red(),
                )
            else:
                usage = f"`{context.prefix}{command.name} {command.signature}`".rstrip()
                embed = discord.Embed(
                    title=f"Aide - {command.name}",
                    description=command.help or "Aucune description disponible.",
                    color=discord.Color.blue(),
                )
                if command.aliases:
                    embed.add_field(name="Aliases", value=", ".join(command.aliases), inline=False)
                embed.add_field(name="Utilisation", value=usage, inline=False)
        else:
            embed = discord.Embed(
                title="📋 Liste des commandes",
                description="Voici toutes les commandes disponibles.",
                color=discord.Color.blue(),
            )
            for cog_name, cog in self.bot.cogs.items():
                visible_commands = [
                    command.name for command in cog.get_commands() if not command.hidden
                ]
                if visible_commands:
                    embed.add_field(
                        name=f"📁 {cog_name}",
                        value=", ".join(f"`{command}`" for command in visible_commands),
                        inline=False,
                    )
            embed.set_footer(text=f"Utilisez {context.prefix}help <commande> pour plus de détails.")
        await context.send(embed=embed)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(General(bot))
