from typing import Any, cast

import discord
from discord.ext import commands, vbu

from cogs import utils


class BotSupport(vbu.Cog):

    @commands.group(
        application_command_meta=commands.ApplicationCommandMeta(
            guild_ids=[
                vbu.Constants.SUPPORT_GUILD_ID,
            ],
            permissions=discord.Permissions(
                manage_guild=True,
            ),
        ),
    )
    async def anyprofile(
            self, ctx: vbu.SlashContext):
        """
        The bot support manage for other profiles.
        """

        ...

    @anyprofile.command(
        name="get",
        application_command_meta=commands.ApplicationCommandMeta(
            options=[
                discord.ApplicationCommandOption(
                    name="id",
                    description="The ID of the profile you want to see.",
                    type=discord.ApplicationCommandOptionType.string,
                    required=True
                )
            ],
            guild_ids=[
                vbu.Constants.SUPPORT_GUILD_ID,
            ],
            permissions=discord.Permissions(
                manage_guild=True,
            ),
        ),
    )
    async def anyprofile_get(
            self,
            ctx: vbu.SlashContext,
            id: str):
        """
        Get any profile by its ID.
        """

        # Get the profile
        async with vbu.Database() as db:
            profile = await utils.UserProfile.fetch_profile_by_id(db, id)
            if profile is None:
                return await ctx.interaction.response.send_message(
                    "That profile doesn't exist.",
                )
            template = await profile.fetch_template(db, allow_deleted=True)
            if template is None:
                return await ctx.interaction.response.send_message(
                    "That profile doesn't have a template.",
                )
            await template.fetch_fields(db)
            await profile.fetch_filled_fields(db)
            profile = cast(utils.UserProfile[utils.Template], profile)

        # Get the guild and user associated
        try:
            guild = (
                self.bot.get_guild(profile.template.guild_id)
                or await self.bot.fetch_guild(profile.template.guild_id)
            )
        except discord.NotFound:
            return await ctx.interaction.response.send_message(
                "That profile's guild doesn't exist.",
            )
        try:
            member = (
                guild.get_member(profile.user_id)
                or await guild.fetch_member(profile.user_id)
            )
        except discord.NotFound:
            return await ctx.interaction.response.send_message(
                "That profile's user doesn't exist.",
            )

        # Build and send the embed
        embed = profile.build_embed(
            self.bot,
            ctx,
            member,
        )
        kwargs: dict[str, Any] = {
            "content": f"Profile for {member} ({profile.user_id})\n\n",
            "embeds": [embed],
        }
        if template.deleted:
            kwargs["content"] += (
                "**The template associated with this profile is deleted.**\n"
            )
        if profile.deleted:
            kwargs["content"] += (
                "**This profile is deleted.**\n"
            )
        await ctx.interaction.response.send_message(**kwargs)

    @commands.group(
        application_command_meta=commands.ApplicationCommandMeta(
            guild_ids=[
                vbu.Constants.SUPPORT_GUILD_ID,
            ],
            permissions=discord.Permissions(
                manage_guild=True,
            ),
        ),
    )
    async def anytemplate(
            self, ctx: vbu.SlashContext):
        """
        The bot support manage for other templates.
        """

        ...

    @anytemplate.command(
        name="edit",
        application_command_meta=commands.ApplicationCommandMeta(
            options=[
                discord.ApplicationCommandOption(
                    name="id",
                    description="The ID of the template you want to edit.",
                    type=discord.ApplicationCommandOptionType.string,
                    required=True
                )
            ],
            guild_ids=[
                vbu.Constants.SUPPORT_GUILD_ID,
            ],
            permissions=discord.Permissions(
                manage_guild=True,
            ),
        ),
    )
    async def anytemplate_edit(
            self,
            ctx: vbu.SlashContext,
            id: str):
        """
        Edit any profile by its ID.
        """

        await self.bot.get_cog("TemplateCommands").template_edit(ctx, id)


def setup(bot: vbu.Bot):
    x = BotSupport(bot)
    bot.add_cog(x)

