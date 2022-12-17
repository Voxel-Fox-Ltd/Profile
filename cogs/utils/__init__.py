from discord.ext import commands

from . import checks, errors, types, uuid_ as uuid
from .profiles.field import Field
from .profiles.field_type import (
    FieldType,
    TextField,
    NumberField,
    ImageField,
    FieldCheckFailure,
)
from .profiles.template import Template
from .profiles.user_profile import UserProfile
from .profiles.filled_field import FilledField
from .profiles.command_processor import CommandProcessor
from .perks_handler import GuildPerks


__all__ = (
    'checks',
    'errors',
    'types',
    'uuid',
    'Field',
    'FieldType',
    'TextField',
    'NumberField',
    'ImageField',
    'Template',
    'UserProfile',
    'FilledField',
    'CommandProcessor',
    'GuildPerks',
    'FieldCheckFailure',
    'mention_command',
)


def mention_command(command: commands.Command) -> str:
    """
    A function that returns a string that mentions a command.
    """

    command_id: int | None
    if (command_id := getattr(command, "id", None)) is None:
        return f"/{command.qualified_name}"
    return f"</{command.qualified_name}:{command_id}>"
