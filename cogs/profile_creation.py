import asyncio
import re

import discord
from discord.ext import commands
import asyncpg

from cogs import utils


class ProfileCreation(utils.Cog):

    TICK_EMOJI = "<:tickYes:596096897995899097>"
    CROSS_EMOJI = "<:crossNo:596096897769275402>"
    COMMAND_REGEX = re.compile(r"(set|get|delete|edit)(\S{1,30})( .*)?", re.IGNORECASE)

    @utils.Cog.listener()
    async def on_command_error(self, ctx:utils.Context, error:commands.CommandError):
        """CommandNotFound handler so the bot can search for that custom command"""

        # Handle commandnotfound which is really just handling the set/get/delete/etc commands
        if not isinstance(error, commands.CommandNotFound):
            return

        # Get the command and used profile
        matches = self.COMMAND_REGEX.search(ctx.message.content)
        if not matches:
            return
        command_operator = matches.group(1)  # get/get/delete/edit
        profile_name = matches.group(2)  # profile name

        # Filter out DMs
        if isinstance(ctx.channel, discord.DMChannel):
            return  # Fail silently on DM invocation

        # Find the profile they asked for on their server
        guild_commands = utils.Profile.all_guilds[ctx.guild.id]
        profile = guild_commands.get(profile_name)
        if not profile:
            return  # Fail silently on profile doesn't exist

        # Invoke command
        metacommand: utils.Command = self.bot.get_command(f'{command_operator.lower()}_profile_meta')
        ctx.command = metacommand
        ctx.profile = profile
        ctx.invoke_meta = True
        try:
            await metacommand.invoke(ctx)  # This converts the args for me, which is nice
        except commands.CommandError as e:
            self.bot.dispatch("command_error", ctx, e)  # Throw any errors we get in this command into its own error handler

    @commands.command(cls=utils.Command, hidden=True)
    @utils.checks.meta_command()
    @commands.guild_only()
    async def set_profile_meta(self, ctx:utils.Context, target_user:discord.Member=None):
        """Talks a user through setting up a profile on a given server"""

        # Set up some variables
        user = ctx.author
        target_user = target_user or user
        profile = ctx.profile
        fields = profile.fields

        # Only mods can see other people's profiles
        if target_user != ctx.author and not utils.checks.member_is_moderator(ctx.bot, ctx.author):
            return await ctx.send(f"You're missing the `manage_roles` permission required to do this.")

        # Check if they already have a profile set
        user_profile: utils.UserProfile = profile.get_profile_for_member(target_user)
        if user_profile is not None:
            if target_user == user:
                await ctx.send(f"You already have a profile set for `{profile.name}`.")
            else:
                await ctx.send(f"{target_user.mention} already has a profile set up for `{profile.name}`.")
            return

        # See if you we can send them the PM
        try:
            if target_user == user:
                await user.send(f"Now talking you through setting up a `{profile.name}` profile.")
            else:
                await user.send(f"Now talking you through setting up a `{profile.name}` profile for {target_user.mention}.")
            await ctx.send("Sent you a DM!")
        except discord.Forbidden:
            return await ctx.send("I'm unable to send you DMs to set up the profile :/")

        # Talk the user through each field
        filled_field_list = []
        for field in fields:

            # Send the user the prompt
            await user.send(field.prompt)

            # Get user input
            while True:
                try:
                    user_message = await self.bot.wait_for(
                        "message", timeout=field.timeout,
                        check=lambda m: m.author == user and isinstance(m.channel, discord.DMChannel)
                    )
                except asyncio.TimeoutError:
                    return await user.send(f"Your input for this field has timed out. Please try running `set{profile.name}` on your server again.")
                try:
                    field_content = field.field_type.get_from_message(user_message)
                    break
                except utils.FieldCheckFailure as e:
                    await user.send(e.message)

            # Add field to list
            filled_field = utils.FilledField(target_user.id, field.field_id, field_content)
            filled_field_list.append(filled_field)

        # Make the UserProfile object
        user_profile = utils.UserProfile(
            user_id=target_user.id,
            profile_id=profile.profile_id,
            verified=profile.verification_channel_id is None
        )

        # Make sure the bot can send the embed at all
        try:
            await user.send(embed=user_profile.build_embed())
        except discord.HTTPException as e:
            return await user.send(f"Your profile couldn't be sent to you, so the embed was probably hecked - `{e}`.\nPlease try again later.")

        # Make sure the bot can send the embed to the channel
        if profile.verification_channel_id:
            try:
                channel = await self.bot.fetch_channel(profile.verification_channel_id)
                embed = user_profile.build_embed()
                embed.set_footer(text=f'{profile.name.upper()} // Verification Check')
                v = await channel.send(f"New **{profile.name}** submission from {target_user.mention}\n{target_user.id}/{profile.profile_id}", embed=embed)
                await v.add_reaction(self.TICK_EMOJI)
                await v.add_reaction(self.CROSS_EMOJI)
            except discord.HTTPException as e:
                return await user.send(f"Your profile couldn't be send to the verification channel? - `{e}`.")
            except AttributeError:
                return await user.send(f"I don't think the verification channel exists - please tell an admin.")

        # Database me up daddy
        async with self.bot.database() as db:
            try:
                await db('INSERT INTO created_profile (user_id, profile_id, verified) VALUES ($1, $2, $3)', user_profile.user_id, user_profile.profile.profile_id, user_profile.verified)
            except asyncpg.UniqueViolationError:
                await db('UPDATE created_profile SET verified=$3 WHERE user_id=$1 AND profile_id=$2', user_profile.user_id, user_profile.profile.profile_id, user_profile.verified)
                await db('DELETE FROM filled_field WHERE user_id=$1 AND field_id in (SELECT field_id FROM field WHERE profile_id=$2)', user_profile.user_id, user_profile.profile.profile_id)
                self.logger.info(f"Deleted profile for {user_profile.user_id} on UniqueViolationError")
            for field in filled_field_list:
                await db('INSERT INTO filled_field (user_id, field_id, value) VALUES ($1, $2, $3)', field.user_id, field.field_id, field.value)

        # Respond to user
        await user.send("Your profile has been created and saved.")

    @commands.command(cls=utils.Command, hidden=True)
    @utils.checks.meta_command()
    @commands.guild_only()
    async def edit_profile_meta(self, ctx:utils.Context, target_user:discord.Member=None):
        """Talks a user through setting up a profile on a given server"""

        # Set up some variables
        user = ctx.author
        target_user = target_user or user
        profile = ctx.profile

        # You can only edit someone else's profile if you're a moderator
        if target_user != ctx.author and not utils.checks.member_is_moderator(ctx.bot, ctx.author):
            return await ctx.send(f"You're missing the `manage_roles` permission required to do this.")

        # Check if they already have a profile set
        user_profile = profile.get_profile_for_member(target_user)
        if user_profile is None:
            if target_user == user:
                await ctx.send(f"You have no profile set for `{profile.name}`.")
            else:
                await ctx.send(f"{target_user.mention} has no profile set up for `{profile.name}`.")
            return

        # See if you we can send them the PM
        try:
            if target_user == user:
                await user.send(f"Now talking you through editing a `{profile.name}` profile.")
            else:
                await user.send(f"Now talking you through editing a `{profile.name}` profile for {target_user.mention}.")
            await ctx.send("Sent you a PM!")
        except Exception:
            return await ctx.send("I'm unable to send you PMs to set up the profile :/")

        # Talk the user through each field
        filled_field_list = []
        for field, current in zip(profile.fields, user_profile.filled_fields):

            # Send the user the prompt
            await user.send(field.prompt + f"\nThe current value for this field is `{current.value}`. Type **pass** to leave the value as it currently is.")

            # Get user input
            while True:
                try:
                    user_message = await self.bot.wait_for(
                        "message", timeout=field.timeout,
                        check=lambda m: m.author == user and isinstance(m.channel, discord.DMChannel)
                    )
                except asyncio.TimeoutError:
                    return await user.send(f"Your input for this field has timed out. Please try running `set{profile.name}` on your server again.")
                if user_message.content.lower() == "pass":
                    field_content = current.value
                    break
                try:
                    field_content = field.field_type.get_from_message(user_message)
                    break
                except utils.FieldCheckFailure as e:
                    await user.send(e.message)

            # Add field to list
            filled_field_list.append(utils.FilledField(target_user.id, field.field_id, field_content))

        # Make the UserProfile object
        user_profile.verified = profile.verification_channel_id is None

        # Make sure the bot can send the embed at all
        try:
            await user.send(embed=user_profile.build_embed())
        except discord.HTTPException as e:
            return await user.send(f"Your profile couldn't be sent to you, so the embed was probably hecked - `{e}`.\nPlease try again later.")

        # Make sure the bot can send the embed to the channel
        if profile.verification_channel_id:
            try:
                channel = await self.bot.fetch_channel(profile.verification_channel_id)
                embed = user_profile.build_embed()
                embed.set_footer(text=f'{profile.name.upper()} // Verification Check')
                v = await channel.send(f"Edited **{profile.name}** submission from {target_user.mention}\n{target_user.id}/{profile.profile_id}", embed=embed)
                await v.add_reaction(self.TICK_EMOJI)
                await v.add_reaction(self.CROSS_EMOJI)
            except discord.HTTPException as e:
                return await user.send(f"Your profile couldn't be send to the verification channel? - `{e}`.")
            except AttributeError:
                return await user.send(f"I don't think the verification channel exists - please tell an admin.")

        # Database me up daddy
        async with self.bot.database() as db:
            await db('UPDATE created_profile SET verified=$3 WHERE user_id=$1 AND profile_id=$2', user_profile.user_id, user_profile.profile.profile_id, user_profile.verified)
            # await db('DELETE FROM filled_field WHERE user_id=$1 AND field_id in (SELECT field_id FROM field WHERE profile_id=$2)', user_profile.user_id, user_profile.profile.profile_id)
            for field in filled_field_list:
                # await db('INSERT INTO filled_field (user_id, field_id, value) VALUES ($1, $2, $3)', field.user_id, field.field_id, field.value)
                await db('UPDATE filled_field SET value=$3 WHERE user_id=$1 AND field_id=$2', field.user_id, field.field_id, field.value)

        # Respond to user
        await user.send("Your profile has been edited and saved.")

    @commands.command(cls=utils.Command, hidden=True)
    @utils.checks.meta_command()
    @commands.guild_only()
    async def delete_profile_meta(self, ctx:utils.Context, target_user:discord.Member=None):
        """Handles deleting a profile"""

        # You can only delete someone else's profile if you're a moderator
        if ctx.author != target_user and not utils.checks.member_is_moderator(self.bot, ctx.author):
            return await ctx.send(f"You're missing the `manage_roles` permission required to do this.")

        # Check it exists
        profile = ctx.profile
        if profile.get_profile_for_member(target_user or ctx.author) is None:
            if target_user:
                await ctx.send(f"{target_user.mention} doesn't have a profile set for `{profile.name}`.")
            else:
                await ctx.send(f"You don't have a profile set for `{profile.name}`.")
            return

        # Database it babey
        target_user = target_user or ctx.author
        async with self.bot.database() as db:
            await db('DELETE FROM filled_field WHERE user_id=$1 AND field_id in (SELECT field_id FROM field WHERE profile_id=$2)', target_user.id, profile.profile_id)
            await db('DELETE FROM created_profile WHERE user_id=$1 AND profile_id=$2', target_user.id, profile.profile_id)
        del utils.UserProfile.all_profiles[(target_user.id, ctx.guild.id, profile.name)]
        await ctx.send("This profile has been deleted.")

    @commands.command(cls=utils.Command, hidden=True)
    @utils.checks.meta_command()
    @commands.guild_only()
    async def get_profile_meta(self, ctx:utils.Context, target_user:discord.Member=None):
        """Gets a profile for a given member"""

        # See if there's a set profile
        profile = ctx.profile
        user_profile = profile.get_profile_for_member(target_user or ctx.author)
        if user_profile is None:
            if target_user:
                await ctx.send(f"{target_user.mention} doesn't have a profile for `{profile.name}`.")
            else:
                await ctx.send(f"You don't have a profile for `{profile.name}`.")
            return

        # See if verified
        if user_profile.verified or utils.checks.member_is_moderator(ctx.bot, ctx.author):
            return await ctx.send(embed=user_profile.build_embed())

        # Not verified
        if target_user:
            await ctx.send(f"{target_user.mention}'s profile hasn't been verified yet, and thus can't be sent.")
        else:
            await ctx.send(f"Your profile hasn't been verified yet, and thus can't be sent.")
        return


def setup(bot:utils.Bot):
    x = ProfileCreation(bot)
    bot.add_cog(x)
