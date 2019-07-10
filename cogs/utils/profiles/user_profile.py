from typing import List
from uuid import UUID

from discord import Embed

from cogs.utils.profiles.profile import Profile
from cogs.utils.profiles.field import Field
from cogs.utils.profiles.filled_field import FilledField


class UserProfile(object):

    all_profiles = {}

    def __init__(self, user_id:int, profile_id:UUID, verified:bool):
        self.user_id = user_id 
        self.profile_id = profile_id 
        self.verified = verified
        self.all_profiles[(self.user_id, self.profile.guild_id, self.profile.name)] = self

    @property 
    def profile(self) -> Profile:
        return Profile.all_profiles.get(self.profile_id)

    @property 
    def filled_fields(self) -> List[FilledField]:
        try:
            return [FilledField.all_filled_fields[(self.user_id, i.field_id)] for i in self.profile.fields]
        except KeyError:
            return []        

    def build_embed(self) -> Embed:
        '''Converts the filled profile into an embed'''

        fields = sorted(self.filled_fields, key=lambda x: x.field.index)
        embed = Embed()
        embed.colour = self.profile.colour 
        embed.title = f"{self.profile.name.title()} profile"
        for f in fields:
            embed.add_field(name=f.field.name, value=f.value)
        # embed.set_footer(text=self.profile.name.upper())
        return embed
