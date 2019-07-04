from uuid import UUID

from cogs.utils.profiles.field import Field


class FilledField(object):

    all_filled_fields = {}

    def __init__(self, user_id:int, field_id:UUID, value:str):
        self.user_id = user_id 
        self.field_id = field_id 
        self.value = value
        self.all_filled_fields[(self.user_id, self.field_id)] = self

    @property 
    def field(self) -> Field:
        return Field.all_fields.get(self.field_id)
