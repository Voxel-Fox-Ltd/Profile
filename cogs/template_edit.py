import discord
from discord.ext import vbu

import regex as re

from cogs import utils


def _t(b: str | discord.Locale, a: str) -> str:
    """
    Translate function for non-commands.
    """

    return vbu.translation(b, "profile").gettext(a)


class TemplateEdit(vbu.Cog[vbu.Bot]):

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
                    options=[
                        NAME_OPTION,
                    ],
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

    def check_template_edit_permissions(
            self,
            interaction: discord.Interaction) -> bool:
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
        if not self.check_template_edit_permissions(interaction):
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
        self.logger.info(
            "Sending template name change modal for template %s",
            utils.uuid.decode(encoded_template_id),
        )

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
        self.logger.info("Changing name for template %s", template_id)

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
                interaction.guild_id,  # type: ignore
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
        if not template.application_command_id:
            return
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
        self.logger.info(
            "Sending dropdown for archive channel for template %s",
            utils.uuid.decode(encoded_template_id),
        )

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
            encoded_template_id, d = interaction.custom_id.split(" ")[2:]  # pyright: ignore
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
        self.logger.info(
            "Setting archive channel for template %s to %s",
            template_id, new_archive_channel_id,
        )

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
        self.logger.info(
            "Sending dropdown for verification channel for template %s",
            utils.uuid.decode(encoded_template_id),
        )

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
            encoded_template_id, d = interaction.custom_id.split(" ")[2:]  # pyright: ignore
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
        self.logger.info(
            "Setting verification channel for template %s to %s",
            template_id, new_verification_channel_id,
        )

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
        self.logger.info(
            "Sending dropdown for role for template %s",
            utils.uuid.decode(encoded_template_id),
        )

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
            encoded_template_id, d = interaction.custom_id.split(" ")[2:]  # pyright: ignore
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
        self.logger.info(
            "Setting role for template %s to %s",
            template_id, new_role_id,
        )

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
        self.logger.info(
            "Sending modal for template max profile edit for template %s",
            utils.uuid.decode(encoded_template_id),
        )

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
                _("The template limit you have given is not a valid number."),
                allowed_mentions=discord.AllowedMentions.none(),
                ephemeral=True,
            )

        # Check that the limit is valid
        await interaction.response.defer_update()
        valid_new_template_limit = int(new_template_limit)
        self.logger.info(
            "Trying to set max profiles for template %s to %s",
            template_id, valid_new_template_limit,
        )

        # Check that the limit is within range
        assert interaction.guild_id
        async with vbu.Database() as db:
            perks = await utils.GuildPerks.fetch(db, interaction.guild_id)
        if valid_new_template_limit > perks.max_template_count:
            if perks.is_premium:
                return await interaction.followup.send(
                    _("The template limit you have given is too large."),
                    ephemeral=True,
                )
            return await interaction.followup.send(
                _(
                    "The template limit you have given is too large. "
                    "To get access to more templates, you can donate via the "
                    "{donate_command_button} command."
                ).format(donate_command_button="/donate"),  # TODO: mention command
                ephemeral=True,
            )


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
        self.logger.info(
            "Trying to update slash command for template %s",
            template_id,
        )

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
            new_application_command = self.get_profile_application_command(
                template.name,
            )
            await guild.edit_application_command(
                application_command,
                name=new_application_command.name,
                description=new_application_command.description,
                options=new_application_command.options,
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


def setup(bot: vbu.Bot):
    x = TemplateEdit(bot)
    bot.add_cog(x)
