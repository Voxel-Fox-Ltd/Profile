import asyncio
import typing

import discord
import voxelbotutils as utils

from cogs import utils as localutils


class ProfileVerification(utils.Cog):

    TICK_EMOJI = "<:tick_yes:596096897995899097>"
    CROSS_EMOJI = "<:cross_no:596096897769275402>"

    async def send_profile_verification(self, user_profile:localutils.UserProfile, target_user:discord.Member) -> bool:
        """Sends a profile in to the template's verification channel

        Args:
            user_profile (utils.UserProfile): The profile to be submitted
            target_user (discord.Member): The owner of the profile

        Returns:
            bool: Whether or not the verification send was successful
        """

        # Grab the verification channel ID
        template: localutils.Template = user_profile.template
        verification_channel_id: typing.Optional[int] = template.get_verification_channel_id(target_user)  # this may raise InvalidCommandText

        # Check if there's a verification channel
        if verification_channel_id is None:
            return True

        # Get the channel
        try:
            channel: discord.TextChannel = self.bot.get_channel(verification_channel_id) or await self.bot.fetch_channel(verification_channel_id)
            if channel is None:
                raise localutils.errors.TemplateVerificationChannelError(f"I can't reach a channel with the ID `{verification_channel_id}`.")
        except discord.HTTPException:
            raise localutils.errors.TemplateVerificationChannelError(f"I can't reach a channel with the ID `{verification_channel_id}`.")

        # Send the data
        embed: utils.Embed = user_profile.build_embed(target_user)
        embed.set_footer(text=f'{template.name} // Verification Check')
        try:
            v = await channel.send(f"New **{template.name}** submission from <@{user_profile.user_id}>\n{user_profile.user_id}/{template.template_id}/{user_profile.name}", embed=embed)
        except discord.HTTPException:
            raise localutils.errors.TemplateVerificationChannelError(f"I can't send messages to {channel.mention}.")

        # Add reactions to message
        try:
            await v.add_reaction(self.TICK_EMOJI)
            await v.add_reaction(self.CROSS_EMOJI)
        except discord.HTTPException:
            try:
                await v.delete()
            except discord.HTTPException:
                pass
            raise localutils.errors.TemplateVerificationChannelError(f"I can't add reactions in {channel.mention}.")

        # Wew nice we're done
        return True

    async def send_profile_archivation(self, user_profile:localutils.UserProfile, target_user:discord.Member) -> bool:
        """Send a profile to the template's archive channel
        This will also add the given role to the user
        Yes, archivation is a word

        Args:
            user_profile (utils.UserProfile): The profile to be submitted
            target_user (discord.Member): The owner of the profile

        Returns:
            bool: Whether or not the archive send was successful
        """

        # Grab the archive channel ID
        template: localutils.Template = user_profile.template
        archive_channel_id: typing.Optional[int] = template.get_archive_channel_id(target_user)  # this may raise InvalidCommandText

        # Check if there's an archive channel set
        if archive_channel_id is None:
            return True

        # Get the channel
        try:
            channel: discord.TextChannel = self.bot.get_channel(archive_channel_id) or await self.bot.fetch_channel(archive_channel_id)
        except discord.HTTPException:
            raise localutils.errors.TemplateArchiveChannelError(f"I can't reach a channel with the ID `{archive_channel_id}`.")

        # Send the data
        embed: utils.Embed = user_profile.build_embed(target_user)
        try:
            await channel.send(target_user.mention, embed=embed)
        except discord.HTTPException:
            raise localutils.errors.TemplateArchiveChannelError(f"I can't send messages to {channel.mention}.")

        # Wew nice we're done
        return True

    async def add_profile_user_roles(self, user_profile:localutils.UserProfile, target_user:discord.Member) -> bool:
        """Add the profile roles to a given user

        Args:
            user_profile (utils.UserProfile): The profile to be submitted
            target_user (discord.Member): The owner of the profile

        Returns:
            bool: Whether or not the role add was successful
        """

        # Grab the role ID
        template: localutils.Template = user_profile.template
        role_id: typing.Optional[int] = template.get_role_id(target_user)

        # See if there's a role to add
        if role_id is None:
            return True

        # Grab the role
        role_to_add: discord.Role = target_user.guild.get_role(role_id)
        try:
            await target_user.add_roles(role_to_add, reason="Verified profile")
        except discord.HTTPException:
            raise localutils.errors.TemplateRoleAddError(f"I couldn't add a role to you with the ID `{role_id}`.")
        except AttributeError:
            raise localutils.errors.TemplateRoleAddError(f"I couldn't find a role on this server with the ID `{role_id}`.")

        # Wew we're done
        return True

    async def send_profile_submission(self, ctx:utils.Context, user_profile:localutils.UserProfile, target_user:discord.Member) -> bool:
        """Send a profile verification OR archive message for a given profile. Returns whether or not the sending was a success

        Args:
            ctx (utils.Context): The command invocation for the user setting the profile
            user_profile (utils.UserProfile): The profile being sent
            target_user (discord.Member): The owner of the profile (may not be the same as ctx.author)

        Returns:
            bool: Whether or not sending the profile verification succeeds. 0 if any errors were found, 1 if it worked fine
        """

        # Grab the template
        template = user_profile.template

        # Run each of the items
        try:
            if template.verification_channel_id:
                await self.send_profile_verification(user_profile, target_user)
            else:
                await self.send_profile_archivation(user_profile, target_user)
                await self.add_profile_user_roles(user_profile, target_user)
        except localutils.errors.TemplateSendError as e:
            await ctx.author.send(str(e))
            return False

        # Wew it worked
        return True

    @utils.Cog.listener('on_raw_reaction_add')
    async def verification_emoji_check(self, payload:discord.RawReactionActionEvent):
        """Triggered when a reaction is added or removed, check for profile verification"""

        # Check that both the channel and the message are readable
        try:
            channel: discord.TextChannel = self.bot.get_channel(payload.channel_id) or await self.bot.fetch_channel(payload.channel_id)
            message: discord.Message = await channel.fetch_message(payload.message_id)
        except discord.HTTPException:
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
        if 'Verification Check' not in embed.footer.text:
            return

        # Get the member who added the reaction
        guild: discord.Guild = self.bot.get_guild(payload.guild_id) or await self.bot.fetch_guild(payload.guild_id)
        moderator: discord.Member = guild.get_member(payload.user_id) or await guild.fetch_member(payload.user_id)
        if moderator.bot:
            return
        if not localutils.checks.member_is_moderator(self.bot, moderator):
            return

        # And FINALLY we can check their emoji
        if payload.emoji.id and str(payload.emoji) not in [self.TICK_EMOJI, self.CROSS_EMOJI]:
            return

        # Check what they reacted with
        verify = str(payload.emoji) == self.TICK_EMOJI

        # Check whom and what we're updating
        try:
            profile_user_id, template_id, profile_name = message.content.split('\n')[-1].split('/')
        except ValueError:
            profile_user_id, template_id = message.content.split('\n')[-1].split('/')
            profile_name = 'default'
        profile_user_id = int(profile_user_id)

        # Decide whether to verify or to delete
        user_profile = None
        template = None
        async with self.bot.database() as db:
            template = await localutils.Template.fetch_template_by_id(db, template_id)
            user_profile = await template.fetch_profile_for_user(db, profile_user_id, profile_name)
            if verify:
                await db("UPDATE created_profile SET verified=true WHERE user_id=$1 AND template_id=$2 AND name=$3", profile_user_id, template_id, profile_name)
            else:
                await db("DELETE FROM created_profile WHERE user_id=$1 AND template_id=$2 AND name=$3", profile_user_id, template_id, profile_name)

        # See if we need to say anything
        if user_profile is None:
            await message.delete()
            return

        # Gets a denial message from the denier
        denial_reason = "No reason provided."
        messages_to_delete = [message]
        if verify is False and moderator.permissions_in(channel).send_messages:
            denial_ask_message = await channel.send("Why was that profile denied?")
            messages_to_delete.append(denial_ask_message)
            try:
                check = lambda m: m.author.id == moderator.id and m.channel.id == channel.id and len(m.content) > 0
                denial_message = await self.bot.wait_for('message', check=check, timeout=120)
                messages_to_delete.append(denial_message)
                denial_reason = denial_message.content
            except asyncio.TimeoutError:
                denial_reason = "No reason provided."

        # Tell the user about the decision
        try:
            profile_user: discord.Member = guild.get_member(profile_user_id) or await guild.fetch_member(profile_user_id)
        except discord.HTTPException:
            profile_user = None
        if profile_user:
            try:
                embed: localutils.Embed = user_profile.build_embed(profile_user)
                if verify:
                    await profile_user.send(f"Your profile for **{user_profile.template.name}** (`{user_profile.name}`) on `{guild.name}` has been verified.", embed=embed)
                else:
                    await profile_user.send(f"Your profile for **{user_profile.template.name}** (`{user_profile.name}`) on `{guild.name}` has been denied with the reason `{denial_reason}`.", embed=embed)
            except discord.HTTPException:
                self.logger.info(f"Couldn't DM user {user_profile.user_id} about their '{user_profile.template.name}' profile verification on {guild.id}")
                pass  # Can't send the user a DM, let's just ignore it

        # Archive and add roles
        if verify:

            # Send the profile to the archive
            try:
                await self.send_profile_archivation(user_profile, profile_user)
            except localutils.errors.TemplateArchiveChannelError:
                pass

            # Add the relevant role to the user
            try:
                await self.add_profile_user_roles(user_profile, profile_user)
            except localutils.errors.TemplateRoleAddError:
                pass

        # Delete relevant messages
        messages_to_delete = [i for i in messages_to_delete if channel.permissions_for(guild.me).manage_messages or i.author.id == self.bot.user.id]
        if len(messages_to_delete) == 1:
            await messages_to_delete[0].delete()
        elif len(messages_to_delete) > 1:
            await channel.purge(check=lambda m: m.id in [i.id for i in messages_to_delete], bulk=channel.permissions_for(guild.me).manage_messages)


def setup(bot:utils.Bot):
    x = ProfileVerification(bot)
    bot.add_cog(x)
