import discord
from discord.ext import commands, vbu


class BotSettings(vbu.Cog[vbu.Bot]):

    @classmethod
    async def set_advanced(cls, guild_id: int, enabled: bool) -> None:
        """
        Set advanced mode for the given guild in the database.
        """

        async with vbu.Database() as db:
            await db(
                """
                INSERT INTO
                    guild_settings
                    (
                        guild_id,
                        advanced
                    )
                VALUES
                    (
                        $1,
                        $2
                    )
                ON CONFLICT
                    (guild_id)
                DO UPDATE
                SET
                    advanced = $2
                """,
                guild_id, enabled
            )

    @commands.group(
        application_command_meta=commands.ApplicationCommandMeta(
            guild_only=True,
            permissions=discord.Permissions(manage_guild=True)
        ),
    )
    async def advanced(self, _):
        """
        The group command for advanced settings.
        """

        ...

    @advanced.command(
        application_command_meta=commands.ApplicationCommandMeta()
    )
    @vbu.i18n("profile")
    async def enable(self, ctx: vbu.SlashContext):
        """
        Enable advanced settings.
        """

        await self.set_advanced(ctx.guild.id, True)
        await ctx.interaction.response.send_message(
            _(
                "Advanced settings have been enabled for your guild. This "
                "means that the character limits for field prompts have been "
                "disabled in modals, allowing you to input commands and use "
                "multi-fields in your templates.\n"
                "The character limits still apply, however, and any prompts "
                "that _aren't_ multi-field prompts or commands will be "
                "truncated without warning."
            ),
            ephemeral=True,
        )

    @advanced.command(
        application_command_meta=commands.ApplicationCommandMeta()
    )
    @vbu.i18n("profile")
    async def disable(self, ctx: vbu.SlashContext):
        """
        Disable advanced settings.
        """

        await self.set_advanced(ctx.guild.id, False)
        await ctx.interaction.response.send_message(
            _("Advanced settings have been disabled for your guild."),
            ephemeral=True,
        )


def setup(bot: vbu.Bot):
    x = BotSettings(bot)
    bot.add_cog(x)
