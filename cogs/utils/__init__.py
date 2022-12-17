from typing import Any

import discord
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
    'compare_embeds',
)


def mention_command(command: commands.Command) -> str:
    """
    A function that returns a string that mentions a command.
    """

    command_id: int | None
    if (command_id := getattr(command, "id", None)) is None:
        return f"/{command.qualified_name}"
    return f"</{command.qualified_name}:{command_id}>"


def compare_embeds(
        embed1: discord.Embed | Any, 
        embed2: discord.Embed | Any) -> bool:
    """
    Return whether or not two embeds share the same values.

    This will compare fields, the image, the description, and the title.
    """

    # Make sure both items are actually embeds first
    if not isinstance(embed1, discord.Embed) or not isinstance(embed2, discord.Embed):
        return False

    # Convert both to dicts to make comparison easier
    embed1_dict = embed1.to_dict()
    embed2_dict = embed2.to_dict()

    # Compare the title
    if embed1_dict.get("title") != embed2_dict.get("title"):
        return False

    # Compare the description
    if embed1_dict.get("description") != embed2_dict.get("description"):
        return False

    # Compare the image URL - we're not gonna compare the image
    # size etc becuase Novus doesn't set it but the API does
    if embed1_dict.get("image", {}).get("url") != embed2_dict.get("image", {}).get("url"):
        return False

    # Iterate through the fields and make sure each of the value,
    # inline, and name are the same
    for field1, field2 in zip(embed1_dict.get("fields", list()), embed2_dict.get("fields", list())):
        if field1["name"] != field2["name"]:
            return False
        if field1["value"] != field2["value"]:
            return False
        if field1.get("inline", True) != field2.get("inline", True):
            return False

    # If we got here, then the embeds are the same
    return True
