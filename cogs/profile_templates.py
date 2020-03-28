import asyncio
import string
import uuid
import typing

import discord
from discord.ext import commands

from cogs import utils


class ProfileTemplates(utils.Cog):

    TICK_EMOJI = "<:tickYes:596096897995899097>"
    CROSS_EMOJI = "<:crossNo:596096897769275402>"

    NUMBERS_EMOJI = "\U00000031\U000020e3"
    LETTERS_EMOJI = "\U0001F170"
    PICTURE_EMOJI = "\U0001f5bc"
    # TICK_EMOJI = "\U00002705"  # TODO make this work or something

    @commands.command(cls=utils.Command)
    @commands.guild_only()
    @commands.has_permissions(manage_roles=True)
    async def deletetemplate(self, ctx:utils.Context, template_name:str):
        """Deletes a template for your guild"""

        # Grab template object
        template: utils.Profile = utils.Profile.all_guilds[ctx.guild.id].get(template_name.lower())
        if template is None:
            return await ctx.send(f"There's no template with the name `{template_name}` on this guild. Please see `{ctx.prefix}help` to see all the created templates.")

        # Ask for confirmation
        template_profiles: typing.List[utils.UserProfile] = [i for i in utils.UserProfile.all_profiles.values() if i.profile_id == template.profile_id]
        delete_confirmation_message = await ctx.send(f"By doing this, you'll delete `{len(template_profiles)}` of the created profiles under this template as well. Would you like to proceed?")
        valid_reactions = [self.TICK_EMOJI, self.CROSS_EMOJI]
        for e in valid_reactions:
            await delete_confirmation_message.add_reaction(e)
        try:
            r, _ = await self.bot.wait_for(
                "reaction_add", timeout=120.0,
                check=lambda r, u: r.message.id == delete_confirmation_message.id and str(r.emoji) in valid_reactions and u.id == ctx.author.id
            )
        except asyncio.TimeoutError:
            return await ctx.send("Template delete timed out - please try again later.")

        # Check if they said no
        if str(r.emoji) == self.CROSS_EMOJI:
            return await ctx.send("Got it, cancelling template delete.")

        # Make sure the emoji is actually valid
        elif str(r.emoji) == self.TICK_EMOJI:
            pass
        else:
            raise RuntimeError("Invalid emoji passed to command")

        # Okay time to delete from the database
        async with self.bot.database() as db:
            await db('DELETE FROM filled_field WHERE field_id IN (SELECT field_id FROM field WHERE profile_id=$1)', template.profile_id)
            await db('DELETE FROM created_profile WHERE profile_id=$1', template.profile_id)
            await db('DELETE FROM field WHERE profile_id=$1', template.profile_id)
            await db('DELETE FROM profile WHERE profile_id=$1', template.profile_id)
        self.logger.info(f"Template '{template.name}' deleted on guild {ctx.guild.id}")

        # And I'll just try to delete things from cache as best I can
        # First grab all the fields and filled fields - I grabbed the created profiles earlier
        fields: typing.List[utils.Field] = []
        filled_fields: typing.List[utils.FilledField] = []
        for t in template_profiles:
            for f in t.filled_fields:
                fields.append(f.field)
                filled_fields.append(f)

        # Delete fields
        for f in fields:
            f.all_fields.pop(f.field_id, None)
            f.all_profile_fields.pop(f.profile_id, None)

        # Delete filled fields
        for f in filled_fields:
            f.all_filled_fields.pop((f.user_id, f.field_id), None)

        # Delete filled profiles
        for c in template_profiles:
            c.all_profiles.pop((c.user_id, ctx.guild.id, template_name), None)

        # Delete profile
        template.all_profiles.pop(template.profile_id, None)
        template.all_guilds[ctx.guild.id].pop(template.name, None)

        # And done
        await ctx.send("Template, fields, and all created profiles have been deleted from the database and cache.")

    @commands.command()
    @commands.guild_only()
    @commands.has_permissions(manage_roles=True)
    async def createtemplate(self, ctx:utils.Context):
        """Creates a new template for your guild"""

        # Send the flavour text behind getting a template name
        await ctx.send(f"What name do you want to give this template? This will be used for the set and get commands, eg if the name of your template is `test`, the commands generated will be `{ctx.prefix}settest` to set a profile, `{ctx.prefix}gettest` to get a profile, and `{ctx.prefix}deletetest` to delete a profile. A profile name is case insensitive.")

        # Get name from the messages they send
        while True:
            # Get message
            try:
                name_message = await self.bot.wait_for('message', check=lambda m: m.author == ctx.author and m.channel == ctx.channel, timeout=120)

            # Catch timeout
            except asyncio.TimeoutError:
                await ctx.send(f"{ctx.author.mention}, your template creation has timed out after 2 minutes of inactivity.")
                return

            # Check name for characters
            profile_name = name_message.content.lower()
            if [i for i in profile_name if i not in string.ascii_lowercase + string.digits]:
                await ctx.send("You can only use normal lettering and digits in your command name. Please run this command again to set a new one.")
                return

            # Check name for length
            if 30 >= len(profile_name) >= 1:
                pass
            else:
                await ctx.send("The maximum length of a profile name is 30 characters. Please give another name.")
                continue

            # Check name is unique
            if utils.Profile.all_guilds[ctx.guild.id].get(profile_name):
                await ctx.send(f"This server already has a template with name `{profile_name}`. Please run this command again to provide another one.")
                return
            break

        # Get colour
        colour = 0x000000  # TODO

        # Get verification channel
        await ctx.send("Sometimes you want to be able to make sure that your users are putting in relevant data before allowing their profiles to be seen on your server - this process is called verification. What channel would you like the the verification process to happen in? If you want profiles to be verified automatically (ie not verified by a mod team), just say `continue`.")
        verification_channel_id = None
        try:
            verification_message = await self.bot.wait_for('message', check=lambda m: m.author == ctx.author and m.channel == ctx.channel, timeout=120)
        except asyncio.TimeoutError:
            await ctx.send(f"{ctx.author.mention}, because of your 2 minutes of inactivity, profiles have been set to automatic approval.")
        else:
            if verification_message.channel_mentions:
                verification_channel = verification_message.channel_mentions[0]
                proper_permissions = discord.Permissions()
                proper_permissions.update(read_messages=True, add_external_emojis=True, send_messages=True, add_reactions=True, embed_links=True)
                if verification_channel.permissions_for(ctx.guild.me).is_superset(proper_permissions):
                    verification_channel_id = verification_channel.id
                else:
                    return await ctx.send("I don't have all the permissions I need to be able to send messages to that channel. I need `read messages`, `send messages`, `add external emojis`, `add reactions`, and `embed links`. Please update the channel permissions, and run this command again.")
            elif verification_message.content.lower() == "continue":
                pass
            else:
                return await ctx.send(f"I couldn't quite work out what you were trying to say there - please mention the channel as a ping, eg {ctx.channel.mention}. Please re-run the command to continue.")

        # Get archive channel
        await ctx.send("Some servers want approved profiles to be sent automatically to a given channel - this is called archiving. What channel would you like verified profiles to be archived in? If you don't want to set up an archive channel, just say `continue`.")
        archive_channel_id = None
        try:
            archive_message = await self.bot.wait_for('message', check=lambda m: m.author == ctx.author and m.channel == ctx.channel, timeout=120)
        except asyncio.TimeoutError:
            await ctx.send(f"{ctx.author.mention}, because of your 2 minutes of inactivity, profiles have been set to automatic approval.")
        else:
            if archive_message.channel_mentions:
                archive_channel = archive_message.channel_mentions[0]
                proper_permissions = discord.Permissions()
                proper_permissions.update(read_messages=True, send_messages=True, embed_links=True)
                if archive_channel.permissions_for(ctx.guild.me).is_superset(proper_permissions):
                    archive_channel_id = archive_channel.id
                else:
                    return await ctx.send("I don't have all the permissions I need to be able to send messages to that channel. I need `read messages`, `send messages`, `embed links`. Please update the channel permissions, and run this command again.")
            elif verification_message.content.lower() == "continue":
                pass
            else:
                return await ctx.send(f"I couldn't quite work out what you were trying to say there - please mention the channel as a ping, eg {ctx.channel.mention}. Please re-run the command to continue.")

        # Get an ID for the profile
        profile = utils.Profile(
            profile_id=uuid.uuid4(),
            colour=colour,
            guild_id=ctx.guild.id,
            verification_channel_id=verification_channel_id,
            name=profile_name,
            archive_channel_id=archive_channel_id,
        )

        # Now we start the field loop
        index = 0
        field = True
        image_set = False
        while field:
            field = await self.create_new_field(ctx, profile.profile_id, index, image_set)
            if field:
                image_set = isinstance(field.field_type, utils.ImageField) or image_set
            index += 1
            if index == 20:
                break  # Set max field amount

        # Save it all to database
        async with self.bot.database() as db:
            await db('INSERT INTO profile (profile_id, name, colour, guild_id, verification_channel_id, archive_channel_id) VALUES ($1, $2, $3, $4, $5, $6)', profile.profile_id, profile.name, profile.colour, profile.guild_id, profile.verification_channel_id, archive_channel_id)
            for field in profile.fields:
                await db('INSERT INTO field (field_id, name, index, prompt, timeout, field_type, optional, profile_id) VALUES ($1, $2, $3, $4, $5, $6, $7, $8)', field.field_id, field.name, field.index, field.prompt, field.timeout, field.field_type.name, field.optional, field.profile_id)

        # Output to user
        self.logger.info(f"New template '{profile.name}' created on guild {ctx.guild.id}")
        await ctx.send(f"Your template has been created with {len(profile.fields)} fields. Users can now run `{ctx.prefix}set{profile.name.lower()}` to set a profile, or `{ctx.prefix}get{profile.name.lower()} @User` to get the profile of another user.")

    async def create_new_field(self, ctx:utils.Context, profile_id:uuid.UUID, index:int, image_set:bool=False) -> utils.Field:
        """Lets a user create a new field in their profile"""

        # Ask if they want a new field
        field_message = await ctx.send("Do you want to make a new field for your profile?")
        await field_message.add_reaction(self.TICK_EMOJI)
        await field_message.add_reaction(self.CROSS_EMOJI)
        message_check = lambda m: m.author == ctx.author and m.channel == ctx.channel
        okay_reaction_check = lambda r, u: str(r.emoji) in [self.TICK_EMOJI, self.CROSS_EMOJI] and u == ctx.author
        try:
            reaction, _ = await self.bot.wait_for('reaction_add', check=okay_reaction_check, timeout=120)
        except asyncio.TimeoutError:
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
            except asyncio.TimeoutError:
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
            except asyncio.TimeoutError:
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
        #     except asyncio.TimeoutError:
        #         await ctx.send("Creating a new field has timed out. The profile is being created with the fields currently added.")
        #         return None
        #     try:
        #         timeout = int(field_timeout_message.content)
        #         break
        #     except ValueError:
        #         await ctx.send("I couldn't convert your message into a number. Please try again.")
        # field_timeout = timeout
        field_timeout = 120

        # Ask for field type
        if image_set:
            text = f"What TYPE is this field? Will you be getting numbers ({self.NUMBERS_EMOJI}), or text ({self.LETTERS_EMOJI})?"
        else:
            text = f"What TYPE is this field? Will you be getting numbers ({self.NUMBERS_EMOJI}), text ({self.LETTERS_EMOJI}), or an image ({self.PICTURE_EMOJI})?"
        field_type_message = await ctx.send(text)

        # Add reactions
        await field_type_message.add_reaction(self.NUMBERS_EMOJI)
        await field_type_message.add_reaction(self.LETTERS_EMOJI)
        if not image_set:
            await field_type_message.add_reaction(self.PICTURE_EMOJI)

        # See what they said
        valid_emoji = [self.NUMBERS_EMOJI, self.LETTERS_EMOJI, self.PICTURE_EMOJI]  # self.TICK_EMOJI
        field_type_check = lambda r, u: str(r.emoji) in valid_emoji and u == ctx.author
        try:
            reaction, _ = await self.bot.wait_for('reaction_add', check=field_type_check, timeout=120)
            emoji = str(reaction.emoji)
        except asyncio.TimeoutError:
            await ctx.send("Picking a field type has timed out - defaulting to text.")
            emoji = self.LETTERS_EMOJI

        # Change that emoji into a datatype
        field_type = {
            self.NUMBERS_EMOJI: utils.NumberField,
            self.LETTERS_EMOJI: utils.TextField,
            # self.TICK_EMOJI: utils.BooleanField,  # TODO
            self.PICTURE_EMOJI: utils.ImageField,
        }.get(emoji, Exception("Shouldn't be reached."))()
        if isinstance(field_type, utils.ImageField) and image_set:
            raise Exception("You shouldn't be able to set two image fields.")

        # Get whether the field is optional
        field_optional = False  # TODO

        # Make the field object
        return utils.Field(
            field_id=uuid.uuid4(),
            name=field_name,
            index=index,
            prompt=field_prompt,
            timeout=field_timeout,
            field_type=field_type,
            profile_id=profile_id,
            optional=field_optional,
        )


def setup(bot:utils.Bot):
    x = ProfileTemplates(bot)
    bot.add_cog(x)
