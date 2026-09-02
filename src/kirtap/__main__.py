import asyncio
import logging

import discord

from .bot import KirtaPBot
from .config import ConfigurationError, load_settings
from .logging import configure_logging

logger = logging.getLogger(__name__)


async def run() -> None:
    settings = load_settings()
    configure_logging(settings.log_level)
    async with KirtaPBot(settings) as bot:
        await bot.start(settings.discord_token)


def main() -> None:
    try:
        asyncio.run(run())
    except ConfigurationError as error:
        raise SystemExit(f"Configuration invalide : {error}") from error
    except KeyboardInterrupt:
        logger.info("Bot stopped")
    except discord.LoginFailure:
        logger.error("Invalid Discord token")
        raise SystemExit(1) from None
    except Exception:
        logger.exception("Bot stopped after an unexpected error")
        raise SystemExit(1) from None
