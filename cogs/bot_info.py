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
    _poeditor("information")
    # TRANSLATORS: Command description.
    _poeditor("Get information and links for the bot.")


class BotInfo(vbu.Cog[vbu.Bot]):

    @commands.command(
        application_command_meta=commands.ApplicationCommandMeta(
            name_localizations={
                i: _t(i, "information").casefold()
                for i in discord.Locale
            },
            description_localizations={
                i: _t(i, "Get information and links for the bot.")
                for i in discord.Locale
            },
        ),
    )
    @vbu.i18n("profile")
    async def information(self, ctx: commands.SlashContext):
        """
        Get information and links for the bot.
        """

        embeds = []
        embeds.append(
            vbu.Embed(use_random_colour=True)
            .add_field(
                # TRANSLATORS: Text appearing on a button in the info command.
                _("Creator"),
                "[Kae Bartlett](https://uwu.social/@kae)\n[Voxel Fox](https://voxelfox.co.uk)",
            )
            .add_field(
                # TRANSLATORS: Text appearing on a button in the info command.
                _("Website"),
                # TRANSLATORS: Text for a hyperlink.
                f"[{_('Click here')}](https://profile.voxelfox.co.uk)",
            )
            .add_field(
                # TRANSLATORS: Text appearing on a button in the info command.
                _("Donate"),
                "[Patreon](https://patreon.com/voxelfox)",
            )
            .add_field(
                # TRANSLATORS: Text appearing on a button in the info command.
                _("Support"),
                "[Discord](https://discord.gg/vfl)",
            )
            .add_field(
                # TRANSLATORS: Text appearing on a button in the info command.
                _("Vote"),
                "[Top.gg](https://top.gg/bot/598553427592871956/vote)",
            )
            .add_field(
                # TRANSLATORS: Text appearing on a button in the info command.
                _("Leave a review"),
                "[Top.gg](https://top.gg/bot/598553427592871956#reviews)",
            )
            .add_field(
                # TRANSLATORS: Text appearing on a button in the info command.
                _("Source Code"),
                "[GitHub](https://github.com/Voxel-Fox-Ltd/Profile)",
            )
        )
        return await ctx.interaction.response.send_message(embeds=embeds)


def setup(bot: vbu.Bot):
    bot.remove_command("info")
    x = BotInfo(bot)
    bot.add_cog(x)
