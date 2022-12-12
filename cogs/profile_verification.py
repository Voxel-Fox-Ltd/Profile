from typing import Optional, cast

import discord
from discord.ext import vbu

from cogs import utils


class ProfileVerification(vbu.Cog[vbu.Bot]):

    @vbu.Cog.listener("on_component_interaction")
    @vbu.i18n("profile")
    async def submit_button_press(
            self,
            interaction: discord.ComponentInteraction):
        """
        Submit a profile for verification.
        """

        # Make sure we're looking at the right component
        if not interaction.custom_id.startswith("PROFILE SUBMIT "):
            return

        # Get the profile ID
        short_profile_id = interaction.custom_id.split(" ")[2]
        profile_id = utils.uuid.decode(short_profile_id)
        user = cast(discord.Member, interaction.user)

        # Get the profile object
        async with vbu.Database() as db:
            profile = await utils.UserProfile.fetch_profile_by_id(
                db,
                profile_id,
            )
            assert profile, "That profile does not exist."
            template = await profile.fetch_template(db)
            assert template, "That template does not exist."
            await profile.fetch_filled_fields(db)

            # See if the profile has already been submitted
            if not profile.draft:
                await interaction.response.edit_message(
                    content=_("This profile has already been submitted."),
                    components=None,
                )
                return

            # Make sure the embed attached to the message is the same as a
            # newly-made embed (minus the colour)
            embed = profile.build_embed(
                self.bot,
                interaction,
                user,
            )
            embed.colour = 0
            embed.remove_footer()
            current_embed = None
            if interaction.message:
                current_embed = interaction.message.embeds[0]
                current_embed.colour = 0
                current_embed.remove_footer()
            if not embed == current_embed:
                return await interaction.response.send_message(
                    _(
                        "This is not the most recent version of your profile. "
                        "Please re-run the edit command to continue."
                    ),
                    ephemeral=True,
                )

        # Defer the interaction so we can post the embed to the archive
        await interaction.response.defer_update()

        # Get our channel IDs
        verification_channel_id = template.get_verification_channel_id(user)
        archive_channel_id = template.get_archive_channel_id(user)
        sent_message: Optional[discord.Message] = None

        # Send to the verification channel
        if verification_channel_id is not None:
            channel = discord.PartialMessageable(
                state=self.bot._connection,
                id=verification_channel_id,
                type=discord.ChannelType.text,
            )

            # Actually do the send
            embed = profile.build_embed(
                self.bot,
                interaction,
                user,
            )
            try:
                sent_message = await channel.send(
                    content=profile.id,
                    embed=embed,
                    allowed_mentions=discord.AllowedMentions.none(),
                    components=discord.ui.MessageComponents(
                        discord.ui.ActionRow(
                            discord.ui.Button(
                                # TRANSLATORS: Label for a button to approve
                                # a profile
                                label=_("Approve"),
                                style=discord.ButtonStyle.success,
                                custom_id=f"PROFILE APPROVE {short_profile_id}",
                            ),
                            discord.ui.Button(
                                # TRANSLATORS: Label for a button to deny
                                # a profile
                                label=_("Deny"),
                                style=discord.ButtonStyle.danger,
                                custom_id=f"PROFILE DENY {short_profile_id}",
                            ),
                        ),
                    ),
                )
            except discord.HTTPException:
                return await interaction.edit_original_message(
                    content=_(
                        "Failed to send your profile to the verification "
                        "channel. Please let an admin know, and then try again "
                        "later."
                    ),
                )

            # Tell them it's done
            await interaction.edit_original_message(
                content=_("Your profile has been submitted for verification."),
            )

        # Send to the verification channel
        elif archive_channel_id is not None:
            channel = discord.PartialMessageable(
                state=self.bot._connection,
                id=archive_channel_id,
                type=discord.ChannelType.text,
            )

            # Actually do the send
            embed = profile.build_embed(
                self.bot,
                interaction,
                user,
            )
            try:
                sent_message = await channel.send(
                    content=profile.id,
                    embed=embed,
                    allowed_mentions=discord.AllowedMentions.none(),
                )
            except discord.HTTPException:
                return await interaction.edit_original_message(
                    content=_(
                        "Failed to send your profile to the archive "
                        "channel. Please let an admin know, and then try "
                        "again later."
                    ),
                )

            # Tell them it's done
            await interaction.edit_original_message(
                content=_("Your profile has been submitted to the archive."),
            )

        # Save newly sent message
        async with vbu.Database() as db:
            await profile.update(
                db,
                posted_message_id=(
                    sent_message.id if sent_message else None
                ),
                posted_channel_id=(
                    sent_message.channel.id if sent_message else None
                ),
                draft=False,
                verified=False,
            )

    @vbu.Cog.listener("on_component_interaction")
    @vbu.i18n("profile")
    async def approve_button_clicked(
            self,
            interaction: discord.ComponentInteraction):
        """
        Run when the approve button is pressed for a profile.
        """

        # Make sure we're looking at the right interaction
        if not interaction.custom_id.startswith("PROFILE APPROVE "):
            return
        await interaction.response.defer_update()

        # Get the profile ID
        short_profile_id = interaction.custom_id.split(" ")[2]
        profile_id = utils.uuid.decode(short_profile_id)

        # Get the profile object
        async with vbu.Database() as db:
            profile = await utils.UserProfile.fetch_profile_by_id(
                db,
                profile_id,
            )
            assert profile, "That profile does not exist."
            template = await profile.fetch_template(db)
            assert template, "That template does not exist."
            await profile.fetch_filled_fields(db)

        # Get the user so we can build their embed properly
        user: discord.Member
        try:
            user = await (
                interaction
                .guild
                .fetch_member(profile.user_id)
            )
        except (discord.HTTPException):

            # The user left the guild - convert their profile back to a draft
            # and leave it at that.
            async with vbu.Database() as db:
                await profile.update(
                    db,
                    verified=False,
                    draft=True,
                )
            await interaction.delete_original_message()
            return

        # Get where the template should be posted to
        sent_message: Optional[discord.Message] = None
        archive_channel_id = template.get_archive_channel_id(user)
        if archive_channel_id is not None:
            channel = discord.PartialMessageable(
                state=self.bot._connection,
                id=archive_channel_id,
                type=discord.ChannelType.text,
            )

            # Actually do the send
            embed = profile.build_embed(
                self.bot,
                interaction,
                user,
            )
            try:
                sent_message = await channel.send(
                    content=f"<@{profile.user_id}>",
                    embed=embed,
                    # allowed_mentions=discord.AllowedMentions.none(),
                )
            except discord.HTTPException:
                await interaction.followup.send(
                    _(
                        "Failed to send the profile to the archive "
                        "channel."
                    ),
                    ephemeral=True,
                )

        # Save the new data into the database
        async with vbu.Database() as db:
            await profile.update(
                db,
                draft=False,
                verified=True,
                posted_message_id=(
                    sent_message.id if sent_message else None
                ),
                posted_channel_id=(
                    sent_message.channel.id if sent_message else None
                ),
            )

        # Try and tell the user it's been approved
        try:
            await user.send(
                _(
                    "Your profile has been approved and is now "
                    "publicly available :)"
                ),
                embeds=interaction.message.embeds,
            )
        except discord.HTTPException:
            pass

        # Delete the original message
        await interaction.delete_original_message()

    @vbu.Cog.listener("on_component_interaction")
    @vbu.i18n("profile")
    async def deny_button_clicked(
            self,
            interaction: discord.ComponentInteraction):
        """
        Run when the deny button is pressed for a profile.
        """

        # Make sure we're looking at the right interaction
        if not interaction.custom_id.startswith("PROFILE DENY "):
            return
        await interaction.response.defer_update()

        # Get the profile ID
        short_profile_id = interaction.custom_id.split(" ")[2]
        profile_id = utils.uuid.decode(short_profile_id)

        # Get the profile object
        async with vbu.Database() as db:
            profile = await utils.UserProfile.fetch_profile_by_id(
                db,
                profile_id,
            )
            assert profile, "That profile does not exist."
            template = await profile.fetch_template(db)
            assert template, "That template does not exist."
            await profile.fetch_filled_fields(db)

        # Get the user so we can build their embed properly
        user: discord.Member
        try:
            user = await (
                interaction
                .guild
                .fetch_member(profile.user_id)
            )
        except (discord.HTTPException):

            # The user left the guild - convert their profile back to a draft
            # and leave it at that.
            async with vbu.Database() as db:
                await profile.update(
                    db,
                    verified=False,
                    draft=True,
                    posted_message_id=None,
                    posted_channel_id=None,
                )
            await interaction.delete_original_message()
            return

        # Save the new data into the database
        async with vbu.Database() as db:
            await profile.update(
                db,
                verified=False,
                draft=True,
                posted_message_id=None,
                posted_channel_id=None,
            )

        # Try and tell the user it's been approved
        try:
            await user.send(
                _(
                    "Your profile has been denied."
                ),
                embeds=interaction.message.embeds,
            )
        except discord.HTTPException:
            pass

        # Delete the original message
        await interaction.delete_original_message()


def setup(bot: vbu.Bot):
    x = ProfileVerification(bot)
    bot.add_cog(x)
