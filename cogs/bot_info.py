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

    # TRANSLATORS: The name of a command.
    _poeditor("information")
    # TRANSLATORS: The description for a command.
    _poeditor("Get information and links for the bot.")


class BotInfo(vbu.Cog[vbu.Bot]):

    @commands.command(
        application_command_meta=commands.ApplicationCommandMeta(
            name_localizations={
                i: _t(i, "information")
                for i in discord.Locale
            },
            description_localizations={
                i: _t(i, "Get information and links for the bot.")
                for i in discord.Locale
            },
        ),
    )
    @vbu.i18n("profile")
    async def info(self, ctx: commands.SlashContext):
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
                "https://profile.voxelfox.co.uk",
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
                _("Source Code"),
                "[GitHub](https://github.com/Voxel-Fox-Ltd/Profile)",
            )
        )
        return await ctx.interaction.response.send_message(embeds=embeds)
