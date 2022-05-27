from __future__ import annotations

import asyncio
import re
from typing import Union, Optional, Dict, List, Tuple, TYPE_CHECKING
import uuid
import collections
import string

import discord
from discord.ext import commands, vbu
import asyncpg

from cogs import utils

if TYPE_CHECKING:
    from .profile_verification import ProfileVerification


class ProfileCommands(vbu.Cog):

    COMMAND_REGEX = re.compile(
        r"^(?P<template>\S{1,30}) (?P<command>set|create|get|delete|edit)(?:\s?(?P<args>.*))$",
        re.IGNORECASE,
    )
    OLD_COMMAND_REGEX = re.compile(
        r"^(?P<command>set|create|get|delete|edit)(?P<template>\S{1,30})",
        re.IGNORECASE,
    )

    def __init__(self, bot: vbu.Bot):
        super().__init__(bot)
        self.set_profile_locks: Dict[int, asyncio.Lock]
        self.set_profile_locks = collections.defaultdict(asyncio.Lock)
        self.profile_lock_uuids: Dict[int, str]  # the component ID of their setup
        self.profile_lock_uuids = {}

    @vbu.Cog.listener()
    async def on_autocomplete_interaction(self, interaction: discord.Interaction):
        """
        Deal with the autocomplete for "[profile] get".
        """

        # A basic filter to only deal with template get
        assert interaction.command_name
        command_name = interaction.command_name
        if command_name.endswith(" get") or command_name.endswith(" delete") or command_name.endswith(" edit"):
            pass
        else:
            return
        assert interaction.options
        assert interaction.user

        # Get the command and used template
        command_invokation = interaction.command_name
        assert command_invokation
        matches = self.COMMAND_REGEX.search(command_invokation)
        if matches is None:
            return
        template_name = matches.group("template")  # template name
        if template_name == "template":
            return  # Don't bother with the non-profile commands

        # Find the template they asked for on their server
        assert interaction.guild_id
        async with vbu.Database() as db:

            # Get the template
            template = await utils.Template.fetch_template_by_name(
                db,
                interaction.guild_id,
                template_name,
                fetch_fields=False,
            )
            if not template:
                self.logger.info(f"Failed at getting template '{template_name}' in guild {interaction.guild_id}")
                return  # Fail silently on template doesn't exist

            # Find the user's profiles
            options = interaction.options[0].options
            user_id = interaction.user.id
            if options:
                for i in options:
                    if i.name == "user" and i.value:
                        user_id = int(i.value)
            user_profiles = await template.fetch_all_profiles_for_user(db, user_id, fetch_filled_fields=False)

        # And return the profile names
        await interaction.response.send_autocomplete([
            discord.ApplicationCommandOptionChoice(name=i.name, value=i.name)
            for i in user_profiles
        ])

    @vbu.Cog.listener()
    async def on_command_error(self, ctx: utils.types.GuildContext, error: commands.CommandError):
        """
        CommandNotFound handler so the bot can search for that custom command.
        """

        # Filter out DMs
        if isinstance(ctx.channel, discord.DMChannel):
            return  # Fail silently on DM invocation

        # Handle commandnotfound which is really just handling the set/get/delete/edit commands
        if not isinstance(error, commands.CommandNotFound):
            return

        # Get the command and used template
        guild_id: Optional[int] = None
        command_invokation: Optional[str] = None
        if isinstance(ctx, commands.SlashContext):
            command_invokation = ctx.interaction.command_name
            guild_id = ctx.interaction.guild_id
        elif isinstance(ctx, commands.Context):
            command_invokation = ctx.message.content[len(ctx.prefix):]
            guild_id = ctx.guild.id
        assert command_invokation
        assert guild_id

        matches = self.COMMAND_REGEX.search(command_invokation) or self.OLD_COMMAND_REGEX.search(command_invokation)
        if matches is None:
            return
        command_operator = matches.group("command").lower()  # get/get/delete/edit
        template_name = matches.group("template")  # template name

        # Find the template they asked for on their server
        async with vbu.Database() as db:
            template = await utils.Template.fetch_template_by_name(db, guild_id, template_name, fetch_fields=False)
        if not template:
            # self.logger.info(f"Failed at getting template '{template_name}' in guild {guild_id}")
            return  # Fail silently on template doesn't exist

        # Get the metacommand
        metacommand: commands.Command
        if command_operator == "get":
            metacommand = self.get_profile_meta
        elif command_operator in ["set", "create"]:
            metacommand = self.set_profile_meta
        elif command_operator == "delete":
            metacommand = self.delete_profile_meta
        elif command_operator == "edit":
            metacommand = self.edit_profile_meta
        else:
            raise ValueError(f"Couldn't get metacommand {command_operator}")

        # Make sure it's a slashie
        if not isinstance(ctx, commands.SlashContext):
            if not template.application_command_id:
                text = vbu.translation(ctx, "profile_commands").gettext(
                    "This command can only be run as a slash command - run "
                    "`/template edit {template_name}` to create it."
                ).format(template_name=template.name)
            else:
                text = vbu.translation(ctx, "profile_commands").gettext(
                    "This command can only be run as a slash command."
                )
            await ctx.send(text)
            return

        # Invoke command
        ctx.command = metacommand
        ctx.template = template
        ctx.invoke_meta = True
        ctx.invoked_with = f"{matches.group('template')} {matches.group('command')}"
        try:
            self.bot.dispatch("command", ctx)
            await metacommand.invoke(ctx)  # This converts the args for me, which is nice
        except (commands.CommandInvokeError, commands.CommandError) as e:
            self.bot.dispatch("command_error", ctx, e)  # Throw any errors we get in this command into its own error handler

    @staticmethod
    async def get_profile_name(
            ctx: utils.types.GuildContext,
            interaction: discord.Interaction,
            template: utils.Template,
            user_profiles: List[utils.UserProfile],
            ) -> Tuple[discord.Interaction, Optional[str]]:
        """
        Ask the user for a name that they want to give to their template.

        Parameters
        -----------
        ctx: :class:`discord.ext.commands.Context`
            The context that invoked the command.
        interaction: :class:`discord.Interaction`
            The interaction that invoked the command.
        template: :class`cogs.utils.profiles.template.Template`
            The template that the user is filling out a profile for.
        user_profiles: List[:class:`cogs.utils.profiles.user_profile.UserProfile`]
            A list of the user's current profiles.

        Returns
        --------
        Tuple[:class:`discord.Interaction`, Optional[:class:`str`]]
            The last interaction that the user responded to.
            The name that the user gave their profile. The bot timed out waiting for the
            user to submit their profile name.
        """

        # Set the user ID
        assert ctx.author
        user_id = ctx.author.id

        # See if we can assign one automatically in the case that there's only one
        # profile allowed for this template
        if template.max_profile_count == 1:
            suffix = None
            while True:
                default_name = vbu.translation(interaction, "profile_commands").gettext("default")  # default profile name
                if suffix is None:
                    name_content = f"{default_name}"
                else:
                    name_content = f"{default_name}{suffix}"
                if name_content.lower() in [i.name.lower() for i in user_profiles]:
                    suffix = (suffix or 0) + 1
                else:
                    break
            return (interaction, name_content)

        # Loop until we get a valid answer
        while True:

            # Send the user a modal to ask for the answer
            modal = discord.ui.Modal(
                title=vbu.translation(interaction, "profile_commands").gettext(
                    "Profile Name"
                ),
                components=[
                    discord.ui.ActionRow(
                        discord.ui.InputText(
                            label=vbu.translation(interaction, "profile_commands").gettext(
                                "What name do you want to give your profile?"
                            ),
                        ),
                    ),
                ]
            )
            await interaction.response.send_modal(modal)

            # Wait for the user to respond to the modal
            try:
                submitted_modal: discord.Interaction = await ctx.bot.wait_for(
                    "modal_submit",
                    timeout=60 * 10,
                    check=lambda i: i.user.id == user_id and i.custom_id == modal.custom_id
                )
            except asyncio.TimeoutError:
                return (interaction, None)

            # Make sure their name is valid
            try:

                # Get the name that they gave from the modal
                assert submitted_modal.components
                text_input = submitted_modal.components[0].components[0]
                utils.TextField.check(text_input.value.strip())
                name_content: str = text_input.value.strip()

                # See if the name they provided is already in use
                if name_content.lower() in [i.name.lower() for i in user_profiles]:
                    error_text = vbu.translation(interaction, "profile_commands").gettext(
                        "You're already using that name for this template. Please provide an alternative."
                    )
                    raise utils.errors.FieldCheckFailure(error_text)

                # Make sure the name they gave is valid
                if any([i for i in name_content if i not in string.ascii_letters + string.digits + ' ']):
                    error_text = vbu.translation(interaction, "profile_commands").gettext(
                        "You can only use standard lettering and digits in your profile name. "
                        "Please provide an alternative."
                    )
                    raise utils.errors.FieldCheckFailure(error_text)

            # We hit an error converting their name to something valid
            except utils.errors.FieldCheckFailure as e:
                button_custom_id = f"userProfileNameOkay {template.id}"
                components = discord.ui.MessageComponents(
                    discord.ui.ActionRow(
                        discord.ui.Button(
                            label=vbu.translation(interaction, "profile_commands").gettext("Okay"),
                            custom_id=button_custom_id,
                            style=discord.ButtonStyle.secondary,
                        )
                    )
                )
                await submitted_modal.response.send_message(
                    content=e.message,
                    components=components,
                    ephemeral=True,
                )

                # Wait for the user to say it's all okay before continuing so that
                # we're able to get a fresh interaction object to send a modal back to
                try:
                    okay_button_clicked: discord.Interaction = await ctx.bot.wait_for(
                        "component_interaction",
                        check=lambda i: i.user.id == user_id and i.custom_id == button_custom_id,
                        timeout=60 * 5,
                    )
                except asyncio.TimeoutError:
                    try:
                        b = components.get_component(button_custom_id)
                        assert isinstance(b, discord.ui.Button)
                        b.label = vbu.translation(interaction, "profile_commands").gettext(
                            "Timed out waiting for you to continue."
                        )
                        b.disabled = True
                        await submitted_modal.edit_original_message(components=components)
                    except discord.HTTPException:
                        pass
                    return (interaction, None)
                assert okay_button_clicked
                interaction = okay_button_clicked

            # It's valid
            else:
                break

        # And return the name given
        return (submitted_modal, name_content)

    @staticmethod
    async def get_field_content(
            ctx: utils.types.GuildContext,
            interaction: discord.Interaction,
            original_id: str,
            profile_name: str,
            field: utils.Field,
            target_user: Union[discord.User, discord.Member],
            current_value: Optional[str] = None
            ) -> Tuple[discord.Interaction, Optional[utils.FilledField]]:
        """
        Ask the user to fill in the content for a field given its prompt.

        The interaction given must not have been responded to.
        The interaction returned must not have been responded to.
        """

        # Make a new ID for this set of components
        # id_to_use = str(uuid.uuid4())
        new_interaction_id = str(uuid.uuid4())
        id_to_use = original_id

        # See if the field is a command
        # If it is, then we can just add that to their profile and continue
        if any(utils.CommandProcessor.get_is_command(field.prompt)):
            return interaction, utils.FilledField(
                user_id=target_user.id,
                name=profile_name,
                field_id=field.id,
                value=vbu.translation(interaction, "profile_commands").gettext("Could not get field information."),
                field=field,
            )

        # Send the user the prompt
        modal = discord.ui.Modal(
            title=field.name[:45],
            custom_id=f"{id_to_use} {field.id}",
            components=[
                discord.ui.ActionRow(
                    discord.ui.InputText(
                        label=field.prompt[:45],
                        required=not field.optional,
                        custom_id=f"fieldText {field.id}",
                        value=current_value,
                        style=discord.TextStyle.long,
                        min_length=None if field.optional else 1,
                        max_length=1_000,
                    )
                )
            ]
        )

        # Ask the user for their input, loop until they give something valid
        invalid_message: Optional[discord.WebhookMessage] = None  # the message used to show errors
        while True:

            # Send the modal
            assert interaction.user
            try:
                await interaction.response.send_modal(modal)
            except discord.InteractionResponded as e:
                await interaction.followup.send(f"{interaction.user.mention} You hit an interaction responded error ({e}) - could you tell the dev how you did that? https://discord.gg/vfl")
                raise
            except discord.HTTPException as e:
                await interaction.followup.send(f"{interaction.user.mention} You hit a form body error ({e}) - could you tell the dev how you did that? https://discord.gg/vfl")
                raise

            # Wait for the user's input
            try:
                interaction = await ctx.bot.wait_for(
                    "modal_submit",
                    check=lambda i: i.user.id == ctx.author.id and i.custom_id == modal.custom_id,
                    timeout=60 * 10,
                )

            # We timed out waiting
            except asyncio.TimeoutError:
                try:
                    error_text = vbu.translation(interaction, "profile_commands").gettext(
                        "Timed out waiting for you to continue."
                    )
                    await interaction.edit_original_message(
                        content=error_text,
                    )
                except discord.HTTPException:
                    pass
                return (interaction, None)  # return responded interaction

            # Try and validate their input
            field_content: str = interaction.components[0].components[0].value.strip()  # type: ignore
            await interaction.response.defer_update()
            try:
                if field_content:
                    if hasattr(field.field_type, "fix"):
                        field_content = await field.field_type.fix(field_content)  # type: ignore
                    field.field_type.check(field_content)
                break
            except utils.errors.FieldCheckFailure as e:
                if invalid_message:
                    meth = invalid_message.edit
                    kwargs = {}
                else:
                    meth = interaction.followup.send
                    kwargs = {"ephemeral": True}
                invalid_message = await meth(
                    content=e.message,
                    components=discord.ui.MessageComponents(
                        discord.ui.ActionRow(
                            discord.ui.Button(
                                label=vbu.translation(interaction, "profile_commands").gettext("Okay"),
                                custom_id=f"{id_to_use} {new_interaction_id}",
                            )
                        )
                    ),
                    **kwargs,
                )

            # Wait for them to click the okay button
            try:
                interaction = await ctx.bot.wait_for(
                    "component_interaction",
                    check=lambda i: i.user.id == ctx.author.id and i.custom_id == f"{id_to_use} {new_interaction_id}",
                    timeout=60 * 3,
                )
            except asyncio.TimeoutError:
                try:
                    await interaction.edit_original_message(
                        content=vbu.translation(interaction, "profile_commands").gettext(
                            "Timed out waiting for you to continue."
                        ),
                        components=None
                    )
                except discord.HTTPException:
                    pass
                return (interaction, None)

        # Delete any errant erorr messages
        if invalid_message:
            try:
                await invalid_message.edit(
                    content=vbu.translation(interaction, "profile_commands").gettext("Error resolved."),
                    components=None,
                )
            except:
                pass

        # Add their filled field object to the list of data
        return interaction, utils.FilledField(
            user_id=target_user.id,
            name=profile_name,
            field_id=field.field_id,
            value=field_content,
            field=field,
        )

    @commands.command(hidden=True)
    @commands.bot_has_permissions(send_messages=True)
    @commands.guild_only()
    @vbu.checks.meta_command()
    async def set_profile_meta(
            self,
            ctx: utils.types.GuildContext,
            target_user: Optional[Union[discord.Member, discord.User]] = None
            ):
        """
        Talks a user through setting up a profile on a given server.
        """

        await self.edit_or_create_profile(
            ctx,
            ctx.interaction,
            ctx.template,
            ctx.author,
            None,
        )

    @commands.command(hidden=True)
    @commands.bot_has_permissions(send_messages=True)
    @commands.guild_only()
    @vbu.checks.meta_command()
    async def edit_profile_meta(
            self,
            ctx: utils.types.GuildContext,
            *,
            profile_name: str
            ):
        """
        Edit one of your profiles.
        """

        await self.edit_or_create_profile(
            ctx,
            ctx.interaction,
            ctx.template,
            ctx.author,
            profile_name,
        )

    async def get_field_content_with_dispatch(
            self,
            ctx: utils.types.GuildContext,
            interaction: discord.Interaction,
            id_to_use: str,
            profile_name: str,
            field: utils.Field,
            user: Union[discord.User, discord.Member],
            current_value: Optional[str] = None
            ):
        filled_field_modal, response_field = await self.get_field_content(
            ctx,
            interaction,
            id_to_use,
            profile_name,
            field,
            user,
            current_value=current_value,
        )
        self.bot.dispatch("profile_edit_update", filled_field_modal, response_field)

    async def edit_or_create_profile(
            self,
            ctx: utils.types.GuildContext,
            interaction: discord.Interaction,
            template: utils.Template,
            user: discord.Member,
            profile_name: Optional[str],
            ):

        # Set up some variables
        assert ctx.author
        assert isinstance(user, discord.Member)

        # See if the user is already setting up a profile
        if self.set_profile_locks[ctx.author.id].locked():
            component_id = self.profile_lock_uuids.get(ctx.author.id)
            if component_id is None:
                components = discord.utils.MISSING
            else:
                components = discord.ui.MessageComponents(
                    discord.ui.ActionRow(
                        discord.ui.Button(
                            label=vbu.translation(interaction, "profile_commands").gettext("Cancel profile setup"),
                            custom_id=f"{component_id} CANCEL",
                        ),
                    )
                )
            return await interaction.response.send_message(
                vbu.translation(interaction, "profile_commands").gettext("You're already setting up a profile."),
                components=components,
                ephemeral=True,
            )

        # Get all necessary profiles
        user_profiles = []
        async with vbu.Database() as db:
            await template.fetch_fields(db)

            # A profile name was provided - fetch that
            if profile_name:
                user_profile = await template.fetch_profile_for_user(db, user.id, profile_name)
                if not user_profile:
                    return await interaction.response.send_message(
                        vbu.translation(interaction, "profile_commands").gettext("Failed to get that profile."),
                        ephemeral=True,
                    )

            # No profile name was provided - get all and check count
            else:
                user_profiles = await template.fetch_all_profiles_for_user(db, user.id)
                if len(user_profiles) >= template.max_profile_count:
                    error_text = vbu.translation(interaction, "profile_commands").gettext(
                        "You're already at the maximum number of profiles set for **{template_name}**."
                    ).format(template_name=template.name)
                    return await interaction.response.send_message(error_text, ephemeral=True,)
                user_profile = utils.UserProfile(
                    user_id=user.id,
                    name="",  # Blank string for now, but it'll be set later
                    template_id=template.template_id,
                    verified=template.verification_channel_id is None
                )

        # See if the template is accepting more profiles - if not then leave it be
        if template.max_profile_count == 0:
            error_text = vbu.translation(interaction, "profile_commands").gettext(
                "Currently the template **{template_name}** is not accepting any more applications.",
            ).format(template_name=template.name)
            return await interaction.response.send_message(error_text, ephemeral=True)

        # If we don't have a profile name, let's ask for one
        if not profile_name:
            interaction, profile_name = await self.get_profile_name(ctx, interaction, template, user_profiles)
            if not profile_name:
                return
            user_profile.name = profile_name

        # Drag the user into the create profile lock
        async with self.set_profile_locks[ctx.author.id]:

            # Make the buttons that the user can click to fill in their profile
            filled_field_dict: Dict[str, utils.FilledField] = user_profile.all_filled_fields
            component_id = str(uuid.uuid4())
            self.profile_lock_uuids[ctx.author.id] = component_id
            buttons = [
                discord.ui.Button(
                    label=field.name,
                    custom_id=f"{component_id} {field.id}",
                    disabled=any(utils.CommandProcessor.get_is_command(field.prompt)),
                    style=(
                        discord.ButtonStyle.primary
                        if any(utils.CommandProcessor.get_is_command(field.prompt)) or field.id in filled_field_dict or field.optional
                        else discord.ButtonStyle.secondary
                    ),
                )
                for field in template.field_list
            ]
            buttons.append(
                discord.ui.Button(
                    label=vbu.translation(interaction, "profile_commands").gettext("Done"),
                    custom_id=f"{component_id} DONE",
                    disabled=len([i for i in buttons if not i.disabled and i.style == discord.ButtonStyle.secondary]) > 0,
                    style=discord.ButtonStyle.success,
                )
            )
            buttons.append(
                discord.ui.Button(
                    label=vbu.translation(interaction, "profile_commands").gettext("Cancel"),
                    custom_id=f"{component_id} CANCEL",
                    style=discord.ButtonStyle.danger,
                )
            )

            # Add the auto-filled fields to their list
            for field in template.field_list:
                if any(utils.CommandProcessor.get_is_command(field.prompt)):
                    filled_field_dict[field.id] = utils.FilledField(
                        user_id=user.id,
                        name=user_profile.name,
                        field_id=field.id,
                        value="Could not get field information",
                        field=field,
                    )

            # Set a flag for if we want to edit the original
            message_sent = False

            # Loop forever until they click the done or cancel button
            while True:

                # Edit the message
                components = discord.ui.MessageComponents.add_buttons_with_rows(*buttons)
                if not message_sent:
                    await interaction.response.send_message(
                        vbu.translation(interaction, "profile_commands").gettext("What attribute do you want to edit?"),
                        components=components,
                        ephemeral=True,
                    )
                    message_sent = True
                else:
                    await interaction.edit_original_message(
                        components=components,
                    )

                # Wait for the user to click a button OR for an update signal
                try:
                    done, pending = await asyncio.wait(
                        [
                            self.bot.wait_for(
                                "component_interaction",
                                check=lambda i: i.user.id == ctx.author.id and i.custom_id.startswith(component_id),
                            ),
                            self.bot.wait_for(
                                "profile_edit_update",
                                check=lambda i, ff: i.user.id == ctx.author.id and i.custom_id.startswith(component_id),
                            ),
                        ],
                        return_when=asyncio.FIRST_COMPLETED,
                        timeout=60 * 15,
                    )
                except asyncio.TimeoutError:
                    return
                for p in pending:
                    p.cancel()

                # Work out what was clicked
                response_field: Optional[utils.FilledField] = None
                try:
                    button_click: discord.Interaction[str] = done.pop().result()
                except KeyError:
                    return
                try:
                    button_click, response_field = button_click  # type: ignore - is a profile edit update
                except TypeError:
                    pass

                # See which button they've clicked
                _, field_id = button_click.custom_id.split(" ")  # type: ignore

                # Cancel button was clicked
                if field_id == "CANCEL":
                    await button_click.response.edit_message(
                        content=vbu.translation(interaction, "profile_commands").gettext("Cancelled profile setup."),
                        components=None,
                        embed=None,
                    )
                    return

                # Done button was clicked
                elif field_id == "DONE":
                    interaction = button_click
                    break

                # No button was clicked - this is a callback from an edit
                elif response_field:
                    filled_field_dict[response_field.field_id] = response_field
                    secondary_count = 0
                    for b in buttons:
                        if b.custom_id.split(" ")[-1] == response_field.field_id:
                            b.style = discord.ButtonStyle.primary
                        if b.style == discord.ButtonStyle.secondary:
                            secondary_count += 1
                    if secondary_count == 0:
                        for b in buttons:
                            if b.custom_id.endswith(" DONE"):
                                b.enable()
                    continue

                # One of the field buttons was clicked
                try:
                    field = template.fields[field_id]

                # Invalid field ID
                except KeyError:
                    continue

                # Send them a modal
                current_response = filled_field_dict.get(field.field_id)
                if current_response is not None:
                    current_response = current_response.value
                self.bot.loop.create_task(self.get_field_content_with_dispatch(
                    ctx,
                    button_click,
                    component_id,
                    user_profile.name,
                    field,
                    user,
                    current_value=current_response,
                ))

        # Make the user profile object and add all of the filled fields
        user_profile.template = template
        user_profile.all_filled_fields = filled_field_dict

        # Make sure that the embed sends
        await interaction.response.edit_message(
            content=vbu.translation(interaction, "profile_commands").gettext("Sending profile..."),
            embeds=[],
            components=None,
        )
        try:
            await interaction.followup.send(
                embed=user_profile.build_embed(self.bot, interaction, user),
                ephemeral=True,
            )
        except discord.HTTPException as e:
            error_text = vbu.translation(interaction, "profile_commands").gettext(
                "I failed to send your profile to you - `{error_text}`.",
            ).format(error_text=str(e))
            return await interaction.followup.send(error_text, ephemeral=True)

        # Delete the currently archived message
        await user_profile.delete_message(self.bot)

        # Send a new profile submission to the guild
        profile_verification: typing.Optional[ProfileVerification] = self.bot.get_cog("ProfileVerification")  # type: ignore
        assert profile_verification
        sent_profile_message = await profile_verification.send_profile_submission(ctx, user_profile, user)
        if user_profile.template.should_send_message and sent_profile_message is None:
            return

        # Get the message attributes
        sent_profile_message_id = None
        sent_profile_channel_id = None
        if sent_profile_message:
            sent_profile_message_id = sent_profile_message.id
            sent_profile_channel_id = sent_profile_message.channel.id

        # Save the new created profile in the database
        async with vbu.Database() as db:
            try:
                await db(
                    """INSERT INTO created_profile (user_id, name, template_id, verified, posted_message_id, posted_channel_id)
                    VALUES ($1, $2, $3, $4, $5, $6) ON CONFLICT (user_id, name, template_id)
                    DO UPDATE SET verified=excluded.verified, posted_message_id=excluded.posted_message_id,
                    posted_channel_id=excluded.posted_channel_id""",
                    user_profile.user_id, user_profile.name, user_profile.template.template_id, user_profile.verified,
                    sent_profile_message_id, sent_profile_channel_id,
                )
            except asyncpg.ForeignKeyViolationError:
                error_text = vbu.translation(interaction, "profile_commands").gettext(
                    "It looks like the template was deleted while you were setting up your profile.",
                )
                return await interaction.followup.send(
                    error_text,
                    ephemeral=True,
                )
            for field in filled_field_dict.values():
                await db(
                    """INSERT INTO filled_field (user_id, name, field_id, value) VALUES ($1, $2, $3, $4)
                    ON CONFLICT (user_id, name, field_id) DO UPDATE SET value=excluded.value""",
                    field.user_id, user_profile.name, field.field_id, field.value,
                )

        # Respond to user
        if template.get_verification_channel_id(user):
            message = vbu.translation(interaction, "profile_commands").gettext(
                "Your profile has been sent to the **{guild_name}** staff team for verification - please hold tight!",
            ).format(guild_name=ctx.guild.name)
        else:
            message = vbu.translation(interaction, "profile_commands").gettext(
                "Your profile has been created and saved.",
            )
        await interaction.edit_original_message(
            content=message,
        )

    @commands.command(hidden=True)
    @commands.bot_has_permissions(send_messages=True)
    @commands.guild_only()
    @vbu.checks.meta_command()
    async def delete_profile_meta(
            self,
            ctx: utils.types.GuildContext,
            user: Optional[discord.Member] = None,
            *,
            profile_name: str):
        """
        Handles deleting a profile.
        """

        # You can only delete someone else's profile if you're a moderator
        if user and ctx.author != user and not utils.checks.member_is_moderator(self.bot, ctx.author):
            raise commands.MissingPermissions(["manage_roles"])

        # Get the profile
        template: utils.Template = ctx.template
        async with vbu.Database() as db:
            user_profile = await template.fetch_profile_for_user(
                db,
                (user or ctx.author).id,
                profile_name,
                fetch_filled_fields=True,
            )

        # There's no profile with that name given
        if user_profile is None:
            if profile_name:
                text = vbu.translation(ctx, "profile_commands").gettext(
                    "You don't have a profile for **{template_name}** with the name **{profile_name}**."
                )
            else:
                text = vbu.translation(ctx, "profile_commands").gettext(
                    "You don't have any profiles for **{template_name}**."
                )
            text.format(template_name=template.name, profile_name=profile_name)
            return await ctx.send(text, allowed_mentions=discord.AllowedMentions.none())

        # Ask if they're sure
        component_id = str(uuid.uuid4())
        are_you_sure_message = await ctx.send(
            vbu.translation(ctx, "profile_commands").gettext(
                "Are you sure you want to delete this profile?"
            ),
            embed=user_profile.build_embed(self.bot, ctx, user or ctx.author),
            components=discord.ui.MessageComponents.boolean_buttons(
                yes=(vbu.translation(ctx, "profile_commands").gettext("Yes"), f"{component_id} YES",),
                no=(vbu.translation(ctx, "profile_commands").gettext("No"), f"{component_id} NO",),
            ),
        )
        try:
            interaction = await self.bot.wait_for(
                "component_interaction",
                check=lambda i: i.user.id == ctx.author.id and i.custom_id.startswith(component_id),
                timeout=60 * 2,
            )
        except asyncio.TimeoutError:
            try:
                await are_you_sure_message.edit(
                    content=vbu.translation(ctx, "profile_commands").gettext(
                        "Timed out waiting for you to continue.",
                    ),
                    embed=None,
                    components=None,
                )
            except discord.HTTPException:
                pass
            return

        # They're not sure
        if interaction.custom_id.endswith("NO"):
            return await interaction.response.edit_message(
                content=vbu.translation(interaction, "profile_commands").gettext(
                    "Cancelled profile delete."
                ),
                embed=None,
                components=None,
            )

        # They want to delete
        await interaction.response.defer_update()

        # Delete the currently archived message, should one exist
        current_profile_message = await user_profile.fetch_message(self.bot)
        if current_profile_message:
            try:
                await current_profile_message.delete()
            except discord.HTTPException:
                pass

        # Remove it from the database
        user = user or ctx.author
        async with vbu.Database() as db:
            await db(
                """DELETE FROM created_profile WHERE user_id=$1 AND template_id=$2 AND name=$3""",
                user.id, template.template_id, user_profile.name,
            )
        await interaction.followup.send(
            content=vbu.translation(interaction, "profile_commands").gettext(
                "Your profile has been deleted."
            ),
        )

    @commands.command(hidden=True)
    @commands.bot_has_permissions(send_messages=True, embed_links=True)
    @commands.guild_only()
    @vbu.checks.meta_command()
    async def get_profile_meta(
            self,
            ctx: utils.types.GuildContext,
            user: Optional[discord.Member] = None,
            *,
            profile_name: Optional[str] = None,
            ):
        """
        Gets a profile for a given member.
        """

        # See if there's a set profile
        template: utils.Template = ctx.template
        async with vbu.Database() as db:
            user_profile: Optional[utils.UserProfile] = None
            try:
                user_profile = await template.fetch_profile_for_user(db, (user or ctx.author).id, profile_name)
            except ValueError:
                if user:
                    text = vbu.translation(ctx, "profile_commands").gettext(
                        "{user} has multiple profiles for **{template_name}** - you need to specify one.",
                    ).format(user=user.mention, template_name=template.name)
                else:
                    text = vbu.translation(ctx, "profile_commands").gettext(
                        "You have multiple profiles for **{template_name}** - you need to specify one."
                    ).format(template_name=template.name)
                await ctx.send(text, allowed_mentions=discord.AllowedMentions.none())
                return

        if user_profile is None:
            if profile_name:
                if user:
                    text = vbu.translation(ctx, "profile_commands").gettext(
                        "{user} doesn't have a profile for **{template_name}** with the name **{profile_name}**.",
                    ).format(user=user.mention, template_name=template.name, profile_name=profile_name)
                else:
                    text = vbu.translation(ctx, "profile_commands").gettext(
                        "You don't have a profile for **{template_name}** with the name **{profile_name}**.",
                    ).format(template_name=template.name, profile_name=profile_name)
                await ctx.send(text, allowed_mentions=discord.AllowedMentions.none())
            else:
                if user:
                    text = vbu.translation(ctx, "profile_commands").gettext(
                        "{user} doesn't have any profiles for **{template_name}**.",
                    ).format(user=user.mention, template_name=template.name)
                else:
                    text = vbu.translation(ctx, "profile_commands").gettext(
                        "You don't have any profiles for **{template_name}**.",
                    ).format(template_name=template.name)
                await ctx.send(text, allowed_mentions=discord.AllowedMentions.none())
            return

        # See if verified
        if user_profile.verified or utils.checks.member_is_moderator(ctx.bot, ctx.author):
            return await ctx.send(embed=user_profile.build_embed(self.bot, ctx, user or ctx.author))

        # Not verified
        if user:
            text = vbu.translation(ctx, "profile_commands").gettext(
                "{user}'s profile hasn't been verified yet, and thus can't be sent.",
            ).format(user=user.mention)
        else:
            text = vbu.translation(ctx, "profile_commands").gettext(
                "Your profile hasn't been verified yet, and thus can't be sent.",
            )
        await ctx.send(text, allowed_mentions=discord.AllowedMentions.none())
        return


def setup(bot: vbu.Bot):
    x = ProfileCommands(bot)
    bot.add_cog(x)
