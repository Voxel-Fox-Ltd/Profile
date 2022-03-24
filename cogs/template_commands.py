import asyncio
import string
import uuid
import typing
import collections

import discord
from discord.ext import commands, vbu

from cogs import utils


def t(i: typing.Union[commands.Context, discord.Interaction, str], l: str) -> str:
    return vbu.translation(i, "template_commands").gettext(l)


def get_profile_application_command(name: str, description: str = None) -> discord.ApplicationCommand:
    """
    Create an application command with the given name, and subcommands
    for create, edit, and delete.
    """

    command = discord.ApplicationCommand(
        name=name,
        description=description or name,
        type=discord.ApplicationCommandType.chat_input,
        options=[
            discord.ApplicationCommandOption(
                name="create",
                description="Create a new profile.",
                type=discord.ApplicationCommandOptionType.subcommand,
                name_localizations={
                    i: t(i, "create")
                    for i in ["de", "pt"]
                },
                description_localizations={
                    i: t(i, "Create a new profile.")
                    for i in ["de", "pt"]
                },
            ),
            discord.ApplicationCommandOption(
                name="delete",
                description="Delete one of your profiles.",
                type=discord.ApplicationCommandOptionType.subcommand,
                options=[
                    discord.ApplicationCommandOption(
                        name="profile_name",
                        description="The name of the profile that you want to delete.",
                        type=discord.ApplicationCommandOptionType.string,
                        autocomplete=True,
                    ),
                ],
            ),
            discord.ApplicationCommandOption(
                name="get",
                description="Create a new profile.",
                type=discord.ApplicationCommandOptionType.subcommand,
                options=[
                    discord.ApplicationCommandOption(
                        name="user",
                        description="The person whose profile you want to get.",
                        type=discord.ApplicationCommandOptionType.user,
                        required=True,
                    ),
                    discord.ApplicationCommandOption(
                        name="profile_name",
                        description="The name of the profile that you want to get.",
                        type=discord.ApplicationCommandOptionType.string,
                        required=True,
                        autocomplete=True,
                    ),
                ],
            ),
            discord.ApplicationCommandOption(
                name="edit",
                description="Edit one of your profiles.",
                type=discord.ApplicationCommandOptionType.subcommand,
                options=[
                    discord.ApplicationCommandOption(
                        name="profile_name",
                        description="The name of the profile that you want to edit.",
                        type=discord.ApplicationCommandOptionType.string,
                        required=True,
                        autocomplete=True,
                    ),
                ],
            ),
        ]
    )
    return command


class TemplateCommands(vbu.Cog):

    def __init__(self, bot:vbu.Bot):
        super().__init__(bot)
        self.template_editing_locks: typing.Dict[int, asyncio.Lock]
        self.template_editing_locks = collections.defaultdict(asyncio.Lock)  # guild_id: asyncio.Lock

    @staticmethod
    def is_valid_template_name(
            template_name: str
            ) -> bool:
        """
        Returns whether a template name is technically valid.

        Parameters
        -----------
        template_name: :class:`str`
            The template name you want to check.

        Returns
        --------
        :class:`bool`
            Whether or not the given template name is valid.
        """

        return len([i for i in template_name if i not in string.ascii_letters + string.digits]) == 0

    @commands.group(
        application_command_meta=commands.ApplicationCommandMeta(
            # Add translations here
        ),
    )
    @commands.bot_has_permissions(send_messages=True)
    @commands.guild_only()
    async def template(self, ctx: commands.SlashContext):
        """
        The parent group for all template commands.
        """

        pass

    @template.command(
        name="list",
        application_command_meta=commands.ApplicationCommandMeta(
            # Add translations here
        ),
    )
    @commands.defer()
    @commands.bot_has_permissions(send_messages=True)
    @commands.guild_only()
    async def template_list(self, ctx: utils.types.GuildContext):
        """
        Lists the templates that have been created for this server.
        """

        # Grab the templates for the server
        async with vbu.Database() as db:
            templates = await db(
                """SELECT template.template_id, template.name, COUNT(created_profile.*) FROM template
                LEFT JOIN created_profile ON template.template_id=created_profile.template_id
                WHERE guild_id=$1 GROUP BY template.template_id""",
                ctx.guild.id
            )

        # See if there are any
        if not templates:
            return await ctx.interaction.followup.send("There are no created templates for this guild.")

        # Format into a nice string
        template_names = [
            f"**{row['name']}** (`{row['template_id']}`, `{row['count']}` created profiles)"
            for row in templates
        ]

        # And send
        return await ctx.interaction.followup.send('\n'.join(template_names))

    @template.command(
        name="describe",
        application_command_meta=commands.ApplicationCommandMeta(
            options=[
                discord.ApplicationCommandOption(
                    name="template",
                    description="The template that you want to get the information of.",
                    type=discord.ApplicationCommandOptionType.string,
                    autocomplete=True,
                ),
                discord.ApplicationCommandOption(
                    name="brief",
                    description="Whether you want to display abbreviated data or not.",
                    type=discord.ApplicationCommandOptionType.boolean,
                ),
            ],
            # Add translations here
        ),
    )
    @commands.defer()
    @commands.bot_has_permissions(send_messages=True, embed_links=True)
    @commands.guild_only()
    async def template_describe(self, ctx: commands.SlashContext, template: utils.Template, brief: bool = True):
        """
        Describe a template and its fields.
        """

        # Build the embed
        embed = template.build_embed(self.bot, brief=brief)

        # Get the number of profiles
        async with vbu.Database() as db:
            user_profiles = await template.fetch_all_profiles(db, fetch_filled_fields=False)
        embed.description += f"\nCurrently there are **{len(user_profiles)}** created profiles for this template."

        # And send
        return await ctx.interaction.followup.send(embed=embed)

    async def user_is_bot_support(self, ctx: commands.Context) -> bool:
        """
        Returns whether or not the user calling the command is bot support.
        """

        try:
            await vbu.checks.is_bot_support().predicate(ctx)
            return True
        except commands.CommandError:
            return False

    @template.command(
        name="edit",
        application_command_meta=commands.ApplicationCommandMeta(
            options=[
                discord.ApplicationCommandOption(
                    name="template",
                    description="The template that you want to edit.",
                    type=discord.ApplicationCommandOptionType.string,
                    autocomplete=True,
                ),
            ],
        ),
    )
    @commands.defer()
    @commands.has_guild_permissions(manage_roles=True)
    @commands.bot_has_permissions(send_messages=True, external_emojis=True, add_reactions=True, manage_messages=True)
    @commands.guild_only()
    async def template_edit(self, ctx: utils.types.GuildContext, template: utils.Template):
        """
        Edits a template for your guild.
        """

        # Set up the interaction to use
        interaction: discord.Interaction = ctx.interaction

        # See if they're already editing that template
        if self.template_editing_locks[ctx.guild.id].locked():
            return await interaction.followup.send("You're already editing a template.")

        # Send a message that we can edit later
        sent_initial_message: bool = False

        # See if they're bot support
        is_bot_support = await self.user_is_bot_support(ctx)

        # Grab the template edit lock
        async with self.template_editing_locks[ctx.guild.id]:

            # Get the template fields
            async with vbu.Database() as db:
                await template.fetch_fields(db)
                guild_settings_rows = await db(
                    """SELECT * FROM guild_settings WHERE guild_id=$1 OR guild_id=0 ORDER BY guild_id DESC""",
                    ctx.guild.id,
                )
                perks = await utils.get_perks_for_guild(db, ctx.guild.id)
            ctx.guild_perks = perks
            guild_settings = guild_settings_rows[0]

            # Set up our initial vars so we can edit them later
            interaction_id = str(uuid.uuid4())
            components = discord.ui.MessageComponents.add_buttons_with_rows(
                discord.ui.Button(label="Template name", custom_id=f"{interaction_id} NAME"),
                discord.ui.Button(label="Profile verification channel", custom_id=f"{interaction_id} VERIFICATION"),
                discord.ui.Button(label="Profile archive channel", custom_id=f"{interaction_id} ARCHIVE"),
                discord.ui.Button(label="Profile completion role", custom_id=f"{interaction_id} ROLE"),
                discord.ui.Button(label="Template fields", custom_id=f"{interaction_id} FIELDS"),
                discord.ui.Button(label="Profile count per user", custom_id=f"{interaction_id} COUNT"),
                discord.ui.Button(label="Done", custom_id=f"{interaction_id} DONE", style=discord.ButtonStyle.success),
            )

            # See if they have a command set up properly
            added_command = None
            if template.application_command_id:
                try:
                    added_command = await ctx.guild.fetch_application_command(template.application_command_id)
                except discord.HTTPException:
                    pass
            if added_command is None:
                components.components[-1].add_component(
                    discord.ui.Button(
                        label="Add slash command",
                        custom_id=f"{interaction_id} COMMAND",
                        style=discord.ButtonStyle.danger,
                        disabled=added_command is not None
                    )
                )
            else:
                components.components[-1].add_component(
                    discord.ui.Button(
                        label="Update slash command",
                        custom_id=f"{interaction_id} COMMAND",
                        style=discord.ButtonStyle.danger,
                    )
                )

            # Start our edit loop
            while True:

                # Edit the message
                if sent_initial_message:
                    try:
                        await interaction.edit_original_message(
                            content=None,
                            embed=template.build_embed(self.bot, brief=True),
                            allowed_mentions=discord.AllowedMentions(roles=False),
                            components=components,
                        )
                    except discord.HTTPException:
                        return
                else:
                    await interaction.followup.send(
                        embed=template.build_embed(self.bot, brief=True),
                        allowed_mentions=discord.AllowedMentions(roles=False),
                        components=components,
                    )
                    sent_initial_message = True

                # Wait for a response from the user
                try:
                    interaction: discord.Interaction = await self.bot.wait_for(
                        "component_interaction",
                        check=lambda i: i.user.id == ctx.author.id and i.component.custom_id.startswith(interaction_id),
                        timeout=60 * 2,
                    )
                    assert interaction.custom_id
                    _, attribute = interaction.custom_id.split(" ")
                except asyncio.TimeoutError:
                    try:
                        await interaction.edit_original_message(
                            content="Timed out waiting for edit response.",
                            components=None,
                            embed=None,
                        )
                    except discord.HTTPException:
                        pass
                    return

                # See if they're done
                response = False
                if attribute == "DONE":
                    await interaction.response.edit_message(components=None)
                    break

                # See if they wanna add a button
                elif attribute == "COMMAND":
                    await interaction.response.defer_update()
                    application_command_object = get_profile_application_command(template.name)
                    if added_command:
                        await ctx.guild.edit_application_command(
                            added_command,
                            options=application_command_object.options
                        )
                    else:
                        added_command = await ctx.guild.create_application_command(application_command_object)
                        async with vbu.Database() as db:
                            await db(
                                """UPDATE template SET application_command_id=$2 WHERE template_id=$1""",
                                template.id, added_command.id,
                            )
                    template.application_command_id = added_command.id
                    components.get_component(f"{interaction_id} COMMAND").label = "Update slash command"
                    response = True

                # See if they wanna change fields
                elif attribute == "FIELDS":
                    response: typing.Optional[bool]
                    interaction, response = await self.edit_field(
                        ctx, interaction, template, guild_settings,
                        is_bot_support,
                    )
                    async with vbu.Database() as db:
                        await template.fetch_fields(db)

                # See if they wanna change an attribute
                elif attribute in ["NAME", "VERIFICATION", "ARCHIVE", "ROLE", "COUNT"]:
                    converter: typing.Union[commands.Converter, type]
                    attribute, converter = {
                        "NAME": ("name", str),
                        "VERIFICATION": ("verification_channel_id", commands.TextChannelConverter()),
                        "ARCHIVE": ("archive_channel_id", commands.TextChannelConverter()),
                        "ROLE": ("role_id", commands.RoleConverter()),
                        "COUNT": ("max_profile_count", int),
                    }[attribute]
                    response: typing.Optional[bool]
                    interaction, response = await self.change_template_attribute(
                        ctx, interaction, template, guild_settings,
                        is_bot_support, attribute, converter,
                    )

                    # Change the command if the name was changed
                    if attribute == "name" and template.application_command_id:
                        await ctx.guild.edit_application_command(
                            discord.Object(template.application_command_id),
                            name=template.name,
                        )

                # Some invalid response
                else:
                    assert False, "Failed to get a response."

                # See if the user gave a response or if they timed out
                if response is None:
                    break

    async def change_template_attribute(
            self,
            ctx: utils.types.GuildContext,
            interaction: discord.Interaction,
            template: utils.Template,
            guild_settings: dict,
            is_bot_support: bool,
            attribute: str,
            converter: typing.Union[commands.Converter, type]
            ) -> typing.Tuple[discord.Interaction, typing.Optional[bool]]:
        """
        Change the attributes of a given template. Returns whether or not the template
        has been changed, and should thus be updated.

        The interaction given must not have been responded to.
        """

        # Make up the text to be sent
        text: str
        if attribute == "name":
            text = "What do you want to set the template's name to?"
        elif attribute == "verification_channel_id":
            text = "What channel do you want to set as the verification channel?"
        elif attribute == "archive_channel_id":
            text = "What channel do you want to set as the archive channel?"
        elif attribute == "role_id":
            text = "What role do you want users to receive when their profile is approved?"
        elif attribute == "max_profile_count":
            text = "What do you want to set the max profile count to?"
        else:
            raise ValueError()

        # Send the text
        await interaction.response.edit_message(
            content=text,
            components=None,
            embed=None,
        )

        # Wait for them to respond
        def check(message):
            return all([
                message.author.id == ctx.author.id,
                message.channel.id == ctx.channel.id,
            ])
        try:
            value_message: discord.Message = await self.bot.wait_for(
                "message",
                check=check,
                timeout=60 * 2,
            )
        except asyncio.TimeoutError:
            try:
                await interaction.edit_original_message(
                    content="Timed out waiting for edit response.",
                    components=None,
                    embed=None,
                )
            except discord.HTTPException:
                pass
            return interaction, None

        # Try and convert their response
        converted: str
        try:
            if isinstance(converter, commands.Converter):
                converted = str((await converter.convert(ctx, value_message.content)).id)
            else:
                converted = converter(value_message.content)
        except commands.BadArgument:
            is_command, is_valid_command = utils.CommandProcessor.get_is_command(value_message.content)
            if is_command and is_valid_command:
                converted = value_message.content
            else:
                return interaction, False
        except ValueError:
            return interaction, False

        # Validate the given information
        checked_converted: typing.Optional[typing.Any] = await self.validate_given_attribute(
            ctx=ctx,
            template=template,
            attribute=attribute,
            converted=converted,
            guild_settings=guild_settings,
            is_bot_support=is_bot_support,
        )
        if checked_converted is None and attribute in ["name", "max_profile_count"]:
            return interaction, False

        # Try and delete the message
        try:
            await value_message.delete()
        except discord.HTTPException:
            pass

        # Store our new shit
        setattr(template, attribute, checked_converted)
        async with vbu.Database() as db:
            await db(
                "UPDATE template SET {0}=$1 WHERE template_id=$2".format(attribute),
                checked_converted, template.template_id,
            )
        return interaction, True

    async def validate_given_attribute(
            self,
            ctx: utils.types.GuildContext,
            template: utils.Template,
            attribute: str,
            converted: typing.Union[str, int],
            guild_settings: dict,
            is_bot_support: bool) -> typing.Optional[typing.Any]:
        """
        Validates the given information from the user as to whether their attribute should be changed.
        Returns either
        """

        # Validate if they provided a new name
        if attribute == "name":

            # Validaate the name
            assert isinstance(converted, str)
            converted = converted.replace(" ", "")

            # See if they're already using the name
            async with vbu.Database() as db:
                name_in_use = await db(
                    """SELECT * FROM template WHERE guild_id=$1 AND LOWER(name)=LOWER($2)
                    AND template_id<>$3""",
                    ctx.guild.id, converted, template.template_id,
                )
            if name_in_use:
                await ctx.send("That template name is already in use.", delete_after=3)
                return None

            # See if the length is fine
            if 30 < len(converted) < 1:
                await ctx.send("That template name is invalid - not within 1 and 30 characters in length.", delete_after=3)
                return None

        # Validate profile count
        elif attribute == "max_profile_count":

            # Validate the number
            assert isinstance(converted, int)
            converted = max(
                min(
                    converted,
                    max(
                        guild_settings['max_template_profile_count'],
                        ctx.guild_perks.max_profile_count,
                    ),
                ),
                0,
            )

        # Return new information
        return converted

    async def edit_field(
            self,
            ctx: utils.types.GuildContext,
            interaction: discord.Interaction,
            template: utils.Template,
            guild_settings: dict,
            is_bot_support: bool,
            ) -> typing.Tuple[discord.Interaction, typing.Optional[bool]]:
        """
        Talk the user through editing a field of a template.
        Returns whether or not the template display needs to be updated, or None for an error (like a timeout).

        The interaction given must not have been responded to.
        """

        # Let's make an ID that we can check for
        interaction_id = str(uuid.uuid4())

        # Create some components to add to the message asking which field to edit
        field_name_buttons = [
            discord.ui.Button(
                label=field.name[:25],
                custom_id=f"{interaction_id} {field.field_id}"
            )
            for field in template.field_list
        ]
        max_field_count = max(guild_settings['max_template_field_count'], ctx.guild_perks.max_field_count)
        if len(template.fields) < max_field_count or is_bot_support:
            new_button = discord.ui.Button(label="New", custom_id=f"{interaction_id} NEW", style=discord.ButtonStyle.success)
        else:
            new_button = discord.ui.Button(label="New (unavailable)", custom_id=f"{interaction_id} NEW", disabled=True, style=discord.ButtonStyle.success)
        components = discord.ui.MessageComponents.add_buttons_with_rows(
            new_button,
            *field_name_buttons,
            discord.ui.Button(label="Cancel", custom_id=f"{interaction_id} CANCEL", style=discord.ButtonStyle.danger),
        )

        # Send a message asking what they want to edit
        await interaction.response.edit_message(
            content="Which field do you want to edit?",
            components=components,
            embed=None,
        )

        # Wait for them to click a button
        action: str = ""
        try:
            interaction = await self.bot.wait_for(
                "component_interaction",
                check=lambda i: i.user.id == ctx.author.id and i.custom_id.startswith(interaction_id),
                timeout=60 * 2,
            )
            _, action = interaction.custom_id.split(" ")
        except asyncio.TimeoutError:
            try:
                await interaction.edit_original_message(
                    content="Timed out waiting for button click.",
                    components=None,
                    embed=None,
                )
            except discord.HTTPException:
                return interaction, None

        # See if they clicked one of the simple buttons
        if action == "NEW":
            image_field_exists: bool = any(
                i for i in template.fields.values()
                if isinstance(i.field_type, utils.ImageField)
            )
            field: typing.Optional[utils.Field]
            interaction, field = await self.create_new_field(
                ctx=ctx,
                interaction=interaction,
                template=template,
                index=len(template.all_fields),
                image_set=image_field_exists,
            )
            if field is None:
                return interaction, None
            await interaction.response.defer_update()
            async with vbu.Database() as db:
                await field.save(db, template)
            return interaction, True
        elif action == "CANCEL":
            await interaction.response.defer_update()
            return interaction, False

        # Otherwise, take them through editing the field
        field_to_edit = template.fields.get(action)
        if field_to_edit is None:
            return interaction, True  # Update the template for them

        # Ask what part of it they want to edit
        interaction_id = str(uuid.uuid4())
        components = discord.ui.MessageComponents(
            discord.ui.ActionRow(
                discord.ui.Button(label="Field name", custom_id=f"{interaction_id} NAME"),
                discord.ui.Button(label="Field prompt", custom_id=f"{interaction_id} PROMPT"),
                discord.ui.Button(label="Field being optional", custom_id=f"{interaction_id} OPTIONAL"),
                discord.ui.Button(label="Field type", custom_id=f"{interaction_id} TYPE"),
            ),
            discord.ui.ActionRow(
                discord.ui.Button(label="Delete field", style=discord.ButtonStyle.danger, custom_id=f"{interaction_id} DELETE"),
                discord.ui.Button(label="Cancel", style=discord.ButtonStyle.secondary, custom_id=f"{interaction_id} CANCEL"),
            ),
        )
        await interaction.response.edit_message(
            content=f"Editing the field **{field_to_edit.name}**. Which part would you like to edit?",
            components=components,
            embed=None,
        )

        # Wait for them to click a butotn
        try:
            interaction = await self.bot.wait_for(
                "component_interaction",
                check=lambda i: i.user.id == ctx.author.id and i.custom_id.startswith(interaction_id),
                timeout=60 * 2,
            )
            _, action = interaction.custom_id.split(" ")
        except asyncio.TimeoutError:
            try:
                await interaction.edit_original_message(
                    content="Timed out waiting for field attribute.",
                    components=None,
                    embed=None,
                )
            except discord.HTTPException:
                pass
            return interaction, None

        # See if they want to cancel
        if action == "CANCEL":
            await interaction.response.defer_update()
            return interaction, False

        # See if they want to delete
        elif action == "DELETE":
            await interaction.response.defer_update()
            async with vbu.Database() as db:
                await db(
                    """UPDATE field SET deleted=true WHERE field_id=$1""",
                    field_to_edit.field_id,
                )
            return interaction, True

        # They want to change something
        attribute_to_change: str = action

        # They want to change something that we spawn a modal for
        if attribute_to_change in ["NAME", "PROMPT"]:

            # Make the modal
            modal = discord.ui.Modal(
                title="Change Field Attribute",
                components=[
                    discord.ui.ActionRow(
                        discord.ui.InputText(
                            label={
                                "NAME": "What name do you want the field to have?",
                                "PROMPT": "What should the prompt for this field be?",
                            }[attribute_to_change],
                            value=getattr(field_to_edit, attribute_to_change.lower()),
                            max_length=256 if attribute_to_change == "NAME" else 2000,
                            min_length=1,
                        )
                    )
                ]
            )

            # Send the modal
            await interaction.response.send_modal(modal)

            # Wait for a response
            try:
                interaction = await self.bot.wait_for(
                    "modal_submit",
                    check=lambda i: i.user.id == ctx.author.id and i.custom_id == modal.custom_id,
                    timeout=60 * 20,
                )
            except asyncio.TimeoutError:
                try:
                    await interaction.edit_original_message(
                        content="Timed out waiting for modal submission.",
                        components=None,
                        embed=None,
                    )
                except discord.HTTPException:
                    pass
                return interaction, None

            # Get the newly changed data
            field_value = interaction.components[0].components[0].value

        # They want to change something we spawn a button for
        elif attribute_to_change in ["OPTIONAL", "TYPE"]:

            # Make the responses
            interaction_id = str(uuid.uuid4())
            if attribute_to_change == "OPTIONAL":
                prompt = "Do you want this field to be optional?"
                components = discord.ui.MessageComponents.boolean_buttons(
                    yes_id=f"{interaction_id} YES",
                    no_id=f"{interaction_id} NO",
                )
            elif attribute_to_change == "TYPE":
                prompt = "What type do you want this field to have?"
                components = discord.ui.MessageComponents(
                    discord.ui.ActionRow(
                        discord.ui.Button(label="Text", custom_id=f"{interaction_id} TEXT"),
                        discord.ui.Button(label="Numbers", custom_id=f"{interaction_id} NUMBERS")
                    )
                )
            else:
                raise ValueError()

            # Ask the user
            await interaction.response.edit_message(
                content=prompt,
                components=components,
                embed=None,
            )

            # Wait for a response
            try:
                interaction = await self.bot.wait_for(
                    "component_interaction",
                    check=lambda i: i.user.id == ctx.author.id and i.component.custon_id.startswith(interaction_id),
                    timeout=60 * 2,
                )
            except asyncio.TimeoutError:
                try:
                    await interaction.edit_original_message(
                        content="Timed out waiting for button click.",
                        components=None,
                        embed=None,
                    )
                except discord.HTTPException:
                    pass
                return interaction, None

            # Get the newly changed data
            field_value = {
                "YES": True,
                "NO": False,
                "TEXT": utils.TextField.name,
                "NUMBERS": utils.NumberField.name,
            }[interaction.component.custom_id]

        # It's something else
        else:
            raise ValueError()

        # We want to defer now
        await interaction.response.defer()

        # Save the data
        async with vbu.Database() as db:
            await db(
                """UPDATE field SET {0}=$2 WHERE field_id=$1""".format(attribute_to_change.lower()),
                field_to_edit.field_id, field_value,
            )

        # And done
        return interaction, True

    @template.command(
        name="delete",
        application_command_meta=commands.ApplicationCommandMeta(
            options=[
                discord.ApplicationCommandOption(
                    name="template",
                    description="The template that you want to delete.",
                    type=discord.ApplicationCommandOptionType.string,
                    autocomplete=True,
                ),
            ],
        ),
    )
    @commands.defer()
    @commands.has_guild_permissions(manage_roles=True)
    @commands.bot_has_permissions(send_messages=True, external_emojis=True, add_reactions=True)
    @commands.guild_only()
    async def template_delete(self, ctx: utils.types.GuildContext, template: utils.Template):
        """
        Deletes a template from your guild.
        """

        # See if they're already editing that template
        if self.template_editing_locks[ctx.guild.id].locked():
            return await ctx.interaction.followup.send("You're already editing a template.")
        interaction: discord.Interaction = ctx.interaction

        # Grab the template edit lock
        async with self.template_editing_locks[ctx.guild.id]:

            # Ask for confirmation
            delete_confirmation_message = await interaction.followup.send(
                "By doing this, you'll delete all of the created profiles under this template as well. Would you like to proceed?",
                components=discord.ui.MessageComponents.boolean_buttons(),
                wait=True,
            )
            try:
                interaction = await self.bot.wait_for(
                    "component_interaction",
                    check=lambda i: i.user.id == ctx.author.id and i.message.id == delete_confirmation_message.id,
                    timeout=120,
                )
            except asyncio.TimeoutError:
                try:
                    await interaction.edit_original_message(
                        content="Template delete timed out - please try again later.",
                        components=None,
                    )
                except discord.HTTPException:
                    pass
                return

            # Check if they said no
            if interaction.component.custom_id == "NO":
                return await interaction.response.edit_message(
                    content="Cancelled template delete.",
                    components=None,
                    embed=None,
                )

            # Defer so we can update without a hitch
            await interaction.response.defer_update()

            # Delete the application command
            if template.application_command_id:
                command = discord.Object(template.application_command_id)
                try:
                    await ctx.guild.delete_application_command(command)
                except discord.HTTPException:
                    pass

            # Delete it from the database
            async with vbu.Database() as db:
                await db(
                    """DELETE FROM template WHERE template_id=$1""",
                    template.template_id,
                )

            # And respond
            return await interaction.edit_original_message(
                content=f"All relevant data for template **{template.name}** (`{template.template_id}`) has been deleted.",
                components=None,
            )

    @template.command(
        name="create",
        application_command_meta=commands.ApplicationCommandMeta(
            options=[
                discord.ApplicationCommandOption(
                    name="template_name",
                    description="The name of the template that you want to create.",
                    type=discord.ApplicationCommandOptionType.string,
                ),
            ],
        ),
    )
    @commands.defer()
    @commands.has_guild_permissions(manage_roles=True)
    @commands.bot_has_permissions(send_messages=True, manage_messages=True, external_emojis=True, add_reactions=True, embed_links=True)
    @commands.guild_only()
    async def template_create(self, ctx: utils.types.GuildContext, template_name: str):
        """
        Creates a new template for your guild.
        """

        # Only allow them to make one template at once
        if self.template_editing_locks[ctx.guild.id].locked():
            return await ctx.interaction.followup.send("You're already creating a template.")
        interaction = ctx.interaction

        # Check their template count
        async with vbu.Database() as db:
            template_list = await db("SELECT template_id FROM template WHERE guild_id=$1", ctx.guild.id)
            guild_settings = await db("SELECT * FROM guild_settings WHERE guild_id=$1 OR guild_id=0 ORDER BY guild_id DESC", ctx.guild.id)
            perks = await utils.get_perks_for_guild(db, ctx.guild.id)
        max_template_count = max(guild_settings[0]['max_template_count'], perks.max_template_count)
        if len(template_list) >= max_template_count:
            if perks.is_premium:
                return await interaction.followup.send((
                    f"You already have {max_template_count} templates set for this server, which is the "
                    "maximum number you are allowed."
                ))
            return await interaction.followup.send((
                f"You already have {max_template_count} templates set for this server, which is the "
                f"maximum number you are allowed - see `{ctx.clean_prefix}donate` to get a "
                "higher profile count for your server."
            ))

        # And now we start creating the template itself
        async with self.template_editing_locks[ctx.guild.id]:

                # Check name for characters
            if not self.is_valid_template_name(template_name):
                await interaction.followup.send((
                    "You can only use normal lettering and digits in your command name. "
                    "Please run this command again to set a new one."
                ))
                return

            # Check name for length
            if 30 >= len(template_name) >= 1:
                pass
            else:
                await interaction.followup.send(
                    "The maximum length of a profile name is 30 characters. "
                    "Please run this command again to set a new one."
                )

            # Check name is unique
            async with vbu.Database() as db:
                template_exists = await db(
                    """SELECT * FROM template WHERE guild_id=$1 AND LOWER(name)=LOWER($2)""",
                    ctx.guild.id, template_name,
                )
            if template_exists:
                await interaction.followup.send(
                    f"This server already has a template with name **{template_name}**. "
                    "Please run this command again to provide another one."
                )
                return

            # Add new application command
            command = get_profile_application_command(template_name.lower())
            command = await ctx.guild.create_application_command(command)

            # Get an ID for the profile
            template = utils.Template(
                template_id=uuid.uuid4(),
                colour=0,
                guild_id=ctx.guild.id,
                verification_channel_id=None,
                name=template_name,
                archive_channel_id=None,
                role_id=None,
                max_profile_count=1,
                max_field_count=10,
                application_command_id=command.id,
            )

        # Save it all to database
        async with vbu.Database() as db:
            await db(
                """INSERT INTO template (template_id, name, colour, guild_id, verification_channel_id,
                archive_channel_id, application_command_id) VALUES ($1, $2, $3, $4, $5, $6, $7)""",
                template.template_id, template.name, template.colour, template.guild_id,
                template.verification_channel_id, template.archive_channel_id,
                template.application_command_id,
            )

        # Follow up into edit
        self.logger.info(f"New template '{template.name}' created on guild {ctx.guild.id}")
        await self.template_edit(ctx, template)

    async def create_new_field(
            self,
            ctx: commands.Context,
            interaction: discord.Interaction,
            template: utils.Template,
            index: int,
            image_set: bool = False,
            ) -> typing.Tuple[discord.Interaction, typing.Optional[utils.Field]]:
        """
        Talk a user through creating a new field for their template.

        The interaction given must not have been responded to.
        """

        # Send a modal off to the user
        modal = discord.ui.Modal(
            title="Create New Field",
            components=[
                discord.ui.ActionRow(
                    discord.ui.InputText(
                        label=(
                            "What name should this field have?"
                        ),
                        max_length=256,
                    )
                ),
                discord.ui.ActionRow(
                    discord.ui.InputText(
                        label=(
                            "What prompt should be sent with this message?"
                        ),
                        style=discord.TextStyle.long,
                    )
                )
            ]
        )
        await interaction.response.send_modal(modal)

        # Wait for the user to respond
        try:
            interaction = await self.bot.wait_for(
                "modal_submit",
                check=lambda i: i.user.id == ctx.author.id and i.custom_id == modal.custom_id,
                timeout=60 * 2
            )
        except asyncio.TimeoutError:
            try:
                await interaction.edit_original_message(
                    content="Creating a new field has timed out.",
                    components=None,
                    embed=None,
                )
            except discord.HTTPException:
                pass
            return interaction, None
        assert interaction.components
        field_name: str = interaction.components[0].components[0].value
        field_prompt: str = interaction.components[1].components[0].value

        # Get field optional
        interaction_id = str(uuid.uuid4())
        buttons_components = discord.ui.MessageComponents.boolean_buttons(
            yes_id=f"{interaction_id} YES",
            no_id=f"{interaction_id} NO",
        )
        await interaction.response.defer_update()
        await interaction.edit_original_message(
            content="Is this field optional?",
            components=buttons_components,
        )
        try:
            interaction = await self.bot.wait_for(
                "component_interaction",
                check=lambda i: i.user.id == ctx.author.id and i.component.custom_id.startswith(interaction_id),
                timeout=60 * 2,
            )
            _, field_optional_emoji = interaction.component.custom_id.split(" ")
        except asyncio.TimeoutError:
            field_optional_emoji = "NO"
        field_optional = field_optional_emoji == "YES"

        # Ask for a field type
        interaction_id = str(uuid.uuid4())
        action_row = discord.ui.ActionRow(
            discord.ui.Button(label="Text", custom_id=f"{interaction_id} TEXT"),
            discord.ui.Button(label="Numbers", custom_id=f"{interaction_id} NUMBERS"),
        )
        if not image_set:
            action_row.add_component(discord.ui.Button(label="Image", custom_id=f"{interaction_id} IMAGE"))
        components = discord.ui.MessageComponents(action_row)
        await interaction.response.edit_message(
            content="What type is this field?",
            components=components,
            embed=None,
        )

        # See what they said
        try:
            interaction = await self.bot.wait_for(
                "component_interaction",
                check=lambda i: i.user.id == ctx.author.id and i.component.custom_id.startswith(interaction_id),
                timeout=60 * 2,
            )
            _, key = interaction.component.custom_id.split(" ")
        except asyncio.TimeoutError:
            try:
                await interaction.edit_original_message(
                    content="Picking a field type has timed out.",
                    components=None,
                    embed=None,
                )
            except discord.HTTPException:
                pass
            return interaction, None

        # Change that emoji into a datatype
        field_type = {
            "NUMBERS": utils.NumberField(),
            "TEXT": utils.TextField(),
            "IMAGE": utils.ImageField(),
        }[key]
        if isinstance(field_type, utils.ImageField) and image_set:
            raise Exception("You shouldn't be able to set two image fields.")

        # Set some defaults for the field stuff
        field_timeout = 60 * 10

        # Make the field object
        field = utils.Field(
            field_id=uuid.uuid4(),
            name=field_name,
            index=index,
            prompt=field_prompt,
            timeout=field_timeout,
            field_type=field_type,
            template_id=template.template_id,
            optional=field_optional,
            deleted=False,
        )

        # And we done
        return interaction, field

    @template_edit.autocomplete
    @template_describe.autocomplete
    @template_delete.autocomplete
    async def template_autocomplete(self, ctx: commands.SlashContext, interaction: discord.Interaction):
        """
        Return the templates for the given guild.
        """

        async with vbu.Database() as db:
            templates = await db(
                """SELECT template_id, name FROM template WHERE guild_id=$1""",
                ctx.interaction.guild_id,
            )
        await interaction.response.send_autocomplete([
            discord.ApplicationCommandOptionChoice(name=row['name'], value=row['name'])
            for row in templates
        ])


def setup(bot: vbu.Bot):
    x = TemplateCommands(bot)
    bot.add_cog(x)
