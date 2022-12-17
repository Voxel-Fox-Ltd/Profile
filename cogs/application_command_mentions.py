import asyncio

from discord.ext import vbu


class ApplicationCommandMentions(vbu.Cog[vbu.Bot]):

    def cog_load(self) -> None:
        asyncio.create_task(self.load_application_commands())

    async def load_application_commands(self):
        """
        Load all of the bot's application commands so that we get their IDs in
        the command instance itself.
        """

        await self.bot.wait_until_ready()
        app_commands = await self.bot.fetch_global_application_commands()
        for i in app_commands:
            bot_command = self.bot.get_command(i.name)
            if not bot_command:
                continue
            bot_command.id = i.id


def setup(bot: vbu.Bot):
    x = ApplicationCommandMentions(bot)
    bot.add_cog(x)
