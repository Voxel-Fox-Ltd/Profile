import asyncio

import discord

from cogs import utils


class ProfileVerification(utils.Cog):

    # TICK_EMOJI_ID = 596096897995899097
    # CROSS_EMOJI_ID = 596096897769275402

    TICK_EMOJI = "<:tick_yes:596096897995899097>"
    CROSS_EMOJI = "<:cross_no:596096897769275402>"

    @utils.Cog.listener('on_raw_reaction_add')
    async def verification_emoji_check(self, payload:discord.RawReactionActionEvent):
        """Triggered when a reaction is added or removed, check for profile verification"""

        # Firstly we wanna check the message being reacted to, make sure its ours
        try:
            channel: discord.TextChannel = self.bot.get_channel(payload.channel_id) or await self.bot.fetch_channel(payload.channel_id)
        except discord.HTTPException:
            return  # Channel may not exist? I guess that's fine

        # Get the message from the channel
        try:
            message: discord.Message = await channel.fetch_message(payload.message_id)
        except discord.HTTPException:
            return  # Message doesn't exist? We can't read it? Wild but whatever, why not

        # Check if we're the author
        if message.author.id != self.bot.user.id:
            return

        # Check if there's an embed
        if not message.embeds:
            return

        # Make sure it's the right kind of embed
        embed: discord.Embed = message.embeds[0]
        if not embed.footer:
            return
        if not embed.footer.text:
            return
        if 'Verification Check' not in embed.footer.text:
            return

        # Get guild for verification
        guild: discord.Guild = self.bot.get_guild(payload.guild_id) or await self.bot.fetch_guild(payload.guild_id)

        # Get the member who added the reaction
        member: discord.Member = guild.get_member(payload.user_id) or await guild.fetch_member(payload.user_id)

        # Make sure they aren't a bot
        if member.bot:
            return

        # Check their permissions
        if not utils.checks.member_is_moderator(self.bot, member):
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
            template = await utils.Template.fetch_template_by_id(db, template_id)
            user_profile = await template.fetch_profile_for_user(db, profile_user_id, profile_name)
            if verify:
                await db("UPDATE created_profile SET verified=true WHERE user_id=$1 AND template_id=$2 AND name=$3", profile_user_id, template_id, profile_name)
            else:
                await db("DELETE FROM created_profile WHERE user_id=$1 AND template_id=$2 AND name=$3", profile_user_id, template_id, profile_name)

        # Delete the verify message
        await message.delete()

        # See if we need to say anything
        if user_profile is None:
            return

        # Gets a denial message from the denier
        denial_reason = None
        if not verify:
            await channel.send("Why was that profile denied?")
            def check(m):
                return m.author == member and m.channel == channel and len(m.content) > 0
            try:
                denial_message = await self.bot.wait_for('message', check=check, timeout=120)
                denial_reason = denial_message.content
            except asyncio.TimeoutError:
                denial_reason = "No reason provided."

        # Tell the user about the decision
        profile_user: discord.User = guild.get_member(profile_user_id) or self.bot.get_user(profile_user_id) or await self.bot.fetch_user(profile_user_id)
        if profile_user:
            try:
                embed: utils.Embed = user_profile.build_embed(profile_user if isinstance(profile_user, discord.Member) else None)
                if verify:
                    await profile_user.send(f"Your profile for `{user_profile.template.name}` on `{guild.name}` has been verified.", embed=embed)
                else:
                    await profile_user.send(f"Your profile for `{user_profile.template.name}` on `{guild.name}` has been denied with the reason `{denial_reason}`.", embed=embed)
            except discord.HTTPException:
                self.logger.info(f"Couldn't DM user {user_profile.user_id} about their '{user_profile.template.name}' profile verification on {guild.id}")
                pass  # Can't send the user a DM, let's just ignore it

        # Add a role to them
        role_to_add: discord.Role = guild.get_role(user_profile.template.role_id)
        if verify and role_to_add and isinstance(profile_user, discord.Member):
            try:
                await profile_user.add_roles(role_to_add, reason="Verified profile")
            except discord.HTTPException:
                self.logger.info(f"Couldn't add role {role_to_add.id} to user {user_profile.user_id} about their '{user_profile.template.name}' profile verification on {guild.id}")
                pass

        # Send the profile off to the archive
        if user_profile.template.archive_channel_id and verify:
            try:
                channel = await self.bot.fetch_channel(user_profile.template.archive_channel_id)
                embed: utils.Embed = user_profile.build_embed(profile_user if isinstance(profile_user, discord.Member) else None)
                await channel.send(profile_user.mention, embed=embed)
            except discord.HTTPException as e:
                self.logger.info(f"Couldn't archive profile in guild {user_profile.template.guild_id} - {e}")
                pass  # Couldn't be sent to the archive channel
            except AttributeError:
                self.logger.info(f"Couldn't archive profile in guild {user_profile.template.guild_id} - AttributeError (probably channel deleted)")
                pass  # The archive channel has been deleted


def setup(bot:utils.Bot):
    x = ProfileVerification(bot)
    bot.add_cog(x)
