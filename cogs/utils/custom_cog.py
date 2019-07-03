from logging import getLogger

from discord.ext.commands import Cog as OriginalCog


class Cog(OriginalCog):

    def __init__(self, cog_name:str):
        self.log_handler = getLogger(f"profilebot.cogs.{cog_name}")
