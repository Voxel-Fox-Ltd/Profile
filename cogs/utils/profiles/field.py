from __future__ import annotations

import typing
import uuid

from discord.ext import vbu

from .field_type import (
    FieldType,
    TextField,
    ImageField,
    NumberField,
    BooleanField,
)

if typing.TYPE_CHECKING:
    from .template import Template


class Field:
    """
    The abstract field object for a given template.
    This itself does not store any user information, but rather the meta information
    associated with a field from a template.

    Attributes
    -----------
    field_id: :class:`str`
        The ID of the field.
    name: :class:`str`
        The name of the field.
    index: :class:`int`
        The index of the field. May not specifically refer to its location in the embed,
        but *will* in relation to the other indexes of the fields.
    prompt: :class:`str`
        The prompt shown to the user when they're asked to fill in this field information.
    timeout: :class:`int`
        How long the user has (in seconds) to fill in this field.
    field_type :class:`cogs.utils.profiles.field_type.FieldType`:
        The type given to this field
    template_id: :class:`str`
        The ID of the template that this field is part of.
    optional: :class:`bool`
        Whether or not this field is optional.
    deleted: :class:`bool`
        Whether or not this field is deleted.

    Parameters
    -----------
    field_id: Union[:class:`str`, :class:`uuid.UUID`]
        The ID of the field.
    name: :class:`str`
        The name of the field.
    index: :class:`int`
        The index of the field. May not specifically refer to its location in the embed,
        but *will* in relation to the other indexes of the fields.
    prompt: :class:`str`
        The prompt shown to the user when they're asked to fill in this field information.
    timeout: :class:`int`
        How long the user has (in seconds) to fill in this field.
    field_type: :class:`FieldType`
        The type given to this field
    template_id: Union[:class:`str`, :class:`uuid.UUID`]
        The ID of the template that this field is part of.
    optional: :class:`bool`
        Whether or not this field is optional.
    deleted: :class:`bool`
        Whether or not this field is deleted.
    """

    __slots__ = ("field_id", "index", "name", "prompt", "timeout", "field_type", "template_id", "optional", "deleted")

    def __init__(
            self,
            field_id: typing.Union[str, uuid.UUID],
            name: str,
            index: int,
            prompt: str,
            timeout: int,
            field_type: FieldType,
            template_id: typing.Union[str, uuid.UUID],
            optional: bool,
            deleted: bool):
        self.field_id: str = str(field_id)
        self.index: int = index
        self.name: str = name
        self.prompt: str = prompt
        self.timeout: int = timeout
        self.field_type: FieldType = {
            '1000-CHAR': TextField(),
            'INT': NumberField(),
            'IMAGE': ImageField(),
            'BOOLEAN': BooleanField(),
        }[getattr(field_type, 'name', field_type)]  # type: ignore
        self.template_id: str = str(template_id)
        self.optional: bool = optional
        self.deleted: bool = deleted

    @property
    def id(self) -> str:
        """
        The ID of the field.
        """

        return self.field_id

    async def save(self, db: vbu.Database, template: Template) -> None:
        """
        Save the current class instance into the database.
        """

        await db.call(
            """INSERT INTO field (field_id, name, index, prompt, timeout, field_type,
            optional, deleted, template_id) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)""",
            self.id, self.name, self.index, self.prompt, self.timeout, self.field_type.name,
            self.optional, self.deleted, template.id,
        )
