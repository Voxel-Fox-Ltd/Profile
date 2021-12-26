import discord
from discord.ext import vbu

from ..perks_handler import GuildPerks
from ..profiles.template import Template

class GuildContext(vbu.SlashContext):
    guild: discord.Guild
    guild_perks: GuildPerks
    template: Template
    invoke_meta: bool
