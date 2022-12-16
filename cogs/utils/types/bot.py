from typing import TypedDict

from discord.ext import vbu


__all__ = (
    'BotConfig',
    'Bot',
)


ImgurConfig = TypedDict('ImgurConfig', {
    'client_id': str,
})


class BotConfig(vbu.types.BotConfig):
    imgur: ImgurConfig


class Bot(vbu.Bot):
    config: BotConfig
