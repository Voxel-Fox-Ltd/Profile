import uuid

from cogs.utils.profiles.field import Field


class FilledField(object):
    """A class holding the filled information of a user for a particular field of a
    particular profile
    """

    __slots__ = ("user_id", "field_id", "value", "field")

    def __init__(self, user_id:int, field_id:uuid.UUID, value:str):
        self.user_id: int = user_id
        self.field_id: uuid.UUID = field_id
        self.value: str = value
        self.field: Field = None
