import uuid

from cogs.utils.profiles.field import Field


class FilledField(object):
    """A class holding the filled information of a user for a particular field of a
    particular profile
    """

    all_filled_fields = {}

    __slots__ = ("user_id", "field_id", "value")

    def __init__(self, user_id:int, field_id:uuid.UUID, value:str):
        self.user_id = user_id
        self.field_id = field_id
        self.value = value
        self.all_filled_fields[(self.user_id, self.field_id)] = self

    @property
    def field(self) -> Field:
        return Field.all_fields.get(self.field_id)
