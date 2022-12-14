from difflib import SequenceMatcher

import discord
from discord.ext import commands, vbu
import regex as re  # must be external module

from cogs import utils


GC = utils.types.GuildContext


def _t(b: str | discord.Locale, a: str) -> str:
    """
    Translate function for non-commands.
    """

    return vbu.translation(b, "profile").gettext(a)


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

    # TEMPLATE COMMAND UTILS

    def check_permissions(self, interaction: discord.Interaction) -> bool:
        """
        Checks if the user running the interaction is
        * someone with the manage_guild permission
        * an owner of the bot
        """

        if interaction.user.id in self.bot.owner_ids:
            return True
        return interaction.permissions.manage_guild

    @staticmethod
    def check_template_name(name: str) -> bool:
        """
        Returns whether or not a template's name is valid for use on Discord.
        """

        command_name_pattern = r"^[-_\p{L}\p{N}\p{sc=Deva}\p{sc=Thai}]{1,32}$"
        return all((
            len(name) <= 30,
            " " not in name,
            "\n" not in name,
            re.match(command_name_pattern, name, re.UNICODE),
        ))

    @staticmethod
    def check_field_name(name: str) -> bool:
        """
        Returns whether or not a field's name is valid.
        """

        return all((
            len(name) <= 45,
        ))

    async def update_template(
            self,
            interaction: discord.Interaction,
            template_id: str,
            **kwargs) -> utils.Template:
        """
        Update a template with given kwargs, and then update the original
        message associated with the interaction with the updated template
        embed.

        Params
        -------
        interaction : discord.Interaction
            A non-responded to interaction.
        template_id : str
            The ID of the template that you want to update.
        **kwargs
            Any attribute of the template that you want to update, and the
            value that you want to set it to.
        """

        # Get and update the template
        async with vbu.Database() as db:
            template = await utils.Template.fetch_template_by_id(
                db,
                template_id,
            )
            assert template, (
                "The template was deleted while the "
                "user was editing an attribute."
            )
            template = await template.update(db, **kwargs)

        # And send the new template to the user
        kwargs = self.get_template_edit_components(
            interaction,
            template,
        )
        del kwargs['ephemeral']
        try:
            await interaction.response.edit_message(**kwargs)
        except discord.InteractionResponded:
            await interaction.edit_original_message(**kwargs)

        # Return new template
        return template

    async def update_field(
            self,
            interaction: discord.Interaction,
            field_id: str,
            **kwargs) -> None:
        """
        Update a template with given kwargs, and then update the original
        message associated with the interaction with the updated template
        embed.

        Params
        -------
        interaction : discord.Interaction
            A non-responded to interaction.
        field_id : str
            The ID of the field that you want to update.
        **kwargs
            Any attribute of the field that you want to update, and the
            value that you want to set it to.
        """

        # Get and update the field
        async with vbu.Database() as db:
            field = await utils.Field.fetch_field_by_id(
                db,
                field_id,
            )
            assert field, (
                "The field was deleted while the "
                "user was editing an attribute."
            )
            field = await field.update(db, **kwargs)

        # And send the new template to the user
        kwargs = self.get_field_edit_components(
            interaction,
            field,
        )
        kwargs.pop("ephemeral", False)
        try:
            await interaction.response.edit_message(**kwargs)
        except discord.InteractionResponded:
            await interaction.edit_original_message(**kwargs)

    @vbu.i18n("profile")
    def get_template_edit_components(
            self,
            interaction: discord.Interaction,
            template: utils.Template):
        """
        Get the components associated with editing a template.
        """

        # Create the buttons to be added to the edit embed
        buttons = [
            discord.ui.Button(
                # TRANSLATORS: Text appearing on a button that edits the
                # attribute when clicked.
                label=_("Name"),
                custom_id=(
                    f"TEMPLATE_EDIT NAME {utils.uuid.encode(template.id)} "
                    f"{template.name}"
                ),
            ),
                discord.ui.Button(
                    # TRANSLATORS: Text appearing on a button that edits the
                    # attribute when clicked.
                    label=_("Archive channel"),
                    custom_id=(
                        f"TEMPLATE_EDIT ARCHIVE {utils.uuid.encode(template.id)}"
                    ),
                ),
            discord.ui.Button(
                # TRANSLATORS: Text appearing on a button that edits the
                # attribute when clicked.
                label=_("Verification channel"),
                custom_id=(
                    f"TEMPLATE_EDIT VERIFICATION {utils.uuid.encode(template.id)}"
                ),
            ),
            discord.ui.Button(
                # TRANSLATORS: Text appearing on a button that edits the
                # attribute when clicked.
                label=_("Given role"),
                custom_id=(
                    f"TEMPLATE_EDIT ROLE {utils.uuid.encode(template.id)}"
                ),
            ),
            discord.ui.Button(
                # TRANSLATORS: Text appearing on a button that edits the
                # attribute when clicked.
                label=_("Max profiles"),
                custom_id=(
                    f"TEMPLATE_EDIT MAX_PROFILES "
                    f"{utils.uuid.encode(template.id)} "
                    f"{template.max_profile_count}"
                ),
            ),
            discord.ui.Button(
                # TRANSLATORS: Text appearing on a button that lets users
                # edit fields
                label=_("Fields"),
                custom_id=(
                    f"TEMPLATE_EDIT FIELDS {utils.uuid.encode(template.id)}"
                ),
            ),
            discord.ui.Button(
                # TRANSLATORS: Text appearing on a button
                label=_("Update template command"),
                custom_id=(
                    f"TEMPLATE_EDIT SLASH {utils.uuid.encode(template.id)} "
                    f"{template.application_command_id or 0}"
                ),
            ),
        ]

        # Custom styling if template is disabled
        if template.max_profile_count <= 0:
            buttons.append(
                discord.ui.Button(
                    # TRANSLATORS: Text appearing on a button; non-action,
                    # just informative
                    label=_("Template disabled"),
                    disabled=True,
                    style=discord.ButtonStyle.danger,
                    custom_id="_",
                )
            )
            profile_button = [
                i
                for i in buttons
                if "MAX_PROFILES" in i.custom_id
            ][0]
            profile_button.style = discord.ButtonStyle.danger

        # Make components
        components = discord.ui.MessageComponents.add_buttons_with_rows(
            *buttons,
            discord.ui.Button(
                # TRANSLATORS: Text appearing on a button
                label=_("Done"),
                style=discord.ButtonStyle.success,
                custom_id="TEMPLATE_EDIT DONE",
            ),
        )

        # Define what we want to send
        kwargs = {
            "content": _(
                "Select which part of the template you want to change."
            ),
            "embeds": [
                template.build_embed(self.bot, interaction)
            ],
            "components": components,
            "ephemeral": True,
        }
        return kwargs

    @vbu.i18n("profile")
    def get_field_edit_components(
            self,
            interaction: discord.Interaction,
            field: utils.Field):
        """
        Get the components associated with editing a field.
        """

        # Show them the attributes they can edit
        buttons = [
            discord.ui.Button(
                # TRANSLATORS: Text appearing on a button that edits the
                # attribute when clicked.
                label=_("Name"),
                custom_id=(
                    f"FIELD_EDIT NAME {utils.uuid.encode(field.id)} "
                    f"{field.name}"
                ),
                style=(
                    discord.ButtonStyle.secondary
                    if
                        field.name != ""
                    else
                        discord.ButtonStyle.primary
                ),
            ),
            discord.ui.Button(
                # TRANSLATORS: Text appearing on a button that edits the
                # attribute when clicked.
                label=_("Prompt"),
                custom_id=(
                    f"FIELD_EDIT PROMPT {utils.uuid.encode(field.id)}"
                ),
                style=(
                    discord.ButtonStyle.secondary
                    if
                        field.prompt != ""
                    else
                        discord.ButtonStyle.primary
                ),
            ),
            discord.ui.Button(
                # TRANSLATORS: Text appearing on a button that edits the
                # attribute when clicked.
                label=_("Optional"),
                custom_id=(
                    f"FIELD_EDIT OPTIONAL {utils.uuid.encode(field.id)}"
                ),
            ),
            discord.ui.Button(
                # TRANSLATORS: Text appearing on a button that edits the
                # attribute when clicked.
                label=_("Type"),
                custom_id=(
                    f"FIELD_EDIT TYPE "
                    f"{utils.uuid.encode(field.id)} "
                    f"{utils.uuid.encode(field.template_id)}"
                ),
            ),
            discord.ui.Button(
                # TRANSLATORS: Text appearing on a button to be pressed when
                # the user is done editing.
                label=_("Done"),
                custom_id=(
                    "TEMPLATE_EDIT FIELDS "
                    f"{utils.uuid.encode(field.template_id)}"
                ),
                style=discord.ButtonStyle.success,
            ),
            discord.ui.Button(
                # TRANSLATORS: Text appearing on a button to be pressed when
                # the user wants to delete a field
                label=_("Delete"),
                custom_id=(
                    f"FIELD_EDIT DELETE {utils.uuid.encode(field.id)}"
                ),
                style=discord.ButtonStyle.danger,
            ),
        ]
        components = (
            discord
            .ui
            .MessageComponents
            .add_buttons_with_rows(*buttons)
        )

        # Define what we want to send
        kwargs = {
            "content": _(
                "Select which part of the field you want to change."
            ),
            "embeds": [
                field.build_embed(self.bot, interaction)
            ],
            "components": components,
            "ephemeral": True,
        }
        return kwargs

    @staticmethod
    def get_profile_application_command(
            name: str,
            description: str | None = None) -> discord.ApplicationCommand:
        """
        Create an application command with the given name, and subcommands
        for create, edit, and delete.
        """

        # Set description
        description = description or name

        # Name option for reuse
        NAME_OPTION = discord.ApplicationCommandOption(
            name="name",
            description="The name of the profile.",
            type=discord.ApplicationCommandOptionType.string,
            autocomplete=True,
            name_localizations={
                # TRANSLATORS: name for an option in a command;
                # eg "character get [name]"
                i: _t(i, "name")
                for i in discord.Locale
            },
            description_localizations={
                # TRANSLATORS: description for an option in a
                # command; eg "character get [name]"
                i: _t(i, "The name of the profile.")
                for i in discord.Locale
            },
        )

        # Create command
        command = discord.ApplicationCommand(
            name=name.lower(),
            description=description,
            type=discord.ApplicationCommandType.chat_input,
            options=[

                # Create
                discord.ApplicationCommandOption(
                    name="create",
                    description="Create a new profile.",
                    type=discord.ApplicationCommandOptionType.subcommand,
                    name_localizations={
                        # TRANSLATORS: subcommand name, eg "profile create"
                        i: _t(i, "create")
                        for i in discord.Locale
                    },
                    description_localizations={
                        # TRANSLATORS: description of a command
                        i: _t(i, "Create a new profile.")
                        for i in discord.Locale
                    },
                ),

                # Delete
                discord.ApplicationCommandOption(
                    name="delete",
                    description="Delete one of your profiles.",
                    type=discord.ApplicationCommandOptionType.subcommand,
                    name_localizations={
                        # TRANSLATORS: subcommand name, eg "profile delete"
                        i: _t(i, "delete")
                        for i in discord.Locale
                    },
                    description_localizations={
                        # TRANSLATORS: description of a command
                        i: _t(i, "Delete one of your profiles.")
                        for i in discord.Locale
                    },
                ),

                # Get
                discord.ApplicationCommandOption(
                    name="get",
                    description="Display a created profile.",
                    type=discord.ApplicationCommandOptionType.subcommand,
                    name_localizations={
                        # TRANSLATORS: subcommand name, eg "profile get"
                        i: _t(i, "get")
                        for i in discord.Locale
                    },
                    description_localizations={
                        # TRANSLATORS: description of a command
                        i: _t(i, "Display a created profile")
                        for i in discord.Locale
                    },
                    options=[
                        discord.ApplicationCommandOption(
                            name="user",
                            description=(
                                "The person whose profile you want to get."
                            ),
                            type=discord.ApplicationCommandOptionType.user,
                            required=False,
                            name_localizations={
                                # TRANSLATORS: parameter name in "profile get
                                # [user]"
                                i: _t(i, "user")
                                for i in discord.Locale
                            },
                            description_localizations={
                                # TRANSLATORS: parameter name descrtiption for
                                # user in "profile get [user]"
                                i: _t(
                                    i,
                                    "The person whose profile you want to get.",
                                )
                                for i in discord.Locale
                            },
                        ),
                    ],
                ),

                # Edit
                discord.ApplicationCommandOption(
                    name="edit",
                    description="Edit one of your profiles.",
                    type=discord.ApplicationCommandOptionType.subcommand,
                    name_localizations={
                        # TRANSLATORS: subcommand name, eg "profile edit"
                        i: _t(i, "edit")
                        for i in discord.Locale
                    },
                    description_localizations={
                        # TRANSLATORS: description of a command
                        i: _t(i, "Edit one of your profiles.")
                        for i in discord.Locale
                    },
                    options=[
                        NAME_OPTION,
                    ],
                ),
            ]
        )
        return command

    # TEMPLATE COMMANDS

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
        if not self.check_permissions(ctx.interaction):
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
        if not self.check_template_name(name):
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
            perks = await utils.get_perks_for_guild(
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
                        "To get access more templates, use the "
                        "{donate_command_button} command."
                    )
                ).format(donate_command_button="/donate")
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
        kwargs = self.get_template_edit_components(
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
        kwargs = self.get_template_edit_components(
            ctx.interaction,
            template,
        )
        return await ctx.interaction.response.send_message(**kwargs)

    @template_edit.autocomplete
    @template_delete.autocomplete
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

    # TEMPLATE EDIT COMPONENT LISTENERS

    @vbu.Cog.listener("on_component_interaction")  # TEMPLATE_DELETE [action] [TID]
    @vbu.i18n("profile")
    async def template_delete_component_listener(
            self,
            interaction: discord.ComponentInteraction):
        """
        Listens for components being interacted with, and deals with the ones
        relating to deleting templates.
        """

        # Make sure we should deal with it
        if not interaction.custom_id.startswith("TEMPLATE_DELETE"):
            return

        # Check they still have permissions to press these buttons
        if not self.check_permissions(interaction):
            return await interaction.response.edit_message(
                content=_(
                    (
                        "Only users with the **manage guild** permission "
                        "can manage templates."
                    )
                ),
            )

        # See if they said to delete or not
        action, encoded_template_id = interaction.custom_id.split(" ")[1:]
        if action == "CANCEL":
            return await interaction.response.edit_message(
                content=_("Cancelled template deletion :)"),
                components=None,
            )
        template_id = utils.uuid.decode(encoded_template_id)

        # They said to delete, get the template data
        async with vbu.Database() as db:
            template = await utils.Template.fetch_template_by_id(
                db,
                template_id,
            )

            # Make sure the template wasn't already deleted
            if template is None:
                return await interaction.response.edit_message(
                    content=_("That template has already been deleted."),
                    components=None,
                )

            # Mark the template as deleted
            template_name = template.name
            await template.update(
                db,
                deleted=True,
                name=f"{template.id} {template.name}",
            )

        # Tell them we're done
        await interaction.response.edit_message(
            content=(
                _("Deleted the template **{template_name}**.")
                .format(template_name=template_name)
            ),
            allowed_mentions=discord.AllowedMentions.none(),
            components=None,
        )

    @vbu.Cog.listener("on_component_interaction")  # TEMPLATE_EDIT NAME [TID] [CV]
    @vbu.i18n("profile")
    async def template_edit_name_component_listener(
            self,
            interaction: discord.ComponentInteraction):
        """
        Listens for edit template name button to be pressed.
        Sends modal.
        """

        # Get current name and template ID
        if not interaction.custom_id.startswith("TEMPLATE_EDIT NAME"):
            return
        encoded_template_id, current_name = interaction.custom_id.split(" ")[2:]

        # Build and send modal
        modal = discord.ui.Modal(
            # TRANSLATORS: Max 45 characters; title of modal
            title=_("Set template name")[:45],
            custom_id=f"TEMPLATE_SET NAME {encoded_template_id}",
            components=[
                discord.ui.ActionRow(
                    discord.ui.InputText(
                        # TRANSLATORS: Max 45 characters; label of text input
                        label=_("What do you want to set the name to?")[:45],
                        style=discord.TextStyle.short,
                        min_length=1,
                        max_length=30,
                        required=True,
                        value=current_name,
                    ),
                ),
            ],
        )
        await interaction.response.send_modal(modal)

    @vbu.Cog.listener("on_modal_submit")  # TEMPLATE_SET NAME [TID]
    @vbu.i18n("profile")
    async def template_edit_name_modal_listener(
            self,
            interaction: discord.ModalInteraction):
        """
        Listens for edit template name modal to be submitted.
        Sets template name.
        """

        # Get the ID of the template
        if not interaction.custom_id.startswith("TEMPLATE_SET NAME"):
            return
        encoded_template_id = interaction.custom_id.split(" ")[2]
        template_id = utils.uuid.decode(encoded_template_id)

        # Get the new name from the components
        new_template_name: str = (
            interaction
            .components[0]
            .components[0]  # type: ignore - not an issue for modals
            .value
        )

        # Check that the name is valid
        if not self.check_template_name(new_template_name):
            # Send new message so they can still edit other attrs
            return await interaction.response.send_message(
                (
                    _("The name **{template_name}** is not valid.")
                    .format(template_name=new_template_name)
                ),
                allowed_mentions=discord.AllowedMentions.none(),
                ephemeral=True,
            )

        # Check that the name isn't already in use
        async with vbu.Database() as db:
            templates = await utils.Template.fetch_all_templates_for_guild(
                db,
                interaction.guild_id,
                fetch_fields=False,
            )
        name_in_use = [
            i
            for i in templates
            if i.id != template_id
            and i.name.casefold() == new_template_name.casefold()
        ]
        if name_in_use:
            return await interaction.response.send_message(
                _(
                    "That template name is already in use. "
                    "Please provide another one."
                ),
                ephemeral=True,
            )

        # Get and update the template
        await interaction.response.defer_update()
        template = await self.update_template(
            interaction,
            template_id,
            name=new_template_name,
        )

        # Edit application command
        assert isinstance(interaction.guild, discord.Guild), "Guild must exist"
        await interaction.guild.edit_application_command(
            discord.Object(template.application_command_id),
            name=template.name.casefold(),
        )

    @vbu.Cog.listener("on_component_interaction")  # TEMPLATE_EDIT ARCHIVE [TID] [CV]
    @vbu.i18n("profile")
    async def template_edit_archive_component_listener(
            self,
            interaction: discord.ComponentInteraction):
        """
        Listens for edit template archive channel button to be pressed.
        Sends dropdown.
        """

        # Get current name and template ID
        if not interaction.custom_id.startswith("TEMPLATE_EDIT ARCHIVE"):
            return
        encoded_template_id = interaction.custom_id.split(" ")[2]

        # Send a channel dropdown
        components = discord.ui.MessageComponents(
            discord.ui.ActionRow(
                discord.ui.ChannelSelectMenu(
                    custom_id=f"TEMPLATE_SET ARCHIVE {encoded_template_id}",
                    channel_types=[
                        discord.ChannelType.news,
                        discord.ChannelType.text,
                    ],
                    min_values=0,
                    max_values=1,
                ),
            ),
            discord.ui.ActionRow(
                discord.ui.Button(
                    # TRANSLATORS: Text appearing on a button; clears selection
                    label=_("Clear"),
                    style=discord.ButtonStyle.danger,
                    custom_id=(
                        f"TEMPLATE_SET ARCHIVE {encoded_template_id} CLEAR"
                    ),
                ),
            ),
        )
        await interaction.response.edit_message(
            content=_("What do you want to set the archive channel to?"),
            embeds=[],
            components=components,
        )

    @vbu.Cog.listener("on_component_interaction")  # TEMPLATE_SET ARCHIVE [TID]
    @vbu.i18n("profile")
    async def template_edit_archive_dropdown_listener(
            self,
            interaction: discord.ComponentInteraction):
        """
        Listens for edit template archive dropdown to be pressed.
        Changes archive channel.
        """

        # See if we should be here
        if not interaction.custom_id.startswith("TEMPLATE_SET ARCHIVE"):
            return

        # See if we should be clearing the value
        clear: bool
        try:
            encoded_template_id, d = interaction.custom_id.split(" ")[2:]
            clear = True
        except ValueError:
            encoded_template_id = interaction.custom_id.split(" ")[2]
            clear = False

        # Get the template ID
        template_id = utils.uuid.decode(encoded_template_id)

        # Get the value that we want to set the archive channel to
        new_archive_channel_id: str | None
        if clear:
            new_archive_channel_id = None
        else:
            new_archive_channel_id = str(list(
                interaction
                .resolved
                .channels
                .keys())[0])

        # Get and update the template
        await self.update_template(
            interaction,
            template_id,
            archive_channel_id=new_archive_channel_id,
        )

    @vbu.Cog.listener("on_component_interaction")  # TEMPLATE_EDIT VERIFICATION [TID] [CV]
    @vbu.i18n("profile")
    async def template_edit_verification_component_listener(
            self,
            interaction: discord.ComponentInteraction):
        """
        Listens for edit template verification channel button to be pressed.
        Sends dropdown.
        """

        # Get current name and template ID
        if not interaction.custom_id.startswith("TEMPLATE_EDIT VERIFICATION"):
            return
        encoded_template_id = interaction.custom_id.split(" ")[2]

        # Send a channel dropdown
        components = discord.ui.MessageComponents(
            discord.ui.ActionRow(
                discord.ui.ChannelSelectMenu(
                    custom_id=f"TEMPLATE_SET VERIFICATION {encoded_template_id}",
                    channel_types=[
                        discord.ChannelType.news,
                        discord.ChannelType.text,
                    ],
                    min_values=0,
                    max_values=1,
                ),
            ),
            discord.ui.ActionRow(
                discord.ui.Button(
                    # TRANSLATORS: Text appearing on a button; clears selection
                    label=_("Clear"),
                    style=discord.ButtonStyle.danger,
                    custom_id=(
                        f"TEMPLATE_SET VERIFICATION {encoded_template_id} CLEAR"
                    ),
                ),
            ),
        )
        await interaction.response.edit_message(
            content=_("What do you want to set the verification channel to?"),
            embeds=[],
            components=components,
        )

    @vbu.Cog.listener("on_component_interaction")  # TEMPLATE_SET VERIFICATION [TID]
    @vbu.i18n("profile")
    async def template_edit_verification_dropdown_listener(
            self,
            interaction: discord.ComponentInteraction):
        """
        Listens for edit template verification dropdown to be pressed.
        Changes verification channel.
        """

        # See if we should be here
        if not interaction.custom_id.startswith("TEMPLATE_SET VERIFICATION"):
            return

        # See if we should be clearing the value
        clear: bool
        try:
            encoded_template_id, d = interaction.custom_id.split(" ")[2:]
            clear = True
        except ValueError:
            encoded_template_id = interaction.custom_id.split(" ")[2]
            clear = False

        # Get the template ID
        template_id = utils.uuid.decode(encoded_template_id)

        # Get the value that we want to set the archive channel to
        new_verification_channel_id: str | None
        if clear:
            new_verification_channel_id = None
        else:
            new_verification_channel_id = str(list(
                interaction
                .resolved
                .channels
                .keys())[0])

        # Get and update the template
        await self.update_template(
            interaction,
            template_id,
            verification_channel_id=new_verification_channel_id,
        )

    @vbu.Cog.listener("on_component_interaction")  # TEMPLATE_EDIT ROLE [TID] [CV]
    @vbu.i18n("profile")
    async def template_edit_role_component_listener(
            self,
            interaction: discord.ComponentInteraction):
        """
        Listens for edit template role channel button to be pressed.
        Sends dropdown.
        """

        # Get current name and template ID
        if not interaction.custom_id.startswith("TEMPLATE_EDIT ROLE"):
            return
        encoded_template_id = interaction.custom_id.split(" ")[2]

        # Send a channel dropdown
        components = discord.ui.MessageComponents(
            discord.ui.ActionRow(
                discord.ui.RoleSelectMenu(
                    custom_id=f"TEMPLATE_SET ROLE {encoded_template_id}",
                    min_values=0,
                    max_values=1,
                ),
            ),
            discord.ui.ActionRow(
                discord.ui.Button(
                    # TRANSLATORS: Text appearing on a button; clears selection
                    label=_("Clear"),
                    style=discord.ButtonStyle.danger,
                    custom_id=(
                        f"TEMPLATE_SET ROLE {encoded_template_id} CLEAR"
                    ),
                ),
            ),
        )
        await interaction.response.edit_message(
            content=_(
                "What role do you want people to get profile verification?"
            ),
            embeds=[],
            components=components,
        )

    @vbu.Cog.listener("on_component_interaction")  # TEMPLATE_SET ROLE [TID]
    @vbu.i18n("profile")
    async def template_edit_role_dropdown_listener(
            self,
            interaction: discord.ComponentInteraction):
        """
        Listens for edit template role dropdown to be pressed.
        Changes role.
        """

        # See if we should be here
        if not interaction.custom_id.startswith("TEMPLATE_SET ROLE"):
            return

        # See if we should be clearing the value
        clear: bool
        try:
            encoded_template_id, d = interaction.custom_id.split(" ")[2:]
            clear = True
        except ValueError:
            encoded_template_id = interaction.custom_id.split(" ")[2]
            clear = False

        # Get the template ID
        template_id = utils.uuid.decode(encoded_template_id)

        # Get the value that we want to set the archive channel to
        new_role_id: str | None
        if clear:
            new_role_id = None
        else:
            new_role_id = str(list(
                interaction
                .resolved
                .roles
                .keys())[0])

        # Get and update the template
        await self.update_template(
            interaction,
            template_id,
            role_id=new_role_id,
        )

    @vbu.Cog.listener("on_component_interaction")  # TEMPLATE_EDIT MAX_PROFILES [TID] [CV]
    @vbu.i18n("profile")
    async def template_edit_max_profiles_component_listener(
            self,
            interaction: discord.ComponentInteraction):
        """
        Listens for edit template max profiles button to be pressed.
        Sends modal.
        """

        # Get current name and template ID
        if not interaction.custom_id.startswith("TEMPLATE_EDIT MAX_PROFILES"):
            return
        encoded_template_id, current_limit = interaction.custom_id.split(" ")[2:]

        # Build and send modal
        modal = discord.ui.Modal(
            # TRANSLATORS: Max 45 characters; title of modal
            title=_("Set template name")[:45],
            custom_id=f"TEMPLATE_SET MAX_PROFILES {encoded_template_id}",
            components=[
                discord.ui.ActionRow(
                    discord.ui.InputText(
                        # TRANSLATORS: Max 45 characters; label of text input
                        label=_("How many profiles can users make?")[:45],
                        style=discord.TextStyle.short,
                        custom_id=f"TEMPLATE_DATA MAX_PROFILES {encoded_template_id}",
                        min_length=1,
                        max_length=4,
                        required=True,
                        value=current_limit,
                    ),
                ),
            ],
        )
        await interaction.response.send_modal(modal)

    @vbu.Cog.listener("on_modal_submit")  # TEMPLATE_SET MAX_PROFILES [TID]
    @vbu.i18n("profile")
    async def template_edit_max_profiles_modal_listener(
            self,
            interaction: discord.ModalInteraction):
        """
        Listens for edit template max profiles modal to be submitted.
        Sets template max profiles.
        """

        # Get the ID of the template
        if not interaction.custom_id.startswith("TEMPLATE_SET MAX_PROFILES"):
            return
        encoded_template_id = interaction.custom_id.split(" ")[2]
        template_id = utils.uuid.decode(encoded_template_id)

        # Get the new name from the components
        new_template_limit: str = (
            interaction
            .components[0]
            .components[0]  # type: ignore - not an issue for modals
            .value
        )

        # Check that the name is valid
        if not re.match(r"^\d+$", new_template_limit):
            # Send new message so they can still edit other attrs
            return await interaction.response.send_message(
                # TRANSLATORS: Error message when setting a max profile count
                _("The limit you have given is not valid."),
                allowed_mentions=discord.AllowedMentions.none(),
                ephemeral=True,
            )

        # Check that the limit is valid
        valid_new_template_limit = int(new_template_limit)
        self.logger.warning("TODO check profile limit max against guild")

        # Get and update the template
        await self.update_template(
            interaction,
            template_id,
            max_profile_count=valid_new_template_limit,
        )

    @vbu.Cog.listener("on_component_interaction")  # TEMPLATE_EDIT SLASH [TID]
    @vbu.i18n("profile")
    async def template_slash_component_listener(
            self,
            interaction: discord.ComponentInteraction):
        """
        Listens for edit template slash button to be pressed.
        """

        # Get the ID of the template
        if not interaction.custom_id.startswith("TEMPLATE_EDIT SLASH"):
            return
        encoded_template_id = interaction.custom_id.split(" ")[2]
        template_id = utils.uuid.decode(encoded_template_id)
        application_command_id = int(interaction.custom_id.split(" ")[3])

        # Get the template
        async with vbu.Database() as db:
            template = await utils.Template.fetch_template_by_id(
                db,
                template_id,
            )
            assert template

        # See if the command exists
        guild = interaction.guild
        assert isinstance(guild, discord.Guild)
        application_commands = await guild.fetch_application_commands()
        application_command = discord.utils.get(
            application_commands,
            id=application_command_id,
        )
        if application_command is None:
            try:
                application_command = await guild.create_application_command(
                    self.get_profile_application_command(
                        template.name,
                    )
                )
            except Exception as e:
                return await interaction.response.send_message(
                    "Failed to update template, {}".format(e),
                )
        else:
            await guild.edit_application_command(
                application_command,
                name=template.name.casefold(),
            )

        # Get and update the template
        await self.update_template(
            interaction,
            template_id,
            application_command_id=application_command.id,
        )
        await interaction.followup.send(
            _("Updated slash command."),
            ephemeral=True,
        )

    @vbu.Cog.listener("on_component_interaction")  # TEMPLATE_EDIT FIELDS [TID]
    @vbu.i18n("profile")
    async def template_edit_fields_component_listener(
            self,
            interaction: discord.ComponentInteraction):
        """
        Listens for edit template fields button to be pressed.
        Sends fields and edit buttons
        """

        # Get template ID
        if not interaction.custom_id.startswith("TEMPLATE_EDIT FIELDS"):
            return
        encoded_template_id = interaction.custom_id.split(" ")[2]
        template_id = utils.uuid.decode(encoded_template_id)

        # Get template
        async with vbu.Database() as db:
            template = await utils.Template.fetch_template_by_id(
                db,
                template_id,
            )
            assert template, (
                "The template was deleted while the "
                "user was editing an attribute."
            )

        # Get fields
        fields = template.field_list

        # Make buttons
        rows = []
        if fields:
            rows.append(discord.ui.ActionRow(
                discord.ui.SelectMenu(
                    custom_id=f"FIELD_EDIT SELECT {encoded_template_id}",
                    options=[
                        discord.ui.SelectOption(
                            label=f.name or f.id,
                            value=f.id,
                        )
                        for f in fields
                    ],
                ),
            ))
        components = discord.ui.MessageComponents(
            *rows,
            discord.ui.ActionRow(
                discord.ui.Button(
                    # TRANSLATORS: Text appearing on a button. Creates a new
                    # field for a template when clicked.
                    label=_("New"),
                    custom_id=f"FIELD_EDIT NEW {encoded_template_id}",
                    style=discord.ButtonStyle.primary,
                    disabled=len(fields) >= 10,
                ),
                discord.ui.Button(
                    label=_("Done"),
                    custom_id=f"FIELD_EDIT DONE {encoded_template_id}",
                    style=discord.ButtonStyle.success,
                ),
            ),
        )

        # Make an embed for all of the fields
        embeds = []
        if fields:
            embeds.append(
                vbu.Embed(
                    use_random_colour=True,
                    description="\n".join([
                        f"{f.index}. **{f.name}**"
                        if
                            f.name and f.prompt
                        else
                            f"{f.index}. ~~**{f.name}**~~"
                        if
                            f.name
                        else
                            f"{f.index}. ~~**{f.id}**~~"
                        for f in fields
                    ])
                )
            )

        # And send
        await interaction.response.edit_message(
            content=_("Select which field you want to edit."),
            embeds=embeds,
            components=components,
        )

    @vbu.Cog.listener("on_component_interaction")  # TEMPLATE_EDIT DONE
    @vbu.i18n("profile")
    async def template_edit_done_component_listener(
            self,
            interaction: discord.ComponentInteraction):
        """
        Listens for edit template done button to be pressed.
        Deletes message.
        """

        if not interaction.custom_id.startswith("TEMPLATE_EDIT DONE"):
            return
        await interaction.response.defer_update()
        await interaction.delete_original_message()

    # FIELD EDIT COMPONENT LISTENERS

    @vbu.Cog.listener("on_component_interaction")  # FIELD_EDIT DONE [TID]
    @vbu.i18n("profile")
    async def template_edit_fields_done_component_listener(
            self,
            interaction: discord.ComponentInteraction):
        """
        Listens for field select dropdown to be selected.
        Sends fields edit buttons
        """

        # Get field ID
        if not interaction.custom_id.startswith("FIELD_EDIT DONE"):
            return
        encoded_template_id = interaction.custom_id.split(" ")[2]
        template_id = utils.uuid.decode(encoded_template_id)

        # Get field
        async with vbu.Database() as db:
            template = await utils.Template.fetch_template_by_id(
                db,
                template_id,
            )
            assert template, (
                "The template was deleted while the "
                "user was editing an attribute."
            )

        # Send them the template edit components
        kwargs = self.get_template_edit_components(
            interaction,
            template,
        )
        del kwargs['ephemeral']
        return await interaction.response.edit_message(**kwargs)

    @vbu.Cog.listener("on_component_interaction")  # FIELD_EDIT SELECT [TID]
    @vbu.i18n("profile")
    async def template_edit_fields_select_component_listener(
            self,
            interaction: discord.ComponentInteraction):
        """
        Listens for field select dropdown to be selected.
        Sends fields edit buttons
        """

        # Get field ID
        if not interaction.custom_id.startswith("FIELD_EDIT SELECT"):
            return
        field_id = interaction.values[0]

        # Get field
        async with vbu.Database() as db:
            field = await utils.Field.fetch_field_by_id(
                db,
                field_id,
            )
            assert field, (
                "The field was deleted while the "
                "user was editing an attribute."
            )

        # Get kwargs
        kwargs = self.get_field_edit_components(
            interaction,
            field,
        )
        del kwargs['ephemeral']
        await interaction.response.edit_message(**kwargs)

    @vbu.Cog.listener("on_component_interaction")  # FIELD_EDIT NEW [TID]
    @vbu.i18n("profile")
    async def template_edit_fields_new_component_listener(
            self,
            interaction: discord.ComponentInteraction):
        """
        Create an ID for a new field, then send them back to the field edit
        segment.
        """

        # Get field ID
        if not interaction.custom_id.startswith("FIELD_EDIT NEW"):
            return
        encoded_template_id = interaction.custom_id.split(" ")[2]
        template_id = utils.uuid.decode(encoded_template_id)

        # Get current fields
        async with vbu.Database() as db:
            template = await utils.Template.fetch_template_by_id(
                db,
                template_id,
            )
            assert template

            # Get perks
            perks = await utils.get_perks_for_guild(
                db,
                interaction.guild.id,  # type: ignore
            )
            if len(template.fields) >= perks.max_field_count:
                error = _(
                    "You are at the maximum amount of fields "
                    "allowed for this template. "
                )
                upsell = _(
                    "To get access more fields, use the "
                    "{donate_command_button} command."
                ).format(donate_command_button="/donate")  # TODO: mention command
                if perks.is_premium:
                    message = error
                else:
                    message = error + upsell

                # Send new message so they can edit other attrs
                return await interaction.followup.send(
                    message,
                    ephemeral=True,
                )

        # Get a new ID
        field = utils.Field(
            id=None,
            name="",
            prompt="",
            index=len(template.all_fields),
            template_id=template_id,
        )

        # Save field
        async with vbu.Database() as db:
            await field.update(db)

        # And send
        kwargs = self.get_field_edit_components(
            interaction,
            field,
        )
        del kwargs['ephemeral']
        await interaction.response.edit_message(**kwargs)

    @vbu.Cog.listener("on_component_interaction")  # FIELD_EDIT DELETE [FID]
    @vbu.i18n("profile")
    async def template_edit_fields_delete_component_listener(
            self,
            interaction: discord.ComponentInteraction):
        """
        Listens for field delete button to be selected.
        Sends fields delete confirm buttons
        """

        # Get field ID
        if not interaction.custom_id.startswith("FIELD_EDIT DELETE"):
            return
        encoded_field_id = interaction.custom_id.split(" ")[2]
        field_id = utils.uuid.decode(encoded_field_id)

        # Try and get the template object
        async with vbu.Database() as db:
            field = await utils.Field.fetch_field_by_id(
                db,
                field_id,
            )
            assert field, (
                "The field was deleted while the "
                "user was editing an attribute."
            )

        # Send them buttons asking if they want to delete
        components = discord.ui.MessageComponents(
            discord.ui.ActionRow(
                discord.ui.Button(
                    # TRANSLATORS: Text appearing on a button.
                    label=_("Yes"),
                    custom_id=(
                        f"FIELD_DELETE CONFIRM {encoded_field_id} "
                        f"{utils.uuid.encode(field.template_id)}"
                    ),
                    style=discord.ButtonStyle.success,
                ),
                discord.ui.Button(
                    # TRANSLATORS: Text appearing on a button.
                    label=_("No"),
                    custom_id=(
                        f"FIELD_DELETE CANCEL {encoded_field_id} "
                        f"{utils.uuid.encode(field.template_id)}"
                    ),
                    style=discord.ButtonStyle.danger,
                ),
            ),
        )
        await interaction.response.edit_message(
            content=_("Are you sure you want to delete this field?"),
            embeds=[],
            components=components,
        )

    @vbu.Cog.listener("on_component_interaction")  # FIELD_DELETE [action] [TID]
    @vbu.i18n("profile")
    async def field_delete_component_listener(
            self,
            interaction: discord.ComponentInteraction):
        """
        Listens for components being interacted with, and deals with the ones
        relating to deleting templates.
        """

        # Make sure we should deal with it
        if not interaction.custom_id.startswith("FIELD_DELETE"):
            return

        # Check they still have permissions to press these buttons
        if not self.check_permissions(interaction):
            return await interaction.response.edit_message(
                content=_(
                    "Only users with the **manage guild** permission "
                    "can manage templates."
                ),
            )

        # See if they said to delete or not
        action, encoded_field_id, encoded_template_id = (
            interaction.custom_id.split(" ")[1:]
        )
        field_id = utils.uuid.decode(encoded_field_id)
        if action == "CANCEL":
            interaction.custom_id = (
                f"TEMPLATE_EDIT FIELDS "
                f"{encoded_template_id}"
            )
            return await self.template_edit_fields_component_listener(
                interaction,
            )
        field_id = utils.uuid.decode(encoded_field_id)

        # Set field as deleted
        async with vbu.Database() as db:
            field = await utils.Field.fetch_field_by_id(
                db,
                field_id,
            )

            # Make sure the template wasn't already deleted
            if field is None:
                interaction.custom_id = (
                    f"TEMPLATE_EDIT FIELDS "
                    f"{encoded_template_id}"
                )
                return await self.template_edit_fields_component_listener(
                    interaction,
                )

            # Mark the template as deleted
            await field.update(
                db,
                deleted=True,
            )
        interaction.custom_id = f"TEMPLATE_EDIT FIELDS {encoded_template_id}"
        return await self.template_edit_fields_component_listener(
            interaction,
        )

    @vbu.Cog.listener("on_component_interaction")  # FIELD_EDIT NAME [FID] [CV]
    @vbu.i18n("profile")
    async def field_edit_name_component_listener(
            self,
            interaction: discord.ComponentInteraction):
        """
        Listens for edit field name button to be pressed.
        Sends modal.
        """

        # Get current name and field ID
        if not interaction.custom_id.startswith("FIELD_EDIT NAME"):
            return
        encoded_field_id, current_name = interaction.custom_id.split(" ")[2:]

        # Build and send modal
        modal = discord.ui.Modal(
            # TRANSLATORS: Max 45 characters; title of modal
            title=_("Set field name")[:45],
            custom_id=f"FIELD_SET NAME {encoded_field_id}",
            components=[
                discord.ui.ActionRow(
                    discord.ui.InputText(
                        # TRANSLATORS: Max 45 characters; label of text input
                        label=_("What do you want to set the name to?")[:45],
                        style=discord.TextStyle.short,
                        custom_id=f"FIELD_DATA NAME {encoded_field_id}",
                        min_length=1,
                        max_length=45,
                        required=True,
                        value=current_name,
                    ),
                ),
            ],
        )
        await interaction.response.send_modal(modal)

    @vbu.Cog.listener("on_modal_submit")  # FIELD_SET NAME [FID]
    @vbu.i18n("profile")
    async def field_edit_name_modal_listener(
            self,
            interaction: discord.ModalInteraction):
        """
        Listens for edit field name modal to be submitted.
        Sets field name.
        """

        # Get the ID of the field
        if not interaction.custom_id.startswith("FIELD_SET NAME"):
            return
        encoded_field_id = interaction.custom_id.split(" ")[2]
        field_id = utils.uuid.decode(encoded_field_id)

        # Get the new name from the components
        new_field_name: str = (
            interaction
            .components[0]
            .components[0]  # type: ignore - not an issue for modals
            .value
        )

        # Check that the name is valid
        if not self.check_field_name(new_field_name):
            return await interaction.response.send_message(
                (
                    _("The name **{field_name}** is not valid.")
                    .format(field_name=new_field_name)
                ),
                allowed_mentions=discord.AllowedMentions.none(),
                ephemeral=True,
            )

        # Get and update the template
        await interaction.response.defer_update()
        await self.update_field(
            interaction,
            field_id,
            name=new_field_name,
        )

    @vbu.Cog.listener("on_component_interaction")  # FIELD_EDIT PROMPT [FID]
    @vbu.i18n("profile")
    async def field_edit_prompt_component_listener(
            self,
            interaction: discord.ComponentInteraction):
        """
        Listens for edit field name button to be pressed.
        Sends modal.
        """

        # Get current name and field ID
        if not interaction.custom_id.startswith("FIELD_EDIT PROMPT"):
            return
        encoded_field_id = interaction.custom_id.split(" ")[2]
        field_id = utils.uuid.decode(encoded_field_id)

        # Get current value
        async with vbu.Database() as db:
            field = await utils.Field.fetch_field_by_id(db, field_id)
            assert field

        # Build and send modal
        modal = discord.ui.Modal(
            # TRANSLATORS: Max 45 characters; title of modal
            title=_("Set field prompt")[:45],
            custom_id=f"FIELD_SET PROMPT {encoded_field_id}",
            components=[
                discord.ui.ActionRow(
                    discord.ui.InputText(
                        # TRANSLATORS: Max 45 characters; label of text input
                        label=_("What do you want to set the prompt to?")[:45],
                        style=discord.TextStyle.long,
                        custom_id=f"FIELD_DATA PROMPT {encoded_field_id}",
                        min_length=1,
                        max_length=45,
                        required=True,
                        value=field.prompt,
                    ),
                ),
            ],
        )
        await interaction.response.send_modal(modal)

    @vbu.Cog.listener("on_modal_submit")  # FIELD_SET PROMPT [FID]
    @vbu.i18n("profile")
    async def field_edit_prompt_modal_listener(
            self,
            interaction: discord.ModalInteraction):
        """
        Listens for edit field name modal to be submitted.
        Sets field name.
        """

        # Get the ID of the field
        if not interaction.custom_id.startswith("FIELD_SET PROMPT"):
            return
        encoded_field_id = interaction.custom_id.split(" ")[2]
        field_id = utils.uuid.decode(encoded_field_id)

        # Get the new name from the components
        new_field_prompt: str = (
            interaction
            .components[0]
            .components[0]  # type: ignore - not an issue for modals
            .value
        )

        # Get and update the template
        await interaction.response.defer_update()
        await self.update_field(
            interaction,
            field_id,
            prompt=new_field_prompt,
        )

    @vbu.Cog.listener("on_component_interaction")  # FIELD_EDIT OPTIONAL [FID]
    @vbu.i18n("profile")
    async def field_edit_optional_component_listener(
            self,
            interaction: discord.ModalInteraction):
        """
        Listens for edit field name modal to be submitted.
        Flips field optionality
        """

        # Get the ID of the field
        if not interaction.custom_id.startswith("FIELD_EDIT OPTIONAL"):
            return
        encoded_field_id = interaction.custom_id.split(" ")[2]
        field_id = utils.uuid.decode(encoded_field_id)

        # Get current
        async with vbu.Database() as db:
            field = await utils.Field.fetch_field_by_id(db, field_id)
            assert field

        # Get and update the template
        await self.update_field(
            interaction,
            field_id,
            optional=not field.optional,
        )

    @vbu.Cog.listener("on_component_interaction")  # FIELD_EDIT TYPE [FID]
    @vbu.i18n("profile")
    async def field_edit_type_component_listener(
            self,
            interaction: discord.ComponentInteraction):
        """
        Listens for edit field type buttom to be pressed.
        Sends dropdown
        """

        # Get the ID of the field
        if not interaction.custom_id.startswith("FIELD_EDIT TYPE"):
            return
        encoded_field_id, encoded_template_id = (
            interaction.custom_id.split(" ")[2:]
        )
        template_id = utils.uuid.decode(encoded_template_id)

        # Get the template so we know what fields they can use
        async with vbu.Database() as db:
            template = await utils.Template.fetch_template_by_id(
                db,
                template_id,
            )
            assert template
        has_image_field = bool([
            i
            for i in template.field_list
            if i.field_type == utils.ImageField
        ])

        # Set up options for them
        options = [
            discord.ui.SelectOption(
                # TRANSLATORS: Text appearing in a select menu describing a
                # field type
                label=_("Text"),
                value="TEXT",
                description=_(
                    "This is used when you want users to input up to 1000 "
                    "characters into a field"
                ),
            ),
            discord.ui.SelectOption(
                # TRANSLATORS: Text appearing in a select menu describing a
                # field type
                label=_("Number"),
                value="NUMBER",
                description=_(
                    "Used when you want users to input a number."
                ),
            ),
        ]
        if not has_image_field:
            options.append(
                discord.ui.SelectOption(
                    # TRANSLATORS: Text appearing in a select menu describing a
                    # field type
                    label=_("Image"),
                    value="IMAGE",
                    description=_(
                        "Used when you want users to input an image URL, "
                        "which will appear on their profile."
                    ),
                )
            )
        components = discord.ui.MessageComponents(
            discord.ui.ActionRow(
                discord.ui.SelectMenu(
                    custom_id=f"FIELD_SET TYPE {encoded_field_id}",
                    options=options,
                    min_values=1,
                    max_values=1,
                )
            )
        )

        # And send
        await interaction.response.edit_message(
            content=_("What do you want to set the field type to?"),
            embeds=[],
            components=components,
        )

    @vbu.Cog.listener("on_component_interaction")  # FIELD_SET TYPE [FID]
    @vbu.i18n("profile")
    async def field_edit_type_dropdown_component_listener(
            self,
            interaction: discord.ComponentInteraction):
        """
        Listens for edit field type dropdown to be submitted.
        Edits field type
        """

        # Get the ID of the field
        if not interaction.custom_id.startswith("FIELD_SET TYPE"):
            return
        encoded_field_id = interaction.custom_id.split(" ")[2]
        field_id = utils.uuid.decode(encoded_field_id)

        # Get current
        async with vbu.Database() as db:
            field = await utils.Field.fetch_field_by_id(db, field_id)
            assert field

        # Get and update the template
        await self.update_field(
            interaction,
            field_id,
            field_type={
                "TEXT": utils.TextField,
                "NUMBER": utils.NumberField,
                "IMAGE": utils.ImageField,
            }[interaction.values[0]],
        )


def setup(bot: vbu.Bot):
    x = TemplateCommands(bot)
    bot.add_cog(x)
