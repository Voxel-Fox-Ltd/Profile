import discord

from cogs import utils


class ProfileVerification(utils.Cog):

    # TICK_EMOJI_ID = 596096897995899097
    # CROSS_EMOJI_ID = 596096897769275402

    TICK_EMOJI = "<:tickYes:596096897995899097>"
    CROSS_EMOJI = "<:crossNo:596096897769275402>"

    @utils.Cog.listener('on_raw_reaction_add')
    async def verification_emoji_check(self, payload:discord.RawReactionActionEvent):
        """Triggered when a reaction is added or removed, check for profile verification"""

        # Firstly we wanna check the message being reacted to, make sure its ours
        channel_id = payload.channel_id
        channel: discord.TextChannel = self.bot.get_channel(channel_id)
        if channel is None:
            channel: discord.TextChannel = await self.bot.fetch_channel(channel_id)

        # Get the message from the channel
        message: discord.Message = await channel.fetch_message(payload.message_id)

        # Check if we're the author
        if message.author.id != self.bot.user.id:
            return

        # Check if there's an embed
        if not message.embeds:
            return

        # Make sure it's the right kind of embed
        embed: discord.Embed = message.embeds[0]
        if 'Verification Check' not in embed.footer.text:
            return
        profile_name = embed.title.split(' ')[0].strip().lower()

        # Get guild for verification
        guild_id = payload.guild_id
        guild: discord.Guild = self.bot.get_guild(guild_id)
        if guild is None:
            guild: discord.Guild = await self.bot.fetch_guild(guild_id)

        # Get the member from the guild
        member: discord.Member = guild.get_member(payload.user_id)

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
        profile_user_id, profile_id = message.content.split('\n')[-1].split('/')
        profile_user_id = int(profile_user_id)

        # Decide whether to verify or to delete
        async with self.bot.database() as db:
            if verify:
                await db('UPDATE created_profile SET verified=true WHERE user_id=$1 AND profile_id=$2', profile_user_id, profile_id)
            else:
                await db('DELETE FROM filled_field WHERE user_id=$1 AND field_id IN (SELECT field_id FROM field WHERE profile_id=$2)', profile_user_id, profile_id)
                await db('DELETE FROM created_profile WHERE user_id=$1 AND profile_id=$2', profile_user_id, profile_id)

        # Delete the verify message
        await message.delete()

        # Get the profile
        user_profile: utils.UserProfile = utils.UserProfile.all_profiles.get((profile_user_id, guild.id, profile_name))
        if user_profile is None:
            self.logger.warning(f"Couldn't get user {user_profile.user_id} '{user_profile.profile.name}' profile for verification on guild {guild.id}")
            return  # Silently fail I guess

        # Remove them if necessary
        if verify is False:
            del utils.UserProfile.all_profiles[(profile_user_id, guild.id, profile_name)]
        else:
            user_profile.verified = verify

        # Tell the user about the decision
        user: discord.User = self.bot.get_user(profile_user_id)
        if user is None:
            user: discord.User = await self.bot.fetch_user(profile_user_id)
        try:
            if verify:
                await user.send(f"Your profile for `{user_profile.profile.name}` on `{guild.name}` has been verified.", embed=user_profile.build_embed())
            else:
                await user.send(f"Your profile for `{user_profile.profile.name}` on `{guild.name}` has been denied.", embed=user_profile.build_embed())
        except discord.Forbidden:
            self.logger.info(f"Couldn't DM user {user_profile.user_id} about their '{user_profile.profile.name}' profile verification on {guild.id}")
            pass  # Can't send the user a DM, let's just ignore it

        # Send the profile off to the archive
        if user_profile.profile.archive_channel_id:
            try:
                channel = self.bot.fetch_channel(user_profile.profile.archive_channel_id)
                embed = user_profile.build_embed()
                await channel.send(embed=embed)
            except discord.HTTPException as e:
                self.logger.info(f"Couldn't archive profile in guild {user_profile.profile.guild_id} - {e}")
                pass  # Couldn't be sent to the archive channel
            except AttributeError:
                self.logger.info(f"Couldn't archive profile in guild {user_profile.profile.guild_id} - AttributeError (probably channel deleted)")
                pass  # The archive channel has been deleted


def setup(bot:utils.Bot):
    x = ProfileVerification(bot)
    bot.add_cog(x)
