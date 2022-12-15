from __future__ import annotations

from difflib import SequenceMatcher
from typing import TYPE_CHECKING

import discord
from discord.ext import commands, vbu

from cogs import utils

if TYPE_CHECKING:
    from .template_edit import TemplateEdit


GC = utils.types.GuildContext


class TemplateCommands(vbu.Cog[vbu.Bot]):
    """
    This class should implement all of the commands associated with managing,
    creating, deleting, etc in regard to templates themselves.

    This includes the following commands/interactions:
    * template list
    * template delete
        * "are you sure?"
    * template describe
    * template create
    * template edit
        * set name
            * modal submission
        * set archive channel
            * select submission
        * set verification channel
            * select submission
        * set role
            * select submission
        * set max_profiles
        * set fields
        * set slash
    """

    @commands.group(
        application_command_meta=commands.ApplicationCommandMeta(),
    )
    async def template(
            self,
            _: GC):
        """
        A parent group for all of the template commands.
        """

        ...

    @template.command(
        name="list",
        application_command_meta=commands.ApplicationCommandMeta(),
    )
    @commands.defer()
    @vbu.i18n("profile")
    async def template_list(
            self,
            ctx: GC[discord.CommandInteraction]):
        """
        A list of all the templates created on your guild.
        """

        # Set up a list of templates
        template_format_zero = _(
            "\u2022 **{template_name}** (0 profiles)",
        )
        template_format_single = _(
            "\u2022 **{template_name}** ({profile_count} profile)",
        )
        template_format_plural = _(
            "\u2022 **{template_name}** ({profile_count} profiles)",
        )
        template_strings: list[str] = list()

        # Get all of the templates
        async with vbu.Database() as db:
            templates = await utils.Template.fetch_all_templates_for_guild(
                db,
                ctx.guild.id,
            )

            # Format them into a list
            for t in templates:
                user_profiles = await t.fetch_all_profiles(
                    db,
                    fetch_filled_fields=False,
                )
                profile_count = len(user_profiles)
                ts: str
                match profile_count:
                    case 0:
                        ts = template_format_zero
                    case 1:
                        ts = template_format_single
                    case _:
                        ts = template_format_plural
                template_strings.append(ts.format(
                    template_name=t.name,
                    profile_count=profile_count,
                ))

        # Output
        if template_strings:
            await ctx.interaction.followup.send(
                "\n".join(template_strings),
                allowed_mentions=discord.AllowedMentions.none(),
            )
        else:
            await ctx.interaction.followup.send(
                _("There are no created templates for this guild."),
                allowed_mentions=discord.AllowedMentions.none(),
            )

    @template.command(
        name="delete",
        application_command_meta=commands.ApplicationCommandMeta(
            options=[
                discord.ApplicationCommandOption(
                    name="template",
                    type=discord.ApplicationCommandOptionType.string,
                    description=(
                        "The name of the template that you want to delete."
                    ),
                    autocomplete=True,
                )
            ],
        ),
    )
    @vbu.i18n("profile")
    async def template_delete(
            self,
            ctx: GC[discord.CommandInteraction],
            template: str):
        """
        Delete one of your templates.
        """

        # This command will spawn the buttons that allow a moderator to delete
        # a template. This command does not directly delete the template.

        # See if the user has permission to run this command
        cog: TemplateEdit = self.bot.get_cog("TemplateEdit")  # type: ignore
        if not cog.check_template_edit_permissions(ctx.interaction):
            return await ctx.interaction.response.send_message(
                _(
                    (
                        "Only users with the **manage guild** permission "
                        "can manage templates."
                    )
                ),
                ephemeral=True,
            )

        # Try and get the template object
        async with vbu.Database() as db:
            try:
                template_o = await utils.Template.fetch_template_by_id(
                    db,
                    template,
                )
            except:
                template_o = await utils.Template.fetch_template_by_name(
                    db,
                    ctx.guild.id,
                    template,
                )

        # Tell them if the template doesn't exist
        if not template_o:
            return await ctx.interaction.response.send_message(
                _(
                    (
                        "There's no template with the name "
                        "**{template_name}** in this guild."
                    )
                ).format(template_name=template),
                allowed_mentions=discord.AllowedMentions.none(),
                ephemeral=True,
            )

        # Send them buttons asking if they want to delete
        components = discord.ui.MessageComponents(
            discord.ui.ActionRow(
                discord.ui.Button(
                    # TRANSLATORS: Text appearing on a button.
                    label=_("Yes"),
                    custom_id=(
                        f"TEMPLATE_DELETE CONFIRM "
                        f"{utils.uuid.encode(template_o.id)}"
                    ),
                    style=discord.ButtonStyle.danger,
                ),
            ),
        )
        await ctx.interaction.response.send_message(
            _(
                (
                    "Are you sure you want to delete the "
                    "template **{template_name}**?"
                )
            ).format(template_name=template_o.name),
            components=components,
            allowed_mentions=discord.AllowedMentions.none(),
            ephemeral=True,
        )

    @template.command(
        name="create",
        application_command_meta=commands.ApplicationCommandMeta(
            options=[
                discord.ApplicationCommandOption(
                    name="name",
                    description=(
                        "The name of the template that you want to create."
                    ),
                    type=discord.ApplicationCommandOptionType.string,
                    required=True,
                ),
            ],
        ),
    )
    @vbu.i18n("profile")
    async def template_create(
            self,
            ctx: GC[discord.CommandInteraction],
            name: str):
        """
        Create a new template for your guild.
        """

        # Check that the name is valid
        cog: TemplateEdit = self.bot.get_cog("TemplateEdit")  # type: ignore
        if not cog.check_template_name(name):
            return await ctx.interaction.response.send_message(
                (
                    _("The name **{template_name}** is not valid.")
                    .format(template_name=name)
                ),
                allowed_mentions=discord.AllowedMentions.none(),
                ephemeral=True,
            )

        # Run some checks
        async with vbu.Database() as db:

            # Check that the name isn't already in use
            template = await utils.Template.fetch_template_by_name(
                db,
                ctx.guild.id,
                name,
            )
            if template:
                return await ctx.interaction.response.send_message(
                    _("That template name is already in use."),
                    ephemeral=True,
                )

            # Check that they're not at the template limit
            all_templates = await utils.Template.fetch_all_templates_for_guild(
                db,
                ctx.guild.id,
                fetch_fields=False,
            )
            perks = await utils.GuildPerks.fetch(
                db,
                ctx.guild.id,
            )
            if len(all_templates) >= perks.max_template_count:
                error = _(
                    (
                        "You are at the maximum amount of templates "
                        "allowed for this guild. "
                    )
                )
                upsell = _(
                    (
                        "To get access more templates, you can donate via the "
                        "{donate_command_button} command."
                    )
                ).format(donate_command_button="/donate")  # TODO: mention command
                if perks.is_premium:
                    message = error
                else:
                    message = error + upsell
                return await ctx.interaction.response.send_message(
                    message,
                    ephemeral=True,
                )

            # Create the new template
            template = utils.Template(
                id=None,
                name=name,
                guild_id=ctx.guild.id,
                max_profile_count=0,
            )
            await template.update(db)

        # Send them the template edit components
        cog: TemplateEdit = self.bot.get_cog("TemplateEdit")  # type: ignore
        kwargs = cog.get_template_edit_components(
            ctx.interaction,
            template,
        )
        return await ctx.interaction.response.send_message(**kwargs)

    @template.command(
        name="edit",
        application_command_meta=commands.ApplicationCommandMeta(
            options=[
                discord.ApplicationCommandOption(
                    name="name",
                    description=(
                        "The name of the template that you want to edit."
                    ),
                    type=discord.ApplicationCommandOptionType.string,
                    required=True,
                    autocomplete=True,
                ),
            ],
        ),
    )
    @vbu.i18n("profile")
    async def template_edit(
            self,
            ctx: GC[discord.CommandInteraction],
            name: str):
        """
        Edit an already existing template.
        """

        # Run some checks
        async with vbu.Database() as db:

            # Check that the name isn't already in use
            template = await utils.Template.fetch_template_by_name(
                db,
                ctx.guild.id,
                name,
            )
            if not template:
                return await ctx.interaction.response.send_message(
                    _("You don't have a template with that name."),
                    ephemeral=True,
                )

        # Send them the template edit components
        cog: TemplateEdit = self.bot.get_cog("TemplateEdit")  # type: ignore
        kwargs = cog.get_template_edit_components(
            ctx.interaction,
            template,
        )
        return await ctx.interaction.response.send_message(**kwargs)

    @template_edit.autocomplete  # type: ignore
    @template_delete.autocomplete  # type: ignore
    async def template_name_autocomplete(
            self,
            ctx,
            interaction: discord.AutocompleteInteraction):
        """
        Send the user back a list of templates for their guild.
        """

        async with vbu.Database() as db:
            templates = await utils.Template.fetch_all_templates_for_guild(
                db,
                guild_id=interaction.guild.id,  # type: ignore
                fetch_fields=False,
            )
        options = [
            discord.ApplicationCommandOptionChoice(name=i.name)
            for i in templates
        ]
        current_val = ""
        try:
            current_val = [i.value for i in interaction.options][0]
        except IndexError:
            pass
        options.sort(
            key=lambda c: (
                SequenceMatcher(
                    None,
                    c.name.lower(),
                    (current_val or "").lower(),
                ).quick_ratio()
            ),
            reverse=True,
        )
        await interaction.response.send_autocomplete(options)


def setup(bot: vbu.Bot):
    x = TemplateCommands(bot)
    bot.add_cog(x)
