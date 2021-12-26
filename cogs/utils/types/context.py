import typing

import discord
from discord.ext import vbu

from cogs.utils.perks_handler import GuildPerks

class GuildContext(vbu.Context):
    guild: discord.Guild
    guild_perks: typing.Optional[GuildPerks] = None
