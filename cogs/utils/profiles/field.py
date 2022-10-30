from __future__ import annotations

from typing import Optional, Type
from typing_extensions import Self
import uuid

import discord
from discord.ext import vbu

from .field_type import (
    FieldType,
    TextField,
    ImageField,
    NumberField,
    BooleanField,
)


def _(a: str) -> str:
    return a


def _t(b: str | discord.Locale, a: str) -> str:
    """
    Translate function for non-commands.
    """

    return vbu.translation(b, __name__).gettext(a)


class Field:
    """
    The abstract field object for a given template.
    This itself does not store any user information, but rather the meta information
    associated with a field from a template.

    Attributes
    -----------
    id: :class:`str`
        The ID of the field.
    name: :class:`str`
        The name of the field.
    index: :class:`int`
        The index of the field. May not specifically refer to its location in the embed,
        but *will* in relation to the other indexes of the fields.
    prompt: :class:`str`
        The prompt shown to the user when they're asked to fill in this field information.
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
    field_type: :class:`FieldType`
        The type given to this field
    template_id: Union[:class:`str`, :class:`uuid.UUID`]
        The ID of the template that this field is part of.
    optional: :class:`bool`
        Whether or not this field is optional.
    deleted: :class:`bool`
        Whether or not this field is deleted.
    """

    __slots__ = (
        "_id",
        "index",
        "name",
        "prompt",
        "field_type",
        "_template_id",
        "optional",
        "deleted",
    )

    def __init__(
            self,
            id: Optional[uuid.UUID],
            name: str,
            index: int,
            prompt: str,
            template_id: str | uuid.UUID,
            field_type: Type[FieldType] = TextField,
            optional: bool = False,
            deleted: bool = False):
        self._id: Optional[uuid.UUID] = id
        self.index: int = index
        self.name: str = name
        self.prompt: str = prompt
        self._template_id: Optional[uuid.UUID]
        self.template_id = template_id
        self.field_type: Type[FieldType] = {
            '1000-CHAR': TextField,
            'INT': NumberField,
            'IMAGE': ImageField,
            'BOOLEAN': BooleanField,
        }[getattr(field_type, 'name', field_type) or '1000-CHAR']
        self.optional: bool = optional
        self.deleted: bool = deleted

    @property
    def id(self) -> str:
        if self._id is None:
            self.id = uuid.uuid4()
        return str(self._id)

    @id.setter
    def id(self, value: str | uuid.UUID):
        if isinstance(value, uuid.UUID):
            self._id = value
        else:
            self._id = uuid.UUID(value)

    @property
    def template_id(self) -> str:
        return str(self._template_id)

    @template_id.setter
    def template_id(self, value: str | uuid.UUID):
        if isinstance(value, uuid.UUID):
            self._template_id = value
        else:
            self._template_id = uuid.UUID(value)

    async def update(self, db: vbu.Database, **kwargs) -> Self:
        """
        Save the current class instance into the database.
        """

        for i, o in kwargs.items():
            setattr(self, i, o)
        await db.call(
            """
            INSERT INTO
                fields
                (
                    id,
                    name,
                    index,
                    prompt,
                    field_type,
                    optional,
                    deleted,
                    template_id
                )
            VALUES
                (
                    $1,
                    $2,
                    $3,
                    $4,
                    $5,
                    $6,
                    $7,
                    $8
                )
            ON CONFLICT
                (id)
            DO UPDATE
            SET
                name = $2,
                index = $3,
                prompt = $4,
                field_type = $5,
                optional = $6,
                deleted = $7,
                template_id = $8
            """,
            self.id,
            self.name,
            self.index,
            self.prompt,
            self.field_type.name,
            self.optional,
            self.deleted,
            self.template_id,
        )
        return self

    @classmethod
    async def fetch_field_by_id(
            cls,
            db: vbu.Database,
            id: str | uuid.UUID,
            *,
            allow_deleted: bool = False) -> Self | None:
        """
        Fetch a field object by its ID.
        """

        deleted = "AND deleted = FALSE" if not allow_deleted else ""
        data = await db.call(
            """
            SELECT
                *
            FROM
                fields
            WHERE
                id = $1
            {0}
            """.format(deleted),
            id,
        )
        if data:
            return cls(**data[0])
        return None

    def build_embed(
            self,
            bot: vbu.Bot,
            interaction: discord.Interaction,
            *,
            full: bool = False) -> discord.Embed:
        """
        Make an embed for the field.
        """

        embed = vbu.Embed(use_random_colour=True)
        embed.add_field(
            name=_("Index"),
            value=str(self.index),
            inline=False,
        )
        embed.add_field(
            name=_("Name"),
            value=self.name or "\u200b",
            inline=False,
        )
        embed.add_field(
            name=_("Prompt"),
            value=(
                self.prompt
                if
                    full
                else
                    self.prompt[:100].replace('\n', '\\n') + "..."
                if
                    len(self.prompt) > 100
                else
                    self.prompt[:100].replace('\n', '\\n')
            ) or "\u200b",
            inline=False,
        )
        embed.add_field(
            name=_("Field Type"),
            value=self.field_type.name,
            inline=False,
        )
        embed.add_field(
            name=_("Optional"),
            value=str(self.optional),
            inline=False,
        )
        bot.set_footer_from_config(embed)
        return embed
