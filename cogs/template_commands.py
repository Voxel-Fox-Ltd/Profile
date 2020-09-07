import asyncio
import string
import uuid
import typing
import collections

import discord
from discord.ext import commands

from cogs import utils


class ProfileTemplates(utils.Cog):

    TICK_EMOJI = "<:tick_yes:596096897995899097>"
    CROSS_EMOJI = "<:cross_no:596096897769275402>"

    NUMBERS_EMOJI = "\U00000031\U000020e3"
    LETTERS_EMOJI = "\U0001F170"
    PICTURE_EMOJI = "\U0001f5bc"

    def __init__(self, bot:utils.Bot):
        super().__init__(bot)
        self.template_creation_locks: typing.Dict[int, asyncio.Lock] = collections.defaultdict(asyncio.Lock)
        self.template_editing_locks: typing.Dict[int, asyncio.Lock] = collections.defaultdict(asyncio.Lock)

    @commands.command(cls=utils.Command)
    @commands.bot_has_permissions(send_messages=True)
    @commands.guild_only()
    async def templates(self, ctx:utils.Context, guild_id:int=None):
        """Lists the templates that have been created for this server"""

        # See if they're allowed to get from another guild ID
        if guild_id is not None and guild_id != ctx.guild.id and self.bot.config.get('bot_support_role_id') not in ctx.author._roles:
            raise commands.MissingRole("Bot Support Team")

        # Grab the templates
        async with self.bot.database() as db:
            templates = await db(
                """SELECT template.template_id, template.name, COUNT(created_profile.*) FROM template
                LEFT JOIN created_profile ON template.template_id=created_profile.template_id
                WHERE guild_id=$1 GROUP BY template.template_id""",
                guild_id or ctx.guild.id
            )

        if not templates:
            return await ctx.send("There are no created templates for this guild.")
        return await ctx.send('\n'.join([f"**{row['name']}** (`{row['template_id']}`, `{row['count']}` created profiles)" for row in templates]))

    @commands.command(cls=utils.Command, aliases=['describe'])
    @commands.bot_has_permissions(send_messages=True, embed_links=True)
    @commands.guild_only()
    async def describetemplate(self, ctx:utils.Context, template:utils.Template, brief:bool=True):
        """Describe a template and its fields"""

        return await ctx.send(embed=template.build_embed(brief=brief))

    @commands.command(cls=utils.Command)
    @commands.has_guild_permissions(manage_roles=True)
    @commands.bot_has_permissions(send_messages=True, external_emojis=True, add_reactions=True, manage_messages=True)
    @commands.guild_only()
    async def edittemplate(self, ctx:utils.Context, template:utils.Template):
        """Edits a template for your guild"""

        # See if they're already editing that template
        if self.template_editing_locks[ctx.guild.id].locked():
            return await ctx.send("You're already editing a template.")

        # Start the template editing
        async with self.template_editing_locks[ctx.guild.id]:

            # Get the template fields
            async with self.bot.database() as db:
                await template.fetch_fields(db)
                guild_settings = await db("SELECT * FROM guild_settings WHERE guild_id=$1 OR guild_id=0 ORDER BY guild_id DESC", ctx.guild.id)

            edit_message = await ctx.send("Loading...")
            messages_to_delete = []
            should_edit = True
            should_add_reactions = True
            while True:

                # Ask what they want to edit
                if should_edit:
                    content = "What do you want to edit - its name (1\u20e3), verification channel (2\u20e3), archive channel (3\u20e3), given role (4\u20e3), fields (5\u20e3), or max profile count (6\u20e3)?"
                    await edit_message.edit(
                        content=content,
                        embed=template.build_embed(brief=True),
                        allowed_mentions=discord.AllowedMentions(roles=False),
                    )
                    should_edit = False

                # Add reactions if there aren't any
                valid_emoji = [
                    "1\N{COMBINING ENCLOSING KEYCAP}", "2\N{COMBINING ENCLOSING KEYCAP}", "3\N{COMBINING ENCLOSING KEYCAP}",
                    "4\N{COMBINING ENCLOSING KEYCAP}", "5\N{COMBINING ENCLOSING KEYCAP}", "6\N{COMBINING ENCLOSING KEYCAP}"
                ]
                valid_emoji.append(self.TICK_EMOJI)
                if should_add_reactions:
                    for e in valid_emoji:
                        await edit_message.add_reaction(e)
                    should_add_reactions = False

                # Wait for a response
                try:
                    reaction, _ = await self.bot.wait_for("reaction_add", check=lambda r, u: u.id == ctx.author.id and r.message.id == edit_message.id and str(r) in valid_emoji, timeout=120)
                except asyncio.TimeoutError:
                    return await ctx.send("Timed out waiting for edit response.")

                # See what they reacted with
                try:
                    available_reactions = {
                        "1\N{COMBINING ENCLOSING KEYCAP}": ('name', str),
                        "2\N{COMBINING ENCLOSING KEYCAP}": ('verification_channel_id', commands.TextChannelConverter()),
                        "3\N{COMBINING ENCLOSING KEYCAP}": ('archive_channel_id', commands.TextChannelConverter()),
                        "4\N{COMBINING ENCLOSING KEYCAP}": ('role_id', commands.RoleConverter()),
                        "5\N{COMBINING ENCLOSING KEYCAP}": (None, self.edit_field(ctx, template, guild_settings[0])),
                        "6\N{COMBINING ENCLOSING KEYCAP}": ('max_profile_count', int),
                        self.TICK_EMOJI: None,
                    }
                    attr, converter = available_reactions[str(reaction)]
                except TypeError:
                    break
                await edit_message.remove_reaction(reaction, ctx.author)

                # See if they want to edit a field
                if attr is None:
                    fields_have_changed = await converter
                    if fields_have_changed is None:
                        return
                    if fields_have_changed:
                        async with self.bot.database() as db:
                            await template.fetch_fields(db)
                        should_edit = True
                    continue

                # Ask what they want to set things to
                if isinstance(converter, commands.Converter):
                    v = await ctx.send("What do you want to set that to? You can give a name, a ping, or an ID, or say `continue` to set the value to null. " + ("Note that any current pending profiles will _not_ be able to be approved after moving the channel" if attr == 'verification_channel_id' else ''))
                else:
                    v = await ctx.send("What do you want to set that to?")
                messages_to_delete.append(v)
                try:
                    value_message = await self.bot.wait_for("message", check=lambda m: m.author.id == ctx.author.id and m.channel.id == ctx.channel.id, timeout=120)
                except asyncio.TimeoutError:
                    return await ctx.send("Timed out waiting for edit response.")
                messages_to_delete.append(value_message)

                # Convert the response
                try:
                    converted = (await converter.convert(ctx, value_message.content)).id
                except commands.BadArgument:
                    if value_message.content == "continue":
                        converted = None
                    else:
                        await ctx.channel.purge(check=lambda m: m.id in [i.id for i in messages_to_delete], bulk=ctx.channel.permissions_for(ctx.guild.me).manage_messages)
                        messages_to_delete.clear()
                        continue
                except AttributeError:
                    converted = converter(value_message.content)

                # Delete the messages we don't need any more
                await ctx.channel.purge(check=lambda m: m.id in [i.id for i in messages_to_delete], bulk=ctx.channel.permissions_for(ctx.guild.me).manage_messages)
                messages_to_delete.clear()

                # Validate if they provided a new name
                if attr == 'name':
                    async with self.bot.database() as db:
                        name_in_use = await db("SELECT * FROM template WHERE guild_id=$1 AND LOWER(name)=LOWER($2)", ctx.guild.id, converted)
                        if name_in_use:
                            continue

                # Store our new shit
                setattr(template, attr, converted)
                async with self.bot.database() as db:
                    await db("UPDATE template SET {0}=$1 WHERE template_id=$2".format(attr), converted, template.template_id)
                should_edit = True

        # Tell them it's done
        await ctx.send("Done editing template.")

    async def edit_field(self, ctx:utils.Context, template:utils.Template, guild_settings:dict):
        """Talk the user through editing a field of a template"""

        # Ask which index they want to edit
        if len(template.fields) == 0:
            ask_field_edit_message: discord.Message = await ctx.send("Now talking you through creating a new field.")
        elif len(template.fields) >= guild_settings['max_template_field_count']:
            ask_field_edit_message: discord.Message = await ctx.send("What is the index of the field you want to edit?")
        else:
            ask_field_edit_message: discord.Message = await ctx.send("What is the index of the field you want to edit? If you want to add a *new* field, type **new**.")
        messages_to_delete = [ask_field_edit_message]

        # Start our infinite loop
        while True:

            # Wait for them to say which field they want to edit
            if len(template.fields) > 0:
                try:
                    field_index_message: discord.Message = await self.bot.wait_for("message", check=lambda m: m.author.id == ctx.author.id and m.channel.id == ctx.channel.id, timeout=120)
                    messages_to_delete.append(field_index_message)
                except asyncio.TimeoutError:
                    await ctx.send("Timed out waiting for field index.")
                    return None

            # Grab the field they want to edit
            try:
                if len(template.fields) == 0:
                    raise ValueError()
                field_index: int = int(field_index_message.content.lstrip('#'))
                field_to_edit: utils.Field = [i for i in template.fields.values() if i.index == field_index and i.deleted is False][0]
                break

            # They either gave an invalid number or want to make a new field
            except (ValueError, IndexError):

                # They want to create a new field
                if len(template.fields) == 0 or (field_index_message.content.lower() == "new" and len(template.fields) < guild_settings['max_template_field_count']):
                    image_field_exists: bool = any([i for i in template.fields.values() if isinstance(i.field_type, utils.ImageField)])
                    field: utils.Field = await self.create_new_field(
                        ctx=ctx,
                        template=template,
                        index=len(template.all_fields),
                        image_set=image_field_exists,
                        prompt_for_creation=False,
                        delete_messages=True
                    )
                    await ctx.channel.purge(check=lambda m: m.id in [i.id for i in messages_to_delete], bulk=ctx.channel.permissions_for(ctx.guild.me).manage_messages)
                    if field is None:
                        return None
                    async with self.bot.database() as db:
                        await db(
                            """INSERT INTO field (field_id, name, index, prompt, timeout, field_type, optional, template_id)
                            VALUES ($1, $2, $3, $4, $5, $6, $7, $8)""",
                            field.field_id, field.name, field.index, field.prompt, field.timeout, field.field_type.name, field.optional, field.template_id
                        )
                    return True

                # They want a new field but they're at the max
                elif field_index_message.content.lower() == "new":
                    v = await ctx.send("You're already at the maximum amount of fields for this template - please provide a field index to edit.")
                    messages_to_delete.append(v)
                    continue

                # If they just messed up the field creation
                else:
                    v = await ctx.send("That isn't a valid index number - please provide another.")
                    messages_to_delete.append(v)
                    continue

        # Ask what part of it they want to edit
        attribute_message: discord.Message = await ctx.send(f"Alright, editing the field **{field_to_edit.name}**. What part do you want to edit? Its name (1\N{COMBINING ENCLOSING KEYCAP}), prompt (2\N{COMBINING ENCLOSING KEYCAP}), whether or not it's optional (3\N{COMBINING ENCLOSING KEYCAP}), or delete it entirely (4\N{COMBINING ENCLOSING KEYCAP})?", allowed_mentions=discord.AllowedMentions(users=False, roles=False, everyone=False))
        messages_to_delete.append(attribute_message)
        valid_emoji = ["1\N{COMBINING ENCLOSING KEYCAP}", "2\N{COMBINING ENCLOSING KEYCAP}", "3\N{COMBINING ENCLOSING KEYCAP}", "4\N{COMBINING ENCLOSING KEYCAP}", self.CROSS_EMOJI]
        for e in valid_emoji:
            await attribute_message.add_reaction(e)

        # Wait for a response
        try:
            reaction, _ = await self.bot.wait_for("reaction_add", check=lambda r, u: u.id == ctx.author.id and r.message.id == attribute_message.id and str(r) in valid_emoji, timeout=120)
        except asyncio.TimeoutError:
            await ctx.send("Timed out waiting for field attribute.")
            return None

        # See what they reacted with
        try:
            available_reactions = {
                "1\N{COMBINING ENCLOSING KEYCAP}": ('name', str),
                "2\N{COMBINING ENCLOSING KEYCAP}": ('prompt', str),
                "3\N{COMBINING ENCLOSING KEYCAP}": ('optional', str),
                "4\N{COMBINING ENCLOSING KEYCAP}": (None, str),
                self.CROSS_EMOJI: None,
            }
            attr, converter = available_reactions[str(reaction)]
        except TypeError:
            await ctx.channel.purge(check=lambda m: m.id in [i.id for i in messages_to_delete], bulk=ctx.channel.permissions_for(ctx.guild.me).manage_messages)
            return False

        # And work with it accordingly
        field_value_message = None
        if attr:
            while True:
                if attr == 'optional':
                    v = await ctx.send("Do you want this field to be optional? Type **yes** or **no**.")
                else:
                    v = await ctx.send("What do you want to set this value to?")
                messages_to_delete.append(v)
                try:
                    field_value_message = await self.bot.wait_for("message", check=lambda m: m.author.id == ctx.author.id and m.channel.id == ctx.channel.id, timeout=120)
                    messages_to_delete.append(field_value_message)
                    field_value = converter(field_value_message.content)
                except asyncio.TimeoutError:
                    await ctx.send("Timed out waiting for field value.")
                    return None
                except ValueError:
                    v = await ctx.send("I couldn't convert your provided value properly. Please provide another.")
                    messages_to_delete.append(v)
                    continue

                # Fix up the inputs
                if attr == 'name' and not 256 >= len(field_value) > 0:
                    v = await ctx.send("That field name is too long. Please provide another.")
                    messages_to_delete.append(v)
                    continue
                if attr == 'optional':
                    field_value = field_value.lower() == 'yes'
                break

        # Save the data
        async with self.bot.database() as db:
            if attr:
                await db("UPDATE field SET {0}=$2 WHERE field_id=$1".format(attr), field_to_edit.field_id, field_value)
            else:
                await db("UPDATE field SET deleted=true WHERE field_id=$1", field_to_edit.field_id)

        # And done
        await ctx.channel.purge(check=lambda m: m.id in [i.id for i in messages_to_delete], bulk=ctx.channel.permissions_for(ctx.guild.me).manage_messages)
        return True

    @commands.command(cls=utils.Command)
    @commands.has_guild_permissions(manage_roles=True)
    @commands.bot_has_permissions(send_messages=True, external_emojis=True, add_reactions=True)
    @commands.guild_only()
    async def deletetemplate(self, ctx:utils.Context, template:utils.Template):
        """Deletes a template for your guild"""

        # Ask for confirmation
        delete_confirmation_message = await ctx.send("By doing this, you'll delete all of the created profiles under this template as well. Would you like to proceed?")
        valid_reactions = [self.TICK_EMOJI, self.CROSS_EMOJI]
        for e in valid_reactions:
            await delete_confirmation_message.add_reaction(e)
        try:
            r, _ = await self.bot.wait_for(
                "reaction_add", timeout=120.0,
                check=lambda r, u: r.message.id == delete_confirmation_message.id and str(r.emoji) in valid_reactions and u.id == ctx.author.id
            )
        except asyncio.TimeoutError:
            try:
                await ctx.send("Template delete timed out - please try again later.")
            except discord.Forbidden:
                pass
            return

        # Check if they said no
        if str(r.emoji) == self.CROSS_EMOJI:
            return await ctx.send("Got it, cancelling template delete.")

        # Delete it from the database
        async with self.bot.database() as db:
            await db("DELETE FROM template WHERE template_id=$1", template.template_id)
        self.logger.info(f"Template '{template.name}' deleted on guild {ctx.guild.id}")
        await ctx.send(f"All relevant data for template **{template.name}** (`{template.template_id}`) has been deleted.")

    @commands.command()
    @commands.has_guild_permissions(manage_roles=True)
    @commands.bot_has_permissions(send_messages=True, manage_messages=True, external_emojis=True, add_reactions=True, embed_links=True)
    @commands.guild_only()
    async def createtemplate(self, ctx:utils.Context, template_name:str=None):
        """Creates a new template for your guild"""

        # Only allow them to make one template at once
        if self.template_creation_locks[ctx.guild.id].locked():
            return await ctx.send("You're already creating a template.")

        # See if they have too many templates already
        async with self.bot.database() as db:
            template_list = await db("SELECT template_id FROM template WHERE guild_id=$1", ctx.guild.id)
            guild_settings = await db("SELECT * FROM guild_settings WHERE guild_id=$1 OR guild_id=0 ORDER BY guild_id DESC", ctx.guild.id)
        if len(template_list) >= guild_settings[0]['max_template_count']:
            return await ctx.send(f"You already have {guild_settings[0]['max_template_count']} templates set for this server, which is the maximum number allowed.")

        # And now we start creating the template itself
        async with self.template_creation_locks[ctx.guild.id]:

            # Send the flavour text behind getting a template name
            if template_name is None:
                await ctx.send(f"What name do you want to give this template? This will be used for the set and get commands; eg if the name of your template is `test`, the commands generated will be `{ctx.prefix}settest` to set a profile, `{ctx.prefix}gettest` to get a profile, and `{ctx.prefix}deletetest` to delete a profile. A profile name is case insensitive when used in commands.")

            # Get name from the messages they send
            while True:

                # Get message
                if template_name is None:
                    try:
                        name_message = await self.bot.wait_for('message', check=lambda m: m.author == ctx.author and m.channel == ctx.channel, timeout=120)

                    # Catch timeout
                    except asyncio.TimeoutError:
                        try:
                            return await ctx.send(f"{ctx.author.mention}, your template creation has timed out after 2 minutes of inactivity.")
                        except discord.Forbidden:
                            return
                    template_name = name_message.content

                # Check name for characters
                if [i for i in template_name if i not in string.ascii_letters + string.digits]:
                    await ctx.send("You can only use normal lettering and digits in your command name. Please run this command again to set a new one.")
                    return

                # Check name for length
                if 30 >= len(template_name) >= 1:
                    pass
                else:
                    await ctx.send("The maximum length of a profile name is 30 characters. Please give another name.")
                    continue

                # Check name is unique
                async with self.bot.database() as db:
                    template_exists = await db("SELECT * FROM template WHERE guild_id=$1 AND LOWER(name)=LOWER($2)", ctx.guild.id, template_name)
                if template_exists:
                    await ctx.send(f"This server already has a template with name **{template_name}**. Please run this command again to provide another one.")
                    return
                break

            # Get an ID for the profile
            template = utils.Template(
                template_id=uuid.uuid4(),
                colour=0x0,
                guild_id=ctx.guild.id,
                verification_channel_id=None,
                name=template_name,
                archive_channel_id=None,
                role_id=None,
                max_profile_count=5,
            )

        # Save it all to database
        async with self.bot.database() as db:
            await db(
                """INSERT INTO template (template_id, name, colour, guild_id, verification_channel_id, archive_channel_id)
                VALUES ($1, $2, $3, $4, $5, $6)""",
                template.template_id, template.name, template.colour, template.guild_id, template.verification_channel_id, template.archive_channel_id
            )

        # Output to user
        self.logger.info(f"New template '{template.name}' created on guild {ctx.guild.id}")
        try:
            await ctx.send(f"Your template has been created with {len(template.fields)} fields. Users can now run `{ctx.prefix}set{template.name.lower()}` to set a profile, or `{ctx.prefix}get{template.name.lower()} @User` to get the profile of another user.")
        except (discord.Forbidden, discord.NotFound):
            pass
        await ctx.invoke(self.bot.get_command("edittemplate"), template)

    async def create_new_field(self, ctx:utils.Context, template:utils.Template, index:int, image_set:bool=False, prompt_for_creation:bool=True, delete_messages:bool=False) -> typing.Optional[utils.Field]:
        """Talk a user through creating a new field for their template"""

        # Here are some things we can use later
        message_check = lambda m: m.author == ctx.author and m.channel == ctx.channel
        okay_reaction_check = lambda r, u: str(r.emoji) in prompt_emoji and u.id == ctx.author.id
        prompt_emoji = [self.TICK_EMOJI, self.CROSS_EMOJI]
        messages_to_delete = []

        # Ask if they want a new field
        if prompt_for_creation:
            field_message = await ctx.send("Do you want to make a new field for your profile?", embed=template.build_embed())
            messages_to_delete.append(field_message)
            for e in prompt_emoji:
                try:
                    await field_message.add_reaction(e)
                except discord.Forbidden:
                    try:
                        await field_message.delete()
                    except discord.NotFound:
                        pass
                    await ctx.send("I tried to add a reaction to my message, but I was unable to. Please update my permissions for this channel and try again.")
                    return None

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
            await field_message.edit(content=field_message.content, embed=None)

        # Get a name for the new field
        v = await ctx.send("What name should this field have? This is the name shown on the embed, so it should be something like 'Name', 'Age', 'Gender', etc.")
        messages_to_delete.append(v)
        while True:
            try:
                field_name_message = await self.bot.wait_for('message', check=message_check, timeout=120)
                messages_to_delete.append(field_name_message)
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
                v = await ctx.send("The maximum length of a field name is 256 characters. Please provide another name.")
                messages_to_delete.append(v)
        field_name = field_name_message.content

        # Get a prompt for the field
        v = await ctx.send("What message should I send when I'm asking people to fill out this field? This should be a question or prompt, eg 'What is your name/age/gender/etc'.")
        messages_to_delete.append(v)
        while True:
            try:
                field_prompt_message = await self.bot.wait_for('message', check=message_check, timeout=120)
                messages_to_delete.append(field_prompt_message)
            except asyncio.TimeoutError:
                try:
                    await ctx.send("Creating a new field has timed out. The profile is being created with the fields currently added.")
                except (discord.Forbidden, discord.NotFound):
                    pass
                return None

            if len(field_prompt_message.content) >= 1:
                break
            else:
                v = await ctx.send("You need to actually give text for the prompt :/")
                messages_to_delete.append(v)
        field_prompt = field_prompt_message.content
        prompt_is_command = bool(utils.Template.COMMAND_REGEX.search(field_prompt))

        # If it's a command, then we don't need to deal with this
        if not prompt_is_command:

            # Get field optional
            prompt_message = await ctx.send("Is this field optional?")
            messages_to_delete.append(prompt_message)
            for e in prompt_emoji:
                await prompt_message.add_reaction(e)
            try:
                field_optional_reaction, _ = await self.bot.wait_for('reaction_add', check=okay_reaction_check, timeout=120)
                field_optional_emoji = str(field_optional_reaction.emoji)
            except asyncio.TimeoutError:
                field_optional_emoji = self.CROSS_EMOJI
            field_optional = field_optional_emoji == self.TICK_EMOJI

            # Get timeout
            v = await ctx.send("How many seconds should I wait for people to fill out this field (I recommend 120 - that's 2 minutes)? The minimum is 30, and the maximum is 600.")
            messages_to_delete.append(v)
            while True:
                try:
                    field_timeout_message = await self.bot.wait_for('message', check=message_check, timeout=120)
                    messages_to_delete.append(field_timeout_message)
                except asyncio.TimeoutError:
                    await ctx.send("Creating a new field has timed out. The profile is being created with the fields currently added.")
                    return None
                try:
                    timeout = int(field_timeout_message.content)
                    if timeout < 30:
                        raise ValueError()
                    break
                except ValueError:
                    v = await ctx.send("I couldn't convert your message into a valid number - the minimum is 30 seconds. Please try again.")
                    messages_to_delete.append(v)
            field_timeout = min([timeout, 600])

            # Ask for field type
            if image_set:
                text = f"What type is this field? Will you be getting numbers ({self.NUMBERS_EMOJI}), or any text ({self.LETTERS_EMOJI})?"
            else:
                text = f"What type is this field? Will you be getting numbers ({self.NUMBERS_EMOJI}), any text ({self.LETTERS_EMOJI}), or an image ({self.PICTURE_EMOJI})?"
            field_type_message = await ctx.send(text)
            messages_to_delete.append(field_type_message)

            # Add reactions
            await field_type_message.add_reaction(self.NUMBERS_EMOJI)
            await field_type_message.add_reaction(self.LETTERS_EMOJI)
            if not image_set:
                await field_type_message.add_reaction(self.PICTURE_EMOJI)

            # See what they said
            field_type_emoji = [self.NUMBERS_EMOJI, self.LETTERS_EMOJI, self.PICTURE_EMOJI]  # self.TICK_EMOJI
            field_type_check = lambda r, u: str(r.emoji) in field_type_emoji and u == ctx.author
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
                self.PICTURE_EMOJI: utils.ImageField,
            }[emoji]
            if isinstance(field_type, utils.ImageField) and image_set:
                raise Exception("You shouldn't be able to set two image fields.")

        # Set some defaults for the field stuff
        else:
            field_optional = False
            field_timeout = 15
            field_type = utils.TextField

        # Make the field object
        field = utils.Field(
            field_id=uuid.uuid4(),
            name=field_name,
            index=index,
            prompt=field_prompt,
            timeout=field_timeout,
            field_type=field_type,
            template_id=template.template_id,
            optional=field_optional,
            deleted=False,
        )

        # See if we need to delete things
        if delete_messages:
            await ctx.channel.purge(check=lambda m: m.id in [i.id for i in messages_to_delete], bulk=ctx.channel.permissions_for(ctx.guild.me).manage_messages)

        # And we done
        return field


def setup(bot:utils.Bot):
    x = ProfileTemplates(bot)
    bot.add_cog(x)
