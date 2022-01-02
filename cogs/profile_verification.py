import uuid
import typing
import asyncio

import discord
from discord.ext import commands, vbu

from cogs import utils


class ProfileVerification(vbu.Cog):

    async def send_profile_verification(
            self,
            user_profile: utils.UserProfile,
            target_user: discord.Member,
            ) -> typing.Optional[discord.Message]:
        """
        Sends a profile in to the template's verification channel.

        Parameters
        -----------
        user_profile: :class:`utils.UserProfile`
            The profile to be submitted.
        target_user: :class:`discord.Member`
            The owner of the profile.

        Returns
        --------
        Optional[:class:`discord.Message`]
            The message that was sent into the verification channel.

        Raises
        -------
        :exception:`utils.errors.TemplateVerificationChannelError`
            The bot encountered an error sending a message to the verification channel.
        """

        # Grab the verification channel ID
        template: typing.Optional[utils.Template] = user_profile.template
        if template is None:
            raise TypeError("Missing template from user profile.")
        verification_channel_id: typing.Optional[int] = template.get_verification_channel_id(target_user)  # this may raise InvalidCommandText

        # Check if there's a verification channel
        if verification_channel_id is None:
            return None

        # Get the channel
        channel: discord.PartialMessageable = self.bot.get_partial_messageable(verification_channel_id)

        # Send the data
        embed: discord.Embed = user_profile.build_embed(self.bot, target_user)
        embed.set_footer(text=f'{template.name} // Verification Check')
        try:
            components = discord.ui.MessageComponents.add_buttons_with_rows(
                discord.ui.Button(label="Approve", style=discord.ButtonStyle.success, custom_id="VERIFY PROFILE YES"),
                discord.ui.Button(label="Decline", style=discord.ButtonStyle.danger, custom_id="VERIFY PROFILE NO"),
            )
            v = await channel.send(
                (
                    f"New **{template.name}** submission from <@{user_profile.user_id}>\n{user_profile.user_id}/"
                    f"{template.template_id}/{user_profile.name}"
                ),
                embed=embed,
                components=components
            )
        except discord.HTTPException:
            raise utils.errors.TemplateVerificationChannelError(f"I can't send messages to the channel with ID {channel.id}.")

        # Wew nice we're done
        return v

    async def send_profile_archivation(
            self,
            user_profile: utils.UserProfile,
            target_user: discord.Member
            ) -> typing.Optional[discord.Message]:
        """
        Send a profile to the template's archive channel.
        This will also add the given role to the user.
        Yes, archivation is a word.

        Parameters
        -----------
        user_profile: :class:`utils.UserProfile`
            The profile to be submitted.
        target_user: :class:`discord.Member`
            The owner of the profile.

        Returns
        --------
        Optional[:class:`discord.Message`]
            The message that was sent to the archive channel.

        Raises
        -------
        :exception:`utils.errors.TemplateVerificationChannelError`
            The bot encountered an error sending a message to the verification channel.
        """

        # Grab the archive channel ID
        template: typing.Optional[utils.Template] = user_profile.template
        if template is None:
            raise TypeError("Missing template from user profile.")
        archive_channel_id: typing.Optional[int] = template.get_archive_channel_id(target_user)  # this may raise InvalidCommandText

        # Check if there's an archive channel set
        if archive_channel_id is None:
            return None

        # Get the channel
        channel: discord.PartialMessageable = self.bot.get_partial_messageable(archive_channel_id)

        # Send the data
        embed: discord.Embed = user_profile.build_embed(self.bot, target_user)
        try:
            return await channel.send(None if target_user is None else target_user.mention, embed=embed)
        except discord.HTTPException:
            raise utils.errors.TemplateArchiveChannelError(f"I can't send messages to the channel with ID {channel.id}.")

    async def add_profile_user_roles(
            self,
            user_profile: utils.UserProfile,
            target_user: discord.Member,
            ):
        """
        Add the profile roles to a given user.

        Parameters
        -----------
        user_profile: :class:`utils.UserProfile`
            The profile to be submitted.
        target_user: :class:`discord.Member`
            The owner of the profile.

        Raises
        -------
        :exception:`utils.errors.TemplateRoleAddError`
            The bot encountered an error adding the roles to the user.
        """

        # Grab the role ID
        template: typing.Optional[utils.Template] = user_profile.template
        if template is None:
            raise TypeError("Missing template from user profile.")
        role_id: typing.Optional[int] = template.get_role_id(target_user)

        # See if there's a role to add
        if role_id is None:
            return

        # Grab the role
        role_to_add: discord.abc.Snowflake = discord.Object(role_id)
        try:
            await target_user.add_roles(role_to_add, reason="Verified profile")
        except discord.HTTPException:
            raise utils.errors.TemplateRoleAddError(f"I couldn't add a role with the ID `{role_id}`.")

    async def send_profile_submission(
            self,
            ctx: commands.SlashContext,
            user_profile: utils.UserProfile,
            target_user: discord.Member,
            ) -> typing.Optional[discord.Message]:
        """
        Send a profile verification OR archive message for a given profile.
        Returns whether or not the sending was a success.

        Parameters
        -----------
        ctx: :class:`commands.SlashContext`
            The command invocation for the user setting the profile.
        user_profile: :class:`utils.UserProfile`
            The profile being sent.
        target_user: :class:`discord.Member`
            The owner of the profile (may not be the same as ctx.author).

        Returns
        --------
        Optional[:class:`discord.Message`]
            The message that was sent by the bot.
        """

        # Grab the template
        template: typing.Optional[utils.Template] = user_profile.template
        if template is None:
            raise TypeError("Missing template from user profile.")
        return_message = None

        # Run each of the items
        try:
            if template.get_verification_channel_id(target_user):
                return_message = await self.send_profile_verification(user_profile, target_user)
            else:
                return_message = await self.send_profile_archivation(user_profile, target_user)
                await self.add_profile_user_roles(user_profile, target_user)
        except utils.errors.TemplateSendError as e:
            await ctx.author.send(str(e))
            return None

        # Wew it worked
        return return_message

    @vbu.Cog.listener('on_component_interaction')
    async def verification_button_check(self, interaction: discord.Interaction):
        """
        Triggered when a reaction is added or removed, check for profile verification.
        """

        # Make sure that the button is something we want to deal with
        if not interaction.component.custom_id.startswith("VERIFY PROFILE"):
            return

        # Check that both the channel and the message are readable
        message = interaction.message
        if message is None:
            return

        # Check that the message was sent by the bot
        if message.author.id != self.bot.user.id:
            return

        # Check the message's embed
        if not message.embeds:
            return
        embed: discord.Embed = message.embeds[0]
        if not embed.footer:
            return
        if not embed.footer.text:
            return
        if 'Verification Check' not in embed.footer.text:  # type: ignore
            return

        # Get the member who added the reaction
        guild: discord.Guild = interaction.guild  # type: ignore
        moderator: discord.Member = interaction.user  # type: ignore
        if moderator.bot:
            return
        if not utils.checks.member_is_moderator(self.bot, moderator):
            return

        # Check what they reacted with
        verify = interaction.component.custom_id == "VERIFY PROFILE YES"
        return await self.perform_verify(interaction, verify)

    async def perform_verify(
            self,
            interaction: discord.Interaction,
            verify: bool,
            ):
        """
        Perform all of the verification that we may need.

        Parameters
        -----------
        interaction: :class:`discord.Interaction`
            The interaction that triggered the verification.
        verify: :class:`bool`
            Whether or not to verify the profile.
        """

        # Make some assertions to help our typing
        assert interaction.message
        assert interaction.guild

        # Check whom and what we're updating
        try:
            profile_user_id, template_id, profile_name = interaction.message.content.split('\n')[-1].split('/')
        except ValueError:
            profile_user_id, template_id = interaction.message.content.split('\n')[-1].split('/')
            profile_name = 'default'
        profile_user_id = int(profile_user_id)

        # Set up our vars
        user_profile: typing.Optional[utils.UserProfile] = None
        template: typing.Optional[utils.Template] = None

        # Defer before we go into our database
        await interaction.response.defer(ephemeral=True)

        # Decide what we're doing
        async with vbu.Database() as db:

            # See if our tempalte exists
            template = await utils.Template.fetch_template_by_id(db, template_id)
            if template is None:
                await interaction.followup.send(
                    f"Failed to get template with ID `{template_id}`.",
                    ephemeral=True,
                )
                return

            # Get a profile
            user_profile = await template.fetch_profile_for_user(db, profile_user_id, profile_name)

            # And verify if necessary
            if verify:
                await db(
                    """UPDATE created_profile SET verified=true WHERE user_id=$1 AND template_id=$2 AND name=$3""",
                    profile_user_id, template_id, profile_name,
                )
            else:
                await db(
                    """DELETE FROM created_profile WHERE user_id=$1 AND template_id=$2 AND name=$3""",
                    profile_user_id, template_id, profile_name,
                )

        # See if we need to say anything
        if user_profile is None:
            await interaction.message.delete()
            return
        assert user_profile.template

        # Get a denial message if we're not verifying
        denial_reason = "No reason provided."
        modal_submit = None
        if not verify:

            # Ask for a denial reason
            interaction_id = str(uuid.uuid4())
            components = discord.ui.MessageComponents.boolean_buttons(
                yes_id=f"{interaction_id} YES",
                no_id=f"{interaction_id} NO",
            )
            await interaction.followup.send(
                "Would you like to give a denial reason?",
                components=components,
                ephemeral=True,
            )

            # Wait for a button click
            button_click: typing.Optional[discord.Interaction]
            try:
                button_click = await self.bot.wait_for(
                    "component_interaction",
                    check=lambda i: i.user.id == interaction.user.id and i.component.custom_id.startswith(interaction_id),
                    timeout=60 * 2,
                )
            except asyncio.TimeoutError:
                button_click = None

            # If there was one, spawn a modal back at em
            if button_click is not None and button_click.component.custom_id.endswith("YES"):
                modal = discord.ui.Modal(
                    title="Denial Reason",
                    components=[
                        discord.ui.ActionRow(
                            discord.ui.InputText(
                                label="Why are you denying this profile?",
                                style=discord.TextStyle.long,
                                max_length=200,
                            ),
                        ),
                    ],
                )
                await button_click.response.send_modal(modal)

                # Wait for the modal submission
                modal_submit: typing.Optional[discord.Interaction]
                try:
                    modal_submit = await self.bot.wait_for(
                        "modal_submit",
                        check=lambda i: i.custom_id == modal.custom_id,
                        timeout=60 * 5,
                    )
                except asyncio.TimeoutError:
                    modal_submit = None

                # And get the denial reason
                if modal_submit:
                    await modal_submit.response.defer(ephemeral=True)
                    denial_reason = modal_submit.components[0].components[0].value

        # Get the profile user
        profile_user: typing.Optional[discord.Member]
        try:
            profile_user = await interaction.guild.fetch_member(profile_user_id)
        except discord.HTTPException:
            profile_user = None

        # Tell the user about the decision
        if profile_user:
            try:
                embed: discord.Embed = user_profile.build_embed(self.bot, profile_user)
                if verify:
                    await profile_user.send(
                        f"Your profile for **{user_profile.template.name}** (`{user_profile.name}`) on "
                        f"`{interaction.guild.name}` has been verified.",
                        embed=embed,
                    )
                else:
                    await profile_user.send(
                        f"Your profile for **{user_profile.template.name}** (`{user_profile.name}`) on "
                        f"`{interaction.guild.name}` has been denied with the reason `{denial_reason}`.",
                        embed=embed,
                    )
            except discord.HTTPException:
                self.logger.info(
                    f"Couldn't DM user {user_profile.user_id} about their '{user_profile.template.name}' "
                    f"profile verification on {interaction.guild.id}"
                )
                pass  # Can't send the user a DM, let's just ignore it

        # Archive and add roles
        if verify and profile_user:

            # Send the profile to the archive
            try:
                await self.send_profile_archivation(user_profile, profile_user)
            except discord.HTTPException:
                pass

            # Add the relevant role to the user
            try:
                await self.add_profile_user_roles(user_profile, profile_user)
            except discord.HTTPException:
                pass

        # And tell the moderator we're done
        await (modal_submit or interaction).followup.send(
            "Profile dealt with successfully.",
            ephemeral=True,
        )


def setup(bot: vbu.Bot):
    x = ProfileVerification(bot)
    bot.add_cog(x)
