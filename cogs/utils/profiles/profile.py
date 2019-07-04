from typing import List
from uuid import UUID

from discord import Embed

from cogs.utils.profiles.field import Field

class Profile(object):

    all_profiles = {}

    def __init__(self, id:UUID, colour:int, guild_id:int, verification_channel_id:int, name:str):
        self.id = id 
        self.colour = colour
        self.guild_id = guild_id
        self.verification_channel_id = verification_channel_id
        self.name = name
        self.all_profiles[self.id] = self

    @property
    def fields(self) -> List[Field]:
        '''Returns a list of cogs.utils.profiles.fields.Field objects for this particular profile'''

        return sorted(Field.all_profile_fields.get(self.id), key=lambda x: x.index)


    def build_embed(self, *fields) -> Embed:
        '''Builds an embed from the FilledField objects presented by the user'''

        # Sort the fields by appearance in the embed
        fields = sorted(fields, key=lambda x: x.field.index)

        # Make sure the non-optional ones are there
        mandatory_field_ids = [i.id for i in self.fields if not i.optional]
        filled_mandatory_fields = [i for i in fields if i.id in mandatory_field_ids]
        if len(filled_mandatory_fields) != len(mandatory_field_ids):
            raise IndexError("Not the right amount of fields to build an embed")

        # Actually build the embed
        embed = Embed(colour=self.colour)
        for f in fields:
            embed.add_field(name=f.field.name, value=f.value)
        return embed
