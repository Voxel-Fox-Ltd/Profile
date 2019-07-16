from asyncio import TimeoutError as AsyncTimeoutError

from discord import DMChannel
from discord.ext.commands import CommandError, Context, CommandNotFound, MemberConverter

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

    def __init__(self, bot:CustomBot):
        super().__init__(self.__class__.__name__)
        self.bot = bot 


    async def on_command_error(self, ctx:Context, error:CommandError):
        '''General error handler, but actually just handles listening for 
        CommandNotFound so the bot can search for that custom command'''

        if not isinstance(error, CommandNotFound):
            return

        # Get the command
        command_name = ctx.invoked_with 
        command_operator = command_name[0:3].upper()
        if command_operator in ['SET', 'GET']:
            profile_name = command_name[3:]
        elif command_operator == 'DEL':
            profile_name = command_name[6:]
        else:
            return  # Silently fail if it's an invalid command
        if ctx.guild:
            self.log_handler.debug(f"Command '{command_name} {profile_name}' run by {ctx.author.id} on {ctx.guild.id}/{ctx.channel.id}")
        else:
            self.log_handler.debug(f"Command '{command_name} {profile_name}' run by {ctx.author.id} on PMs/{ctx.channel.id}")
        args = ctx.message.content[len(ctx.prefix) + len(ctx.invoked_with):].strip().split()

        # See if the command exists on their server
        guild_commands = Profile.all_guilds[ctx.guild.id]
        profile = guild_commands.get(profile_name)
        if not profile:
            return 

        # Convert some params
        try:
            user = await MemberConverter().convert(ctx, args[0])
        except IndexError:
            user = ctx.author
        user_profile = UserProfile.all_profiles.get((user.id, ctx.guild.id, profile.name))

        # Command invoke - SET
        if command_operator == 'SET' and user != ctx.author:
            await ctx.send("You can't set someone else's profile.")
            return
        elif command_operator == 'SET' and user_profile is None:
            await self.set_profile(ctx, profile)
            return
        elif command_operator == 'SET': 
            await ctx.send(f"You already have a profile set for `{profile.name}`.")
            return 

        # Command invoke - DEL
        if command_operator == 'DEL' and user != ctx.author:
            # Check if they're a bot admin
            if member_is_moderator(self.bot, ctx.author):
                # Ya it's fine 
                pass 
            else:
                await ctx.send("You can't delete someone else's profile.")
                return 
        if command_operator == 'DEL' and user_profile is None:
            await ctx.send(f"You don't have a profile set for `{profile.name}`.")
            return
        elif command_operator == 'DEL':
            async with self.bot.database() as db:
                await db('DELETE FROM filled_field WHERE user_id=$1 AND field_id in (SELECT field_id FROM field WHERE profile_id=$2)', user.id, profile.profile_id)
                await db('DELETE FROM created_profile WHERE user_id=$1 AND profile_id=$2', user.id, profile.profile_id)
            del UserProfile.all_profiles[(user.id, ctx.guild.id, profile.name)]
            await ctx.send("Profile deleted.")
            return

        # Command invoke - GET
        if user_profile is None:
            await ctx.send(f"`{user!s}` don't have a profile for `{profile.name}`.")
            return
        if user_profile.verified:
            await ctx.send(embed=user_profile.build_embed())
            return
        else:
            await ctx.send("That profile hasn't yet been verified.")
            return


    async def set_profile(self, ctx:Context, profile:Profile):
        '''Talks a user through setting up a profile on a given server'''

        # Set up some variaballlales
        user = ctx.author 
        fields = profile.fields 

        # See if you we can send them the PM
        try:
            await user.send(f"Now talking you through setting up a `{profile.name}` profile.")
            await ctx.send("Sent you a PM!")
        except Exception:
            await ctx.send("I'm unable to send you PMs to set up your profile :/")
            return

        # Talk the user through each field
        filled_fields = []
        for field in fields:
            # Send them the prompt
            await user.send(field.prompt)

            # User text input
            if isinstance(field.field_type, (TextField, NumberField)) or field.field_type in [TextField, NumberField]:
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
            elif isinstance(field.field_type, ImageField) or field.field_type == ImageField:
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

            # Reaction input
            elif isinstance(field.field_type, BooleanField):
                # TODO
                pass

            else:
                # print(field.field_type)
                # print(ImageField)
                raise Exception(f"Field type {field.field_type} is not catered for")

            # Add field to list
            filled_fields.append(FilledField(user.id, field.field_id, field_content))

        # Make the UserProfile object
        up = UserProfile(user.id, profile.profile_id, profile.verification_channel_id == None)

        # Make sure the bot can send the embed at all
        try:
            await user.send(embed=up.build_embed())
        except Exception as e:
            await user.send(f"Your profile couldn't be sent to you? `{e}`.")
            return

        # Make sure the bot can send the embed to the channel
        if profile.verification_channel_id:
            try:
                channel = await self.bot.fetch_channel(profile.verification_channel_id)
                embed = up.build_embed()
                embed.set_footer(text=f'{profile.name.upper()} // Verification Check')
                v = await channel.send(f"New **{profile.name}** submission from {user.mention}\n{user.id}/{profile.profile_id}", embed=embed)
                await v.add_reaction(self.TICK_EMOJI)
                await v.add_reaction(self.CROSS_EMOJI)
            except Exception as e:
                await user.send(f"Your profile couldn't be send to the verification channel? `{e}`.")
                return

        # Database me up daddy
        async with self.bot.database() as db:
            await db('INSERT INTO created_profile (user_id, profile_id, verified) VALUES ($1, $2, $3)', up.user_id, up.profile.profile_id, up.verified)
            for field in filled_fields:
                await db('INSERT INTO filled_field (user_id, field_id, value) VALUES ($1, $2, $3)', field.user_id, field.field_id, field.value)
        
        # Respond to user
        await user.send("Your profile has been created and saved.")


def setup(bot:CustomBot):
    x = ProfileCreation(bot)
    bot.add_cog(x)      
