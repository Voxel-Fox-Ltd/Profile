from typing import Optional, cast

import discord
from discord.ext import vbu

from cogs import utils


class ProfileVerification(vbu.Cog[vbu.Bot]):

    async def get_archive_channel(
            self,
            guild: discord.Guild,
            member: discord.Member,
            template: utils.Template) -> discord.abc.Messageable | None:
        """
        Get the archive channel from a template.
        """

        # Assert an archive channel existing
        archive_channel_id: Optional[int]
        archive_channel_id = template.get_archive_channel_id(member)
        if archive_channel_id is None:
            return None

        # See if it's a forum
        if template.archive_is_forum:
            threads = await guild.active_threads()
            for thread in threads:
                if thread.parent_id != archive_channel_id:
                    continue
                if thread.owner_id == member.id:
                    return thread
            return None

        # It's not
        return discord.PartialMessageable(
            state=self.bot._connection,
            id=archive_channel_id,
            type=discord.ChannelType.text,
        )

    async def check_if_max_profiles_hit(
            self,
            db: vbu.Database,
            template: utils.Template,
            user_id: int,
            *,
            submitted: bool = False) -> bool:
        """
        Return whether or not the maximum profile count for the user has been
        hit for the given template.
        """

        # See if they're able to submit any more profiles
        all_profiles = await template.fetch_all_profiles_for_user(
            db,
            user_id,
        )
        if submitted:
            return (
                len([i for i in all_profiles if not i.draft])
                >= template.max_profile_count
            )
        return len(all_profiles) >= template.max_profile_count

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
        user = cast(discord.Member, interaction.user)  # May be wrong user, checked later
        self.logger.info(
            "Processing profile submission for %s, profile %s",
            user.id, profile_id,
        )

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

            # Make sure we have the right user
            assert isinstance(interaction.guild, discord.Guild)
            assert profile.user_id
            user = await interaction.guild.fetch_member(profile.user_id)

            # See if they're able to submit any more profiles
            if await self.check_if_max_profiles_hit(
                        db, template, user.id,
                        submitted=True):
                return await interaction.response.edit_message(
                    content=_(
                        "You have already submitted the maximum number of "
                        "profiles for this template."
                    ),
                    components=None,
                )

        # Make sure the embed attached to the message is the same as a
        # newly-made embed (minus the colour)
        embed = profile.build_embed(
            self.bot,
            interaction,
            user,
        )
        current_embed = None
        if interaction.message:
            current_embed = interaction.message.embeds[0]
        if not utils.compare_embeds(embed, current_embed):
            return await interaction.response.edit_message(
                content=_(
                    "This is not the most recent version of the profile. "
                    "Please re-run the edit command to continue."
                ),
                components=None,
            )

        # Defer the interaction so we can post the embed to the archive
        await interaction.response.defer_update()

        # Get our channel IDs
        verification_channel_id = template.get_verification_channel_id(user)
        archive_channel_id = template.get_archive_channel_id(user)
        sent_message: Optional[discord.Message] = None

        # Send to the verification channel
        verified = False  # Whether or not the profile is verified
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
                        "Failed to send the profile to the verification "
                        "channel. Please let an admin know, and then try again "
                        "later."
                    ),
                    components=None,
                )

            # Tell them it's done
            await interaction.edit_original_message(
                content=_("This profile has been submitted for verification."),
                components=None,
            )

        # Send to the verification channel
        elif archive_channel_id is not None:
            channel = await self.get_archive_channel(
                interaction.guild,
                user,
                template,
            )

            # See if we got a channel
            if channel is None:
                await interaction.edit_original_message(
                    content=_(
                        "You don't have an archive thread. Your "
                        "profile has still been approved, but no archive "
                        "message has been sent."
                    ),
                    components=None,
                )

            # Actually do the send
            else:
                embed = profile.build_embed(
                    self.bot,
                    interaction,
                    user,
                )
                try:
                    sent_message = await channel.send(
                        content=f"<@{profile.user_id}>",
                        embed=embed,
                    )
                except discord.HTTPException:
                    return await interaction.edit_original_message(
                        content=_(
                            "Failed to send the profile to the archive "
                            "channel. Please let an admin know, and then try "
                            "again later."
                        ),
                        components=None,
                    )

                # Tell them it's done
                await interaction.edit_original_message(
                    content=_("This profile has been submitted to the archive."),
                    components=None,
                )

            # We done
            verified = True

        # No archive or verification channel; just tell the user it's done :)
        else:
            await interaction.edit_original_message(
                content=_(
                    "This profile has been submitted."
                ),
                components=None,
            )
            verified = True

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
                verified=verified,
            )

        # If they've been verified, add the relevant role to them
        if verified:
            role_id_to_add = template.get_role_id(user)
            if role_id_to_add:
                try:
                    await user.add_roles(
                        discord.Object(role_id_to_add),
                        reason="Profile has been verified.",
                    )
                except discord.HTTPException:
                    await interaction.followup.send(
                        _(
                            "I couldn't add the role to you for some reason. "
                            "Please let an admin know, and they should be able to "
                            "fix this."
                        ),
                        ephemeral=True,
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
        self.logger.info(f"Approving profile {profile_id}")

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
            guild = cast(discord.Guild, interaction.guild)
            assert profile.user_id is not None
            user = await guild.fetch_member(profile.user_id)
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
            channel = await self.get_archive_channel(
                guild,
                user,
                template,
            )

            # Make sure they have a channel
            if channel is None:
                await interaction.followup.send(
                    content=_(
                        "{user} doesn't have an archive thread. Their "
                        "profile has still been approved, but no archive "
                        "message has been sent."
                    ).format(user=f"<@{profile.user_id}>"),
                    ephemeral=True,
                )

            # Actually do the send
            else:
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
        try:
            await interaction.delete_original_message()
        except discord.HTTPException:
            pass

        # Add the role to the user
        role_id_to_add = template.get_role_id(user)
        if role_id_to_add:
            try:
                await user.add_roles(
                    discord.Object(role_id_to_add),
                    reason="Profile has been verified.",
                )
            except discord.HTTPException:
                await interaction.followup.send(
                    _(
                        "I couldn't failed to add the role for this template "
                        "to the user."
                    ),
                    ephemeral=True,
                )

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
        self.logger.info(f"Denying profile {profile_id}")

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
            guild = cast(discord.Guild, interaction.guild)
            assert profile.user_id is not None
            user = await guild.fetch_member(profile.user_id)
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
