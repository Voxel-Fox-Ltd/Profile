from typing import TYPE_CHECKING, Optional
import discord
from discord.ext import vbu

from cogs import utils

if TYPE_CHECKING:
    from .template_edit import TemplateEdit


class TemplateFieldEdit(vbu.Cog[vbu.Bot]):

    @staticmethod
    def check_field_name(name: str) -> bool:
        """
        Returns whether or not a field's name is valid.
        """

        return all((
            len(name) <= 45,
        ))

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
                allow_deleted=interaction.guild_id == vbu.Constants.SUPPORT_GUILD_ID
            )
            assert field, (
                "The field was deleted while the "
                "user was editing an attribute."
            )
            field = await field.update(db, **kwargs)

        # And send the new template to the user
        cog: Optional[TemplateFieldEdit]
        cog = self.bot.get_cog("TemplateFieldEdit")  # type: ignore
        assert cog, "Cog not loaded."
        kwargs = cog.get_field_edit_components(
            interaction,
            field,
        )
        kwargs.pop("ephemeral", False)
        try:
            await interaction.response.edit_message(**kwargs)
        except discord.InteractionResponded:
            await interaction.edit_original_message(**kwargs)

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
                label=_("Index"),
                custom_id=(
                    f"FIELD_EDIT INDEX {utils.uuid.encode(field.id)} "
                    f"{field.index}"
                ),
                style=discord.ButtonStyle.secondary,
            ),
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
        self.logger.info(
            "Sending field edit buttons for template %s",
            template_id,
        )

        # Get template
        async with vbu.Database() as db:
            template = await utils.Template.fetch_template_by_id(
                db,
                template_id,
                allow_deleted=interaction.guild_id == vbu.Constants.SUPPORT_GUILD_ID
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
                allow_deleted=interaction.guild_id == vbu.Constants.SUPPORT_GUILD_ID
            )
            assert template, (
                "The template was deleted while the "
                "user was editing an attribute."
            )

        # Send them the template edit components
        cog: Optional[TemplateEdit]
        cog = self.bot.get_cog("TemplateEdit")  # type: ignore
        assert cog, "Cog not loaded."
        kwargs = cog.get_template_edit_components(
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
                allow_deleted=interaction.guild_id == vbu.Constants.SUPPORT_GUILD_ID
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
            perks = await utils.GuildPerks.fetch(
                db,
                interaction.guild.id,  # type: ignore
            )
            if len(template.fields) >= perks.max_field_count:
                error = _(
                    "You are at the maximum amount of fields "
                    "allowed for this template."
                )
                mention = utils.mention_command(self.bot.get_command("information"))
                upsell = _(
                    "To get access more fields, you can donate via the use the "
                    "{donate_command_button} command."
                ).format(donate_command_button=mention)
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
        new_index: int
        try:
            new_index = max(i.index for i in template.all_fields.values()) + 1
        except ValueError:
            new_index = 0
        field = utils.Field(
            id=None,
            name="",
            prompt="",
            index=new_index,
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
        self.logger.info("Asking to confirm deletion of field %s", field_id)

        # Try and get the template object
        async with vbu.Database() as db:
            field = await utils.Field.fetch_field_by_id(
                db,
                field_id,
                allow_deleted=interaction.guild_id == vbu.Constants.SUPPORT_GUILD_ID
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
        cog: Optional[TemplateEdit]
        cog = self.bot.get_cog("TemplateEdit")  # type: ignore
        assert cog, "Cog not loaded."
        if not cog.check_template_edit_permissions(interaction):
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
        self.logger.info("Deleting field %s", field_id)

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
        if not interaction.custom_id.startswith("FIELD_EDIT NAME "):
            return
        encoded_field_id, current_name = interaction.custom_id.split(" ", 4)[2:]
        self.logger.info(
            "Sending modal for field name change for field %s",
            utils.uuid.decode(encoded_field_id),
        )

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
                        value=current_name or None,
                    ),
                ),
            ],
        )
        await interaction.response.send_modal(modal)

    @vbu.Cog.listener("on_component_interaction")  # FIELD_EDIT INDEX [FID] [IDX]
    @vbu.i18n("profile")
    async def field_edit_index_component_listener(
            self,
            interaction: discord.ComponentInteraction):
        """
        Listens for edit field name button to be pressed.
        Sends modal.
        """

        # Get current name and field ID
        if not interaction.custom_id.startswith("FIELD_EDIT INDEX "):
            return
        encoded_field_id, current_index = interaction.custom_id.split(" ")[2:]
        self.logger.info(
            "Sending modal for field index change for field %s",
            utils.uuid.decode(encoded_field_id),
        )

        # Build and send modal
        modal = discord.ui.Modal(
            # TRANSLATORS: Max 45 characters; title of modal
            title=_("Set field index")[:45],
            custom_id=f"FIELD_SET INDEX {encoded_field_id}",
            components=[
                discord.ui.ActionRow(
                    discord.ui.InputText(
                        # TRANSLATORS: Max 45 characters; label of text input
                        label=_("What do you want to set the index to?")[:45],
                        style=discord.TextStyle.short,
                        custom_id=f"FIELD_DATA INDEX {encoded_field_id}",
                        min_length=1,
                        max_length=3,
                        required=True,
                        value=current_index,
                    ),
                ),
            ],
        )
        await interaction.response.send_modal(modal)

    @vbu.Cog.listener("on_modal_submit")  # FIELD_SET INDEX [FID]
    @vbu.i18n("profile")
    async def field_edit_index_modal_listener(
            self,
            interaction: discord.ModalInteraction):
        """
        Listens for edit field name modal to be submitted.
        Sets field name.
        """

        # Get the ID of the field
        if not interaction.custom_id.startswith("FIELD_SET INDEX"):
            return
        encoded_field_id = interaction.custom_id.split(" ")[2]
        field_id = utils.uuid.decode(encoded_field_id)

        # Get the new name from the components
        new_field_index_str: str = (
            interaction
            .components[0]
            .components[0]  # type: ignore - not an issue for modals
            .value
        )

        # Check that the name is valid
        if not new_field_index_str.isdigit():
            return await interaction.response.send_message(
                _("You did not give a valid number."),
                allowed_mentions=discord.AllowedMentions.none(),
                ephemeral=True,
            )
        self.logger.info(
            "Setting index for field %s to %s",
            field_id, new_field_index_str,
        )

        # Get and update the template
        await interaction.response.defer_update()
        await self.update_field(
            interaction,
            field_id,
            index=int(new_field_index_str),
        )

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
        self.logger.info(
            "Setting name for field %s to %s",
            field_id, new_field_name,
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
        self.logger.info(
            "Sending modal for prompt edit for field %s",
            field_id,
        )

        # Get current value
        async with vbu.Database() as db:
            field = await utils.Field.fetch_field_by_id(db, field_id)
            assert field

            # See if the guild is set to advanced
            advanced = await utils.is_guild_advanced(db, interaction.guild_id)

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
                        style=(
                            discord.TextStyle.long
                            if advanced
                            else discord.TextStyle.short
                        ),
                        custom_id=f"FIELD_DATA PROMPT {encoded_field_id}",
                        min_length=1,
                        max_length=None if advanced else 45,
                        required=True,
                        value=field.prompt or None,
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
        self.logger.info(
            "Updating prompt for field %s",
            field_id,
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
        self.logger.info(
            "Updating optional for field %s",
            field_id,
        )

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
        self.logger.info(
            "Sending type dropdown for field field %s",
            utils.uuid.decode(encoded_field_id),
        )

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
                )[:100],
            ),
            discord.ui.SelectOption(
                # TRANSLATORS: Text appearing in a select menu describing a
                # field type
                label=_("Number"),
                value="NUMBER",
                description=_(
                    "Used when you want users to input a number."
                )[:100],
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
                    )[:100],
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
        self.logger.info(
            "Updating type for field field %s to %s",
            field_id, interaction.values[0],
        )

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
    x = TemplateFieldEdit(bot)
    bot.add_cog(x)
