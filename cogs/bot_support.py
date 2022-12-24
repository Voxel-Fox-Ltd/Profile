from typing import cast

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
            template = await profile.fetch_template(db)
            if template is None:
                return await ctx.interaction.response.send_message(
                    "That profile doesn't have a template.",
                )
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
        await ctx.interaction.response.send_message(
            embeds=[embed],
        )


def setup(bot: vbu.Bot):
    x = BotSupport(bot)
    bot.add_cog(x)

