from asyncio import TimeoutError as AsyncTimeoutError
from string import ascii_lowercase as ASCII_LOWERCASE, digits as DIGITS
from uuid import UUID, uuid4 as generate_id

from discord.ext.commands import command, Context, MissingPermissions, has_permissions

from cogs.utils.custom_cog import Cog
from cogs.utils.custom_bot import CustomBot
from cogs.utils.profiles.field import Field
from cogs.utils.profiles.profile import Profile
from cogs.utils.profiles.field_type import TextField, NumberField, BooleanField


class ProfileTemplates(Cog):

    TICK_EMOJI = "<:tickYes:596096897995899097>"
    CROSS_EMOJI = "<:crossNo:596096897769275402>"

    def __init__(self, bot:CustomBot):
        super().__init__(self.__class__.__name__)
        self.bot = bot


    async def cog_command_error(self, ctx, error):
        '''Handles errors for the cog'''

        if ctx.author.id in self.bot.config['owners'] and not isinstance(error, MissingRole):
            text = f'```py\n{error}```'
            await ctx.send(text)
            raise error

        if isinstance(error, MissingPermissions):
            if ctx.author.id in self.bot.config['owners']:
                return await ctx.reinvoke()
            if ctx.guild and ctx.author == ctx.guild.owner:
                return await ctx.invoke()
            await ctx.send(f"You need the `{error.missing_perms[0]}` permission to run this command.")
            return


    @command()
    @has_permissions(manage_roles=True)
    async def createtemplate(self, ctx:Context):
        '''Creates a new template for your guild'''

        # Send the flavour text behind getting a template name
        clean_prefix = ctx.prefix if '<@' not in ctx.prefix else str(self.bot.get_user(int(''.join([i for i in ctx.prefix if i.isdigit()]))))
        await ctx.send(''.join(["What name do you want to give this template? ",
            "This will be used for the set and get commands, eg if the name of your ",
            f"template is `test`, the commands generated will be `{clean_prefix}settest` ",
            f"to set a profile, `{clean_prefix}gettest` to get a profile, ",
            f"and `{clean_prefix}deletetest` to delete a profile. ",
            "A profile name is case insensitive.",
        ]))

        # Get name from the messages they send
        while True:
            # Get message
            try:
                name_message = await self.bot.wait_for('message', check=lambda m: m.author == ctx.author and m.channel == ctx.channel, timeout=120)

            # Catch timeout
            except AsyncTimeoutError:
                await ctx.send(f"{ctx.author.mention}, your template creation has timed out after 2 minutes of inactivity.")
                return

            # Check name for characters
            profile_name = name_message.content.lower()
            if [i for i in profile_name if i not in ASCII_LOWERCASE + DIGITS]:
                await ctx.send("You can only use normal lettering and digits in your command name. Please give another name.")
                continue 

            # Check name for length
            if 30 >= len(profile_name) >= 1:
                pass
            else:
                await ctx.send("The maximum length of a profile name is 30 characters. Please give another name.")
                continue 

            # Check name is unique
            if Profile.all_guilds[ctx.guild.id].get(profile_name):
                await ctx.send(f"This server already has a template with name `{profile_name}`. Please provide another one.")
                continue
            break

        # Get colour
        # TODO
        colour = 0x000000

        # Get verification channel
        await ctx.send("What channel would you like the the verification process to happen in? If you want profiles to be verified automatically, just say `continue`.")
        verification_channel_id = None
        try:
            verification_message = await self.bot.wait_for('message', check=lambda m: m.author == ctx.author and m.channel == ctx.channel, timeout=120)
        except AsyncTimeoutError:
            await ctx.send(f"{ctx.author.mention}, because of your 2 minutes of inactivity, profiles have been set to automatic approval.")
        else:
            if verification_message.channel_mentions:
                verification_channel_id = verification_message.channel_mentions[0].id 

        # Get an ID for the profile
        profile = Profile(
            profile_id=generate_id(),
            colour=colour,
            guild_id=ctx.guild.id,
            verification_channel_id=verification_channel_id,
            name=profile_name,
        )

        # Now we start the field loop
        index = 0
        field = True
        while field:
            field = await self.create_new_field(ctx, profile.profile_id, index)
            index += 1
            if index == 20:
                break

        # Save it all to database
        async with self.bot.database() as db:
            await db('INSERT INTO profile (profile_id, name, colour, guild_id, verification_channel_id) VALUES ($1, $2, $3, $4, $5)', profile.profile_id, profile.name, profile.colour, profile.guild_id, profile.verification_channel_id)
            for field in profile.fields:
                await db('INSERT INTO field (field_id, name, index, prompt, timeout, field_type, optional, profile_id) VALUES ($1, $2, $3, $4, $5, $6, $7, $8)', field.field_id, field.name, field.index, field.prompt, field.timeout, field.field_type.name, field.optional, field.profile_id)

        # Output to user
        await ctx.send(f"Your profile has been created with {len(profile.fields)} fields.")


    async def create_new_field(self, ctx:Context, profile_id:UUID, index:int) -> Field:
        '''Lets a user create a new field in their profile'''

        # Ask if they want a new field
        field_message = await ctx.send("Do you want to make a new field for your profile?")
        await field_message.add_reaction(self.TICK_EMOJI)
        await field_message.add_reaction(self.CROSS_EMOJI)
        message_check = lambda m: m.author == ctx.author and m.channel == ctx.channel
        okay_reaction_check = lambda r, u: str(r.emoji) in [self.TICK_EMOJI, self.CROSS_EMOJI] and u == ctx.author
        try:
            reaction, _ = await self.bot.wait_for('reaction_add', check=okay_reaction_check, timeout=120)
        except AsyncTimeoutError:
            await ctx.send("Creating a new field has timed out. The profile is being created with the fields currently added.")
            return None

        # See if they don't wanna continue 
        if str(reaction.emoji) == self.CROSS_EMOJI:
            return None 
    
        # Get a name for the new field
        await ctx.send("What name should this field have?")
        while True:
            try:
                field_name_message = await self.bot.wait_for('message', check=message_check, timeout=120)
            except AsyncTimeoutError:
                await ctx.send("Creating a new field has timed out. The profile is being created with the fields currently added.")
                return None

            # Check if if name is too long
            if 256 >= len(field_name_message.content) >= 1:
                break 
            else:
                await ctx.send("The maximum length of a field name is 256 characters. Please give another name.")
        field_name = field_name_message.content 

        # Get a prompt for the field 
        await ctx.send("What prompt should I send when I ask people to fill out this field?")
        while True:
            try:
                field_prompt_message = await self.bot.wait_for('message', check=message_check, timeout=120)
            except AsyncTimeoutError:
                await ctx.send("Creating a new field has timed out. The profile is being created with the fields currently added.")
                return None

            if len(field_prompt_message.content) >= 1:
                break
            else:
                await ctx.send("You need to actually give text for the prompt.")
        field_prompt = field_prompt_message.content

        # Get timeout
        await ctx.send("How many seconds should I wait for people to fill out this field (I recommend 120 seconds)?")
        while True:
            try:
                field_timeout_message = await self.bot.wait_for('message', check=message_check, timeout=120)
            except AsyncTimeoutError:
                await ctx.send("Creating a new field has timed out. The profile is being created with the fields currently added.")
                return None
            try:
                timeout = int(field_timeout_message.content)
                break
            except ValueError:
                await ctx.send("I couldn't convert your message into a number. Please try again.")
        field_timeout = timeout

        # Get field type 
        NUMBERS = '\U00000031\U000020e3'
        LETTERS = '\U0001f1e6'
        # PICTURE = '\U0001f5bc'  TODO make this work or something
        TICK = '\U00002705'
        field_type_message = await ctx.send(f"What TYPE is this field? Will you be getting numbers ({NUMBERS}), text ({LETTERS}), or a yes/no ({TICK})?")
        await field_type_message.add_reaction(NUMBERS)
        await field_type_message.add_reaction(LETTERS)
        await field_type_message.add_reaction(TICK)
        field_type_check = lambda r, u: str(r.emoji) in [NUMBERS, LETTERS, TICK] and u == ctx.author
        try:
            reaction, _ = await self.bot.wait_for('reaction_add', check=field_type_check, timeout=120)
            emoji = str(reaction.emoji)
        except AsyncTimeoutError:
            await ctx.send("Picking a field type has timed out - defaulting to text.") 
            emoji = LETTERS
        if emoji == NUMBERS: field_type = NumberField() 
        elif emoji == LETTERS: field_type = TextField()
        elif emoji == TICK: field_type = BooleanField()
        else: raise Exception("Shouldn't be reached")


        # Get whether the field is optional
        # TODO
        field_optional = False

        # Make the field that'll be used 
        return Field(
            field_id=generate_id(),
            name=field_name,
            index=index,
            prompt=field_prompt,
            timeout=field_timeout,
            field_type=field_type,
            profile_id=profile_id,
            optional=field_optional,
        )

            
def setup(bot:CustomBot):
    x = ProfileTemplates(bot)
    bot.add_cog(x)
