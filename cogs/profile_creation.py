from asyncio import TimeoutError as AsyncTimeoutError

from discord import DMChannel
from discord.ext.commands import CommandError, Context, CommandNotFound, MemberConverter

from cogs.utils.custom_bot import CustomBot
from cogs.utils.custom_cog import Cog
from cogs.utils.profiles.profile import Profile
from cogs.utils.profiles.filled_field import FilledField
from cogs.utils.profiles.field_type import TextField, BooleanField, NumberField, ImageField, FieldCheckFailure
from cogs.utils.profiles.user_profile import UserProfile


class ProfileCreation(Cog):

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
        if command_operator not in ['SET', 'GET']:
            return
        profile_name = command_name[3:]
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

        # Invoke the commandnddndn
        if command_operator == 'SET' and user != ctx.author:
            await ctx.send("You can't set someone else's profile.")
            return
        elif command_operator == 'SET' and user_profile is None:
            await self.set_profile(ctx, profile)
            return
        elif command_operator == 'SET': 
            await ctx.send(f"You already have a profile set for `{profile.name}`.")
            return 

        # Get the profile
        if user_profile is None:
            await ctx.send(f"`{user!s}` don't have a profile for `{profile.name}`.")
            return 

        # Don't show if not verified
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
            await ctx.send("Send you a PM!")
        except Exception:
            await ctx.send("I'm unable to send you PMs to set up your profile :/")
            return

        # Talk the user through each field
        filled_fields = []
        for field in fields:
            # Send them the prompt
            await user.send(field.prompt)

            # User text input
            if isinstance(field.field_type, (TextField, NumberField, ImageField)):
                check = lambda m: m.author == user and isinstance(m.channel, DMChannel)
                while True:
                    try:
                        m = await self.bot.wait_for('message', check=check, timeout=field.timeout)
                    except AsyncTimeoutError:
                        await ctx.send(f"Your input for this field has timed out. Please try running `set{profile.name}` on your server again.")
                        return
                    try:
                        field.field_type.check(m.content)
                        break
                    except FieldCheckFailure as e:
                        await user.send(e.message)

            # Reaction input
            elif isinstance(field.field_type, BooleanField):
                # TODO
                pass

            # Add field to list
            filled_fields.append(FilledField(user.id, field.field_id, m.content))

        # Make the UserProfile object
        up = UserProfile(user.id, profile.profile_id, profile.verification_channel_id == None)

        # Database me up daddy
        async with self.bot.database() as db:
            await db('INSERT INTO created_profile (user_id, profile_id, verified) VALUES ($1, $2, $3)', up.user_id, up.profile.profile_id, up.verified)
            for field in filled_fields:
                await db('INSERT INTO filled_field (user_id, field_id, value) VALUES ($1, $2, $3)', field.user_id, field.field_id, field.value)
        
        # Respond to user
        await user.send("Your profile has been created.", embed=up.build_embed())


def setup(bot:CustomBot):
    x = ProfileCreation(bot)
    bot.add_cog(x)      
