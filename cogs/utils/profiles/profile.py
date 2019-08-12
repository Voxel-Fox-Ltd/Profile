import typing
from uuid import UUID
from collections import defaultdict

import discord

from cogs.utils.profiles.field import Field


class Profile(object):

    all_profiles: typing.Dict['profile_id', 'Profile'] = {}
    all_guilds: typing.Dict['guild_id', typing.Dict['name', 'Profile']] = defaultdict(dict)

    def __init__(self, profile_id:UUID, colour:int, guild_id:int, verification_channel_id:int, name:str):
        self.profile_id = profile_id 
        self.colour = colour
        self.guild_id = guild_id
        self.verification_channel_id = verification_channel_id
        self.name = name

        self.all_profiles[self.profile_id] = self
        self.all_guilds[self.guild_id][self.name] = self

    @property
    def fields(self) -> typing.List[Field]:
        """Returns a list of cogs.utils.profiles.fields.Field objects for this particular profile"""

        try:
            return sorted(Field.all_profile_fields.get(self.profile_id), key=lambda x: x.index)
        except TypeError:
            return list()

    def get_profile_for_member(self, member:typing.Union[discord.Member, int]) -> 'cogs.utils.profiles.user_profile.UserProfile':
        """Gets the filled profile for a given member"""

        from cogs.utils.profiles.user_profile import UserProfile
        member_id = getattr(member, 'id', member)
        return UserProfile.all_profiles.get((member_id, self.guild_id, self.name))
