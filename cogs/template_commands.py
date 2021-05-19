import asyncio
import string
import uuid
import typing
import collections
import operator

import discord
from discord.ext import commands
import voxelbotutils as utils
import asyncpg

from cogs import utils as localutils


class ProfileTemplates(utils.Cog):

    def __init__(self, bot:utils.Bot):
        super().__init__(bot)
        self.template_editing_locks: typing.Dict[int, asyncio.Lock] = collections.defaultdict(asyncio.Lock)  # guild_id: asyncio.Lock

    @staticmethod
    def is_valid_template_name(template_name: str) -> bool:
        """
        Returns whether a template name is technically valid.

        Args:
            template_name (str): The template name you want to check.

        Returns:
            bool: Whether or not the given template name is valid.
        """

        return len([i for i in template_name if i not in string.ascii_letters + string.digits]) == 0

    @utils.command()
    @commands.bot_has_permissions(send_messages=True)
    @commands.guild_only()
    async def templates(self, ctx: utils.Context, guild_id: int = None):
        """
        Lists the templates that have been created for this server.
        """

        # See if they're allowed to get from another guild ID
        if guild_id is not None and guild_id != ctx.guild.id:
            await utils.checks.is_bot_support().predicate(ctx)

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
        template_names = [f"**{row['name']}** (`{row['template_id']}`, `{row['count']}` created profiles)" for row in templates]
        return await ctx.send('\n'.join(template_names))

    @utils.command(aliases=['describe'])
    @commands.bot_has_permissions(send_messages=True, embed_links=True)
    @commands.guild_only()
    async def describetemplate(self, ctx: utils.Context, template: localutils.Template, brief: bool = True):
        """
        Describe a template and its fields.
        """

        embed = template.build_embed(self.bot, brief=brief)
        async with self.bot.database() as db:
            user_profiles = await template.fetch_all_profiles(db, fetch_filled_fields=False)
        embed.description += f"\nCurrently there are **{len(user_profiles)}** created profiles for this template."
        return await ctx.send(embed=embed)

    def purge_message_list(
            self, channel: discord.TextChannel, message_list: typing.List[discord.Message]) -> asyncio.Task:
        """
        Delete a list of messages from the channel.
        """

        async def wrapper():
            def check(message):
                return message.id in [i.id for i in message_list]
            bulk = channel.permissions_for(channel.guild.me).manage_messages
            await channel.purge(check=check, bulk=bulk)
            message_list.clear()
        return self.bot.loop.create_task(wrapper())

    async def user_is_bot_support(self, ctx: utils.Context) -> bool:
        """
        Returns whether or not the user calling the command is bot support.
        """

        try:
            await utils.checks.is_bot_support().predicate(ctx)
            return True
        except commands.CommandError:
            return False

    @utils.command()
    @commands.has_guild_permissions(manage_roles=True)
    @commands.bot_has_permissions(send_messages=True, external_emojis=True, add_reactions=True, manage_messages=True)
    @commands.guild_only()
    async def edittemplate(self, ctx: utils.Context, template: localutils.Template):
        """
        Edits a template for your guild.
        """

        # See if they're already editing that template
        if self.template_editing_locks[ctx.guild.id].locked():
            return await ctx.send("You're already editing a template.")

        # See if they're bot support
        is_bot_support = await self.user_is_bot_support(ctx)

        # Grab the template edit lock
        async with self.template_editing_locks[ctx.guild.id]:

            # Get the template fields
            async with self.bot.database() as db:
                await template.fetch_fields(db)
                guild_settings_rows = await db(
                    """SELECT * FROM guild_settings WHERE guild_id=$1 OR guild_id=0 ORDER BY guild_id DESC""",
                    ctx.guild.id,
                )
            guild_settings = guild_settings_rows[0]

            # Set up our initial vars so we can edit them later
            template_display_edit_message = await ctx.send("Loading template...")  # The message with the template
            components = utils.MessageComponents.add_buttons_with_rows(
                utils.Button("Template name", custom_id="1\N{COMBINING ENCLOSING KEYCAP}"),
                utils.Button("Profile verification channel", custom_id="2\N{COMBINING ENCLOSING KEYCAP}"),
                utils.Button("Profile archive channel", custom_id="3\N{COMBINING ENCLOSING KEYCAP}"),
                utils.Button("Profile completion role", custom_id="4\N{COMBINING ENCLOSING KEYCAP}"),
                utils.Button("Template fields", custom_id="5\N{COMBINING ENCLOSING KEYCAP}"),
                utils.Button("Profile count per user", custom_id="6\N{COMBINING ENCLOSING KEYCAP}"),
            )
            if is_bot_support:
                components.components[-1].add_component(
                    utils.Button("Maximum field count", custom_id="7\N{COMBINING ENCLOSING KEYCAP}"),
                )
            components.components[-1].add_component(utils.Button("Done", custom_id="DONE", style=utils.ButtonStyle.SUCCESS))
            template_options_edit_message = None
            should_edit = True  # Whether or not the template display message should be edited

            # Start our edit loop
            while True:

                # Ask what they want to edit
                if should_edit:
                    try:
                        await template_display_edit_message.edit(
                            content=None,
                            embed=template.build_embed(self.bot, brief=True),
                            allowed_mentions=discord.AllowedMentions(roles=False),
                        )
                    except discord.HTTPException:
                        return
                    should_edit = False

                # Wait for a response from the user
                try:
                    if template_options_edit_message:
                        await template_options_edit_message.edit(components=components.enable_components())
                    else:
                        template_options_edit_message = await ctx.send("What would you like to edit?", components=components)
                    payload = await template_options_edit_message.wait_for_button_click(check=lambda p: p.user.id == ctx.author.id, timeout=120)
                    await payload.ack()
                    reaction = payload.component.custom_id
                except asyncio.TimeoutError:
                    try:
                        await template_options_edit_message.edit(content="Timed out waiting for edit response.", components=None)
                    except discord.HTTPException:
                        pass
                    return

                # See what they reacted with
                try:
                    available_reactions = {
                        "1\N{COMBINING ENCLOSING KEYCAP}": ("name", str),
                        "2\N{COMBINING ENCLOSING KEYCAP}": ("verification_channel_id", commands.TextChannelConverter()),
                        "3\N{COMBINING ENCLOSING KEYCAP}": ("archive_channel_id", commands.TextChannelConverter()),
                        "4\N{COMBINING ENCLOSING KEYCAP}": ("role_id", commands.RoleConverter()),
                        "5\N{COMBINING ENCLOSING KEYCAP}": (None, self.edit_field(ctx, template, guild_settings, is_bot_support)),
                        "6\N{COMBINING ENCLOSING KEYCAP}": ("max_profile_count", int),
                        "7\N{COMBINING ENCLOSING KEYCAP}": ("max_field_count", int),
                        "DONE": None,
                    }
                    attr, converter = available_reactions[reaction]
                except TypeError:
                    break  # They're done

                # Disable the components
                await template_options_edit_message.edit(components=components.disable_components())

                # If they want to edit a field, we go through this section
                if attr is None:

                    # Let them change the fields
                    fields_have_changed = await converter

                    # If the fields have changed then we should update the message
                    if fields_have_changed:
                        async with self.bot.database() as db:
                            await template.fetch_fields(db)
                        should_edit = True

                    # And we're done with this round, so continue upwards
                    continue

                # Change the given attribute
                should_edit = await self.change_template_attribute(ctx, template, is_bot_support, attr, converter)

        # Tell them it's done
        await template_options_edit_message.edit(
            content=(
                f"Finished editing template. Users can create profiles with `{ctx.clean_prefix}{template.name.lower()} set`, "
                f"edit with `{ctx.clean_prefix}{template.name.lower()} edit`, and show them with "
                f"`{ctx.clean_prefix}{template.name.lower()} get`."
            ),
            components=None,
        )

    async def change_template_attribute(
            self, ctx: utils.Context, template: localutils.Template, is_bot_support: bool, attribute: str,
            converter: typing.Union[commands.Converter, type]) -> bool:
        """
        Change the attributes of a given template. Returns whether or not the template has been changed, and should
        thus be updated.
        """

        # Ask what they want to set things to
        if isinstance(converter, commands.Converter):
            note = ""
            if attribute == "verification_channel_id":
                note = "Note that any current pending profiles will _not_ be able to be approved after moving the channel"
            v = await ctx.send((
                f"What do you want to set the template's **{' '.join(attribute.split('_')[:-1])}** to? "
                f"You can give a name, a ping, or an ID, or say `continue` to set the value to null. {note}"
            ))
        else:
            v = await ctx.send(f"What do you want to set the template's **{attribute.replace('_', ' ')}** to?")
        messages_to_delete = [v]

        # Wait for them to respond
        try:
            def check(message):
                return all([
                    message.author.id == ctx.author.id,
                    message.channel.id == ctx.channel.id,
                ])
            value_message = await self.bot.wait_for("message", check=check, timeout=120)
        except asyncio.TimeoutError:
            try:
                return await ctx.send("Timed out waiting for edit response.")
            except discord.HTTPException:
                return
        messages_to_delete.append(value_message)

        # Try and convert their response
        try:
            converted = str((await converter.convert(ctx, value_message.content)).id)

        # The converter failed
        except commands.BadArgument:

            # They want to set it to none
            if value_message.content == "continue":
                converted = None

            # They either gave a command or just something invalid
            else:
                is_command, is_valid_command = localutils.CommandProcessor.get_is_command(value_message.content)
                if is_command and is_valid_command:
                    converted = value_message.content
                else:
                    self.purge_message_list(ctx.channel, messages_to_delete)
                    return False

        # It isn't a converter object it's just a type
        except AttributeError:
            try:
                converted = converter(value_message.content)
            except ValueError:
                self.purge_message_list(ctx.channel, messages_to_delete)
                return False

        # Delete the messages we don't need any more
        self.purge_message_list(ctx.channel, messages_to_delete)

        # Validate the given information
        converted = await self.validate_given_attribute(ctx, template, attribute, converted, is_bot_support)
        if converted is None:
            return False

        # Store our new shit
        setattr(template, attribute, converted)
        async with self.bot.database() as db:
            await db("UPDATE template SET {0}=$1 WHERE template_id=$2".format(attribute), converted, template.template_id)
        return True

    async def validate_given_attribute(
            self, ctx: utils.Context, template: localutils.Template, attribute: str,
            converted: str, is_bot_support: bool) -> str:
        """
        Validates the given information from the user as to whether their attribute should be changed.
        Returns either
        """

        # Validate if they provided a new name
        if attribute == 'name':
            converted = converted.replace(" ", "")
            async with self.bot.database() as db:
                name_in_use = await db(
                    """SELECT * FROM template WHERE guild_id=$1 AND LOWER(name)=LOWER($2)
                    AND template_id<>$3""",
                    ctx.guild.id, converted, template.template_id,
                )
                if name_in_use:
                    await ctx.send("That template name is already in use.", delete_after=3)
                    return None
            if 30 < len(converted) < 1:
                await ctx.send("That template name is invalid - not within 1 and 30 characters in length.", delete_after=3)
                return None

        # Validate profile count
        if attribute == 'max_profile_count':
            if is_bot_support:
                pass
            else:
                original_converted = converted
                converted = max([min([converted, guild_settings['max_template_profile_count']]), 0])
                if original_converted > converted:
                    await ctx.send(
                        f"Your max profile count has been set to **{guild_settings['max_template_profile_count']}** instead "
                        f"of **{original_converted}**.",
                        delete_after=3,
                    )

        # Validate field count
        if attribute == 'max_field_count':
            if is_bot_support:
                pass
            else:
                original_converted = converted
                converted = max([min([converted, guild_settings['max_template_field_count']]), 0])
                if original_converted > converted:
                    await ctx.send(
                        f"Your max field count has been set to **{guild_settings['max_template_field_count']}** instead "
                        f"of **{original_converted}**.",
                        delete_after=3,
                    )

        # Return new information
        return converted

    async def edit_field(
            self, ctx: utils.Context, template: localutils.Template, guild_settings: dict,
            is_bot_support: bool) -> bool:
        """
        Talk the user through editing a field of a template.
        Returns whether or not the template display needs to be updated, or None for an error (like a timeout).
        """

        # Create some components to add to the message
        if len(template.fields) == 0:
            components = None
        else:
            field_name_buttons = [
                utils.Button(field.name[:25], style=utils.ButtonStyle.SECONDARY, custom_id=field.field_id)
                for field in sorted(template.fields.values(), key=operator.attrgetter("index"))
            ]
            if len(template.fields) < max([guild_settings['max_template_field_count'], template.max_field_count]) or is_bot_support:
                components = utils.MessageComponents.add_buttons_with_rows(
                    utils.Button("New", custom_id="NEW"),
                    *field_name_buttons
                )
            else:
                components = utils.MessageComponents.add_buttons_with_rows(*field_name_buttons)

        # Send a message asking what they want to edit
        if components:
            ask_field_edit_message: discord.Message = await ctx.send("Which field do you want to edit?", components=components)
            messages_to_delete = [ask_field_edit_message]
        else:
            ask_field_edit_message = None
            messages_to_delete = []

        # Get field index message
        field_to_edit: localutils.Field = await self.get_field_to_edit(
            ctx, template, ask_field_edit_message, guild_settings, is_bot_support,
        )
        if not isinstance(field_to_edit, localutils.Field):
            self.purge_message_list(ctx.channel, messages_to_delete)
            return field_to_edit  # A new field was created - let's just exit here
        await ask_field_edit_message.edit(components=components.disable_components())

        # Ask what part of it they want to edit
        components = utils.MessageComponents(
            utils.ActionRow(
                utils.Button("Field name", custom_id="NAME"),
                utils.Button("Field prompt", custom_id="PROMPT"),
                utils.Button("Field being optional", custom_id="OPTIONAL"),
                utils.Button("Field type", custom_id="TYPE"),
            ),
            utils.ActionRow(
                utils.Button("Delete field", style=utils.ButtonStyle.DANGER, custom_id="DELETE"),
                utils.Button("Cancel", style=utils.ButtonStyle.SECONDARY, custom_id="CANCEL"),
            ),
        )
        attribute_message: discord.Message = await ctx.send(
            f"Editing the field **{field_to_edit.name}**. Which part would you like to edit?",
            allowed_mentions=discord.AllowedMentions.none(),
            components=components
        )
        messages_to_delete.append(attribute_message)

        # Wait for them to say what they want to edit
        try:
            payload = await attribute_message.wait_for_button_click(check=lambda p: p.user.id == ctx.author.id, timeout=120)
            await payload.ack()
            payload_id = payload.component.custom_id
        except asyncio.TimeoutError:
            try:
                await attribute_message.edit(content="Timed out waiting for field attribute.", components=None)
            except discord.HTTPException:
                pass
            return None

        # See if they want to cancel
        if payload_id == "CANCEL":
            self.purge_message_list(ctx.channel, messages_to_delete)
            return False
        await attribute_message.edit(components=components.disable_components())

        # Let's set up our validity converters for each of the fields
        def name_validity_checker(given_value):
            if len(given_value) > 256 or len(given_value) <= 0:
                return "Your given field name is too long. Please provide another."
            return True

        # See what they reacted with
        try:
            available_reactions = {
                "NAME": (
                    "name", "What do you want to set the name of this field to?",
                    lambda given: "Your given field name is too long. Please provide another." if 0 >= len(given) > 256 else True,
                    None,
                ),
                "PROMPT": (
                    "prompt", "What do you want to set the prompt for this field to?",
                    lambda given: "Your given field prompt is too short. Please provide another." if len(given) == 0 else True,
                    None,
                ),
                "OPTIONAL": (
                    "optional", "Do you want this field to be optional?",
                    None,
                    utils.MessageComponents.boolean_buttons(),
                ),
                "TYPE": (
                    "field_type", "What type do you want this field to have?",
                    None,
                    utils.MessageComponents(utils.ActionRow(utils.Button("Text", "TEXT"), utils.Button("Numbers", "NUMBERS"))),
                ),
                "DELETE": None,
                # "CANCEL": None,
            }
            changed_attribute, prompt, value_check, components = available_reactions[payload_id]
        except TypeError:
            changed_attribute = None  # Delete field

        # Get the value they asked for
        field_value_message = None
        if changed_attribute:

            # Loop so we can deal with invalid values
            while True:

                # Send the prompt
                v = await ctx.send(prompt, components=components)
                messages_to_delete.append(v)

                # Ask the user for some content
                try:
                    if value_check:
                        def check(message):
                            return all([
                                message.author.id == ctx.author.id,
                                message.channel.id == ctx.channel.id,
                            ])
                        field_value_message = await self.bot.wait_for("message", check=check, timeout=120)
                        messages_to_delete.append(field_value_message)
                        field_value = str(field_value_message.content)
                    elif components:
                        payload = await v.wait_for_button_click(check=lambda p: p.user.id == ctx.author.id, timeout=120)
                        await payload.ack()
                        field_value = {
                            "YES": True,
                            "NO": False,
                            "TEXT": localutils.TextField.name,
                            "NUMBERS": localutils.NumberField.name,
                        }[payload.component.custom_id]
                    else:
                        raise Exception("You shouldn't be able to get here.")

                # Value failed to convert
                except ValueError:
                    v = await ctx.send("I couldn't convert your provided value properly. Please provide another.")
                    messages_to_delete.append(v)
                    continue

                # Timed out
                except asyncio.TimeoutError:
                    try:
                        await ctx.send("Timed out waiting for field value.")
                    except discord.HTTPException:
                        pass
                    return None

                # Fix up the inputs
                if value_check:
                    value_is_valid = value_check(field_value)
                    if isinstance(value_is_valid, str) or isinstance(value_is_valid, bool) and value_is_valid is False:
                        v = await ctx.send(value_is_valid or "Your provided value is invalid. Please provide another.")
                        messages_to_delete.append(v)
                        continue
                break

        # Save the data
        async with self.bot.database() as db:
            if changed_attribute:
                await db(
                    """UPDATE field SET {0}=$2 WHERE field_id=$1""".format(changed_attribute),
                    field_to_edit.field_id, field_value,
                )
            else:
                await db(
                    """UPDATE field SET deleted=true WHERE field_id=$1""",
                    field_to_edit.field_id,
                )

        # And done
        self.purge_message_list(ctx.channel, messages_to_delete)
        return True

    async def get_field_to_edit(
            self, ctx: utils.Context, template: localutils.Template, sent_message: discord.Message,
            guild_settings: dict, is_bot_support: bool) -> localutils.Field:
        """
        Get the index of the field that we want to edit. Either returns the field that the user wants to edit,
        True if a new field was successfully created, or None if the user timed out.
        """

        # Start our infinite loop
        messages_to_delete = []
        while True:

            # Wait for them to say which field they want to edit
            if len(template.fields) > 0:
                try:
                    payload = await sent_message.wait_for_button_click(check=lambda p: p.user.id == ctx.author.id, timeout=120)
                    await payload.ack()
                except asyncio.TimeoutError:
                    try:
                        await sent_message.edit(content="Timed out waiting for field index.", components=None)
                    except discord.HTTPException:
                        pass
                    return None

            # Grab the field they want to edit
            try:
                if len(template.fields) == 0:
                    raise ValueError()
                return template.fields[payload.component.custom_id]

            # They either gave an invalid number or want to make a new field
            except (ValueError, KeyError):

                # See if an iamge field already exists
                image_field_exists: bool = any([i for i in template.fields.values() if isinstance(i.field_type, localutils.ImageField)])

                # Talk the user through creating a new field
                field: localutils.Field = await self.create_new_field(
                    ctx=ctx,
                    template=template,
                    index=len(template.all_fields),
                    image_set=image_field_exists,
                    prompt_for_creation=False,
                    delete_messages=True
                )

                # If they errored on setting up then we can exit here
                if field is None:
                    return None

                # Save the new field into the database
                async with self.bot.database() as db:
                    try:
                        await db(
                            """INSERT INTO field (field_id, name, index, prompt, timeout, field_type, optional, template_id)
                            VALUES ($1, $2, $3, $4, $5, $6, $7, $8)""",
                            field.field_id, field.name, field.index, field.prompt, field.timeout, field.field_type.name,
                            field.optional, field.template_id,
                        )
                    except asyncpg.ForeignKeyViolationError:
                        return True  # The template was deleted while it was being edited
                return True

    @utils.command()
    @commands.has_guild_permissions(manage_roles=True)
    @commands.bot_has_permissions(send_messages=True, external_emojis=True, add_reactions=True)
    @commands.guild_only()
    async def deletetemplate(self, ctx: utils.Context, template: localutils.Template):
        """
        Deletes a template from your guild.
        """

        # See if they're already editing that template
        if self.template_editing_locks[ctx.guild.id].locked():
            return await ctx.send("You're already editing a template.")

        # Grab the template edit lock
        async with self.template_editing_locks[ctx.guild.id]:

            # Ask for confirmation
            delete_confirmation_message = await ctx.send(
                "By doing this, you'll delete all of the created profiles under this template as well. Would you like to proceed?",
                components=utils.MessageComponents.boolean_buttons()
            )
            try:
                payload = await delete_confirmation_message.wait_for_button_click(check=lambda p: p.user.id == ctx.author.id, timeout=120.0)
                await payload.ack()
            except asyncio.TimeoutError:
                try:
                    await delete_confirmation_message.edit(
                        content="Template delete timed out - please try again later.",
                        components=utils.MessageComponents.boolean_buttons().disable_components(),
                    )
                except discord.HTTPException:
                    pass
                return

            # Check if they said no
            if payload.component.custom_id == "NO":
                return await payload.message.delete()

            # Delete it from the database
            async with self.bot.database() as db:
                await db("DELETE FROM template WHERE template_id=$1", template.template_id)
            self.logger.info(f"Template '{template.name}' deleted on guild {ctx.guild.id}")
            return await payload.message.edit(
                content=f"All relevant data for template **{template.name}** (`{template.template_id}`) has been deleted.",
                components=None,
            )

    @utils.command()
    @commands.has_guild_permissions(manage_roles=True)
    @commands.bot_has_permissions(send_messages=True, manage_messages=True, external_emojis=True, add_reactions=True, embed_links=True)
    @commands.guild_only()
    async def createtemplate(self, ctx: utils.Context, template_name: str = None):
        """
        Creates a new template for your guild.
        """

        # Only allow them to make one template at once
        if self.template_editing_locks[ctx.guild.id].locked():
            return await ctx.send("You're already creating a template.")

        # See if they have too many templates already
        async with self.bot.database() as db:
            template_list = await db("SELECT template_id FROM template WHERE guild_id=$1", ctx.guild.id)
            guild_settings = await db("SELECT * FROM guild_settings WHERE guild_id=$1 OR guild_id=0 ORDER BY guild_id DESC", ctx.guild.id)
        if len(template_list) >= guild_settings[0]['max_template_count']:
            return await ctx.send(
                f"You already have {guild_settings[0]['max_template_count']} templates set for this server, which is the maximum number allowed.",
            )

        # And now we start creating the template itself
        async with self.template_editing_locks[ctx.guild.id]:

            # Send the flavour text behind getting a template name
            if template_name is None:
                await ctx.send((
                    f"What name do you want to give this template? This will be used for the set "
                    f"and get commands; eg if the name of your template is `test`, the commands generated "
                    f"will be `{ctx.prefix}settest` to set a profile, `{ctx.prefix}gettest` to get a "
                    f"profile, and `{ctx.prefix}deletetest` to delete a profile. A profile name is case "
                    f"insensitive when used in commands."
                ))

            # Get name from the messages they send
            while True:

                # Get message
                if template_name is None:
                    try:
                        check = lambda m: m.author == ctx.author and m.channel == ctx.channel
                        name_message = await self.bot.wait_for('message', check=check, timeout=120)

                    # Catch timeout
                    except asyncio.TimeoutError:
                        try:
                            return await ctx.send((
                                f"{ctx.author.mention}, your template creation has "
                                f"timed out after 2 minutes of inactivity."
                            ))
                        except discord.Forbidden:
                            return
                    template_name = name_message.content

                # Check name for characters
                if not self.is_valid_template_name(template_name):
                    await ctx.send((
                        "You can only use normal lettering and digits in your command name. "
                        "Please run this command again to set a new one."
                    ))
                    return

                # Check name for length
                if 30 >= len(template_name) >= 1:
                    pass
                else:
                    await ctx.send("The maximum length of a profile name is 30 characters. Please give another name.")
                    continue

                # Check name is unique
                async with self.bot.database() as db:
                    template_exists = await db(
                        """SELECT * FROM template WHERE guild_id=$1 AND LOWER(name)=LOWER($2)""",
                        ctx.guild.id, template_name,
                    )
                if template_exists:
                    await ctx.send((
                        f"This server already has a template with name **{template_name}**. "
                        "Please run this command again to provide another one."
                    ))
                    return
                break

            # Get an ID for the profile
            template = localutils.Template(
                template_id=uuid.uuid4(),
                colour=0x0,
                guild_id=ctx.guild.id,
                verification_channel_id=None,
                name=template_name,
                archive_channel_id=None,
                role_id=None,
                max_profile_count=1,
                max_field_count=10,
            )

        # Save it all to database
        async with self.bot.database() as db:
            await db(
                """INSERT INTO template (template_id, name, colour, guild_id, verification_channel_id, archive_channel_id)
                VALUES ($1, $2, $3, $4, $5, $6)""",
                template.template_id, template.name, template.colour, template.guild_id,
                template.verification_channel_id, template.archive_channel_id,
            )

        # Output to user
        self.logger.info(f"New template '{template.name}' created on guild {ctx.guild.id}")
        await ctx.invoke(self.bot.get_command("edittemplate"), template)

    async def get_field_name(self, ctx: utils.Context, messages_to_delete: list) -> typing.Optional[str]:
        """
        A method for use in template creation - asks the user for the name of the field they want to add.
        """

        # Set up a check we can use later
        def message_check(message):
            return all([
                message.author.id == ctx.author.id,
                message.channel.id == ctx.channel.id,
            ])

        # Get a name for the new field
        v = await ctx.send(
            "What name should this field have? This is the name shown on the embed, "
            "so it should be something like 'Name', 'Age', 'Gender', etc."
        )
        messages_to_delete.append(v)
        while True:
            try:
                field_name_message = await self.bot.wait_for('message', check=message_check, timeout=120)
                messages_to_delete.append(field_name_message)
            except asyncio.TimeoutError:
                try:
                    await ctx.send(
                        "Creating a new field has timed out. The profile "
                        "is being created with the fields currently added."
                    )
                except (discord.Forbidden, discord.NotFound):
                    pass
                return None

            # Check if if name is too long
            if 256 >= len(field_name_message.content) >= 1:
                break
            else:
                v = await ctx.send(
                    "The maximum length of a field name is 256 characters. "
                    "Please provide another name."
                )
                messages_to_delete.append(v)
        return field_name_message.content

    async def create_new_field(
            self, ctx: utils.Context, template: localutils.Template, index: int, image_set: bool = False,
            prompt_for_creation: bool = True, delete_messages: bool = False) -> typing.Optional[localutils.Field]:
        """
        Talk a user through creating a new field for their template.
        """

        # Here are some things we can use later
        def message_check(message):
            return all([
                message.author.id == ctx.author.id,
                message.channel.id == ctx.channel.id,
            ])
        messages_to_delete = []

        # Ask if they want a new field
        if prompt_for_creation:
            field_message = await ctx.send(
                "Do you want to make a new field for your profile?",
                embed=template.build_embed(self.bot),
                components=utils.MessageComponents.boolean_buttons(),
            )
            messages_to_delete.append(field_message)

            # Here's us waiting for the "do you want to make a new field" reaction
            try:
                payload = await field_message.wait_for_button_click(check=lambda p: p.user.id == ctx.author.id, timeout=120)
                await payload.ack()
            except asyncio.TimeoutError:
                try:
                    await ctx.send("Creating a new field has timed out. The profile is being created with the fields currently added.")
                except (discord.Forbidden, discord.NotFound):
                    pass
                return None

            # See if they don't wanna continue
            if payload.component.custom_id == "NO":
                return None
            await field_message.edit(content=field_message.content, embed=None)

        # Get a name for the new field
        field_name = await self.get_field_name(ctx, messages_to_delete)
        if field_name is None:
            return

        # Get a prompt for the field
        v = await ctx.send((
            "What message should I send when I'm asking people to fill out this field? "
            "This should be a question or prompt, eg 'What is your name/age/gender/etc'."
        ))
        messages_to_delete.append(v)
        while True:
            try:
                field_prompt_message = await self.bot.wait_for('message', check=message_check, timeout=120)
                messages_to_delete.append(field_prompt_message)
            except asyncio.TimeoutError:
                try:
                    await ctx.send(
                        "Creating a new field has timed out. The profile is being "
                        "created with the fields currently added."
                    )
                except (discord.Forbidden, discord.NotFound):
                    pass
                return None

            if len(field_prompt_message.content) >= 1:
                break
            else:
                v = await ctx.send("You need to actually give text for the prompt :/")
                messages_to_delete.append(v)
        field_prompt = field_prompt_message.content
        prompt_is_command = bool(localutils.CommandProcessor.COMMAND_REGEX.search(field_prompt))

        # If it's a command, then we don't need to deal with this
        if not prompt_is_command:

            # Get field optional
            prompt_message = await ctx.send(
                "Is this field optional?",
                components=utils.MessageComponents.boolean_buttons(),
            )
            messages_to_delete.append(prompt_message)
            try:
                payload = await prompt_message.wait_for_button_click(check=lambda p: p.user.id == ctx.author.id, timeout=120)
                await payload.ack()
                field_optional_emoji = payload.component.custom_id
            except asyncio.TimeoutError:
                field_optional_emoji = "NO"
            field_optional = field_optional_emoji == "YES"
            self.bot.loop.create_task(payload.message.edit(
                components=utils.MessageComponents.boolean_buttons().disable_components(),
            ))

            # Get timeout
            v = await ctx.send((
                "How many seconds should I wait for people to fill out this field (I recommend 120 - "
                "that's 2 minutes)? The minimum is 30, and the maximum is 600."
            ))
            messages_to_delete.append(v)
            while True:
                try:
                    field_timeout_message = await self.bot.wait_for('message', check=message_check, timeout=120)
                    messages_to_delete.append(field_timeout_message)
                except asyncio.TimeoutError:
                    await ctx.send(
                        "Creating a new field has timed out. The profile is being created with the fields currently added."
                    )
                    return None
                try:
                    timeout = int(field_timeout_message.content)
                    if timeout < 30:
                        raise ValueError()
                    break
                except ValueError:
                    v = await ctx.send(
                        "I couldn't convert your message into a valid number - the minimum is 30 seconds. Please try again."
                    )
                    messages_to_delete.append(v)
            field_timeout = min([timeout, 600])

            # Ask for a field type
            action_row = utils.ActionRow()
            action_row.add_component(utils.Button("Text", custom_id="TEXT"))
            action_row.add_component(utils.Button("Numbers", custom_id="NUMBERS"))
            if not image_set:
                action_row.add_component(utils.Button("Image", custom_id="IMAGE"))
            components = utils.MessageComponents(action_row)
            field_type_message = await ctx.send("What type is this field?", components=components)
            messages_to_delete.append(field_type_message)

            # See what they said
            try:
                payload = await field_type_message.wait_for_button_click(check=lambda p: p.user.id == ctx.author.id, timeout=120)
                await payload.ack()
                key = payload.component.custom_id
            except asyncio.TimeoutError:
                try:
                    await ctx.send("Picking a field type has timed out - defaulting to text.")
                except (discord.Forbidden, discord.NotFound):
                    pass
                key = "TEXT"

            # Change that emoji into a datatype
            field_type = {
                "NUMBERS": localutils.NumberField,
                "TEXT": localutils.TextField,
                "IMAGE": localutils.ImageField,
            }[key]
            if isinstance(field_type, localutils.ImageField) and image_set:
                raise Exception("You shouldn't be able to set two image fields.")

        # Set some defaults for the field stuff
        else:
            field_optional = False
            field_timeout = 15
            field_type = localutils.TextField

        # Make the field object
        field = localutils.Field(
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
            self.purge_message_list(ctx.channel, messages_to_delete)

        # And we done
        return field


def setup(bot: utils.Bot):
    x = ProfileTemplates(bot)
    bot.add_cog(x)
