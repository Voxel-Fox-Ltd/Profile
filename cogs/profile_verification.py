from typing import List

from discord import (Guild, TextChannel, Reaction, Member, User,
                        Message, Embed, Role, RawReactionActionEvent)

from cogs.utils.custom_bot import CustomBot
from cogs.utils.custom_cog import Cog 
from cogs.utils.profiles.user_profile import UserProfile
from cogs.utils.checks import member_is_moderator


class ProfileVerification(Cog):

    TICK_EMOJI_ID = 596096897995899097
    CROSS_EMOJI_ID = 596096897769275402

    def __init__(self, bot:CustomBot):
        self.bot = bot 

    
    @Cog.listener('on_raw_reaction_add')
    async def verification_emoji_check(self, payload:RawReactionActionEvent):
        '''Triggered when a reaction is added or removed, check for profile verification'''

        # Firstly we wanna check the message being reacted to, make sure its ours
        channel_id = payload.channel_id
        channel: TextChannel = self.bot.get_channel(channel_id)
        if channel is None:
            channel: TextChannel = await self.bot.fetch_channel(channel_id)

        # Get the message from the channel
        message: Message = await channel.fetch_message(payload.message_id)

        # Check if we're the author
        if message.author.id != self.bot.user.id:
            return

        # Check if there's an embed
        if not message.embeds:
            return

        # Make sure it's the right kind of embed
        embed: Embed = message.embeds[0]
        if 'Verification Check' not in embed.footer.text:
            return
        # profile_name = embed.footer.text.split('//')[0].strip().lower()
        profile_name = embed.title.split(' ')[0].strip().lower()

        # It's a verification message! Now we wanna check the author to make sure they're approved
        # Get guild
        guild_id = payload.guild_id 
        guild: Guild = self.bot.get_guild(guild_id)
        if guild is None:
            guild: Guild = await self.bot.fetch_guild(guild_id)

        # Get the member from the guild
        member: Member = guild.get_member(payload.user_id)

        # Make sure they aren't a bot
        if member.bot:
            return

        # Check their permissions
        if not member_is_moderator(self.bot, member):
            return

        # And FINALLY we can check their emoji
        if payload.emoji.id and payload.emoji.id not in [self.TICK_EMOJI_ID, self.CROSS_EMOJI_ID]:
            return

        # Check what they reacted with
        verify = payload.emoji.id == self.TICK_EMOJI_ID 

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
        profile = UserProfile.all_profiles.get((profile_user_id, guild.id, profile_name))
        if profile is None:
            # Silently fail I guess
            return

        # Remove them if necessary
        if verify is False:
            del UserProfile.all_profiles[(profile_user_id, guild.id, profile_name)]
        else:
            profile.verified = verify

        # Tell the user about the decision
        user: User = self.bot.get_user(profile_user_id)
        if user is None:
            user: User = await self.bot.fetch_user(profile_user_id)
        try:
            if verify:
                await user.send(f"Your profile for `{profile.profile.name}` on `{guild.name}` has been verified.", embed=profile.build_embed())
            else:
                await user.send(f"Your profile for `{profile.profile.name}` on `{guild.name}` has been denied.", embed=profile.build_embed())
        except Exception:
            # Issues sending info to the user, just fail silently
            # raise e 
            pass


def setup(bot:CustomBot):
    x = ProfileVerification(bot)
    bot.add_cog(x)
