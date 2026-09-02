import logging
from typing import Any

import aiohttp
import discord
from discord import app_commands
from discord.ext import commands

from .config import Settings

logger = logging.getLogger(__name__)

EXTENSIONS = (
    "kirtap.cogs.general",
    "kirtap.cogs.moderation",
    "kirtap.cogs.crous",
    "kirtap.cogs.fun",
)


class KirtaPBot(commands.Bot):
    def __init__(self, settings: Settings) -> None:
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(
            command_prefix=settings.command_prefix,
            intents=intents,
            help_command=None,
            case_insensitive=True,
        )
        self.settings = settings
        self.http_session: aiohttp.ClientSession | None = None
        self.tree.on_error = self.on_app_command_error

    async def setup_hook(self) -> None:
        self.http_session = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10))
        for extension in EXTENSIONS:
            await self.load_extension(extension)
            logger.info("Loaded extension %s", extension)

        commands_synced = await self.tree.sync()
        logger.info("Synced %s application command(s)", len(commands_synced))

    async def close(self) -> None:
        if self.http_session is not None and not self.http_session.closed:
            await self.http_session.close()
        await super().close()

    async def on_ready(self) -> None:
        await self.change_presence(activity=discord.Game(name=self.settings.status_message))
        logger.info("%s connected to %s guild(s)", self.user, len(self.guilds))

    async def on_command_error(
        self, context: commands.Context[Any], error: commands.CommandError
    ) -> None:
        if isinstance(error, commands.CommandNotFound):
            return
        if isinstance(error, commands.MissingPermissions):
            message = "❌ Vous n'avez pas les permissions nécessaires pour cette commande."
        elif isinstance(error, commands.BotMissingPermissions):
            message = "❌ Je n'ai pas les permissions nécessaires pour cette commande."
        elif isinstance(error, commands.MissingRequiredArgument):
            message = f"❌ Argument manquant : `{error.param.name}`."
        elif isinstance(error, commands.BadArgument):
            message = "❌ Argument invalide. Vérifiez votre syntaxe."
        elif isinstance(error, commands.CommandOnCooldown):
            message = f"⏰ Commande en cooldown. Réessayez dans {error.retry_after:.1f}s."
        else:
            logger.error(
                "Unhandled prefix command error",
                exc_info=(type(error), error, error.__traceback__),
            )
            message = "❌ Une erreur inattendue s'est produite."
        await context.send(message)

    async def on_app_command_error(
        self, interaction: discord.Interaction[Any], error: app_commands.AppCommandError
    ) -> None:
        original = error.original if isinstance(error, app_commands.CommandInvokeError) else error
        if isinstance(original, (app_commands.MissingPermissions, commands.MissingPermissions)):
            message = "❌ Vous n'avez pas les permissions nécessaires pour cette commande."
        elif isinstance(
            original, (app_commands.BotMissingPermissions, commands.BotMissingPermissions)
        ):
            message = "❌ Je n'ai pas les permissions nécessaires pour cette commande."
        elif isinstance(original, (app_commands.TransformerError, commands.BadArgument)):
            message = "❌ Argument invalide. Vérifiez votre syntaxe."
        elif isinstance(original, app_commands.CommandOnCooldown):
            message = f"⏰ Commande en cooldown. Réessayez dans {original.retry_after:.1f}s."
        else:
            logger.error(
                "Unhandled application command error",
                exc_info=(type(error), error, error.__traceback__),
            )
            message = "❌ Une erreur inattendue s'est produite."

        if interaction.response.is_done():
            await interaction.followup.send(message, ephemeral=True)
        else:
            await interaction.response.send_message(message, ephemeral=True)
