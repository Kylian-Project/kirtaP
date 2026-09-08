from collections.abc import Awaitable, Callable, Iterable
from typing import Any

import discord

from ..bot import KirtaPBot
from ..presence import PresenceClass, parse_periods, rotation_slots

SynchronizeCallback = Callable[[discord.Guild], Awaitable[int]]
TopoCallback = Callable[[PresenceClass], discord.Embed]

MAX_SELECT_OPTIONS = 25


def classes_embed(classes: Iterable[PresenceClass]) -> discord.Embed:
    configured_classes = list(classes)
    embed = discord.Embed(title="Classes de présence", color=discord.Color.blurple())
    if not configured_classes:
        embed.description = "Aucune classe n'est encore configurée."
        return embed

    for presence_class in configured_classes[:MAX_SELECT_OPTIONS]:
        channel = f"<#{presence_class.channel_id}>" if presence_class.channel_id else "Non défini"
        embed.add_field(
            name=presence_class.name,
            value=(
                f"Salon : {channel}\n"
                f"Élèves : {len(presence_class.member_ids)}\n"
                f"Périodes : {len(presence_class.periods)}"
            ),
            inline=True,
        )

    remaining = len(configured_classes) - MAX_SELECT_OPTIONS
    if remaining > 0:
        embed.set_footer(text=f"{remaining} classe(s) supplémentaire(s) ne sont pas affichées.")
    return embed


def setup_embed(classes: Iterable[PresenceClass]) -> discord.Embed:
    embed = classes_embed(classes)
    embed.title = "Configuration des fiches de présence"
    if embed.description is None:
        embed.description = "Sélectionnez une classe pour la modifier ou créez-en une nouvelle."
    embed.set_footer(text="Les actions de configuration sont réservées aux administrateurs.")
    return embed


def class_setup_embed(presence_class: PresenceClass, *, notice: str | None = None) -> discord.Embed:
    embed = discord.Embed(
        title=f"Configuration - {presence_class.name}",
        description=notice or "Modifiez la classe avec les sélecteurs et les boutons ci-dessous.",
        color=discord.Color.blurple(),
    )
    embed.add_field(
        name="Salon de notification",
        value=f"<#{presence_class.channel_id}>" if presence_class.channel_id else "Non défini",
        inline=False,
    )
    embed.add_field(
        name=f"Élèves ({len(presence_class.member_ids)})",
        value=_member_list(presence_class.member_ids),
        inline=False,
    )
    embed.add_field(
        name=f"Périodes de formation ({len(presence_class.periods)})",
        value=_period_list(presence_class),
        inline=False,
    )
    embed.add_field(
        name="Tours prévus",
        value=str(len(rotation_slots(presence_class.periods))),
        inline=True,
    )
    return embed


class PresenceSetupView(discord.ui.View):
    def __init__(
        self,
        bot: KirtaPBot,
        *,
        classes: Iterable[PresenceClass] = (),
        synchronize: SynchronizeCallback,
        topo: TopoCallback,
        persistent: bool = False,
    ) -> None:
        super().__init__(timeout=None if persistent else 900)
        self.bot = bot
        self.synchronize = synchronize
        self.topo = topo
        self.add_item(ClassSelect(self, classes, enabled_when_empty=persistent))

    async def interaction_check(self, interaction: discord.Interaction[Any]) -> bool:
        return await _check_administrator(self.bot, interaction)

    @discord.ui.button(
        label="Créer une classe",
        style=discord.ButtonStyle.primary,
        custom_id="presence_setup:create_class",
        row=1,
    )
    async def create_class(
        self, interaction: discord.Interaction[Any], _: discord.ui.Button[Any]
    ) -> None:
        await interaction.response.send_modal(
            CreateClassModal(self.bot, synchronize=self.synchronize, topo=self.topo)
        )


class ClassSelect(discord.ui.Select[Any]):
    def __init__(
        self,
        setup_view: PresenceSetupView,
        classes: Iterable[PresenceClass],
        *,
        enabled_when_empty: bool,
    ) -> None:
        self.setup_view = setup_view
        configured_classes = list(classes)
        options = [
            discord.SelectOption(
                label=presence_class.name[:100],
                value=str(presence_class.id),
                description=_class_description(presence_class),
            )
            for presence_class in configured_classes[:MAX_SELECT_OPTIONS]
        ]
        if not options:
            options = [discord.SelectOption(label="Aucune classe disponible", value="0")]
        super().__init__(
            custom_id="presence_setup:select_class",
            placeholder="Choisir une classe",
            options=options,
            disabled=not configured_classes and not enabled_when_empty,
            row=0,
        )

    async def callback(self, interaction: discord.Interaction[Any]) -> None:
        if interaction.guild is None:
            await interaction.response.send_message(
                "Cette action doit être utilisée sur un serveur.", ephemeral=True
            )
            return
        try:
            class_id = int(self.values[0])
        except (IndexError, ValueError):
            await interaction.response.send_message("Classe invalide.", ephemeral=True)
            return

        presence_class = await self.setup_view.bot.presence_store.get_class_by_id(
            interaction.guild.id, class_id
        )
        if presence_class is None:
            await interaction.response.send_message(
                "Cette classe n'existe plus. Relancez `presence setup`.", ephemeral=True
            )
            return
        await interaction.response.send_message(
            embed=class_setup_embed(presence_class),
            view=PresenceClassSetupView(
                self.setup_view.bot,
                presence_class.id,
                synchronize=self.setup_view.synchronize,
                topo=self.setup_view.topo,
            ),
            ephemeral=True,
        )


class PresenceClassSetupView(discord.ui.View):
    def __init__(
        self,
        bot: KirtaPBot,
        class_id: int,
        *,
        synchronize: SynchronizeCallback,
        topo: TopoCallback,
    ) -> None:
        super().__init__(timeout=900)
        self.bot = bot
        self.class_id = class_id
        self.synchronize = synchronize
        self.topo = topo
        self.add_item(ChannelPicker(self))
        self.add_item(MemberPicker(self, add=True))
        self.add_item(MemberPicker(self, add=False))

    async def interaction_check(self, interaction: discord.Interaction[Any]) -> bool:
        return await _check_administrator(self.bot, interaction)

    async def get_class(self, interaction: discord.Interaction[Any]) -> PresenceClass | None:
        if interaction.guild is None:
            return None
        return await self.bot.presence_store.get_class_by_id(interaction.guild.id, self.class_id)

    async def refresh(self, interaction: discord.Interaction[Any], notice: str) -> None:
        presence_class = await self.get_class(interaction)
        if presence_class is None:
            await interaction.response.edit_message(
                content="Cette classe n'existe plus.", embed=None, view=None
            )
            return
        await interaction.response.edit_message(
            embed=class_setup_embed(presence_class, notice=notice),
            view=PresenceClassSetupView(
                self.bot,
                self.class_id,
                synchronize=self.synchronize,
                topo=self.topo,
            ),
        )

    @discord.ui.button(label="Calendrier", style=discord.ButtonStyle.secondary, row=4)
    async def edit_calendar(
        self, interaction: discord.Interaction[Any], _: discord.ui.Button[Any]
    ) -> None:
        presence_class = await self.get_class(interaction)
        if presence_class is None:
            await interaction.response.send_message("Cette classe n'existe plus.", ephemeral=True)
            return
        await interaction.response.send_modal(
            CalendarModal(
                self.bot,
                presence_class,
                synchronize=self.synchronize,
                topo=self.topo,
            )
        )

    @discord.ui.button(label="Voir le topo", style=discord.ButtonStyle.secondary, row=4)
    async def show_topo(
        self, interaction: discord.Interaction[Any], _: discord.ui.Button[Any]
    ) -> None:
        presence_class = await self.get_class(interaction)
        if presence_class is None:
            await interaction.response.send_message("Cette classe n'existe plus.", ephemeral=True)
            return
        await interaction.response.send_message(embed=self.topo(presence_class), ephemeral=True)

    @discord.ui.button(label="Synchroniser", style=discord.ButtonStyle.primary, row=4)
    async def synchronize_now(
        self, interaction: discord.Interaction[Any], _: discord.ui.Button[Any]
    ) -> None:
        if interaction.guild is None:
            await interaction.response.send_message(
                "Cette action doit être utilisée sur un serveur.", ephemeral=True
            )
            return
        await interaction.response.defer(ephemeral=True, thinking=True)
        try:
            assignments = await self.synchronize(interaction.guild)
        except (discord.Forbidden, discord.HTTPException, ValueError) as error:
            await interaction.followup.send(f"Synchronisation impossible : {error}", ephemeral=True)
            return
        await interaction.followup.send(
            f"Synchronisation terminée : {assignments} porteur(s) actif(s).", ephemeral=True
        )


class ChannelPicker(discord.ui.ChannelSelect[Any]):
    def __init__(self, editor_view: PresenceClassSetupView) -> None:
        self.editor_view = editor_view
        super().__init__(
            custom_id="presence_setup:select_channel",
            channel_types=[discord.ChannelType.text],
            placeholder="Définir le salon de notification",
            row=1,
        )

    async def callback(self, interaction: discord.Interaction[Any]) -> None:
        presence_class = await self.editor_view.get_class(interaction)
        if presence_class is None:
            await interaction.response.send_message("Cette classe n'existe plus.", ephemeral=True)
            return
        try:
            channel = self.values[0]
        except IndexError:
            await interaction.response.send_message("Salon invalide.", ephemeral=True)
            return
        await self.editor_view.bot.presence_store.set_channel(presence_class, channel.id)
        await self.editor_view.refresh(interaction, f"Salon défini sur <#{channel.id}>.")


class MemberPicker(discord.ui.UserSelect[Any]):
    def __init__(self, editor_view: PresenceClassSetupView, *, add: bool) -> None:
        self.editor_view = editor_view
        self.add = add
        super().__init__(
            custom_id="presence_setup:add_member" if add else "presence_setup:remove_member",
            placeholder="Ajouter un élève" if add else "Retirer un élève",
            row=2 if add else 3,
        )

    async def callback(self, interaction: discord.Interaction[Any]) -> None:
        presence_class = await self.editor_view.get_class(interaction)
        if presence_class is None:
            await interaction.response.send_message("Cette classe n'existe plus.", ephemeral=True)
            return
        try:
            member = self.values[0]
        except IndexError:
            await interaction.response.send_message("Élève invalide.", ephemeral=True)
            return

        if self.add:
            changed = await self.editor_view.bot.presence_store.add_member(
                presence_class, member.id
            )
            notice = (
                f"{member.mention} a été ajouté à la rotation."
                if changed
                else f"{member.mention} est déjà dans la rotation."
            )
        else:
            changed = await self.editor_view.bot.presence_store.remove_member(
                presence_class, member.id
            )
            notice = (
                f"{member.mention} a été retiré de la rotation."
                if changed
                else f"{member.mention} n'est pas dans la rotation."
            )
        await self.editor_view.refresh(interaction, notice)


class CreateClassModal(discord.ui.Modal):
    def __init__(
        self, bot: KirtaPBot, *, synchronize: SynchronizeCallback, topo: TopoCallback
    ) -> None:
        super().__init__(title="Créer une classe")
        self.bot = bot
        self.synchronize = synchronize
        self.topo = topo
        self.name = discord.ui.TextInput(label="Nom de la classe", max_length=100)
        self.add_item(self.name)

    async def on_submit(self, interaction: discord.Interaction[Any]) -> None:
        if not await _check_administrator(self.bot, interaction):
            return
        if interaction.guild is None:
            await interaction.response.send_message(
                "Cette action doit être utilisée sur un serveur.", ephemeral=True
            )
            return
        try:
            presence_class = await self.bot.presence_store.ensure_class(
                interaction.guild.id, self.name.value
            )
        except ValueError as error:
            await interaction.response.send_message(str(error), ephemeral=True)
            return
        await interaction.response.send_message(
            embed=class_setup_embed(presence_class, notice="Classe créée."),
            view=PresenceClassSetupView(
                self.bot,
                presence_class.id,
                synchronize=self.synchronize,
                topo=self.topo,
            ),
            ephemeral=True,
        )


class CalendarModal(discord.ui.Modal):
    def __init__(
        self,
        bot: KirtaPBot,
        presence_class: PresenceClass,
        *,
        synchronize: SynchronizeCallback,
        topo: TopoCallback,
    ) -> None:
        super().__init__(title=f"Calendrier - {presence_class.name}"[:45])
        self.bot = bot
        self.class_id = presence_class.id
        self.synchronize = synchronize
        self.topo = topo
        self.periods = discord.ui.TextInput(
            label="Périodes de formation",
            placeholder="2026-09-07,2026-09-25 2026-10-12,2026-10-16",
            default=_period_input(presence_class),
            style=discord.TextStyle.paragraph,
            max_length=4000,
        )
        self.add_item(self.periods)

    async def on_submit(self, interaction: discord.Interaction[Any]) -> None:
        if not await _check_administrator(self.bot, interaction):
            return
        if interaction.guild is None:
            await interaction.response.send_message(
                "Cette action doit être utilisée sur un serveur.", ephemeral=True
            )
            return
        presence_class = await self.bot.presence_store.get_class_by_id(
            interaction.guild.id, self.class_id
        )
        if presence_class is None:
            await interaction.response.send_message("Cette classe n'existe plus.", ephemeral=True)
            return
        try:
            periods = parse_periods(self.periods.value)
        except ValueError as error:
            await interaction.response.send_message(str(error), ephemeral=True)
            return
        await self.bot.presence_store.replace_periods(presence_class, periods)
        updated_class = await self.bot.presence_store.get_class_by_id(
            interaction.guild.id, self.class_id
        )
        if updated_class is None:
            await interaction.response.send_message("Cette classe n'existe plus.", ephemeral=True)
            return
        await interaction.response.send_message(
            embed=class_setup_embed(updated_class, notice="Calendrier enregistré."),
            view=PresenceClassSetupView(
                self.bot,
                updated_class.id,
                synchronize=self.synchronize,
                topo=self.topo,
            ),
            ephemeral=True,
        )


async def _check_administrator(bot: KirtaPBot, interaction: discord.Interaction[Any]) -> bool:
    member = interaction.user
    role_id = bot.settings.presence_access_role_id
    allowed = (
        isinstance(member, discord.Member)
        and member.guild_permissions.administrator
        and role_id is not None
        and any(role.id == role_id for role in member.roles)
    )
    if allowed:
        return True
    if not interaction.response.is_done():
        await interaction.response.send_message(
            "Vous n'avez pas les permissions nécessaires pour cette action.", ephemeral=True
        )
    return False


def _class_description(presence_class: PresenceClass) -> str:
    return (f"{len(presence_class.member_ids)} élève(s), {len(presence_class.periods)} période(s)")[
        :100
    ]


def _member_list(member_ids: tuple[int, ...]) -> str:
    if not member_ids:
        return "Aucun élève dans la rotation."
    return _truncate_lines(
        [f"{position}. <@{member_id}>" for position, member_id in enumerate(member_ids, 1)]
    )


def _period_list(presence_class: PresenceClass) -> str:
    if not presence_class.periods:
        return "Aucune période de formation."
    return _truncate_lines(
        [
            f"{period.start.strftime('%d-%m-%Y')} - {period.end.strftime('%d-%m-%Y')}"
            for period in presence_class.periods
        ]
    )


def _period_input(presence_class: PresenceClass) -> str:
    return " ".join(
        f"{period.start.isoformat()},{period.end.isoformat()}" for period in presence_class.periods
    )


def _truncate_lines(lines: list[str], limit: int = 1024) -> str:
    value = ""
    for position, line in enumerate(lines):
        candidate = f"{value}\n{line}" if value else line
        if len(candidate) > limit:
            remaining = len(lines) - position
            suffix = f"\n... et {remaining} élément(s) en plus"
            return f"{value[: limit - len(suffix)]}{suffix}"
        value = candidate
    return value
