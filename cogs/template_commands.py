import asyncio
import string
import uuid
import typing

import discord
from discord.ext import commands

from cogs import utils


class ProfileTemplates(utils.Cog):

    TICK_EMOJI = "<:tick_yes:596096897995899097>"
    CROSS_EMOJI = "<:cross_no:596096897769275402>"

    NUMBERS_EMOJI = "\U00000031\U000020e3"
    LETTERS_EMOJI = "\U0001F170"
    PICTURE_EMOJI = "\U0001f5bc"
    # TICK_EMOJI = "\U00002705"  # TODO make this work or something

    @commands.command(cls=utils.Command)
    @commands.has_permissions(manage_roles=True)
    @commands.bot_has_permissions(send_messages=True, external_emojis=True, add_reactions=True)
    @commands.guild_only()
    async def edittemplate(self, ctx:utils.Context, template_name:str):
        """Edits a template for your guild"""

        # Grab template object
        template: utils.Template = utils.Template.all_guilds[ctx.guild.id].get(template_name.lower())
        if template is None:
            return await ctx.send(f"There's no template with the name `{template_name}` on this guild. Please see `{ctx.prefix}templates` to see all the created templates.", allowed_mentions=discord.AllowedMentions(everyone=False, users=False, roles=False))

        # Ask what they want to edit
        lines = [
            "What do you want to edit?",
            "1\N{COMBINING ENCLOSING KEYCAP} Verification channel " + (ctx.guild.get_channel(template.verification_channel_id).mention if template.verification_channel_id else ''),
            "2\N{COMBINING ENCLOSING KEYCAP} Profile archive channel " + (ctx.guild.get_channel(template.archive_channel_id).mention if template.archive_channel_id else ''),
            "3\N{COMBINING ENCLOSING KEYCAP} Verified profile role " + (ctx.guild.get_role(template.role_id).mention if template.role_id else ''),
        ]
        edit_message = await ctx.send('\n'.join(lines), allowed_mentions=discord.AllowedMentions(roles=False))
        valid_emoji = ["1\N{COMBINING ENCLOSING KEYCAP}", "2\N{COMBINING ENCLOSING KEYCAP}", "3\N{COMBINING ENCLOSING KEYCAP}"]
        for e in valid_emoji:
            await edit_message.add_reaction(e)

        # Wait for a response
        try:
            reaction, _ = await self.bot.wait_for("reaction_add", check=lambda r, u: u.id == ctx.author.id and r.message.id == edit_message.id and str(r) in valid_emoji)
        except asyncio.TimeoutError:
            return await ctx.send("Timed out waiting for edit response.")

        # See what they reacted with
        attr, converter = {
            "1\N{COMBINING ENCLOSING KEYCAP}": ('verification_channel_id', commands.TextChannelConverter()),
            "2\N{COMBINING ENCLOSING KEYCAP}": ('archive_channel_id', commands.TextChannelConverter()),
            "3\N{COMBINING ENCLOSING KEYCAP}": ('role_id', commands.RoleConverter()),
        }[str(reaction)]

        # Ask what they want to set things to
        await ctx.send("What do you want to set that to? You can give a name, a ping, or an ID, or say `continue` to set the value to null. " + ("Note that any current pending profiles will _not_ be able to be approved after moving the channel" if attr == 'verification_channel_id' else ''))
        try:
            value_message = await self.bot.wait_for("message", check=lambda m: m.author.id == ctx.author.id and m.channel.id == ctx.channel.id)
        except asyncio.TimeoutError:
            return await ctx.send("Timed out waiting for edit response.")

        # Convert the response
        try:
            converted = (await converter.convert(ctx, value_message.content)).id
        except commands.BadArgument:
            if value_message.content == "continue":
                converted = None
            else:
                return await ctx.send("I couldn't work out what you were trying to mention - please re-run this command to try again.")

        # Store our new shit
        setattr(template, attr, converted)
        async with self.bot.database() as db:
            await db(f"UPDATE template SET {attr}=$1 WHERE template_id=$2", converted, template.template_id)
        await ctx.send("Converted and stored the information.")

    @commands.command(cls=utils.Command)
    @commands.guild_only()
    async def templates(self, ctx:utils.Context):
        """Lists the templates that have been created for this server"""

        templates: typing.List[utils.Template] = list(utils.Template.all_guilds[ctx.guild.id].values())
        if not templates:
            return await ctx.send("There are no created templats for this guild.")
        templates_and_count = [(i, len(i.fields)) for i in templates]
        return await ctx.send('\n'.join([f"`{i.name}` ({o} fields)" for i, o in templates_and_count]))

    @commands.command(cls=utils.Command)
    @commands.has_permissions(manage_roles=True)
    @commands.bot_has_permissions(send_messages=True, external_emojis=True, add_reactions=True)
    @commands.guild_only()
    async def deletetemplate(self, ctx:utils.Context, template_name:str):
        """Deletes a template for your guild"""

        # Grab template object
        template: utils.Template = utils.Template.all_guilds[ctx.guild.id].get(template_name.lower())
        if template is None:
            return await ctx.send(f"There's no template with the name `{template_name}` on this guild. Please see `{ctx.prefix}templates` to see all the created templates.", allowed_mentions=discord.AllowedMentions(everyone=False, users=False, roles=False))

        # Ask for confirmation
        template_profiles: typing.List[utils.UserProfile] = [i for i in utils.UserProfile.all_profiles.values() if i.template_id == template.template_id]
        if len(template_profiles):
            delete_confirmation_message = await ctx.send(f"By doing this, you'll delete `{len(template_profiles)}` of the created profiles under this template as well. Would you like to proceed?")
            valid_reactions = [self.TICK_EMOJI, self.CROSS_EMOJI]
            for e in valid_reactions:
                try:
                    await delete_confirmation_message.add_reaction(e)
                except discord.Forbidden:
                    try:
                        await delete_confirmation_message.delete()
                    except discord.NotFound:
                        pass
                    return await ctx.send("I tried to add a reaction to my message, but I was unable to. Please update my permissions for this channel and try again.")
            try:
                r, _ = await self.bot.wait_for(
                    "reaction_add", timeout=120.0,
                    check=lambda r, u: r.message.id == delete_confirmation_message.id and str(r.emoji) in valid_reactions and u.id == ctx.author.id
                )
            except asyncio.TimeoutError:
                try:
                    return await ctx.send("Template delete timed out - please try again later.")
                except discord.Forbidden:
                    return

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
            await db('DELETE FROM filled_field WHERE field_id IN (SELECT field_id FROM field WHERE template_id=$1)', template.template_id)
            await db('DELETE FROM created_profile WHERE template_id=$1', template.template_id)
            await db('DELETE FROM field WHERE template_id=$1', template.template_id)
            await db('DELETE FROM template WHERE template_id=$1', template.template_id)
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
            f.all_profile_fields.pop(f.template_id, None)

        # Delete filled fields
        for f in filled_fields:
            f.all_filled_fields.pop((f.user_id, f.field_id), None)

        # Delete filled profiles
        for c in template_profiles:
            c.all_profiles.pop((c.user_id, ctx.guild.id, template_name), None)

        # Delete profile
        template.all_profiles.pop(template.template_id, None)
        template.all_guilds[ctx.guild.id].pop(template.name, None)

        # And done
        await ctx.send("Template, fields, and all created profiles have been deleted from the database and cache.")

    @commands.command()
    @commands.has_permissions(manage_roles=True)
    @commands.bot_has_permissions(send_messages=True, external_emojis=True, add_reactions=True, embed_links=True)
    @commands.guild_only()
    async def createtemplate(self, ctx:utils.Context):
        """Creates a new template for your guild"""

        # See if they have too many templates already
        if len(utils.Template.all_guilds[ctx.guild.id]) >= 5:
            return await ctx.send("You already have 5 templates set for this server, which is the maximum amount allowed.")

        # Send the flavour text behind getting a template name
        await ctx.send(f"What name do you want to give this template? This will be used for the set and get commands, eg if the name of your template is `test`, the commands generated will be `{ctx.prefix}settest` to set a profile, `{ctx.prefix}gettest` to get a profile, and `{ctx.prefix}deletetest` to delete a profile. A profile name is case insensitive.")

        # Get name from the messages they send
        while True:
            # Get message
            try:
                name_message = await self.bot.wait_for('message', check=lambda m: m.author == ctx.author and m.channel == ctx.channel, timeout=120)

            # Catch timeout
            except asyncio.TimeoutError:
                try:
                    return await ctx.send(f"{ctx.author.mention}, your template creation has timed out after 2 minutes of inactivity.")
                except discord.Forbidden:
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
            if utils.Template.all_guilds[ctx.guild.id].get(profile_name):
                await ctx.send(f"This server already has a template with name `{profile_name}`. Please run this command again to provide another one.", allowed_mentions=discord.AllowedMentions(everyone=False, users=False, roles=False))
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
            try:
                return await ctx.send(f"{ctx.author.mention}, because of your 2 minutes of inactivity, profiles have been set to automatic approval.")
            except (discord.Forbidden, discord.NotFound):
                return
        else:
            try:
                verification_channel = await commands.TextChannelConverter().convert(ctx, verification_message.content)
                proper_permissions = discord.Permissions()
                proper_permissions.update(read_messages=True, add_external_emojis=True, send_messages=True, add_reactions=True, embed_links=True)
                if verification_channel.permissions_for(ctx.guild.me).is_superset(proper_permissions):
                    verification_channel_id = verification_channel.id
                else:
                    return await ctx.send("I don't have all the permissions I need to be able to send messages to that channel. I need `read messages`, `send messages`, `add external emojis`, `add reactions`, and `embed links`. Please update the channel permissions, and run this command again.")
            except commands.BadArgument:
                if verification_message.content.lower() == "continue":
                    pass
                else:
                    return await ctx.send(f"I couldn't quite work out what you were trying to say there - please mention the channel as a ping, eg {ctx.channel.mention}. Please re-run the command to continue.")

        # Get archive channel
        await ctx.send("Some servers want approved profiles to be sent automatically to a given channel - this is called archiving. What channel would you like verified profiles to be archived in? If you don't want to set up an archive channel, just say `continue`.")
        archive_channel_id = None
        try:
            archive_message = await self.bot.wait_for('message', check=lambda m: m.author == ctx.author and m.channel == ctx.channel, timeout=120)
        except asyncio.TimeoutError:
            try:
                await ctx.send(f"{ctx.author.mention}, because of your 2 minutes of inactivity, profiles have been set to automatic approval.")
            except (discord.Forbidden, discord.NotFound):
                return
        else:
            try:
                archive_channel = await commands.TextChannelConverter().convert(ctx, archive_message.content)
                proper_permissions = discord.Permissions()
                proper_permissions.update(read_messages=True, send_messages=True, embed_links=True)
                if archive_channel.permissions_for(ctx.guild.me).is_superset(proper_permissions):
                    archive_channel_id = archive_channel.id
                else:
                    return await ctx.send("I don't have all the permissions I need to be able to send messages to that channel. I need `read messages`, `send messages`, `embed links`. Please update the channel permissions, and run this command again.")
            except commands.BadArgument:
                if archive_message.content.lower() == "continue":
                    pass
                else:
                    return await ctx.send(f"I couldn't quite work out what you were trying to say there - please mention the channel as a ping, eg {ctx.channel.mention}. Please re-run the command to continue.")

        # Get filled profile role
        await ctx.send("Some servers want users with approved profiles to be given a role automatically - if you want users to be assigned a role, provide one here. If not, send `continue`.")
        profile_role_id = None
        try:
            role_message = await self.bot.wait_for('message', check=lambda m: m.author == ctx.author and m.channel == ctx.channel, timeout=120)
        except asyncio.TimeoutError:
            try:
                await ctx.send(f"{ctx.author.mention}, because of your 2 minutes of inactivity, profiles have been set to have no assigned role.")
            except (discord.Forbidden, discord.NotFound):
                return
        else:
            try:
                profile_role = await commands.RoleConverter().convert(ctx, role_message.content)
                profile_role_id = profile_role.id
            except commands.BadArgument:
                if role_message.content.lower() == "continue":
                    pass
                else:
                    return await ctx.send("I couldn't quite work out what you were trying to say there - please either ping the role you want, give its ID, or give its name (case sensitive). Please re-run the command to continue.")

        # Get an ID for the profile
        profile = utils.Template(
            template_id=uuid.uuid4(),
            colour=colour,
            guild_id=ctx.guild.id,
            verification_channel_id=verification_channel_id,
            name=profile_name,
            archive_channel_id=archive_channel_id,
            role_id=profile_role_id,
        )

        # Now we start the field loop
        index = 0
        field = True
        image_set = False
        while field:
            field = await self.create_new_field(ctx, profile.template_id, index, image_set)
            if field:
                image_set = isinstance(field.field_type, utils.ImageField) or image_set
            index += 1
            if index == 20:
                break  # Set max field amount

        # Save it all to database
        async with self.bot.database() as db:
            await db(
                """INSERT INTO template (template_id, name, colour, guild_id, verification_channel_id, archive_channel_id)
                VALUES ($1, $2, $3, $4, $5, $6)""",
                profile.template_id, profile.name, profile.colour, profile.guild_id, profile.verification_channel_id, archive_channel_id
            )
            for field in profile.fields:
                await db(
                    """INSERT INTO field (field_id, name, index, prompt, timeout, field_type, optional, template_id)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8)""",
                    field.field_id, field.name, field.index, field.prompt, field.timeout, field.field_type.name, field.optional, field.template_id
                )

        # Output to user
        self.logger.info(f"New template '{profile.name}' created on guild {ctx.guild.id}")
        try:
            await ctx.send(f"Your template has been created with {len(profile.fields)} fields. Users can now run `{ctx.prefix}set{profile.name.lower()}` to set a profile, or `{ctx.prefix}get{profile.name.lower()} @User` to get the profile of another user.")
        except (discord.Forbidden, discord.NotFound):
            return

    async def create_new_field(self, ctx:utils.Context, template_id:uuid.UUID, index:int, image_set:bool=False) -> typing.Optional[utils.Field]:
        """Lets a user create a new field in their profile"""

        # Ask if they want a new field
        field_message = await ctx.send("Do you want to make a new field for your profile?")
        try:
            await field_message.add_reaction(self.TICK_EMOJI)
            await field_message.add_reaction(self.CROSS_EMOJI)
        except discord.Forbidden:
            try:
                await field_message.delete()
            except discord.NotFound:
                pass
            await ctx.send("I tried to add a reaction to my message, but I was unable to. Please update my permissions for this channel and try again.")
            return None

        # Here are some checks we can use later
        message_check = lambda m: m.author == ctx.author and m.channel == ctx.channel
        okay_reaction_check = lambda r, u: str(r.emoji) in [self.TICK_EMOJI, self.CROSS_EMOJI] and u.id == ctx.author.id

        # Here's us waiting for the "do you want to make a new field" reaction
        try:
            reaction, _ = await self.bot.wait_for('reaction_add', check=okay_reaction_check, timeout=120)
        except asyncio.TimeoutError:
            try:
                await ctx.send("Creating a new field has timed out. The profile is being created with the fields currently added.")
            except (discord.Forbidden, discord.NotFound):
                pass
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
                try:
                    await ctx.send("Creating a new field has timed out. The profile is being created with the fields currently added.")
                except (discord.Forbidden, discord.NotFound):
                    pass
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
                try:
                    await ctx.send("Creating a new field has timed out. The profile is being created with the fields currently added.")
                except (discord.Forbidden, discord.NotFound):
                    pass
                return None

            if len(field_prompt_message.content) >= 1:
                break
            else:
                await ctx.send("You need to actually give text for the prompt :/")
        field_prompt = field_prompt_message.content

        # Get field optional
        prompt_message = await ctx.send("Is this field optional?")
        await prompt_message.add_reaction(self.TICK_EMOJI)
        await prompt_message.add_reaction(self.CROSS_EMOJI)
        try:
            field_optional_reaction, _ = await self.bot.wait_for('reaction_add', check=okay_reaction_check, timeout=120)
            field_optional_emoji = str(field_optional_reaction.emoji)
        except asyncio.TimeoutError:
            field_optional_emoji = self.CROSS_EMOJI
        field_optional = field_optional_emoji == self.TICK_EMOJI

        # Get timeout
        await ctx.send("How many seconds should I wait for people to fill out this field (I recommend 120 - that's 2 minutes)? The minimum is 30, and the maximum is 600.")
        while True:
            try:
                field_timeout_message = await self.bot.wait_for('message', check=message_check, timeout=120)
            except asyncio.TimeoutError:
                await ctx.send("Creating a new field has timed out. The profile is being created with the fields currently added.")
                return None
            try:
                timeout = int(field_timeout_message.content)
                if timeout < 30:
                    raise ValueError()
                break
            except ValueError:
                await ctx.send("I couldn't convert your message into a valid number - the minimum is 30 seconds. Please try again.")
        field_timeout = min([timeout, 600])

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
            try:
                await ctx.send("Picking a field type has timed out - defaulting to text.")
            except (discord.Forbidden, discord.NotFound):
                pass
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

        # Make the field object
        return utils.Field(
            field_id=uuid.uuid4(),
            name=field_name,
            index=index,
            prompt=field_prompt,
            timeout=field_timeout,
            field_type=field_type,
            template_id=template_id,
            optional=field_optional,
            deleted=False,
        )


def setup(bot:utils.Bot):
    x = ProfileTemplates(bot)
    bot.add_cog(x)
