from asyncio import TimeoutError as AsyncTimeoutError
from string import ascii_lowercase as ASCII_LOWERCASE, digits as DIGITS
from uuid import UUID, uuid4 as generate_id
from typing import List

from discord import Permissions
from discord.ext.commands import command, Context, MissingPermissions, has_permissions, MissingRole, guild_only, NoPrivateMessage

from cogs.utils.custom_cog import Cog
from cogs.utils.custom_bot import CustomBot
from cogs.utils.profiles.field import Field
from cogs.utils.profiles.profile import Profile
from cogs.utils.profiles.user_profile import UserProfile
from cogs.utils.profiles.filled_field import FilledField
from cogs.utils.profiles.field_type import TextField, NumberField, BooleanField, ImageField


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

        elif isinstance(error, NoPrivateMessage):
            await ctx.send("You can't run this command in PMs - please try again in your server.")
            return


    @command()
    @guild_only()
    @has_permissions(manage_roles=True)
    async def deletetemplate(self, ctx:Context, template_name:str):
        '''Deletes a template for your guild'''

        # Grab template object
        template: Profile = Profile.all_guilds[ctx.guild.id].get(template_name.lower())
        if template is None:
            await ctx.send(f"There's no template with the name `{template_name}` on this guild. Please see `{ctx.prefix}help` to see all the created templates.")
            return

        # Ask for confirmation
        template_profiles: List[UserProfile] = [i for i in UserProfile.all_profiles.values() if i.profile_id == template.profile_id]
        m = await ctx.send(f"By doing this, you'll delete `{len(template_profiles)}` of the created profiles under this template as well. Would you like to proceed?")
        await m.add_reaction(self.TICK_EMOJI)
        await m.add_reaction(self.CROSS_EMOJI)
        check = lambda r, u: r.message.id == m.id and str(r.emoji) in [self.TICK_EMOJI, self.CROSS_EMOJI] and u.id == ctx.author.id
        try:
            r, _ = await self.bot.wait_for('reaction_add', check=check, timeout=120)
        except AsyncTimeoutError:
            await ctx.send("No response recieved in 120 seconds, cancelling template delete.")
            return
        
        # Check if they said no
        if str(r.emoji) == self.CROSS_EMOJI:
            await ctx.send("Got it, cancelling template delete.")
            return

        # Make sure the emoji is actually valid
        elif str(r.emoji) == self.TICK_EMOJI:
            pass 
        else:
            raise Exception("Bot made a fucky wucky")

        # Okay time to delete from the database
        async with self.bot.database() as db:
            await db('DELETE FROM filled_field WHERE field_id IN (SELECT field_id FROM field WHERE profile_id=$1)', template.profile_id)
            await db('DELETE FROM created_profile WHERE profile_id=$1', template.profile_id)
            await db('DELETE FROM field WHERE profile_id=$1', template.profile_id)
            await db('DELETE FROM profile WHERE profile_id=$1', template.profile_id)
        self.log_handler.info(f"Template '{template.name}' deleted on guild {ctx.guild.id}")
        
        # And I'll just try to delete things from cache as best I can
        # First grab all the fields and filled fields - I grabbed the created profiles earlier
        fields: List[Field] = []
        filled_fields: List[FilledField] = []
        for t in template_profiles:
            for f in t.filled_fields:
                fields.append(f.field)
                filled_fields.append(f) 

        # Loop over the fields and delete em
        for f in fields:
            try: del f.all_fields[f.field_id]
            except KeyError: pass
            try: del f.all_profile_fields[f.profile_id]
            except KeyError: pass

        # Loop over the filled fields
        for f in filled_fields:
            try: del f.all_filled_fields[(f.user_id, f.field_id)]
            except KeyError: pass 
        
        # Loop over the created profiles 
        for c in template_profiles:
            try: del c.all_profiles[(c.user_id, ctx.guild.id, template_name)]
            except KeyError: pass 
        
        # Delete the profile
        try: del template.all_profiles[template.profile_id]
        except KeyError: pass 
        try: del template.all_guilds[ctx.guild.id][template.name]
        except KeyError: pass

        # Wew all deleted
        await ctx.send("Template, fields, and all created profiles have been deleted from the database and cache.")


    @command()
    @guild_only()
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
                await ctx.send("You can only use normal lettering and digits in your command name. Please run this command again to set a new one.")
                return

            # Check name for length
            if 30 >= len(profile_name) >= 1:
                pass
            else:
                await ctx.send("The maximum length of a profile name is 30 characters. Please give another name.")
                continue 

            # Check name is unique
            if Profile.all_guilds[ctx.guild.id].get(profile_name):
                await ctx.send(f"This server already has a template with name `{profile_name}`. Please run this command again to provide another one.")
                return
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
                verification_channel = verification_message.channel_mentions[0]
                proper_permissions = Permissions()
                proper_permissions.update(read_messages=True, add_external_emojis=True, send_messages=True, add_reactions=True, embed_links=True)
                if verification_channel.permissions_for(ctx.guild.me).is_superset(proper_permissions):
                    verification_channel_id = verification_channel.id
                    pass 
                else:
                    await ctx.send("I don't have all the permissions I need to be able to send messages to that channel. I need `read messages`, `send messages`, `add external emojis`, `add reactions`, and `embed links`. Please update the channel permissions, and run this command again.")
                    return
            # elif verification_message.content.lower() == 'continue':
            #     pass 

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
        image_set = False
        while field:
            field = await self.create_new_field(ctx, profile.profile_id, index, image_set)
            if field:
                image_set = isinstance(field.field_type, ImageField) or image_set
            index += 1
            if index == 20:
                break

        # Save it all to database
        async with self.bot.database() as db:
            await db('INSERT INTO profile (profile_id, name, colour, guild_id, verification_channel_id) VALUES ($1, $2, $3, $4, $5)', profile.profile_id, profile.name, profile.colour, profile.guild_id, profile.verification_channel_id)
            for field in profile.fields:
                await db('INSERT INTO field (field_id, name, index, prompt, timeout, field_type, optional, profile_id) VALUES ($1, $2, $3, $4, $5, $6, $7, $8)', field.field_id, field.name, field.index, field.prompt, field.timeout, field.field_type.name, field.optional, field.profile_id)

        # Output to user
        self.log_handler.info(f"New template '{profile.name}' created on guild {ctx.guild.id}")
        await ctx.send(f"Your template has been created with {len(profile.fields)} fields. Users can now run `{ctx.prefix}set{profile.name.lower()}` to set a profile, or `{ctx.prefix}get{profile.name.lower()} @User` to get the profile of another user.")


    async def create_new_field(self, ctx:Context, profile_id:UUID, index:int, image_set:bool=False) -> Field:
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
        await ctx.send("What name should this field have (eg: `Name`, `Age`, `Image`, etc - this is what shows on the embed)?")
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
                await ctx.send("The maximum length of a field name is 256 characters. Please provide another name.")
        field_name = field_name_message.content 

        # Get a prompt for the field 
        await ctx.send(f"What message should I send when I'm asking people to fill out this field (eg: `What is your {field_name.lower()}?`)?")
        while True:
            try:
                field_prompt_message = await self.bot.wait_for('message', check=message_check, timeout=120)
            except AsyncTimeoutError:
                await ctx.send("Creating a new field has timed out. The profile is being created with the fields currently added.")
                return None

            if len(field_prompt_message.content) >= 1:
                break
            else:
                await ctx.send("You need to actually give text for the prompt :/")
        field_prompt = field_prompt_message.content

        # Get timeout
        # await ctx.send("How many seconds should I wait for people to fill out this field (I recommend 120 seconds)?")
        # while True:
        #     try:
        #         field_timeout_message = await self.bot.wait_for('message', check=message_check, timeout=120)
        #     except AsyncTimeoutError:
        #         await ctx.send("Creating a new field has timed out. The profile is being created with the fields currently added.")
        #         return None
        #     try:
        #         timeout = int(field_timeout_message.content)
        #         break
        #     except ValueError:
        #         await ctx.send("I couldn't convert your message into a number. Please try again.")
        # field_timeout = timeout
        field_timeout = 120

        # Get field type 
        NUMBERS = '\U00000031\U000020e3'
        LETTERS = '\U0001F170'
        PICTURE = '\U0001f5bc'
        TICK = '\U00002705'  # TODO make this work or something
        if image_set:
            text = f"What TYPE is this field? Will you be getting numbers ({NUMBERS}), or text ({LETTERS})?"
        else:
            text = f"What TYPE is this field? Will you be getting numbers ({NUMBERS}), text ({LETTERS}), or an image ({PICTURE})?"
        field_type_message = await ctx.send(text)
        await field_type_message.add_reaction(NUMBERS)
        await field_type_message.add_reaction(LETTERS)
        if not image_set:
            await field_type_message.add_reaction(PICTURE)
        field_type_check = lambda r, u: str(r.emoji) in [NUMBERS, LETTERS, TICK, PICTURE] and u == ctx.author
        try:
            reaction, _ = await self.bot.wait_for('reaction_add', check=field_type_check, timeout=120)
            emoji = str(reaction.emoji)
        except AsyncTimeoutError:
            await ctx.send("Picking a field type has timed out - defaulting to text.") 
            emoji = LETTERS

        field_type = {
            NUMBERS: NumberField,
            LETTERS: TextField,
            TICK: BooleanField,  # TODO
            PICTURE: ImageField,
        }.get(emoji, Exception("Shouldn't be reached."))()
        if isinstance(field_type, ImageField) and image_set:
            raise Exception("You lil shit")


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
