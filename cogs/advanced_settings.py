import discord
from discord.ext import commands, vbu


def _t(b: str | discord.Locale, a: str) -> str:
    """
    Translate function for non-commands.
    """

    return vbu.translation(b, "profile").gettext(a)


if __debug__:
    # For POEditor
    _poeditor = lambda x: x

    # TRANSLATORS: Command name.
    _poeditor("advanced")
    # TRANSLATORS: Command description.
    _poeditor("The group command for advanced settings.")

    # TRANSLATORS: Command name.
    _poeditor("enable")
    # TRANSLATORS: Command description.
    _poeditor("Enable advanced mode for this guild.")

    # TRANSLATORS: Command name.
    _poeditor("disable")
    # TRANSLATORS: Command description.
    _poeditor("Disable advanced mode for this guild.")


class AdvancedSettings(vbu.Cog[vbu.Bot]):

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
            permissions=discord.Permissions(manage_guild=True),
            name_localizations={
                i: _t(i, "advanced").casefold()
                for i in discord.Locale
            },
            description_localizations={
                i: _t(i, "The group command for advanced settings.")
                for i in discord.Locale
            },
        ),
    )
    async def advanced(self, _):
        """
        The group command for advanced settings.
        """

        ...

    @advanced.command(
        application_command_meta=commands.ApplicationCommandMeta(
            guild_only=True,
            permissions=discord.Permissions(manage_guild=True),
            name_localizations={
                i: _t(i, "enable").casefold()
                for i in discord.Locale
            },
            description_localizations={
                i: _t(i, "Enable advanced mode for this guild.")
                for i in discord.Locale
            },
        ),
    )
    @vbu.i18n("profile")
    async def enable(self, ctx: vbu.SlashContext):
        """
        Enable advanced mode for this guild.
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
        application_command_meta=commands.ApplicationCommandMeta(
            guild_only=True,
            permissions=discord.Permissions(manage_guild=True),
            name_localizations={
                i: _t(i, "disable").casefold()
                for i in discord.Locale
            },
            description_localizations={
                i: _t(i, "Disable advanced mode for this guild.")
                for i in discord.Locale
            },
        ),
    )
    @vbu.i18n("profile")
    async def disable(self, ctx: vbu.SlashContext):
        """
        Disable advanced mode for this guild.
        """

        await self.set_advanced(ctx.guild.id, False)
        await ctx.interaction.response.send_message(
            _("Advanced settings have been disabled for your guild."),
            ephemeral=True,
        )


def setup(bot: vbu.Bot):
    x = AdvancedSettings(bot)
    bot.add_cog(x)
