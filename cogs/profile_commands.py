import asyncio
import re
import typing
import uuid
import collections
import string

import discord
from discord.ext import commands
import voxelbotutils as utils
import asyncpg

from cogs import utils as localutils


class ProfileCreation(utils.Cog):

    TICK_EMOJI = "<:tick_yes:596096897995899097>"
    CROSS_EMOJI = "<:cross_no:596096897769275402>"

    OLD_COMMAND_REGEX = re.compile(
        r"^(?P<command>set|get|delete|edit)(?P<template>\S{1,30})(?P<args> ?.*)$",
        re.IGNORECASE
    )
    COMMAND_REGEX = re.compile(
        r"^(?P<template>\S{1,30}) (?P<command>set|get|delete|edit)(?P<args> ?.*)$",
        re.IGNORECASE
    )

    def __init__(self, bot:utils.Bot):
        super().__init__(bot)
        self.set_profile_locks: typing.Dict[int, asyncio.Lock] = collections.defaultdict(asyncio.Lock)

    @utils.Cog.listener()
    async def on_command_error(self, ctx: utils.Context, error: commands.CommandError):
        """
        CommandNotFound handler so the bot can search for that custom command.
        """

        # Handle commandnotfound which is really just handling the set/get/delete/etc commands
        if not isinstance(error, commands.CommandNotFound):
            return

        # Get the command and used template
        prefixless_content = ctx.message.content[len(ctx.prefix):]
        matches = self.COMMAND_REGEX.search(prefixless_content)
        if matches is None:
            matches = self.OLD_COMMAND_REGEX.search(prefixless_content)
            if matches is None:
                return
            matches = self.OLD_COMMAND_REGEX.search(f"{matches.group('command')}{matches.group('template')}{matches.group('args')}")
        if not matches:
            return
        command_operator = matches.group("command")  # get/get/delete/edit
        template_name = matches.group("template")  # template name

        # Filter out DMs
        if isinstance(ctx.channel, discord.DMChannel):
            return  # Fail silently on DM invocation

        # Find the template they asked for on their server
        async with self.bot.database() as db:
            template = await localutils.Template.fetch_template_by_name(db, ctx.guild.id, template_name, fetch_fields=False)
        if not template:
            self.logger.info(f"Failed at getting template '{template_name}' in guild {ctx.guild.id}")
            return  # Fail silently on template doesn't exist

        # Invoke command
        metacommand: utils.Command = self.bot.get_command(f'{command_operator.lower()}_profile_meta')
        ctx.command = metacommand
        ctx.template = template
        ctx.invoke_meta = True
        try:
            self.bot.dispatch("command", ctx)
            await metacommand.invoke(ctx)  # This converts the args for me, which is nice
        except (commands.CommandInvokeError, commands.CommandError) as e:
            self.bot.dispatch("command_error", ctx, e)  # Throw any errors we get in this command into its own error handler

    @staticmethod
    async def get_profile_name(
            ctx: utils.Context, template: localutils.Template,
            user_profiles: typing.List[localutils.UserProfile]) -> str:
        """
        Ask the user for a name that they want to give to their template.
        """

        # See if we can assign one automatically
        if template.max_profile_count == 1:
            suffix = None
            while True:
                if suffix is None:
                    name_content = "default"
                else:
                    name_content = f"default{suffix}"
                if name_content.lower() in [i.name.lower() for i in user_profiles]:
                    suffix = (suffix or 0) + 1
                else:
                    break
            return name_content

        # Tell the user what they need to input
        await ctx.author.send(
            f"What name would you like to give this profile? This will be used to get the "
            f"profile information (eg for the name \"test\", you could run `{template.name.lower()} get test`).",
        )

        # Loop until we get a valid answer
        while True:

            # Wait for the user to respond
            try:
                user_message = await ctx.bot.wait_for(
                    "message", timeout=120,
                    check=lambda m: m.author == ctx.author and isinstance(m.channel, discord.DMChannel)
                )
            except asyncio.TimeoutError:
                try:
                    return await ctx.author.send(
                        f"Your input for this field has timed out. Please try running `set{template.name}` "
                        "on your server again.",
                    )
                except discord.Forbidden:
                    return None

            # Make sure their name is valid
            try:

                # Get the name they gave
                name_content = localutils.TextField.get_from_message(user_message)

                # See if they're already using the name
                if name_content.lower() in [i.name.lower() for i in user_profiles]:
                    raise localutils.errors.FieldCheckFailure(
                        "You're already using that name for this template. Please provide an alternative.",
                    )

                # See if the characters used are invalid
                if any([i for i in name_content if i not in string.ascii_letters + string.digits + ' ']):
                    raise localutils.errors.FieldCheckFailure(
                        "You can only use standard lettering and digits in your profile name. Please provide an alternative.",
                    )

                # Cool it's valid
                break

            # We hit an error converting their name to somethign valid
            except localutils.errors.FieldCheckFailure as e:
                await ctx.author.send(e.message)

        # And return the name given
        return name_content

    @staticmethod
    async def get_field_content(ctx: utils.Context, field: localutils.Field) -> localutils.FilledField:
        """
        Ask the user for a the content of a field.
        """

        # See if the field is a command
        # If it is, then we can just add that to their profile and continue
        if localutils.CommandProcessor.COMMAND_REGEX.search(field.prompt):
            return localutils.FilledField(
                user_id=target_user.id,
                name=name_content,
                field_id=field.field_id,
                value="Could not get field information",
                field=field,
            )

        # Send the user the prompt
        if field.optional:
            await ctx.author.send(f"{field.prompt.rstrip('.')}. Type **pass** to skip this field.")
        else:
            await ctx.author.send(field.prompt)

        # Ask the user for their input
        # Loop until they give something valid
        while True:

            # Wait for the user's input
            try:
                user_message = await self.bot.wait_for(
                    "message", timeout=field.timeout,
                    check=lambda m: m.author == ctx.author and isinstance(m.channel, discord.DMChannel)
                )

            # We timed out waiting
            except asyncio.TimeoutError:
                try:
                    await ctx.author.send(
                        f"Your input for this field has timed out. Running `set{template.name}` on your server "
                        "again to go back through this setup.",
                    )
                    return None
                except discord.Forbidden:
                    return None

            # Try and validate their input
            try:
                if user_message.content.lower() == 'pass' and field.optional:
                    field_content = None
                else:
                    field_content = field.field_type.get_from_message(user_message)
                break
            except localutils.errors.FieldCheckFailure as e:
                await ctx.author.send(e.message)

        # Add their filled field object to the list of data
        return = localutils.FilledField(
            user_id=target_user.id,
            name=name_content,
            field_id=field.field_id,
            value=field_content,
            field=field,
        )

    @utils.command(hidden=True)
    @commands.bot_has_permissions(send_messages=True)
    @commands.guild_only()
    @utils.checks.meta_command()
    async def set_profile_meta(self, ctx: utils.Context, target_user: typing.Optional[discord.Member]):
        """
        Talks a user through setting up a profile on a given server.
        """

        # Set up some variables
        target_user: discord.Member = target_user or ctx.author
        template: localutils.Template = ctx.template

        # See if the user is already setting up a profile
        if self.set_profile_locks[ctx.author.id].locked():
            return await ctx.send("You're already setting up a profile.")

        # Only mods can see other people's profiles
        if target_user != ctx.author and not localutils.checks.member_is_moderator(ctx.bot, ctx.author):
            raise commands.MissingPermissions(["manage_roles"])

        # Check if they're already at the maximum amount of profiles
        async with self.bot.database() as db:
            await template.fetch_fields(db)
            user_profiles: typing.List[localutils.UserProfile] = await template.fetch_all_profiles_for_user(db, target_user.id)
        if len(user_profiles) >= template.max_profile_count:
            if target_user == ctx.author:
                await ctx.send(f"You're already at the maximum number of profiles set for **{template.name}**.")
            else:
                await ctx.send(f"{target_user.mention} is already at the maximum number of profiles set up for **{template.name}**.")
            return

        # See if the template is accepting more profiles
        if template.max_profile_count == 0:
            return await ctx.send(f"Currently the template **{template.name}** is not accepting any more applications.")

        # See if you we can send them DMs
        try:
            if target_user == ctx.author:
                await ctx.author.send(
                    f"Now talking you through setting up your **{template.name}** profile.",
                )
            else:
                await ctx.author.send(
                    f"Now talking you through setting up {target_user.mention}'s **{template.name}** profile.",
                    allowed_mentions=discord.AllowedMentions(users=False),
                )
            await ctx.send("Sent you a DM!")
        except discord.Forbidden:
            return await ctx.send("I'm unable to send you DMs to set up the profile :/")

        # Drag the user into the create profile lock
        async with self.set_profile_locks[ctx.author.id]:

            # Get a name for the profile
            name_content = await self.get_profile_name(ctx, template, user_profiles)
            if not name_content:
                return

            # Talk the user through each field
            filled_field_dict = {}
            for field in sorted(template.fields.values(), key=lambda x: x.index):
                response_field = await self.get_field_content(ctx, field)
                if not response_field:
                    return
                filled_field_dict[field.field_id] = response_field

        # Make the user profile object and add all of the filled fields
        user_profile = localutils.UserProfile(
            user_id=target_user.id,
            name=name_content,
            template_id=template.template_id,
            verified=template.verification_channel_id is None
        )
        user_profile.template = template
        user_profile.all_filled_fields = filled_field_dict

        # Make sure that the embed sends
        try:
            await ctx.author.send(embed=user_profile.build_embed(self.bot, target_user))
        except discord.HTTPException as e:
            return await ctx.author.send(f"Your profile couldn't be sent to you - `{e}`.\nPlease try again later.")

        # Delete the currently archived message
        await user_profile.delete_message(self.bot)

        # Let's see if this worked
        sent_profile_message = await self.bot.get_cog("ProfileVerification").send_profile_submission(ctx, user_profile, target_user)
        if user_profile.template.should_send_message and sent_profile_message is None:
            return
        send_profile_message_id = None
        send_profile_channel_id = None
        if sent_profile_message:
            send_profile_message_id = sent_profile_message.id
            send_profile_channel_id = sent_profile_message.channel.id

        # Database me up daddy
        async with self.bot.database() as db:
            try:
                await db(
                    """INSERT INTO created_profile (user_id, name, template_id, verified, posted_message_id, posted_channel_id)
                    VALUES ($1, $2, $3, $4, $5, $6) ON CONFLICT (user_id, name, template_id)
                    DO UPDATE SET verified=excluded.verified, posted_message_id=excluded.posted_message_id,
                    posted_channel_id=excluded.posted_channel_id""",
                    user_profile.user_id, user_profile.name, user_profile.template.template_id, user_profile.verified,
                    send_profile_message_id, send_profile_channel_id
                )
            except asyncpg.ForeignKeyViolationError:
                return await ctx.author.send(
                    "Unfortunately, it looks like the template was deleted while you were setting up your profile.",
                )
            for field in filled_field_dict.values():
                await db(
                    """INSERT INTO filled_field (user_id, name, field_id, value) VALUES ($1, $2, $3, $4)
                    ON CONFLICT (user_id, name, field_id) DO UPDATE SET value=excluded.value""",
                    field.user_id, name_content, field.field_id, field.value
                )

        # Respond to user
        if template.get_verification_channel_id(target_user):
            await ctx.author.send(f"Your profile has been sent to the **{ctx.guild.name}** staff team for verification - please hold tight!")
        else:
            await ctx.author.send("Your profile has been created and saved.")

    @utils.command(hidden=True)
    @commands.bot_has_permissions(send_messages=True)
    @commands.guild_only()
    @utils.checks.meta_command()
    async def edit_profile_meta(
            self, ctx: utils.Context, target_user: typing.Optional[discord.Member], *,
            profile_name: str = None):
        """
        Talks a user through setting up a profile on a given server.
        """

        # Set up some variables
        target_user = target_user or ctx.author
        template = ctx.template

        # See if they're allowed to edit their profile
        if template.max_profile_count == 0:
            return await ctx.send(
                f"Currently the template **{template.name}** is not accepting any more applications, "
                "and you can't edit profiles while that's disabled.",
            )

        # See if the user is already setting up a profile
        if self.set_profile_locks[ctx.author.id].locked():
            return await ctx.send("You're already setting up a profile.")

        # You can only edit someone else's profile if you're a moderator
        if target_user and target_user != ctx.author and not localutils.checks.member_is_moderator(ctx.bot, ctx.author):
            raise commands.MissingPermissions(["manage_roles"])

        # Grab the data we need
        async with self.bot.database() as db:
            await template.fetch_fields(db)
            try:
                user_profile: localutils.UserProfile = await template.fetch_profile_for_user(db, target_user.id, profile_name)
                user_profiles: typing.List[localutils.UserProfile] = await template.fetch_all_profiles_for_user(
                    db, target_user.id, fetch_filled_fields=False,
                )
            except ValueError:
                user_profiles: typing.List[localutils.UserProfile] = await template.fetch_all_profiles_for_user(db, target_user.id)
                fixed_user_profile_names = [i.name.replace('*', '\\*').replace('`', '\\`').replace('_', '\\_') for i in user_profiles]
                profile_names_string = [f'"{o}"' for o in fixed_user_profile_names]
                if target_user == ctx.author:
                    await ctx.send(
                        f"You have multiple profiles set for the template **{template.name}** "
                        f"- {', '.join(profile_names_string)}.",
                    )
                else:
                    await ctx.send(
                        f"{target_user.mention} has multiple profiles set for the template "
                        f"**{template.name}** - {', '.join(profile_names_string)}."
                    )
                return

        # Check if they already have a profile set
        if user_profile is None:
            if profile_name:
                if target_user == ctx.author:
                    await ctx.send(f"You don't have a profile for **{template.name}** with the name **{profile_name}**.")
                else:
                    await ctx.send(
                        f"{target_user.mention} doesn't have a profile for **{template.name}** with the name **{profile_name}**.",
                        allowed_mentions=discord.AllowedMentions(users=False),
                    )
            else:
                if target_user == ctx.author:
                    await ctx.send(f"You don't have a profile for **{template.name}**.")
                else:
                    await ctx.send(
                        f"{target_user.mention} doesn't have a profile for **{template.name}**.",
                        allowed_mentions=discord.AllowedMentions(users=False),
                    )
            return

        # See if you we can send them the PM
        try:
            if target_user == ctx.author:
                await ctx.author.send(f"Now talking you through editing your **{template.name}** profile.")
            else:
                await ctx.author.send(
                    f"Now talking you through editing {target_user.mention}'s **{template.name}** profile.",
                    allowed_mentions=discord.AllowedMentions(users=False),
                )
            await ctx.send("Sent you a PM!")
        except discord.HTTPException:
            return await ctx.send("I'm unable to send you a DM to set up the profile :/")

        # Drag them into a lock
        async with self.set_profile_locks[ctx.author.id]:

            # Talk the user through each field
            user_profile.all_filled_fields: typing.Dict[uuid.UUID, localutils.FilledField] = user_profile.filled_fields
            for field in sorted(template.fields.values(), key=lambda x: x.index):

                # See if it's a command
                if localutils.CommandProcessor.COMMAND_REGEX.search(field.prompt):
                    filled_field = localutils.FilledField(
                        user_id=target_user.id,
                        name=user_profile.name,
                        field_id=field.field_id,
                        value="Could not get field information",
                        field=field,
                    )
                    user_profile.all_filled_fields[field.field_id] = filled_field
                    continue

                # Get the current value
                current_filled_field = user_profile.all_filled_fields.get(field.field_id)
                current_value = None
                if current_filled_field:
                    current_value = current_filled_field.value

                # Send the user a prompt
                if current_filled_field is None:
                    if field.optional:
                        await ctx.author.send(f"{field.prompt.rstrip('.')}. Type **pass** to skip this field.")
                    else:
                        await ctx.author.send(field.prompt)
                else:
                    await ctx.author.send(
                        f"{field.prompt.rstrip('.')}. The current value for this field is `{current_value or 'empty'}`. "
                        "Type **pass** to leave the value as it currently is.",
                    )

                # Get user input
                while True:
                    try:
                        user_message = await self.bot.wait_for(
                            "message", timeout=field.timeout,
                            check=lambda m: m.author == ctx.author and isinstance(m.channel, discord.DMChannel)
                        )
                    except asyncio.TimeoutError:
                        try:
                            return await ctx.author.send(
                                f"Your input for this field has timed out. Please try running `set{template.name}` on your server again.",
                            )
                        except discord.Forbidden:
                            return
                    if user_message.content.lower() == "pass" and (current_filled_field or field.optional):
                        field_content = current_value
                        break
                    try:
                        field_content = field.field_type.get_from_message(user_message)
                        break
                    except localutils.errors.FieldCheckFailure as e:
                        await ctx.author.send(e.message)

                # Add field to list
                user_profile.all_filled_fields[field.field_id] = localutils.FilledField(
                    user_id=target_user.id,
                    name=user_profile.name,
                    field_id=field.field_id,
                    value=field_content,
                    field=field,
                )

        # Update verification
        user_profile.verified = template.verification_channel_id is None

        # Make sure the bot can send the embed at all
        try:
            await ctx.author.send(embed=user_profile.build_embed(self.bot, target_user))
        except discord.HTTPException as e:
            return await ctx.author.send(f"Your profile couldn't be sent to you, so the embed was probably hecked - `{e}`.\nPlease try again later.")

        # Delete the currently archived message, should one exist
        current_profile_message = await user_profile.fetch_message(self.bot)
        if current_profile_message:
            try:
                await current_profile_message.delete()
            except discord.HTTPException:
                pass

        # Send profile over to the mods
        sent_profile_message = await self.bot.get_cog("ProfileVerification").send_profile_submission(ctx, user_profile, target_user)
        if user_profile.template.should_send_message and sent_profile_message is None:
            return
        send_profile_message_id = None
        send_profile_channel_id = None
        if sent_profile_message:
            send_profile_message_id = sent_profile_message.id
            send_profile_channel_id = sent_profile_message.channel.id

        # Database me up daddy
        async with self.bot.database() as db:
            await db(
                """INSERT INTO created_profile (user_id, name, template_id, verified, posted_message_id, posted_channel_id)
                VALUES ($1, $2, $3, $4, $5, $6) ON CONFLICT (user_id, name, template_id)
                DO UPDATE SET verified=excluded.verified, posted_message_id=excluded.posted_message_id,
                posted_channel_id=excluded.posted_channel_id""",
                user_profile.user_id, user_profile.name, user_profile.template.template_id, user_profile.verified,
                send_profile_message_id, send_profile_channel_id,
            )
            for field in user_profile.all_filled_fields.values():
                await db(
                    """INSERT INTO filled_field (user_id, name, field_id, value) VALUES ($1, $2, $3, $4)
                    ON CONFLICT (user_id, name, field_id) DO UPDATE SET value=excluded.value""",
                    field.user_id, user_profile.name, field.field_id, field.value
                )

        # Respond to user
        await ctx.author.send("Your profile has been edited and saved.")

    @utils.command(hidden=True)
    @commands.bot_has_permissions(send_messages=True)
    @commands.guild_only()
    @utils.checks.meta_command()
    async def delete_profile_meta(
            self, ctx: utils.Context, user: typing.Optional[discord.Member], *, profile_name: str = None):
        """
        Handles deleting a profile.
        """

        # You can only delete someone else's profile if you're a moderator
        if user and ctx.author != user and not localutils.checks.member_is_moderator(self.bot, ctx.author):
            raise commands.MissingPermissions(["manage_roles"])

        # Check it exists
        template: localutils.Template = ctx.template
        async with self.bot.database() as db:
            try:
                user_profile = await template.fetch_profile_for_user(db, (user or ctx.author).id, profile_name, fetch_filled_fields=False)
            except ValueError:
                user_profiles: typing.List[localutils.UserProfile] = await template.fetch_all_profiles_for_user(db, (user or ctx.author).id)
                profile_names_string = [f'"{o}"' for o in [i.name.replace('*', '\\*').replace('`', '\\`').replace('_', '\\_') for i in user_profiles]]
                if user:
                    await ctx.send(f"{user.mention} has multiple profiles set for the template **{template.name}** - {', '.join(profile_names_string)}.")
                else:
                    await ctx.send(f"You have multiple profiles set for the template **{template.name}** - {', '.join(profile_names_string)}.")
                return
        if user_profile is None:
            if profile_name:
                if user:
                    await ctx.send(
                        f"{user.mention} doesn't have a profile for **{template.name}** with the name **{profile_name}**.",
                        allowed_mentions=discord.AllowedMentions(users=False),
                    )
                else:
                    await ctx.send(f"You don't have a profile for **{template.name}** with the name **{profile_name}**.")
            else:
                if user:
                    await ctx.send(
                        f"{user.mention} doesn't have a profile for **{template.name}**.",
                        allowed_mentions=discord.AllowedMentions(users=False),
                    )
                else:
                    await ctx.send(f"You don't have a profile for **{template.name}**.")
            return

        # Delete the currently archived message, should one exist
        current_profile_message = await user_profile.fetch_message(self.bot)
        if current_profile_message:
            try:
                await current_profile_message.delete()
            except discord.HTTPException:
                pass

        # Remove it from the database
        user = user or ctx.author
        async with self.bot.database() as db:
            await db("DELETE FROM created_profile WHERE user_id=$1 AND template_id=$2 AND name=$3", user.id, template.template_id, user_profile.name)
        await ctx.send("This profile has been deleted.")

    @utils.command(hidden=True)
    @commands.bot_has_permissions(send_messages=True, embed_links=True)
    @commands.guild_only()
    @utils.checks.meta_command()
    async def get_profile_meta(
            self, ctx: utils.Context, user: typing.Optional[discord.Member], *, profile_name: str = None):
        """
        Gets a profile for a given member.
        """

        # See if there's a set profile
        template: localutils.Template = ctx.template
        async with self.bot.database() as db:
            try:
                user_profile: localutils.UserProfile = await template.fetch_profile_for_user(db, (user or ctx.author).id, profile_name)
            except ValueError:
                user_profiles: typing.List[localutils.UserProfile] = await template.fetch_all_profiles_for_user(db, (user or ctx.author).id)
                profile_names_string = [f'"{o}"' for o in [i.name.replace('*', '\\*').replace('`', '\\`').replace('_', '\\_') for i in user_profiles]]
                if user:
                    await ctx.send(f"{user.mention} has multiple profiles set for the template **{template.name}** - {', '.join(profile_names_string)}.")
                else:
                    await ctx.send(f"You have multiple profiles set for the template **{template.name}** - {', '.join(profile_names_string)}.")
                return
        if user_profile is None:
            if profile_name:
                if user:
                    await ctx.send(
                        f"{user.mention} doesn't have a profile for **{template.name}** with the name **{profile_name}**.",
                        allowed_mentions=discord.AllowedMentions(users=False),
                    )
                else:
                    await ctx.send(f"You don't have a profile for **{template.name}** with the name **{profile_name}**.")
            else:
                if user:
                    await ctx.send(
                        f"{user.mention} doesn't have a profile for **{template.name}**.",
                        allowed_mentions=discord.AllowedMentions(users=False),
                    )
                else:
                    await ctx.send(f"You don't have a profile for **{template.name}**.")
            return

        # See if verified
        if user_profile.verified or localutils.checks.member_is_moderator(ctx.bot, ctx.author):
            return await ctx.send(embed=user_profile.build_embed(self.bot, user or ctx.author))

        # Not verified
        if user:
            await ctx.send(
                f"{user.mention}'s profile hasn't been verified yet, and thus can't be sent.",
                allowed_mentions=discord.AllowedMentions(users=False),
            )
        else:
            await ctx.send("Your profile hasn't been verified yet, and thus can't be sent.")
        return


def setup(bot: utils.Bot):
    x = ProfileCreation(bot)
    bot.add_cog(x)
