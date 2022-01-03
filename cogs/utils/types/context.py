import discord
from discord.ext import commands

from ..perks_handler import GuildPerks
from ..profiles.template import Template

class GuildContext(commands.SlashContext):
    guild: discord.Guild
    author: discord.Member
    guild_perks: GuildPerks
    template: Template
    invoke_meta: bool
