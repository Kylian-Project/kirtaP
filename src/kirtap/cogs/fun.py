import random
from pathlib import Path
from typing import Any

import discord
from discord import app_commands
from discord.ext import commands

IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".gif"}


class Fun(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.assets_directory = Path(__file__).parents[1] / "assets" / "caillou"
        self.last_image: Path | None = None

    @commands.hybrid_command(
        name="caillou",
        aliases=["pierre", "rock"],
        help="Raconte l'histoire épique du caillou du voisin du Y.",
        hidden=True,
    )
    @commands.has_permissions(administrator=True)
    @app_commands.default_permissions(administrator=True)
    @app_commands.checks.has_permissions(administrator=True)
    async def caillou(self, context: commands.Context[Any]) -> None:
        image_path = self._random_image()
        if image_path is None:
            await context.send("❌ Aucune image de caillou disponible ! 😢")
            return

        embed = discord.Embed(
            title="🪨 L'INCIDENT DU CAILLOU VOLANT 🚜",
            description="",
            color=discord.Color.from_rgb(139, 69, 19),
            timestamp=discord.utils.utcnow(),
        )
        embed.add_field(name="⚠️ Niveau de danger", value="🔴🔴🔴🔴🔴 EXTRÊME")
        embed.add_field(name="😱 Peur du Y", value="999/10")
        embed.add_field(name="🚜 Puissance du tracteur", value="OVER 9000 !")
        embed.set_footer(text="Histoire véridique | Les cailloux sont dangereux")

        file = discord.File(image_path, filename=image_path.name)
        embed.set_image(url=f"attachment://{image_path.name}")
        await context.send(file=file, embed=embed)

    def _random_image(self) -> Path | None:
        if not self.assets_directory.is_dir():
            return None
        images = sorted(
            path
            for path in self.assets_directory.iterdir()
            if path.is_file() and path.suffix.lower() in IMAGE_SUFFIXES
        )
        if not images:
            return None

        choices = [image for image in images if image != self.last_image]
        selected = random.choice(choices or images)
        self.last_image = selected
        return selected


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Fun(bot))
