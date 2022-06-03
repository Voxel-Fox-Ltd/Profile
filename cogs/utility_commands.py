import discord
from discord.ext import commands, vbu


class UtilityCommands(vbu.Cog[vbu.Bot]):

    @commands.command(
        application_command_meta=commands.ApplicationCommandMeta(
            permissions=discord.Permissions(manage_guild=True),
            guild_only=True,
        ),
    )
    @commands.defer()
    @commands.guild_only()
    async def clearcommands(self, ctx: vbu.SlashContext[discord.Guild]):
        """
        Clear all of hte slash commands from your guild.
        """

        commands = await ctx.guild.fetch_application_commands()
        for command in commands:
            await ctx.guild.delete_application_command(command)
        await ctx.send("Deleted all commands.")


def setup(bot: vbu.Bot):
    x = UtilityCommands(bot)
    bot.add_cog(x)
