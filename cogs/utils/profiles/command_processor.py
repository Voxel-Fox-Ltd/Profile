import typing
import re

import discord
from discord.ext import commands


class InvalidCommandText(commands.BadArgument):
    pass


class CommandProcessor(object):

    COMMAND_REGEX = re.compile(
        r'^{{.+?}}$',
        re.IGNORECASE | re.MULTILINE | re.VERBOSE | re.DOTALL
    )
    VALID_COMMAND_REGEX = re.compile(
        r'''
        {{
            DEFAULT\s*(?<!\\)\"(?P<default>.+?)(?<!\\)\"
            (\s*
                (?P<command>
                    (?P<commandname>HASROLE|HASANYROLE|FIELDVALUE)
                    \((?P<commandparams>(?:\d{16,23}(?:,\s*)?)+|(?:(?<!\\)\".+(?<!\\)\"(?:,\s*)?)+)\)
                    \s*SAYS\s*(?<!\\)\"(?P<text>.+?)(?<!\\)\"
                )
            )+
        }}
        ''',
        re.IGNORECASE | re.MULTILINE | re.VERBOSE | re.DOTALL
    )
    COMMAND_PARAMETERS_REGEX = re.compile(
        r'''
        (?P<command>
            (?P<commandname>HASROLE|HASANYROLE|FIELDVALUE)
            \((?P<commandparams>(?:\d{16,23}(?:,\s*)?)+|(?:(?<!\\)\".+(?<!\\)\"(?:,\s*)?)+)\)
            \s*SAYS\s*(?<!\\)\"(?P<text>.+?)(?<!\\)\"
        )
        ''',
        re.IGNORECASE | re.MULTILINE | re.VERBOSE | re.DOTALL
    )

    @classmethod
    def get_is_command(cls, text: str) -> typing.Tuple[bool, bool]:
        """
        Returns whether or not the given text is a command as well as whether or not it's a _valid_ command.
        """

        return (
            cls.COMMAND_REGEX.search(text) is not None,
            cls.VALID_COMMAND_REGEX.search(text) is not None,
        )

    @classmethod
    def get_value(cls, text: str, member: typing.Optional[discord.Member] = None) -> typing.Optional[str]:
        """
        Return the value for a field.
        """

        # See if it's a command
        valid_command = cls.VALID_COMMAND_REGEX.search(text)
        if valid_command is None:
            raise InvalidCommandText()

        # Get the command values
        default_text = valid_command.group("default")
        command_list = cls.COMMAND_PARAMETERS_REGEX.finditer(text)

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
                        return command.group("text").replace('\\n', '\n').replace('\\"', '"')

                # hasanyrole check
                elif command_name.upper() == "HASANYROLE":
                    if any([i for i in role_ids_to_check if i in member._roles]):
                        return command.group("text").replace('\\n', '\n').replace('\\"', '"')

            # fieldvalue can't apply here so we'll ignore it
            if command_name.upper() == "FIELDVALUE":
                return "Could not process field value"

        # Guess we'll have to return the default
        return default_text
