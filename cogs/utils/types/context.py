from typing import Generic, TypeVar

import discord
from discord.ext import commands, vbu

from ..perks_handler import GuildPerks
from ..profiles.template import Template


__all__ = (
    'GuildContext',
)


TI = TypeVar('TI', bound=discord.Interaction)


class GuildContext(commands.SlashContext, Generic[TI]):
    bot: vbu.Bot
    interaction: TI
    guild: discord.Guild
    author: discord.Member
    guild_perks: GuildPerks
    template: Template
    invoke_meta: bool
