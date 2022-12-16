import uuid
from typing import TYPE_CHECKING, Optional, Tuple
import random

import discord
from discord.ext import vbu

from cogs import utils

if TYPE_CHECKING:
    from .profile_verification import ProfileVerification


class ProfileCommands(vbu.Cog[vbu.Bot]):
    """
    Commands and events that allow users to create and manage profiles.
    """

    PROFILES_ARE_PRIVATE = True

    async def try_application_command(
            self,
            db: vbu.Database,
            interaction: discord.CommandInteraction | discord.AutocompleteInteraction) -> Tuple[str, utils.Template] | None:
        """
        Search all rows of the template table in the database to work out
        which context command was called for which template.
        """

        # See if it's a normal slashie
        template_rows = await db.call(
            """
            SELECT
                id
            FROM
                templates
            WHERE
                application_command_id = $1
            """,
            discord.utils._get_as_snowflake(interaction.data, 'id'),
        )
        if template_rows:
            template_id = template_rows[0]['id']
            action = interaction.command_name.split(" ")[-1]
            template = await utils.Template.fetch_template_by_id(
                db,
                template_id,
            )
            try:
                assert template
            except AssertionError as e:
                raise ValueError((
                    f"Somehow failed to get template of id {template_id} via "
                    f"application command ID {interaction.data['id']}"
                )) from e
            return action, template

        # See if it's a context command
        template_rows = await db.call(
            """
            SELECT
                id
            FROM
                templates
            WHERE
                context_command_id = $1
            """,
            interaction.data['id'],
        )
        if template_rows:
            template_id = template_rows[0]['id']
            action = interaction.command_name.split(" ")[-1]
            template = await utils.Template.fetch_template_by_id(
                db,
                template_id,
            )
            try:
                assert template
            except AssertionError as e:
                raise ValueError((
                    f"Somehow failed to get template of id {template_id} via "
                    f"context command ID {interaction.data['id']}"
                )) from e
            return "get", template

        # Oh well
        return None

    @vbu.Cog.listener()
    async def on_autocomplete_interaction(
            self,
            interaction: discord.AutocompleteInteraction):
        """
        Dispatched for all autocompletes. The bot shouldn't have any
        autocompletes other than profiles.
        """

        # Make sure it's not a template autocomplete
        if interaction.command_name.startswith("template "):
            return

        # Try and get the template
        async with vbu.Database() as db:
            ans = await self.try_application_command(
                db,
                interaction,
            )
            if ans is None:
                return
            _, template = ans

            # Get a list of profiles for the user in this template
            profiles = await template.fetch_all_profiles_for_user(
                db,
                interaction.user.id,
                fetch_filled_fields=False,
            )

        # Return them some options
        await interaction.response.send_autocomplete([
            discord.ApplicationCommandOptionChoice(
                name=str(profile.name),
                value=str(profile.id),
            )
            for profile in profiles
        ])

    @vbu.Cog.listener()
    async def on_slash_command(
            self,
            interaction: discord.CommandInteraction):
        """
        Dispatched for slash commands and context commands. Listens for profile
        commands being run and deals with them appropriately.
        """

        # See if it's something we need to look into
        if any((
                interaction.command_name.startswith("template "),
                interaction.command_name == "info",)):
            return

        # Work out the associated template
        async with vbu.Database() as db:
            data = await self.try_application_command(
                db,
                interaction,
            )
        if data is None:
            return
        action, template = data

        # See what they're trying to do
        self.logger.info(
            f"/{template.name} {action} ({template.id}) "
            f"(G{interaction.guild_id}/U{interaction.user.id})"
        )
        match action:
            case "get":
                if interaction.resolved.members:
                    return await self.profile_get(
                        interaction,
                        template,
                        list(interaction.resolved.members.values())[0],
                    )
                else:
                    return await self.profile_get(
                        interaction,
                        template,
                    )
            case "create":
                return await self.profile_create(
                    interaction,
                    template,
                )
            case "delete":
                return await self.profile_delete(
                    interaction,
                    template,
                )
            case "edit":
                return await self.profile_edit(
                    interaction,
                    template,
                )

    @vbu.i18n("profile")
    async def profile_get(
            self,
            interaction: discord.CommandInteraction,
            template: utils.Template,
            user: discord.User | discord.Member | None = None):
        """
        Run when someone tries to get a profile for a given user.
        """

        # See what profiles the user has for that template
        async with vbu.Database() as db:
            user_profiles = await template.fetch_all_profiles_for_user(
                db,
                (user or interaction.user).id,
            )

        # Make sure they have something
        if not user_profiles:
            message = (
                _("You don't have any profiles for the template **{template}**.")
                if user is None
                else
                _("**{user}** doesn't have any profiles for the template **{template}**.")
            )
            return await interaction.response.send_message(
                message.format(
                    user=user.mention if user else None,
                    template=template.name,
                ),
                ephemeral=True,
            )

        # If they only have one, just send that profile
        if len(user_profiles) == 1:
            profile = user_profiles[0]
            return await interaction.response.send_message(
                embeds=[
                    profile.build_embed(
                        self.bot,
                        interaction,
                        user or interaction.user,  # type: ignore
                    ),
                ],
                ephemeral=self.PROFILES_ARE_PRIVATE,
            )

        # If they have multiple, send a dropdown of their profile names
        short_template_id = utils.uuid.encode(user_profiles[0].template_id)
        components = discord.ui.MessageComponents(
            discord.ui.ActionRow(
                discord.ui.SelectMenu(
                    custom_id=(
                        f"PROFILE GET {user_profiles[0].user_id} "
                        f"{short_template_id}"
                    ),
                    options=[
                        discord.ui.SelectOption(
                            label=profile.name,
                            value=str(profile.name),
                        )
                        for profile in user_profiles
                    ],
                    max_values=1,
                    min_values=1,
                ),
            ),
        )
        return await interaction.response.send_message(
            _("Please select a profile to view."),
            components=components,
            ephemeral=True,
        )

    @vbu.Cog.listener("on_component_interaction")
    async def profile_get_dropdown_listener(
            self,
            interaction: discord.ComponentInteraction):
        """
        Listens for a profile select dropdown to be interacted with.
        """

        # Check it's a profile get dropdown
        if not interaction.custom_id.startswith("PROFILE GET"):
            return

        # Get the user ID
        user_id = int(interaction.custom_id.split(" ")[2])

        # Work out our args
        short_template_id = interaction.custom_id.split(" ")[-1]
        template_id = utils.uuid.decode(short_template_id)

        # Open a DB connection for fetching the profile and template
        async with vbu.Database() as db:

            # Get the template
            template = await utils.Template.fetch_template_by_id(
                db,
                template_id,
            )
            assert template, "Template does not exist."

            # Get the profile
            profile = await template.fetch_profile_for_user(
                db,
                user_id,
                interaction.values[0],
            )
            assert profile, "Profile does not exist."

        # Send the profile - defer so it doesn't stay as ephemeral
        await interaction.response.defer_update()
        await interaction.delete_original_message()
        assert isinstance(interaction.user, discord.Member)
        await interaction.followup.send(
            embeds=[
                profile.build_embed(
                    self.bot,
                    interaction,
                    interaction.user,
                ),
            ],
            ephemeral=self.PROFILES_ARE_PRIVATE,
        )

    @vbu.i18n("profile")
    async def profile_delete(
            self,
            interaction: discord.CommandInteraction,
            template: utils.Template):
        """
        Run when someone tries to delete a profile for a given user.
        """

        # See what profiles the user has for that template
        async with vbu.Database() as db:
            profile = await utils.UserProfile.fetch_profile_by_id(
                db,
                (
                    interaction
                    .options[0]  # pyright: ignore
                    .options[0]
                    .value
                ),  # pyright: ignore
            )

        # Do some basic checks
        assert profile, "Profile does not exist."
        assert not profile.deleted
        assert profile.user_id == interaction.user.id

        # Make sure they have something
        if not profile:
            message = _(
                "You don't have a profile for the template **{template}** with that name.",
            )
            return await interaction.response.send_message(
                message.format(template=template.name),
                ephemeral=True,
            )

        # If they only have one, ask if they're sure
        return await self.profile_delete_ask_confirm(interaction, profile)

    async def profile_delete_ask_confirm(
            self,
            interaction: discord.CommandInteraction | discord.ComponentInteraction,
            profile: utils.UserProfile):
        """
        Asks the user to confirm they want to delete a profile.
        """

        message = _(
            "Are you sure you want to delete your profile **{profile}**?",
        )
        message = message.format(profile=profile.name)
        components = discord.ui.MessageComponents(
            discord.ui.ActionRow(
                discord.ui.Button(
                    # TRANSLATORS: This is the label for a button
                    # that confirms a profile deletion
                    label=_("Yes"),
                    custom_id=(
                        f"PROFILE CONFIRM_DELETE "
                        f"{utils.uuid.encode(profile.id)}"
                    ),
                    style=discord.ButtonStyle.danger,
                ),
            ),
        )
        return await interaction.response.send_message(
            message,
            components=components,
            ephemeral=True,
        )

    @vbu.Cog.listener("on_component_interaction")
    @vbu.i18n("profile")
    async def profile_delete_button_listener(
            self,
            interaction: discord.ComponentInteraction):
        """
        Listens for a profile delete button to be interacted with.
        """

        # Check it's a profile delete button
        if not interaction.custom_id.startswith("PROFILE CONFIRM_DELETE "):
            return

        # Get the profile name
        short_profile_id = interaction.custom_id.split(" ")[2]
        profile_id = utils.uuid.decode(short_profile_id)

        # Open a DB connection for fetching the profile
        async with vbu.Database() as db:

            # Get the profile
            profile = await utils.UserProfile.fetch_profile_by_id(
                db,
                profile_id,
            )
            assert profile

            # Set the profile as deleted
            original_name = profile.name
            await profile.update(
                db,
                name=f"{uuid.uuid4()} {profile.name}",
                deleted=True,
            )

        # Send a confirmation message
        message = _("Your profile **{profile}** has been deleted.")
        message = message.format(profile=original_name)
        await interaction.response.edit_message(
            content=message,
            components=None,
        )

    @vbu.Cog.listener("on_component_interaction")
    async def profile_delete_dropdown_listener(
            self,
            interaction: discord.ComponentInteraction):
        """
        Listens for a profile delete dropdown to be interacted with.
        """

        # Check it's a profile delete dropdown
        if not interaction.custom_id.startswith("PROFILE DELETE"):
            return

        # Get the profile
        short_template_id = interaction.custom_id.split(" ")[-1]
        template_id = utils.uuid.decode(short_template_id)
        async with vbu.Database() as db:
            template = await utils.Template.fetch_template_by_id(
                db,
                template_id,
            )
            assert template
            profile = await template.fetch_profile_for_user(
                db,
                interaction.user.id,
                interaction.values[0],
            )
            assert profile

        # Ask them to confirm
        await self.profile_delete_ask_confirm(interaction, profile)

    @vbu.i18n("profile")
    async def profile_edit(
            self,
            interaction: discord.CommandInteraction | discord.ModalInteraction,
            template: utils.Template,
            profile: Optional[utils.UserProfile] = None,
            edit_original: bool = False):
        """
        Run when someone tries to edit a profile for a given user.
        """

        # See what profiles the user has for that template
        if not profile:
            async with vbu.Database() as db:
                profile = await utils.UserProfile.fetch_profile_by_id(
                    db,
                    (
                        interaction
                        .options[0]  # pyright: ignore
                        .options[0]
                        .value
                    ),  # pyright: ignore
                )

                # Make sure they have something
                if not profile:
                    message = _(
                        "You have no profiles for the template "
                        "**{template}** with that name."
                    )
                    return await interaction.response.send_message(
                        message.format(template=template.name),
                        ephemeral=True,
                    )

                # Get fields
                profile.template = template
                await profile.fetch_filled_fields(db)

        # Do some basic checks
        assert not profile.deleted
        assert profile.user_id == interaction.user.id

        # And let's go
        profile.template = template
        short_profile_id = utils.uuid.encode(profile.id)

        # Make sure the profile is a draft
        if not profile.draft:
            buttons = [
                discord.ui.Button(
                    # TRANSLATORS: The confirm button for editing a profile
                    label=_("Yes"),
                    custom_id=f"PROFILE CONFIRM_EDIT {short_profile_id}",
                    style=discord.ButtonStyle.success,
                ),
            ]
            return await interaction.response.send_message(
                _(
                    "To edit this profile, it must be converted to a "
                    "draft. This will unsubmit it, and it will need to be "
                    "re-verified before others can see it again. "
                    "Are you sure you want to continue?"
                ),
                components=(
                    discord.ui.MessageComponents
                    .add_buttons_with_rows(*buttons)
                ),
                ephemeral=True,
            )

        # Make buttons for them to edit
        buttons = [
            discord.ui.Button(
                # TRANSLATORS: This is the label for a button
                # that edits a profile's name
                label=_("Edit profile name"),
                custom_id=f"PROFILE EDIT_NAME {short_profile_id}",
                style=discord.ButtonStyle.success,
            ),
        ]
        unfilled_field_count = 0
        for field in profile.template.field_list:
            short_field_id = utils.uuid.encode(field.id)
            button_style = (
                discord.ButtonStyle.secondary
                if
                    profile.filled_fields.get(field.id)
                or
                    field.is_command
                or
                    field.optional
                else
                    discord.ButtonStyle.danger
            )
            if button_style is discord.ButtonStyle.danger:
                unfilled_field_count += 1
            buttons.append(
                discord.ui.Button(
                    label=field.name,
                    custom_id=f"PROFILE EDIT {short_profile_id} {short_field_id}",
                    style=button_style,
                    disabled=field.is_command,
                )
            )
        buttons.append(
            discord.ui.Button(
                # TRANSLATORS: This is the label for a button that submits
                # a profile.
                label=_("Submit"),
                custom_id=f"PROFILE SUBMIT {short_profile_id}",
                style=discord.ButtonStyle.success,
                disabled=unfilled_field_count > 0,
            ),
        )
        components = (
            discord.ui.MessageComponents
            .add_buttons_with_rows(*buttons)
        )

        # Send the buttons
        assert isinstance(interaction.user, discord.Member)
        embed = profile.build_embed(self.bot, interaction, interaction.user)
        if edit_original:
            await interaction.edit_original_message(
                content=_("What would you like to edit?"),
                embeds=[embed],
                components=components,
            )
        else:
            await interaction.response.send_message(
                _("What would you like to edit?"),
                embeds=[embed],
                components=components,
                ephemeral=True,
            )

    @vbu.i18n("profile")
    async def profile_create(
            self,
            interaction: discord.CommandInteraction,
            template: utils.Template):
        """
        Run when someone tries to create a profile for a given user.
        """

        # Get a random name from the animals file
        with open("config/animals.txt") as f:
            animals = f.read().strip().splitlines()
        name = random.choice(animals)

        # Create a usable profile
        profile = utils.UserProfile(
            user_id=interaction.user.id,
            template_id=template.id,
            name=name,
            draft=True,
            verified=False,
        )
        profile.template = template

        # Create an ID for that user's profile
        async with vbu.Database() as db:

            # See if they're able to submit any more profiles
            cog: Optional[ProfileVerification]
            cog = self.bot.get_cog("ProfileVerification")  # type: ignore
            assert cog, "Cog not loaded."
            if await cog.check_if_max_profiles_hit(db, template, interaction.user.id):
                return await interaction.response.send_message(
                    content=_(
                        "You have already submitted the maximum number of "
                        "profiles for this template."
                    ),
                    ephemeral=True,
                )

            # If they can, save this one
            await profile.update(db)

        # And update the message
        return await self.profile_edit(interaction, template, profile)


def setup(bot: vbu.Bot):
    x = ProfileCommands(bot)
    bot.add_cog(x)
