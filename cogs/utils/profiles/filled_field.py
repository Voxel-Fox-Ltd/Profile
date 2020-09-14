import uuid

from cogs.utils.profiles.field import Field


class FilledField(object):
    """A class holding the filled information of a user for a particular field of a
    particular profile

    Args:
        user_id (int): the ID of the user who owns this field
        field_id (uuid.UUID): the ID of the field which has been filled
        value (str): the value that this field was filled with by the user
    Attrs:
        field (cogs.utils.profiles.field.Field): the field object which this filled field refers to
    """

    __slots__ = ("user_id", "name", "field_id", "value", "field")

    def __init__(self, user_id:int, name:str, field_id:uuid.UUID, value:str, field:Field=None):
        self.user_id: int = user_id
        self.name: str = name
        self.field_id: uuid.UUID = field_id
        self.value: str = value
        self.field: Field = field
