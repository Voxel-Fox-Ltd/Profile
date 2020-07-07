import typing
import uuid
import collections

import discord
from discord.ext import commands

from cogs.utils.profiles.field import Field


class TemplateNotFoundError(commands.BadArgument):

    def __init__(self, profile_name:str):
        self.profile_name = profile_name

    def __str__(self):
        return f"There's no template with the name `{self.profile_name}` on this guild."


class Template(object):
    """A class for an abstract template object that's saved to guild
    This contains no user data, but rather the metadata for the template itself
    """

    all_profiles: typing.Dict[uuid.UUID, 'Template'] = {}
    all_guilds: typing.Dict[int, typing.Dict[str, 'Template']] = collections.defaultdict(dict)

    __slots__ = ("template_id", "colour", "guild_id", "verification_channel_id", "name", "archive_channel_id", "role_id")

    def __init__(self, template_id:uuid.UUID, colour:int, guild_id:int, verification_channel_id:int, name:str, archive_channel_id:int, role_id:int):
        self.template_id = template_id
        self.colour = colour
        self.guild_id = guild_id
        self.verification_channel_id = verification_channel_id
        self.name = name
        self.archive_channel_id = archive_channel_id
        self.role_id = role_id

        self.all_profiles[self.template_id] = self
        self.all_guilds[self.guild_id][self.name] = self

    @property
    def fields(self) -> typing.List[Field]:
        """Returns a list of cogs.utils.profiles.fields.Field objects for this particular profile"""

        try:
            return [i for i in sorted(Field.all_profile_fields.get(self.template_id), key=lambda x: x.index) if i.deleted is False]
        except TypeError:
            return list()

    def get_profile_for_member(self, member:typing.Union[discord.Member, int]) -> 'cogs.utils.profiles.user_profile.UserProfile':
        """Gets the filled profile for a given member"""

        from cogs.utils.profiles.user_profile import UserProfile
        member_id = getattr(member, 'id', member)
        return UserProfile.all_profiles.get((member_id, self.guild_id, self.name))

    @classmethod
    async def convert(cls, ctx, argument:str):
        """The Discord.py convert method for getting a template"""

        v = cls.all_guilds[ctx.guild.id].get(argument.lower())
        if v is None:
            raise TemplateNotFoundError(argument.lower())
        return v
