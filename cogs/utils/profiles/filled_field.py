from __future__ import annotations

from typing import TYPE_CHECKING, Union, Optional
import uuid

from .field import Field

if TYPE_CHECKING:
    from discord.ext import vbu


any_id = Union[str, uuid.UUID]


class FilledField:
    """
    A class holding the filled information of a user for a particular field of a
    particular profile.

    Parameters
    -----------
    profile_id
    field_id
    value
    field: Optional[:class:`cogs.utils.profiles.field.Field`]
        The field that's been filled.

    Attributes
    -----------
    profile_id: :class:`str`
        The ID of the profile associated.
    field_id: :class:`str`
        The ID of the field which has been filled.
    value: :class:`str`
        The value provided by the user for this field.
    field: Optional[:class:`cogs.utils.profiles.field.Field`]
        The field that's been filled.
    """

    __slots__ = (
        "_profile_id",
        "_field_id",
        "value",
        "field",
    )

    def __init__(
            self,
            profile_id: any_id,
            field_id: any_id,
            value: str,
            field: Optional[Field] = None):
        self.profile_id = profile_id  # type: ignore
        self.field_id = field_id  # type: ignore
        self.value: str = value
        self.field: Optional[Field] = field

    @property
    def profile_id(self) -> str:
        if self._profile_id is None:
            self._profile_id = uuid.uuid4()
        return str(self._profile_id)

    @profile_id.setter
    def profile_id(self, value: str | uuid.UUID):
        if isinstance(value, uuid.UUID):
            self._profile_id = value
        else:
            self._profile_id = uuid.UUID(value)

    @property
    def field_id(self) -> str:
        if self._field_id is None:
            self._field_id = uuid.uuid4()
        return str(self._field_id)

    @field_id.setter
    def field_id(self, value: str | uuid.UUID):
        if isinstance(value, uuid.UUID):
            self._field_id = value
        else:
            self._field_id = uuid.UUID(value)

    @classmethod
    async def update_by_id(
            cls,
            db: vbu.Database,
            profile_id: any_id,
            field_id: any_id,
            new_value: Optional[str]):
        """
        Update a filled field value in the database, creating if one does not
        exist.
        """

        if new_value is None:
            await db.call(
                """
                DELETE FROM
                    filled_fields
                WHERE
                    profile_id = $1
                AND
                    field_id = $2
                """,
                profile_id, field_id,
            )
            return

        await db.call(
            """
            INSERT INTO
                filled_fields
                (
                    profile_id,
                    field_id,
                    value
                )
            VALUES
                (
                    $1,
                    $2,
                    $3
                )
            ON CONFLICT
                (profile_id, field_id)
            DO UPDATE
            SET
                value = $3
            """,
            profile_id, field_id, new_value,
        )
        return cls(
            profile_id=profile_id,
            field_id=field_id,
            value=new_value,
        )
