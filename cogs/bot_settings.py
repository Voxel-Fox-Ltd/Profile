import voxelbotutils as utils


class BotSettings(utils.Cog):

    @utils.command(aliases=['settings'])
    @utils.checks.is_bot_support()
    async def setup(self, ctx: utils.Context):
        """
        Set up individual settings for each guild.
        """

        menu = utils.SettingsMenu()
        settings_mention = utils.SettingsMenuOption.get_guild_settings_mention
        menu.add_multiple_options(
            utils.SettingsMenuOption(
                ctx=ctx,
                display=lambda c: "Set max template count (currently {0})".format(settings_mention(c, 'max_template_count')),
                converter_args=[
                    utils.SettingsMenuConverter(
                        prompt="How many templates should this guild be able to create?",
                        asking_for="max template count",
                        converter=int,
                    ),
                ],
                callback=utils.SettingsMenuOption.get_set_guild_settings_callback("guild_settings", "max_template_count"),
            ),
            utils.SettingsMenuOption(
                ctx=ctx,
                display=lambda c: "Set max template field count (currently {0})".format(settings_mention(c, 'max_template_field_count')),
                converter_args=[
                    utils.SettingsMenuConverter(
                        prompt="How many fields should each template in this guild be able to have?",
                        asking_for="max template field count",
                        converter=int,
                    ),
                ],
                callback=utils.SettingsMenuOption.get_set_guild_settings_callback("guild_settings", "max_template_field_count"),
            ),
            utils.SettingsMenuOption(
                ctx=ctx,
                display=lambda c: "Set max profile count (currently {0})".format(settings_mention(c, 'max_template_profile_count')),
                converter_args=[
                    utils.SettingsMenuConverter(
                        prompt="How many profiles should each template in this guild be able to create?",
                        asking_for="max profile count",
                        converter=int,
                    ),
                ],
                callback=utils.SettingsMenuOption.get_set_guild_settings_callback("guild_settings", "max_template_profile_count"),
            ),
        )
        try:
            await menu.start(ctx)
            await ctx.send("Done setting up!")
        except utils.errors.InvokedMetaCommand:
            pass


def setup(bot: utils.Bot):
    x = BotSettings(bot)
    bot.add_cog(x)
