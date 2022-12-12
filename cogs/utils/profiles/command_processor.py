import typing
import re

import discord
from discord.ext import commands


class InvalidCommandText(commands.BadArgument):
    """
    The given command text for the field was invalid.
    """

    pass


class CommandProcessor:
    """
    An object that processes commands for the user.
    """

    COMMAND_REGEX = re.compile(
        r'^{{.+?}}$',
        re.IGNORECASE | re.MULTILINE | re.VERBOSE | re.DOTALL
    )
    VALID_COMMAND_REGEX = re.compile(
        r'''
        {{\s*(HASROLE\s*"[^"]+"\s*"[^"]+"\s*)*\s*DEFAULT\s*"([^"]+)"\s*}}
        ''',
        re.IGNORECASE | re.MULTILINE | re.VERBOSE | re.DOTALL
    )
    HASROLE_REGEX = re.compile(
        r'''HASROLE\s*"([^"]+)"\s*"([^"]+)"''',
        re.IGNORECASE | re.MULTILINE | re.VERBOSE | re.DOTALL
    )
    ELSE_REGEX = re.compile(
        r'''DEFAULT\s*"([^"]+)"''',
        re.IGNORECASE | re.MULTILINE | re.VERBOSE | re.DOTALL
    )

    @classmethod
    def get_is_command(cls, text: str) -> typing.Tuple[bool, bool]:
        """
        Returns whether or not the given text is a command as well as whether or not it's
        a *valid* command.

        Parameters
        -----------
        text: :class:`str`
            The text that you want to check for command validity.

        Returns
        --------
        Tuple[:class:`bool`, :class:`bool`]
            Whether or not the command is a command, and whether or not said
            command is valid.
        """

        return (
            cls.COMMAND_REGEX.search(text) is not None,
            cls.VALID_COMMAND_REGEX.search(text) is not None,
        )

    @classmethod
    def get_value(
            cls,
            text: str,
            member: typing.Optional[discord.Member] = None) -> str:
        """
        Return the value for a field after it's run through a command.

        Parameters
        -----------
        text: :class:`str`
            The command value that was assigned to the field.
        member: Optional[:class:`discord.Member`]
            The member for whom the text should be generated.

        Raises
        -------
        :class:`cogs.utils.errors.InvalidCommandText`
            If the command is not valid.
        :class:`ValueError`
            If the command requires a member to get a value.

        Returns
        --------
        :class:`str`
            The value for the field.
        """

        # See if it's a command
        valid_command_match = cls.VALID_COMMAND_REGEX.search(text)
        if valid_command_match is None:
            return ""

        # Get the command values
        default_text_match = cls.ELSE_REGEX.search(text)
        if not default_text_match:
            return ""
        hasrole_match_iter = cls.HASROLE_REGEX.finditer(text)

        # See if the member has the relevant role
        for hasrole_match in hasrole_match_iter:
            if member is None:
                raise ValueError("Member is required for this command.")
            role_id = int(hasrole_match.group(1))
            if role_id in member.role_ids:
                return hasrole_match.group(2)

        # Otherwise return the default
        return default_text_match.group(1)
