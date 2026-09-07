import logging
from datetime import date, datetime, time
from typing import Any

import discord
from discord import app_commands
from discord.ext import commands, tasks

from ..bot import KirtaPBot
from ..crous import PARIS_TIMEZONE
from ..presence import (
    PresenceAssignment,
    PresenceClass,
    assignment_for_date,
    next_assignment,
    parse_periods,
    rotation_slots,
)

logger = logging.getLogger(__name__)


class Presence(commands.Cog):
    def __init__(self, bot: KirtaPBot) -> None:
        self.bot = bot
        if self._automation_configured:
            self.presence_task.start()
        else:
            logger.info(
                "Presence automation is disabled because its channel or role is not configured"
            )

    def cog_unload(self) -> None:
        self.presence_task.cancel()

    async def cog_check(self, context: commands.Context[Any]) -> bool:
        role_id = self.bot.settings.presence_access_role_id
        if (
            role_id is None
            or not isinstance(context.author, discord.Member)
            or not any(role.id == role_id for role in context.author.roles)
        ):
            raise commands.MissingRole(role_id or 0)
        return True

    async def interaction_check(self, interaction: discord.Interaction[Any]) -> bool:
        role_id = self.bot.settings.presence_access_role_id
        if (
            role_id is None
            or not isinstance(interaction.user, discord.Member)
            or not any(role.id == role_id for role in interaction.user.roles)
        ):
            raise app_commands.MissingRole(role_id or 0)
        return True

    @commands.hybrid_group(
        name="presence",
        invoke_without_command=True,
        help="Configure et consulte la rotation des fiches de présence.",
    )
    async def presence(self, context: commands.Context[Any]) -> None:
        await context.send(
            "Utilisez `presence classe_creer`, `presence membre_ajouter`, "
            "`presence periodes_definir`, `presence statut` ou `presence topo`."
        )

    @presence.command(name="classe_creer", help="Crée une classe pour la rotation de présence.")
    @commands.has_permissions(administrator=True)
    @app_commands.default_permissions(administrator=True)
    @app_commands.checks.has_permissions(administrator=True)
    @app_commands.describe(classe="Exemple : M2 SIL")
    async def classe_creer(self, context: commands.Context[Any], classe: str) -> None:
        guild = self._guild_from_context(context)
        try:
            presence_class = await self.bot.presence_store.ensure_class(guild.id, classe)
        except ValueError as error:
            await context.send(f"❌ {error}", ephemeral=context.interaction is not None)
            return
        await context.send(f"Classe **{presence_class.name}** prête pour la configuration.")

    @presence.command(name="membre_ajouter", help="Ajoute un élève à la fin de la rotation.")
    @commands.has_permissions(administrator=True)
    @app_commands.default_permissions(administrator=True)
    @app_commands.checks.has_permissions(administrator=True)
    @app_commands.describe(classe="Nom de la classe", membre="Élève à ajouter")
    async def membre_ajouter(
        self, context: commands.Context[Any], classe: str, membre: discord.Member
    ) -> None:
        presence_class = await self._get_class(context, classe)
        if presence_class is None:
            return
        added = await self.bot.presence_store.add_member(presence_class, membre.id)
        if not added:
            await context.send(
                f"{membre.mention} est déjà dans la rotation de **{presence_class.name}**."
            )
            return
        await context.send(
            f"{membre.mention} est ajouté à la rotation de **{presence_class.name}**."
        )

    @presence.command(name="membre_retirer", help="Retire un élève de la rotation.")
    @commands.has_permissions(administrator=True)
    @app_commands.default_permissions(administrator=True)
    @app_commands.checks.has_permissions(administrator=True)
    @app_commands.describe(classe="Nom de la classe", membre="Élève à retirer")
    async def membre_retirer(
        self, context: commands.Context[Any], classe: str, membre: discord.Member
    ) -> None:
        presence_class = await self._get_class(context, classe)
        if presence_class is None:
            return
        removed = await self.bot.presence_store.remove_member(presence_class, membre.id)
        if not removed:
            await context.send(
                f"{membre.mention} n'est pas dans la rotation de **{presence_class.name}**."
            )
            return
        await context.send(
            f"{membre.mention} est retiré de la rotation de **{presence_class.name}**."
        )

    @presence.command(
        name="periodes_definir", help="Remplace le calendrier de formation d'une classe."
    )
    @commands.has_permissions(administrator=True)
    @app_commands.default_permissions(administrator=True)
    @app_commands.checks.has_permissions(administrator=True)
    @app_commands.describe(
        classe="Nom de la classe",
        periodes="Périodes séparées par un espace ou un retour à la ligne : AAAA-MM-JJ,AAAA-MM-JJ",
    )
    async def periodes_definir(
        self, context: commands.Context[Any], classe: str, *, periodes: str
    ) -> None:
        presence_class = await self._get_class(context, classe)
        if presence_class is None:
            return
        try:
            parsed_periods = parse_periods(periodes)
        except ValueError as error:
            await context.send(f"❌ {error}", ephemeral=context.interaction is not None)
            return
        await self.bot.presence_store.replace_periods(presence_class, parsed_periods)
        await context.send(
            f"Calendrier de **{presence_class.name}** enregistré avec "
            f"{len(parsed_periods)} période(s) de formation."
        )

    @presence.command(name="statut", help="Affiche les porteurs actuels et les prochains tours.")
    @app_commands.describe(classe="Laissez vide pour voir toutes les classes")
    async def statut(self, context: commands.Context[Any], classe: str | None = None) -> None:
        guild = self._guild_from_context(context)
        if classe:
            presence_class = await self._get_class(context, classe)
            classes = [presence_class] if presence_class is not None else []
        else:
            classes = await self.bot.presence_store.list_classes(guild.id)

        if not classes:
            await context.send("📋 Aucune classe de présence n'est configurée.")
            return

        today = datetime.now(PARIS_TIMEZONE).date()
        embed = discord.Embed(title="📋 Fiches de présence", color=discord.Color.blue())
        for presence_class in classes:
            if presence_class is None:
                continue
            assignment = assignment_for_date(presence_class, today)
            if assignment is not None:
                value = f"🟢 Porteur actuel : <@{assignment.holder_id}>"
            else:
                following = next_assignment(presence_class, today)
                value = (
                    f"🔵 Entreprise ou hors calendrier\nProchain tour : <@{following.holder_id}> "
                    f"le {following.slot.first_school_day.strftime('%d-%m-%Y')}"
                    if following is not None
                    else "⚪ Calendrier ou rotation incomplet"
                )
            embed.add_field(name=presence_class.name, value=value, inline=False)
        await context.send(embed=embed)

    @presence.command(name="topo", help="Affiche le calendrier, la rotation et les fiches prévues.")
    @app_commands.describe(classe="Laissez vide pour voir toutes les classes")
    async def topo(self, context: commands.Context[Any], classe: str | None = None) -> None:
        guild = self._guild_from_context(context)
        if classe:
            presence_class = await self._get_class(context, classe)
            classes = [presence_class] if presence_class is not None else []
        else:
            classes = await self.bot.presence_store.list_classes(guild.id)

        if not classes:
            await context.send("📋 Aucune classe de présence n'est configurée.")
            return

        if context.interaction:
            await context.defer()
        today = datetime.now(PARIS_TIMEZONE).date()
        for presence_class in classes:
            if presence_class is not None:
                await context.send(embed=_topo_embed(presence_class, today))

    @presence.command(name="sync", help="Synchronise immédiatement le rôle du porteur actuel.")
    @commands.has_permissions(administrator=True)
    @app_commands.default_permissions(administrator=True)
    @app_commands.checks.has_permissions(administrator=True)
    async def sync(self, context: commands.Context[Any]) -> None:
        if context.interaction:
            await context.defer(ephemeral=True)
        try:
            assignments = await self._synchronize_presence(send_notifications=True)
        except (discord.Forbidden, discord.HTTPException, ValueError) as error:
            logger.exception("Unable to synchronize presence roles")
            message = f"❌ Synchronisation impossible : {error}"
        else:
            message = f"Synchronisation terminée : {len(assignments)} porteur(s) actif(s)."

        await context.send(message, ephemeral=context.interaction is not None)

    @tasks.loop(time=time(hour=8, tzinfo=PARIS_TIMEZONE))
    async def presence_task(self) -> None:
        try:
            await self._synchronize_presence(send_notifications=True)
        except (discord.Forbidden, discord.HTTPException, ValueError):
            logger.exception("Unable to run scheduled presence synchronization")

    @presence_task.before_loop
    async def wait_until_ready(self) -> None:
        await self.bot.wait_until_ready()
        try:
            await self._synchronize_presence(send_notifications=True)
        except (discord.Forbidden, discord.HTTPException, ValueError):
            logger.exception("Unable to run initial presence synchronization")

    @property
    def _automation_configured(self) -> bool:
        settings = self.bot.settings
        return (
            settings.presence_channel_id is not None
            and settings.presence_carrier_role_id is not None
        )

    async def _get_class(
        self, context: commands.Context[Any], class_name: str
    ) -> PresenceClass | None:
        guild = self._guild_from_context(context)
        presence_class = await self.bot.presence_store.get_class(guild.id, class_name)
        if presence_class is None:
            await context.send(
                f"❌ La classe **{class_name}** n'existe pas. Créez-la avec `presence classe_creer`."
            )
        return presence_class

    @staticmethod
    def _guild_from_context(context: commands.Context[Any]) -> discord.Guild:
        if context.guild is None:
            raise commands.NoPrivateMessage()
        return context.guild

    async def _synchronize_presence(self, *, send_notifications: bool) -> list[PresenceAssignment]:
        channel = await self._notification_channel()
        guild = channel.guild
        role_id = self.bot.settings.presence_carrier_role_id
        if role_id is None:
            raise ValueError("PRESENCE_CARRIER_ROLE_ID n'est pas configuré.")
        role = guild.get_role(role_id)
        if role is None:
            raise ValueError("Le rôle de porteur configuré est introuvable sur ce serveur.")

        today = datetime.now(PARIS_TIMEZONE).date()
        classes = await self.bot.presence_store.list_classes(guild.id)
        assignments = [
            assignment
            for presence_class in classes
            if (assignment := assignment_for_date(presence_class, today)) is not None
        ]
        current_holders = {assignment.holder_id for assignment in assignments}
        previous_holders = await self.bot.presence_store.role_holders(guild.id)

        for user_id in previous_holders - current_holders:
            member = await self._fetch_member(guild, user_id)
            if member is not None and role in member.roles:
                await member.remove_roles(role, reason="Fin du tour de fiche de présence")
        for user_id in current_holders:
            member = await self._fetch_member(guild, user_id)
            if member is not None and role not in member.roles:
                await member.add_roles(role, reason="Nouveau porteur de fiche de présence")
        await self.bot.presence_store.replace_role_holders(guild.id, assignments)

        if send_notifications:
            for assignment in assignments:
                if assignment.slot.first_school_day != today:
                    continue
                if await self.bot.presence_store.notification_was_sent(
                    assignment.presence_class, assignment.slot
                ):
                    continue
                await channel.send(
                    f"📋 **Fiche de présence - {assignment.presence_class.name}**\n"
                    f"<@{assignment.holder_id}>, c'est ton tour. Pense à faire signer "
                    "la fiche et à la rendre chaque soir."
                )
                await self.bot.presence_store.mark_notification_sent(
                    assignment.presence_class, assignment.slot
                )
        return assignments

    async def _notification_channel(self) -> discord.TextChannel:
        channel_id = self.bot.settings.presence_channel_id
        if channel_id is None:
            raise ValueError("PRESENCE_CHANNEL_ID n'est pas configuré.")
        channel = self.bot.get_channel(channel_id)
        if channel is None:
            channel = await self.bot.fetch_channel(channel_id)
        if not isinstance(channel, discord.TextChannel):
            raise ValueError("PRESENCE_CHANNEL_ID doit désigner un salon textuel classique.")
        return channel

    @staticmethod
    async def _fetch_member(guild: discord.Guild, user_id: int) -> discord.Member | None:
        member = guild.get_member(user_id)
        if member is not None:
            return member
        try:
            return await guild.fetch_member(user_id)
        except discord.NotFound:
            logger.warning("Presence member %s is no longer in guild %s", user_id, guild.id)
            return None


def _topo_embed(presence_class: PresenceClass, today: date) -> discord.Embed:
    embed = discord.Embed(
        title=f"📋 Topo présence - {presence_class.name}",
        color=discord.Color.blue(),
    )
    assignment = assignment_for_date(presence_class, today)
    if assignment is not None:
        current_value = (
            f"🟢 Porteur : <@{assignment.holder_id}>\n"
            f"Tour commencé le {assignment.slot.first_school_day.strftime('%d-%m-%Y')}"
        )
    else:
        following = next_assignment(presence_class, today)
        current_value = (
            f"🔵 Pas de fiche active\nProchain porteur : <@{following.holder_id}> "
            f"le {following.slot.first_school_day.strftime('%d-%m-%Y')}"
            if following is not None
            else "⚪ Calendrier ou rotation incomplet"
        )
    embed.add_field(name="Fiche actuelle", value=current_value, inline=False)

    roster = [
        f"{position}. <@{user_id}>"
        for position, user_id in enumerate(presence_class.member_ids, start=1)
    ]
    embed.add_field(
        name="Ordre de rotation",
        value=_field_value(roster, "Aucun élève dans la rotation."),
        inline=False,
    )

    periods = [
        f"• {period.start.strftime('%d-%m-%Y')} -> {period.end.strftime('%d-%m-%Y')}"
        for period in presence_class.periods
    ]
    embed.add_field(
        name="Périodes de formation",
        value=_field_value(periods, "Aucune période enregistrée."),
        inline=False,
    )

    slots = rotation_slots(presence_class.periods)
    schedule = (
        [
            f"• {slot.first_school_day.strftime('%d-%m-%Y')} -> "
            f"<@{presence_class.member_ids[index % len(presence_class.member_ids)]}>"
            for index, slot in enumerate(slots)
        ]
        if presence_class.member_ids
        else []
    )
    embed.add_field(
        name="Planning des fiches",
        value=_field_value(schedule, "Ajoutez des élèves pour générer le planning."),
        inline=False,
    )
    return embed


def _field_value(lines: list[str], empty_message: str) -> str:
    if not lines:
        return empty_message

    value = ""
    hidden_lines = 0
    for position, line in enumerate(lines):
        candidate = f"{value}\n{line}" if value else line
        if len(candidate) > 1024:
            hidden_lines = len(lines) - position
            break
        value = candidate
    if hidden_lines:
        suffix = f"\n... et {hidden_lines} ligne(s) en plus"
        value = f"{value[: 1024 - len(suffix)]}{suffix}"
    return value


async def setup(bot: KirtaPBot) -> None:
    await bot.add_cog(Presence(bot))
