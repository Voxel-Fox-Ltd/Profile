from asyncio import TimeoutError as AsyncTimeoutError
import re

from discord import DMChannel, Member
from discord.ext.commands import CommandError, Context, CommandNotFound, MemberConverter, guild_only, NoPrivateMessage, BadArgument, command, MissingPermissions
from asyncpg.exceptions import UniqueViolationError

from cogs.utils.custom_bot import CustomBot
from cogs.utils.custom_cog import Cog
from cogs.utils.profiles.profile import Profile
from cogs.utils.profiles.filled_field import FilledField
from cogs.utils.profiles.field_type import TextField, BooleanField, NumberField, ImageField, FieldCheckFailure
from cogs.utils.profiles.user_profile import UserProfile
from cogs.utils.checks import member_is_moderator


class ProfileCreation(Cog):

    TICK_EMOJI = "<:tickYes:596096897995899097>"
    CROSS_EMOJI = "<:crossNo:596096897769275402>"
    COMMAND_REGEX = re.compile(r"(set|get|delete|edit)(\S{1,30})( .*)?", re.IGNORECASE)

    def __init__(self, bot:CustomBot):
        super().__init__(self.__class__.__name__)
        self.bot = bot 

    async def on_command_error(self, ctx:Context, error:CommandError):
        '''General error handler, but actually just handles listening for 
        CommandNotFound so the bot can search for that custom command'''

        # Missing permissions
        if isinstance(error, MissingPermissions):
            await ctx.send(f"You're missing the {error.missing_perms[0]} permission required to do this.")
            return

        # Handle commandnotfound which is really just handling the set/get/delete/etc commands
        elif not isinstance(error, CommandNotFound):
            return

        # Get the command and used profile
        matches = self.COMMAND_REGEX.search(ctx.message.content)
        if matches:
            command_operator = matches.group(1)
            profile_name = matches.group(2)
            try:
                args = matches.group(3).strip()
            except AttributeError:
                args = None
        else:
            return  # Silently fail if it's an invalid command

        # Filter out DMs
        if isinstance(ctx.channel, DMChannel):
            await ctx.send("You can't run this command in PMs - please try again in your server.")
            return

        # Find the profile they asked for on their server
        guild_commands = Profile.all_guilds[ctx.guild.id]
        profile = guild_commands.get(profile_name)
        if not profile:
            return

        # Get the optional arg
        print(args)
        if args:
            try:
                args = await MemberConverter().convert(ctx, args)
            except BadArgument:
                await ctx.send(f"Member `{args}` could not be found.")
                return

        # Get the relevant command
        command_to_run = self.bot.get_command(f'{command_operator.lower()}profilemeta')

        # Invoke it
        await ctx.invoke(command_to_run, profile, args)

        """
            self.log_handler.debug(f"Command '{command_name} {profile_name}' run by {ctx.author.id} on {ctx.guild.id}/{ctx.channel.id}")
        else:
            await ctx.send("You can't run this command in PMs - please try again in your server.")
            self.log_handler.debug(f"Command '{command_name} {profile_name}' run by {ctx.author.id} on PMs/{ctx.channel.id}")
            return
        """

    @command(enabled=False)
    async def setprofilemeta(self, ctx:Context, profile:Profile, target_user:Member):
        """Talks a user through setting up a profile on a given server"""

        # Set up some variaballlales
        user = ctx.author 
        target_user = target_user or user
        fields = profile.fields 

        # Check if they're setting someone else's profile and they're not a mod
        if target_user != ctx.author and not member_is_moderator(ctx.bot, ctx.author):
            raise MissingPermissions(['manage_roles'])

        # Check if they already have a profile set
        user_profile = profile.get_profile_for_member(target_user)
        if user_profile is not None:
            await ctx.send(f"{'You' if target_user == user else target_user.mention} already {'have' if target_user == user else 'has'} a profile set for `{profile.name}`.")
            return 

        # See if you we can send them the PM
        try:
            await user.send(f"Now talking you through setting up a `{profile.name}` profile{' for ' + target_user.mention if target_user != user else ''}.")
            await ctx.send("Sent you a PM!")
        except Exception:
            await ctx.send("I'm unable to send you PMs to set up the profile :/")
            return

        # Talk the user through each field
        filled_fields = []
        for field in fields:
            await user.send(field.prompt)

            # User text input
            if isinstance(field.field_type, (TextField, NumberField)):
                check = lambda m: m.author == user and isinstance(m.channel, DMChannel)
                while True:
                    try:
                        m = await self.bot.wait_for('message', check=check, timeout=field.timeout)
                    except AsyncTimeoutError:
                        await user.send(f"Your input for this field has timed out. Please try running `set{profile.name}` on your server again.")
                        return
                    try:
                        field.field_type.check(m.content)
                        field_content = m.content
                        break
                    except FieldCheckFailure as e:
                        await user.send(e.message)

            # Image input
            elif isinstance(field.field_type, ImageField):
                check = lambda m: m.author == user and isinstance(m.channel, DMChannel)
                while True:
                    try:
                        m = await self.bot.wait_for('message', check=check, timeout=field.timeout)
                    except AsyncTimeoutError:
                        await user.send(f"Your input for this field has timed out. Please try running `set{profile.name}` on your server again.")
                        return
                    try:
                        if m.attachments:
                            content = m.attachments[0].url
                        else:
                            content = m.content
                        field.field_type.check(content)
                        field_content = content
                        break
                    except FieldCheckFailure as e:
                        await user.send(e.message)

            # Invalid field type apparently
            else:
                raise Exception(f"Field type {field.field_type} is not catered for")

            # Add field to list
            filled_fields.append(FilledField(target_user.id, field.field_id, field_content))

        # Make the UserProfile object
        up = UserProfile(target_user.id, profile.profile_id, profile.verification_channel_id == None)

        # Make sure the bot can send the embed at all
        try:
            await user.send(embed=up.build_embed())
        except Exception as e:
            await user.send(f"Your profile couldn't be sent to you - `{e}`.\nPlease try again later.")
            return

        # Make sure the bot can send the embed to the channel
        if profile.verification_channel_id:
            try:
                channel = await self.bot.fetch_channel(profile.verification_channel_id)
                embed = up.build_embed()
                embed.set_footer(text=f'{profile.name.upper()} // Verification Check')
                v = await channel.send(f"New **{profile.name}** submission from {target_user.mention}\n{target_user.id}/{profile.profile_id}", embed=embed)
                await v.add_reaction(self.TICK_EMOJI)
                await v.add_reaction(self.CROSS_EMOJI)
            except Exception as e:
                await user.send(f"Your profile couldn't be send to the verification channel? - `{e}`.")
                return

        # Database me up daddy
        async with self.bot.database() as db:
            try:
                await db('INSERT INTO created_profile (user_id, profile_id, verified) VALUES ($1, $2, $3)', up.user_id, up.profile.profile_id, up.verified)
            except UniqueViolationError:
                await db('UPDATE created_profile SET verified=$3 WHERE user_id=$1 AND profile_id=$2', up.user_id, up.profile.profile_id, up.verified)
                await db('DELETE FROM filled_field WHERE user_id=$1 AND field_id in (SELECT field_id FROM field WHERE profile_id=$2)', up.user_id, up.profile.profile_id)
                self.log_handler.warn(f"Deleted profile for {up.user_id} on UniqueViolationError")
            for field in filled_fields:
                await db('INSERT INTO filled_field (user_id, field_id, value) VALUES ($1, $2, $3)', field.user_id, field.field_id, field.value)
        
        # Respond to user
        await user.send("Your profile has been created and saved.")

    @command(enabled=False)
    async def deleteprofilemeta(self, ctx:Context, profile:Profile, target_user:Member):
        """Handles deleting a profile"""

        # Handle permissions
        if ctx.author != target_user and not member_is_moderator(self.bot, ctx.author):
            raise MissingPermissions(['manage_roles'])

        # Check it exists
        if profile.get_profile_for_member(target_user or ctx.author) is None:
            if target_user:
                await ctx.send(f"{target_user.mention} doesn't have a profile set for `{profile.name}`.")
            else:
                await ctx.send(f"You don't have a profile set for `{profile.name}`.")
            return

        # Database it babey
        async with self.bot.database() as db:
            await db('DELETE FROM filled_field WHERE user_id=$1 AND field_id in (SELECT field_id FROM field WHERE profile_id=$2)', target_user.id, profile.profile_id)
            await db('DELETE FROM created_profile WHERE user_id=$1 AND profile_id=$2', target_user.id, profile.profile_id)
        del UserProfile.all_profiles[(target_user.id, ctx.guild.id, profile.name)]
        await ctx.send("Profile deleted.")

    @command(enabled=False)
    async def getprofilemeta(self, ctx:Context, profile:Profile, target_user:Member):
        """Gets a profile for a given member"""

        # See if there's a set profile
        user_profile = profile.get_profile_for_member(target_user or ctx.author)
        if user_profile is None:
            if target_user:
                await ctx.send(f"{target_user.mention} doesn't have a profile for `{profile.name}`.")
            else:
                await ctx.send(f"You don't have a profile for `{profile.name}`.")
            return

        # See if verified
        if user_profile.verified or member_is_moderator(ctx.bot, ctx.author):
            await ctx.send(embed=user_profile.build_embed())
            return
    
        # Not verified
        if target_user:
            await ctx.send(f"{target_user.mention}'s profile hasn't been verified yet.")
        else:
            await ctx.send(f"Your profile hasn't been verified yet.")
        return


def setup(bot:CustomBot):
    x = ProfileCreation(bot)
    bot.add_cog(x)      
