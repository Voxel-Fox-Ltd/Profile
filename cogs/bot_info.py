import discord
from discord.ext import commands, vbu


def _t(b: str | discord.Locale, a: str) -> str:
    """
    Translate function for non-commands.
    """

    return vbu.translation(b, "profile").gettext(a)


_poeditor = lambda x: x
PROFILE_DONATE_UPSELL = _poeditor("""By donating to Profile, you're directly helping keep the bot alive and running, and contributing to making it better.

Running a bot isn't free, so by helping out, Profile can get even better :)

Of course, there are things you get in return for your contribution!

\N{BULLET} Increase your maximum number of templates to 15.
\N{BULLET} Have up to 20 fields in your templates.
\N{BULLET} Allow 30 profiles per template.
\N{BULLET} Direct access to the bot developers to pitch your ideas.

You can [donate here](https://voxelfox.co.uk/portal/profile) if you're interested!

Thanks!""")
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
            # .add_field(
            #     # TRANSLATORS: Text appearing on a button in the info command.
            #     _("Website"),
            #     # TRANSLATORS: Text for a hyperlink.
            #     f"[{_('Click here')}](https://profile.voxelfox.co.uk)",
            # )
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
        embeds.append(
            vbu.Embed(
                use_random_colour=True,
                description=_(PROFILE_DONATE_UPSELL),
            )
        )
        return await ctx.interaction.response.send_message(embeds=embeds)


def setup(bot: vbu.Bot):
    bot.remove_command("info")
    x = BotInfo(bot)
    bot.add_cog(x)
