import typing
import uuid
import re

import discord
from discord.ext import commands
import voxelbotutils as utils

from cogs.utils.profiles.field import Field
from cogs.utils.profiles.filled_field import FilledField
from cogs.utils.profiles.command_processor import CommandProcessor, InvalidCommandText


class TemplateNotFoundError(commands.BadArgument):
    def __init__(self, template_name: str = None):
        if template_name:
            message = f"There's no template with the name `{template_name}` on this guild."
        else:
            message = "The given template could not be found."
        super().__init__(message)


class TemplateSendError(commands.BadArgument):
    pass


class TemplateVerificationChannelError(TemplateSendError):
    pass


class TemplateArchiveChannelError(TemplateSendError):
    pass


class TemplateRoleAddError(TemplateSendError):
    pass


class Template(object):
    """
    A class for an abstract template object that's saved to guild.
    This contains no user data, but rather the metadata for the template itself.
    """

    TEMPLATE_ID_REGEX = re.compile(r"^(?P<uuid>.{8}-.{4}-.{4}-.{4}-.{12})$")

    __slots__ = (
        "template_id", "colour", "guild_id", "verification_channel_id", "name", "archive_channel_id", "role_id",
        "max_profile_count", "max_field_count", "all_fields",
    )

    def __init__(
            self, template_id: uuid.UUID, colour: int, guild_id: int, verification_channel_id: str,
            name: str, archive_channel_id: str, role_id: str, max_profile_count: int, max_field_count: int):
        self.template_id: uuid.UUID = template_id
        self.colour: int = colour
        self.guild_id: int = guild_id
        self.verification_channel_id: str = verification_channel_id
        self.name: str = name
        self.archive_channel_id: str = archive_channel_id
        self.role_id: str = role_id
        self.max_profile_count: int = max_profile_count
        self.max_field_count: int = max_field_count
        self.all_fields: typing.Dict[uuid.UUID, Field] = dict()

    @property
    def should_send_message(self) -> bool:
        """
        Says whether or not this template should send a message (verification/archivation) on its submission.
        """

        return bool(self.verification_channel_id or self.archive_channel_id)

    def get_verification_channel_id(self, member: discord.Member) -> typing.Optional[int]:
        """
        Get the correct verification channel ID for the given member.
        """

        return self._get_id_from_command(self.verification_channel_id, member)

    def get_archive_channel_id(self, member: discord.Member) -> typing.Optional[int]:
        """
        Get the correct archive channel ID for a given member.
        """

        return self._get_id_from_command(self.archive_channel_id, member)

    def get_role_id(self, member: discord.Member) -> typing.Optional[int]:
        """
        Get the correct role ID for a given member.
        """

        return self._get_id_from_command(self.role_id, member)

    @staticmethod
    def _get_id_from_command(text: str, member: discord.Member) -> typing.Optional[int]:
        """
        Get the ID from either a command or as a straight value.
        """

        # Given as a straight int
        if text is None:
            return None
        if text.isdigit():
            return int(text)

        # Given as a command
        return_value = CommandProcessor.get_value(text, member)
        if return_value.isdigit():
            return int(return_value)
        if return_value == "continue":
            return None
        raise InvalidCommandText()

    @property
    def fields(self) -> typing.Dict[uuid.UUID, Field]:
        """
        Returns a dict of `utils.Field` objects for this particular profile.
        """

        return {i: o for i, o in self.all_fields.items() if o.deleted is False}

    async def fetch_profile_for_user(
            self, db, user_id:int, profile_name: str = None,
            *, fetch_filled_fields: bool = True) -> 'cogs.utils.profiles.user_profile.UserProfile':
        """
        Gets the filled profile for a given user.

        Args:
            db (cogs.utils.database.DatabaseConnection): An active connection to the database.
            user_id (int): The ID of the user you want to grab the information for.
            profile_name (str, optional): The name of the profile you want to grab.
            fetch_filled_fields (bool, optional): Whether or not to populate the filled fields for the UserProfile.

        Returns:
            cogs.utils.profiles.user_profile.UserProfile: The user profile that you asked for.

        Raises:
            ValueError: If no profile name was provided and multiple profiles were retrieved.
        """

        # Grab our imports here to avoid circular importing
        from cogs.utils.profiles.user_profile import UserProfile

        # Grab the user profile
        if profile_name is None:
            profile_rows = await db(
                """SELECT * FROM created_profile WHERE template_id=$1 AND user_id=$2""", self.template_id, user_id,
            )
        else:
            profile_rows = await db(
                """SELECT * FROM created_profile WHERE template_id=$1 AND user_id=$2 AND LOWER(name)=LOWER($3)""",
                self.template_id, user_id, profile_name,
            )
        if not profile_rows:
            return None
        if profile_name is None and len(profile_rows) > 1:
            raise ValueError("Too many saved profiles to have no set profile name")
        user_profile = UserProfile(**profile_rows[0], template=self)
        if fetch_filled_fields:
            await user_profile.fetch_filled_fields(db)
        return user_profile

    async def fetch_all_profiles_for_user(
            self, db, user_id: int, *, fetch_filled_fields: bool = True) -> typing.List['cogs.utils.profiles.user_profile.UserProfile']:
        """
        Gets the filled profile for a given user.

        Args:
            db (cogs.utils.database.DatabaseConnection): An active connection to the database.
            user_id (int): The ID of the user you want to grab the information for.
            fetch_filled_fields (bool, optional): Whether or not to populate the filled fields for the UserProfile.

        Returns:
            typing.List['cogs.utils.profiles.user_profile.UserProfile']: A list of UserProfiles for the given user.
        """

        # Grab our imports here to avoid circular importing
        from cogs.utils.profiles.user_profile import UserProfile

        # Grab the user profile
        profile_rows = await db("SELECT * FROM created_profile WHERE template_id=$1 AND user_id=$2", self.template_id, user_id)
        profiles = [UserProfile(**i, template=self) for i in profile_rows]
        if fetch_filled_fields:
            [await i.fetch_filled_fields(db) for i in profiles]
        return profiles

    async def fetch_all_profiles(self, db, *, fetch_filled_fields: bool = True) -> typing.List['cogs.utils.profiles.user_profile.UserProfile']:
        """
        Gets the filled profile for a given user

        Args:
            db (cogs.utils.database.DatabaseConnection): An active connection to the database.
            fetch_filled_fields (bool, optional): Whether or not to populate the filled fields for the UserProfile.

        Returns:
            typing.List['cogs.utils.profiles.user_profile.UserProfile']: A list of UserProfiles for the given template.
        """

        # Grab our imports here to avoid circular importing
        from cogs.utils.profiles.user_profile import UserProfile

        # Grab the user profile
        profile_rows = await db("SELECT * FROM created_profile WHERE template_id=$1", self.template_id)
        profiles = [UserProfile(**i, template=self) for i in profile_rows]
        if fetch_filled_fields:
            [await i.fetch_filled_fields(db) for i in profiles]
        return profiles

    @classmethod
    async def fetch_template_by_id(cls, db, template_id: uuid.UUID, *, fetch_fields: bool = True) -> typing.Optional['Template']:
        """
        Get a template from the database via its ID.
        """

        # Grab the template
        template_rows = await db("SELECT * FROM template WHERE template_id=$1", template_id)
        if not template_rows:
            return None
        template = cls(**template_rows[0])
        if fetch_fields:
            await template.fetch_fields(db)
        return template

    @classmethod
    async def fetch_template_by_name(cls, db, guild_id: int, template_name: str, *, fetch_fields: bool = True) -> typing.Optional['Template']:
        """
        Get a template from the database via its name.
        """

        # Grab the template
        template_rows = await db("SELECT * FROM template WHERE guild_id=$1 AND LOWER(name)=LOWER($2)", guild_id, template_name)
        if not template_rows:
            return None
        template = cls(**template_rows[0])
        if fetch_fields:
            await template.fetch_fields(db)
        return template

    async def fetch_fields(self, db) -> typing.Dict[uuid.UUID, FilledField]:
        """
        Fetch the fields for this template and store them in .all_fields.
        """

        field_rows = await db("SELECT * FROM field WHERE template_id=$1", self.template_id)
        self.all_fields.clear()
        for f in field_rows:
            field = Field(**f)
            self.all_fields[field.field_id] = field
        return self.all_fields

    @classmethod
    async def convert(cls, ctx, argument: str):
        """
        The Discord.py convert method for getting a template.
        """

        match = cls.TEMPLATE_ID_REGEX.search(argument)
        async with ctx.bot.database() as db:
            if match is None:
                v = await cls.fetch_template_by_name(db, ctx.guild.id, argument)
            else:
                v = await cls.fetch_template_by_id(db, match.group("uuid"))
            if v is not None and v.guild_id != ctx.guild.id and ctx.author.id not in ctx.bot.owner_ids:
                v = None
        if v is None:
            raise TemplateNotFoundError(argument.lower())
        return v

    def build_embed(self, bot, brief: bool = False) -> utils.Embed:
        """
        Create an embed to visualise all of the created fields and given information.
        """

        # Create the initial embed
        fields: typing.List[Field] = sorted(self.fields.values(), key=lambda x: x.index)
        embed = utils.Embed(use_random_colour=True, title=self.name)

        # Work out what goes in the description
        description_lines = [
            f"Template ID: `{self.template_id}`",
            f"Guild ID: `{self.guild_id}`",
            f"Maximum allowed profiles: `{self.max_profile_count}`",
            f"Maximum field count: `{self.max_field_count}`",
        ]

        # Add verification channel ID
        if self.verification_channel_id:
            is_command, is_valid_command = CommandProcessor.get_is_command(self.verification_channel_id)
            if is_command:
                if is_valid_command:
                    description_lines.append(f"Verification channel: (COMMAND) `{self.verification_channel_id}`")
                else:
                    description_lines.append(f"Verification channel: (COMMAND::INVALID) `{self.verification_channel_id}`")
            else:
                description_lines.append(f"Verification channel: `{self.verification_channel_id}` (<#{self.verification_channel_id}>)")
        else:
            description_lines.append("Verification channel: N/A")

        # Add archive channel ID
        if self.archive_channel_id:
            is_command, is_valid_command = CommandProcessor.get_is_command(self.archive_channel_id)
            if is_command:
                if is_valid_command:
                    description_lines.append(f"Archive channel: (COMMAND) `{self.archive_channel_id}`")
                else:
                    description_lines.append(f"Archive channel: (COMMAND::INVALID) `{self.archive_channel_id}`")
            else:
                description_lines.append(f"Archive channel: `{self.archive_channel_id}` (<#{self.archive_channel_id}>)")
        else:
            description_lines.append("Archive channel: N/A")

        # Add given role ID
        if self.role_id:
            is_command, is_valid_command = CommandProcessor.get_is_command(self.role_id)
            if is_command:
                if is_valid_command:
                    description_lines.append(f"Given role: (COMMAND) `{self.role_id}`")
                else:
                    description_lines.append(f"Given role: (COMMAND::INVALID) `{self.role_id}`")
            else:
                description_lines.append(f"Given role: `{self.role_id}` (<@&{self.role_id}>)")
        else:
            description_lines.append("Given role: N/A")

        # Add all our lines dab
        embed.description = '\n'.join(description_lines)

        # Add the user
        if brief is False:
            embed.add_field(name="Discord User", value="In this field, the owner of the created profile will be pinged.", inline=False)

        # Set the colour if there is one to set
        if self.colour:
            embed.colour = self.colour

        # Add each of the fields
        text = []
        char_limit_text = []
        for index, f in enumerate(fields):
            if f.deleted:
                continue

            # Work out the field type
            field_type_string = str(f.field_type)
            is_command, is_valid_command = CommandProcessor.get_is_command(f.prompt)
            if is_command:
                if is_valid_command:
                    field_type_string = "COMMAND"
                else:
                    field_type_string = "COMMAND::INVALID"

            # Wew let's add this jazz
            if brief:
                text.append(f"#{f.index} **{f.name}** ({field_type_string})")
                char_limit_text.append((f.index, f.name, field_type_string))
            else:
                embed.add_field(
                    name=f.name,
                    value=f'Field ID `{f.field_id}` at position {index} with index {f.index}, type `{field_type_string}`.```\n{f.prompt}```',
                    inline=False
                )

        # If we're being brief, then just add all the field text at once
        if brief:
            if not text:
                text = ["No fields added"]
            if len('\n'.join(text)) > 1000:
                for index, name, ftype in char_limit_text:
                    embed.add_field(
                        name=name,
                        value=f"#{index} ({ftype})",
                        inline=False,
                    )
            else:
                embed.add_field(
                    name="Fields",
                    value='\n'.join(text),
                    inline=False,
                )

        # Add a footer to our embed
        bot.set_footer_from_config(embed)

        # Return embed
        return embed
