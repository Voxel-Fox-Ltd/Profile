import uuid
from typing import Optional, Tuple
import random

import discord
from discord.ext import vbu

from cogs import utils


class ProfileCommands(vbu.Cog[vbu.Bot]):
    """
    Commands and events that allow users to create and manage profiles.
    """

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
            assert template
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
            assert template
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

        # Try and get the template
        async with vbu.Database() as db:
            ans = await self.try_application_command(
                db,
                interaction,
            )
            if ans is None:
                return
            subcommand, template = ans

            # Get a list of profiles for the user in this template
            profiles = await template.fetch_all_profiles_for_user(
                db,
                interaction.user.id,
                fetch_filled_fields=False,
            )

        # Return them some options
        await interaction.response.send_autocomplete([
            discord.ApplicationCommandOptionChoice(
                name=profile.name,
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
        match action:
            case "get":
                return await self.profile_get(interaction, template)
            case "create":
                return await self.profile_create(interaction, template)
            case "delete":
                return await self.profile_delete(interaction, template)
            case "edit":
                return await self.profile_edit(interaction, template)

    @vbu.i18n(__name__)
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
                ]
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
            assert template

            # Get the profile
            profile = await template.fetch_profile_for_user(
                db,
                user_id,
                interaction.values[0],
            )
            assert profile

        # Send the profile - defer so it doesn't stay as ephemeral
        await interaction.response.defer_update()
        await interaction.delete_original_message()
        await interaction.followup.send(
            embeds=[
                profile.build_embed(
                    self.bot,
                    interaction,
                    interaction.user,
                ),
            ],
        )

    @vbu.i18n(__name__)
    async def profile_delete(
            self,
            interaction: discord.CommandInteraction,
            template: utils.Template):
        """
        Run when someone tries to delete a profile for a given user.
        """

        # See what profiles the user has for that template
        async with vbu.Database() as db:
            user_profiles = await template.fetch_profile_for_user(
                db,
                interaction.user.id,
                interaction.options[0].options[0].value,
            )

        # Make sure they have something
        if not user_profiles:
            message = _(
                "You don't have a profile for the template **{template}** with that name.",
            )
            return await interaction.response.send_message(
                message.format(template=template.name),
                ephemeral=True,
            )

        # If they only have one, ask if they're sure
        profile = user_profiles[0]
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
                    label=_("Yes."),
                    custom_id=(
                        f"PROFILE CONFIRM_DELETE "
                        f"{profile.template_id} {profile.name}"
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
    async def profile_delete_button_listener(
            self,
            interaction: discord.ComponentInteraction):
        """
        Listens for a profile delete button to be interacted with.
        """

        # Check it's a profile delete button
        if not interaction.custom_id.startswith("PROFILE CONFIRM_DELETE"):
            return

        # Get the template ID
        template_id = interaction.custom_id.split(" ")[2]

        # Get the profile name
        profile_name = interaction.custom_id.split(" ")[3]

        # Open a DB connection for fetching the profile and template
        async with vbu.Database() as db:

            # Get the template
            template = await utils.Template.fetch_template_by_id(
                db,
                template_id,
            )
            assert template

            # Get the profile
            profile = await template.fetch_profile_for_user(
                db,
                interaction.user.id,
                profile_name,
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
        await interaction.response.send_message(
            message,
            ephemeral=True,
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

    @vbu.i18n(__name__)
    async def profile_edit(
            self,
            interaction: discord.CommandInteraction,
            template: utils.Template,
            profile: Optional[utils.UserProfile] = None):
        """
        Run when someone tries to edit a profile for a given user.
        """

        # See what profiles the user has for that template
        if not profile:
            async with vbu.Database() as db:
                profile = await template.fetch_profile_for_user(
                    db,
                    interaction.user.id,
                    interaction.options[0].options[0].value,
                )

                # Make sure they have something
                if not profile:
                    message = _(
                        (
                            "You have no profiles for the template "
                            "**{template}** with that name."
                        ),
                    )
                    return await interaction.response.send_message(
                        message.format(template=template.name),
                        ephemeral=True,
                    )
        profile.template = template

        # Make buttons for them to edit
        short_profile_id = utils.uuid.encode(profile.id)
        buttons = [
            discord.ui.Button(
                # TRANSLATORS: This is the label for a button
                # that edits a profile's name
                label=_("Edit name"),
                custom_id=f"PROFILE EDIT_NAME {short_profile_id}",
                style=discord.ButtonStyle.primary,
            ),
        ]
        for field in profile.template.field_list:
            buttons.append(
                discord.ui.Button(
                    label=field.name,
                    custom_id=f"PROFILE EDIT {short_profile_id} {field.id}",
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
            ),
        )
        components = discord.ui.MessageComponents.add_buttons_with_rows(*buttons)

        # Send the buttons
        embed = profile.build_embed(self.bot, interaction, interaction.user)
        await interaction.response.send_message(
            _("What would you like to edit?"),
            embeds=[embed],
            components=components,
        )

    @vbu.i18n(__name__)
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
        )
        profile.template = template

        # Create an ID for that user's profile
        async with vbu.Database() as db:
            await profile.update(db)
        return await self.profile_edit(interaction, template, profile)


def setup(bot: vbu.Bot):
    x = ProfileCommands(bot)
    bot.add_cog(x)
