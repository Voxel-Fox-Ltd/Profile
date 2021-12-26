import typing
import uuid

from cogs.utils.profiles.field import Field


class FilledField:
    """
    A class holding the filled information of a user for a particular field of a
    particular profile.

    Parameters
    -----------
    user_id: :class:`int`
        The ID of the user who owns this field.
    name: :class:`str`
        The name of the profile that the field is added to.
    field_id: Union[:class:`str`, :class:`uuid.UUID`
        The ID of the field which has been filled.
    value: :class:`str`
        The value provided by the user for this field.
    field: Optional[:class:`cogs.utils.profiles.field.Field`]
        The field that's been filled.

    Attributes
    -----------
    user_id: :class:`int`
        The ID of the user who owns this field.
    name: :class:`str`
        The name of the profile that the field is added to.
    field_id: Union[:class:`str`, :class:`uuid.UUID`
        The ID of the field which has been filled.
    value: :class:`str`
        The value provided by the user for this field.
    field: Optional[:class:`cogs.utils.profiles.field.Field`]
        The field that's been filled.
    """

    __slots__ = ("user_id", "name", "field_id", "value", "field")

    def __init__(
            self,
            user_id: int,
            name: str,
            field_id: typing.Union[str, uuid.UUID],
            value: str,
            field: typing.Optional[Field] = None):
        self.user_id: int = user_id
        self.name: str = name
        self.field_id: str = str(field_id)
        self.value: str = value
        self.field: typing.Optional[Field] = field
