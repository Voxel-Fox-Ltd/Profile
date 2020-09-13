import typing
import uuid

import discord

from cogs.utils.profiles.field import Field
from cogs.utils.profiles.command_processor import CommandProcessor


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

    def get_value(self, member:typing.Optional[discord.Member]=None) -> str:
        """Return the value for a field"""

        # See if it's a command
        valid_command = CommandProcessor.VALID_COMMAND_REGEX.search(self.field.prompt)
        if valid_command is None:
            return self.value

        # Get the command values
        default_text = valid_command.group("default")
        command_list = CommandProcessor.COMMAND_PARAMETERS_REGEX.finditer(self.field.prompt)

        # Work out how we're applying each thing
        for command in command_list:
            command_name = command.group("commandname")
            command_params = command.group("commandparams")

            # hasrole command processing
            if command_name.upper() in ["HASROLE", "HASANYROLE"]:
                if member is None:
                    raise ValueError("No provided member")
                role_strings_to_check = [i.strip(' "') for i in command_params.split(',')]
                role_ids_to_check = [int(i) for i in role_strings_to_check if i.isdigit()]

                # hasrole check
                if command_name.upper() == "HASROLE":
                    if len([i for i in role_ids_to_check if i in member._roles]) == len(role_ids_to_check):
                        return command.group("text").replace('\\n', '\n')

                # hasanyrole check
                elif command_name.upper() == "HASANYROLE":
                    if any([i for i in role_ids_to_check if i in member._roles]):
                        return command.group("text").replace('\\n', '\n')

            # fieldvalue can't apply here so we'll ignore it
            if command_name.upper() == "FIELDVALUE":
                return "Could not process field value"

        # Guess we'll have to return the default
        return default_text
