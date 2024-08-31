import discord
from discord.ext import commands, vbu

from cogs import utils


def _t(b: str | discord.Locale, a: str) -> str:
    """
    Translate function for non-commands.
    """

    return vbu.translation(b, "profile").gettext(a)


if __debug__:
    # For POEditor
    _poeditor = lambda x: x

    # TRANSLATORS: Command name.
    _poeditor("export")
    # TRANSLATORS: Command description.
    _poeditor("Export all profiles for a given template.")

    # # TRANSLATORS: Command name.
    # _poeditor("enable")
    # # TRANSLATORS: Command description.
    # _poeditor("Enable advanced mode for this guild.")

    # # TRANSLATORS: Command name.
    # _poeditor("disable")
    # # TRANSLATORS: Command description.
    # _poeditor("Disable advanced mode for this guild.")


class Export(vbu.Cog[vbu.Bot]):

    @commands.command(
        application_command_meta=commands.ApplicationCommandMeta(
            guild_only=True,
            permissions=discord.Permissions(administrator=True),
            name_localizations={
                i: _t(i, "export").casefold()
                for i in discord.Locale
            },
            description_localizations={
                i: _t(i, "Export all profiles for a given template.")
                for i in discord.Locale
            },
            options=[
                discord.ApplicationCommandOption(
                    name="template",
                    type=discord.ApplicationCommandOptionType.string,
                    description="The template that you want to export.",
                    autocomplete=True,
                ),
                discord.ApplicationCommandOption(
                    name="format",
                    type=discord.ApplicationCommandOptionType.string,
                    description="The format that you want the template to be exported in.",
                    choices=[
                        discord.ApplicationCommandOptionChoice(
                            name="JSON",
                            value="JSON",
                        ),
                    ],
                ),
            ],
        ),
    )
    @vbu.i18n("profile")
    async def export(self, ctx: vbu.SlashContext, template: str, format: str):
        """
        Export all profiles for a given template.
        """

        # Make sure they used the autocomplete to get the template
        if not utils.uuid.check(template):
            return await ctx.interaction.response.send_message(
                _("Please use the autocomplete to select a template."),
                ephemeral=True,
            )

        # Try and get the template object
        async with vbu.Database() as db:
            template_o = await utils.Template.fetch_template_by_id(
                db,
                template,
            )

            # Tell them if the template doesn't exist
            if not template_o:
                return await ctx.interaction.response.send_message(
                    _(
                        (
                            "There's no template with the name "
                            "**{template_name}** in this guild."
                        )
                    ).format(template_name=template),
                    allowed_mentions=discord.AllowedMentions.none(),
                    ephemeral=True,
                )

            # Make sure the template comes from this guild
            if ctx.command and ctx.command.cog_name == "BotSupport":
                pass
            else:
                assert ctx.interaction.guild
                if ctx.interaction.guild.id != template_o.guild_id:
                    return await ctx.interaction.response.send_message(
                        _("That template doesn't belong to this guild."),
                        ephemeral=True,
                    )

            # There is a template and they can export it
            # Let's defer to do the complicated operations
            await ctx.interaction.response.defer(ephemeral=True)


def setup(bot: vbu.Bot):
    bot.remove_command("export")
    x = Export(bot)
    bot.add_cog(x)
