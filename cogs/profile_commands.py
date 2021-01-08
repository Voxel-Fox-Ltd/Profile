import asyncio
import re
import typing
import uuid
import collections
import string

import discord
from discord.ext import commands
import voxelbotutils as utils

from cogs import utils as localutils


class ProfileCreation(utils.Cog):

    TICK_EMOJI = "<:tick_yes:596096897995899097>"
    CROSS_EMOJI = "<:cross_no:596096897769275402>"

    COMMAND_REGEX = re.compile(
        r"^(?P<command>set|get|delete|edit)(?P<template>\S{1,30})( .*)?$",
        re.IGNORECASE
    )

    def __init__(self, bot:utils.Bot):
        super().__init__(bot)
        self.set_profile_locks: typing.Dict[int, asyncio.Lock] = collections.defaultdict(asyncio.Lock)

    @utils.Cog.listener()
    async def on_command_error(self, ctx:utils.Context, error:commands.CommandError):
        """
        CommandNotFound handler so the bot can search for that custom command.
        """

        # Handle commandnotfound which is really just handling the set/get/delete/etc commands
        if not isinstance(error, commands.CommandNotFound):
            return

        # Get the command and used template
        matches = self.COMMAND_REGEX.search(ctx.message.content[len(ctx.prefix):])
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

    @utils.command(hidden=True)
    @commands.bot_has_permissions(send_messages=True)
    @commands.guild_only()
    @utils.checks.meta_command()
    async def set_profile_meta(self, ctx:utils.Context, target_user:typing.Optional[discord.Member]):
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
        if template.max_profile_count == 0:
            await ctx.send(f"Currently the template **{template.name}** is not accepting any more applications.")
            return
        if len(user_profiles) >= template.max_profile_count:
            if target_user == ctx.author:
                await ctx.send(f"You're already at the maximum number of profiles set for **{template.name}**.")
            else:
                await ctx.send(f"{target_user.mention} is already at the maximum number of profiles set up for **{template.name}**.")
            return

        # See if you we can send them the PM
        try:
            if target_user == ctx.author:
                await ctx.author.send(f"Now talking you through setting up your **{template.name}** profile.")
            else:
                await ctx.author.send(f"Now talking you through setting up {target_user.mention}'s **{template.name}** profile.", allowed_mentions=discord.AllowedMentions(users=False))
            await ctx.send("Sent you a DM!")
        except discord.Forbidden:
            return await ctx.send("I'm unable to send you DMs to set up the profile :/")

        # Drag the user into the create profile lock
        async with self.set_profile_locks[ctx.author.id]:

            # See if we need to ask for a name
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
            else:
                await ctx.author.send(f"What name would you like to give this profile? This will be used to get the profile information (eg for the name \"test\", you could run `get{template.name.lower()} test`).")
                while True:
                    try:
                        user_message = await self.bot.wait_for(
                            "message", timeout=120,
                            check=lambda m: m.author == ctx.author and isinstance(m.channel, discord.DMChannel)
                        )
                    except asyncio.TimeoutError:
                        try:
                            return await ctx.author.send(f"Your input for this field has timed out. Please try running `set{template.name}` on your server again.")
                        except discord.Forbidden:
                            return
                    try:

                        # Get the name they gave
                        name_content = localutils.TextField.get_from_message(user_message)

                        # They've misunderstood
                        if f"get{template.name.lower()} " in name_content.lower():
                            raise localutils.errors.FieldCheckFailure(f"Please provide the name for your profile _without_ the command call, eg if you wanted to run `get{template.name.lower()} test`, just say \"test\".")

                        # See if they're already using the name
                        if name_content.lower() in [i.name.lower() for i in user_profiles]:
                            raise localutils.errors.FieldCheckFailure("You're already using that name for this template. Please provide an alternative.")

                        # See if the characters used are invalid
                        if any([i for i in name_content if i not in string.ascii_letters + string.digits + ' ']):
                            raise localutils.errors.FieldCheckFailure("You can only use standard lettering and digits in your profile name. Please provide an alternative.")
                        break

                    except localutils.errors.FieldCheckFailure as e:
                        await ctx.author.send(e.message)

            # Talk the user through each field
            filled_field_dict = {}
            for field in sorted(template.fields.values(), key=lambda x: x.index):

                # See if it's a command
                if localutils.CommandProcessor.COMMAND_REGEX.search(field.prompt):
                    filled_field_dict[field.field_id] = localutils.FilledField(
                        user_id=target_user.id,
                        name=name_content,
                        field_id=field.field_id,
                        value="Could not get field information",
                        field=field,
                    )
                    continue

                # Send the user the prompt
                if field.optional:
                    await ctx.author.send(f"{field.prompt.rstrip('.')}. Type **pass** to skip this field.")
                else:
                    await ctx.author.send(field.prompt)

                # Get user input
                while True:
                    try:
                        user_message = await self.bot.wait_for(
                            "message", timeout=field.timeout,
                            check=lambda m: m.author == ctx.author and isinstance(m.channel, discord.DMChannel)
                        )
                    except asyncio.TimeoutError:
                        try:
                            return await ctx.author.send(f"Your input for this field has timed out. Running `set{template.name}` on your server again to go back through this setup.")
                        except discord.Forbidden:
                            return
                    try:
                        if user_message.content.lower() == 'pass' and field.optional:
                            field_content = None
                        else:
                            field_content = field.field_type.get_from_message(user_message)
                        break
                    except localutils.errors.FieldCheckFailure as e:
                        await ctx.author.send(e.message)

                # Add field to list
                filled_field_dict[field.field_id] = localutils.FilledField(
                    user_id=target_user.id,
                    name=name_content,
                    field_id=field.field_id,
                    value=field_content,
                    field=field,
                )

        # Make the UserProfile object
        user_profile = localutils.UserProfile(
            user_id=target_user.id,
            name=name_content,
            template_id=template.template_id,
            verified=template.verification_channel_id is None
        )
        user_profile.template = template
        user_profile.all_filled_fields = filled_field_dict

        # Make sure the bot can send the embed at all
        try:
            await ctx.author.send(embed=user_profile.build_embed(target_user))
        except discord.HTTPException as e:
            return await ctx.author.send(f"Your profile couldn't be sent to you - `{e}`.\nPlease try again later.")

        # Delete the currently archived message, should one exist
        current_profile_message = await user_profile.fetch_message(self.bot)
        if current_profile_message:
            try:
                await current_profile_message.delete()
            except discord.HTTPException:
                pass

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
            await db(
                """INSERT INTO created_profile (user_id, name, template_id, verified, posted_message_id, posted_channel_id)
                VALUES ($1, $2, $3, $4, $5, $6) ON CONFLICT (user_id, name, template_id)
                DO UPDATE SET verified=excluded.verified, posted_message_id=excluded.posted_message_id, posted_channel_id=excluded.posted_channel_id""",
                user_profile.user_id, user_profile.name, user_profile.template.template_id, user_profile.verified,
                send_profile_message_id, send_profile_channel_id
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
    async def edit_profile_meta(self, ctx:utils.Context, target_user:typing.Optional[discord.Member], *, profile_name:str=None):
        """
        Talks a user through setting up a profile on a given server.
        """

        # Set up some variables
        target_user = target_user or ctx.author
        template = ctx.template

        # See if they're allowed to edit their profile
        if template.max_profile_count == 0:
            await ctx.send(f"Currently the template **{template.name}** is not accepting any more applications, and you can't edit profiles while that's disabled.")
            return

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
                user_profiles: typing.List[localutils.UserProfile] = await template.fetch_all_profiles_for_user(db, target_user.id, fetch_filled_fields=False)
            except ValueError:
                user_profiles: typing.List[localutils.UserProfile] = await template.fetch_all_profiles_for_user(db, target_user.id)
                profile_names_string = [f'"{o}"' for o in [i.name.replace('*', '\\*').replace('`', '\\`').replace('_', '\\_') for i in user_profiles]]
                if target_user == ctx.author:
                    await ctx.send(f"You have multiple profiles set for the template **{template.name}** - {', '.join(profile_names_string)}.")
                else:
                    await ctx.send(f"{target_user.mention} has multiple profiles set for the template **{template.name}** - {', '.join(profile_names_string)}.")
                return

        # Check if they already have a profile set
        if user_profile is None:
            if profile_name:
                if target_user == ctx.author:
                    await ctx.send(f"You don't have a profile for **{template.name}** with the name **{profile_name}**.")
                else:
                    await ctx.send(f"{target_user.mention} doesn't have a profile for **{template.name}** with the name **{profile_name}**.", allowed_mentions=discord.AllowedMentions(users=False))
            else:
                if target_user == ctx.author:
                    await ctx.send(f"You don't have a profile for **{template.name}**.")
                else:
                    await ctx.send(f"{target_user.mention} doesn't have a profile for **{template.name}**.", allowed_mentions=discord.AllowedMentions(users=False))
            return

        # See if you we can send them the PM
        try:
            if target_user == ctx.author:
                await ctx.author.send(f"Now talking you through editing your **{template.name}** profile.")
            else:
                await ctx.author.send(f"Now talking you through editing {target_user.mention}'s **{template.name}** profile.", allowed_mentions=discord.AllowedMentions(users=False))
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
                    await ctx.author.send(f"{field.prompt.rstrip('.')}. The current value for this field is `{current_value or 'empty'}`. Type **pass** to leave the value as it currently is.")

                # Get user input
                while True:
                    try:
                        user_message = await self.bot.wait_for(
                            "message", timeout=field.timeout,
                            check=lambda m: m.author == ctx.author and isinstance(m.channel, discord.DMChannel)
                        )
                    except asyncio.TimeoutError:
                        try:
                            return await ctx.author.send(f"Your input for this field has timed out. Please try running `set{template.name}` on your server again.")
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
            await ctx.author.send(embed=user_profile.build_embed(target_user))
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
                DO UPDATE SET verified=excluded.verified, posted_message_id=excluded.posted_message_id, posted_channel_id=excluded.posted_channel_id""",
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
    async def delete_profile_meta(self, ctx:utils.Context, user:typing.Optional[discord.Member], *, profile_name:str=None):
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
                    await ctx.send(f"{user.mention} doesn't have a profile for **{template.name}** with the name **{profile_name}**.", allowed_mentions=discord.AllowedMentions(users=False))
                else:
                    await ctx.send(f"You don't have a profile for **{template.name}** with the name **{profile_name}**.")
            else:
                if user:
                    await ctx.send(f"{user.mention} doesn't have a profile for **{template.name}**.", allowed_mentions=discord.AllowedMentions(users=False))
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
    async def get_profile_meta(self, ctx:utils.Context, user:typing.Optional[discord.Member], *, profile_name:str=None):
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
                    await ctx.send(f"{user.mention} doesn't have a profile for **{template.name}** with the name **{profile_name}**.", allowed_mentions=discord.AllowedMentions(users=False))
                else:
                    await ctx.send(f"You don't have a profile for **{template.name}** with the name **{profile_name}**.")
            else:
                if user:
                    await ctx.send(f"{user.mention} doesn't have a profile for **{template.name}**.", allowed_mentions=discord.AllowedMentions(users=False))
                else:
                    await ctx.send(f"You don't have a profile for **{template.name}**.")
            return

        # See if verified
        if user_profile.verified or localutils.checks.member_is_moderator(ctx.bot, ctx.author):
            return await ctx.send(embed=user_profile.build_embed(user or ctx.author))

        # Not verified
        if user:
            await ctx.send(f"{user.mention}'s profile hasn't been verified yet, and thus can't be sent.", allowed_mentions=discord.AllowedMentions(users=False))
        else:
            await ctx.send("Your profile hasn't been verified yet, and thus can't be sent.")
        return

    @utils.command(hidden=True)
    @commands.is_owner()
    @commands.bot_has_permissions(send_messages=True, embed_links=True)
    async def forcegetprofile(self, ctx:utils.Context, template:localutils.Template, user:utils.converters.UserID, name:str='default'):
        """
        Get the profile of a user.
        """

        async with self.bot.database() as db:
            profile: localutils.UserProfile = await template.fetch_profile_for_user(db, user, name, fetch_filled_fields=True)
        if not profile:
            return await ctx.send("No profile found.")
        guild = self.bot.get_guild(template.guild_id) or await self.bot.fetch_guild(template.guild_id)
        member = guild.get_member(user) or await guild.fetch_member(user)
        return await ctx.send(embed=profile.build_embed(member))


def setup(bot:utils.Bot):
    x = ProfileCreation(bot)
    bot.add_cog(x)
