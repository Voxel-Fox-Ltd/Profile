from __future__ import annotations

from typing import TYPE_CHECKING, Union, Optional, List, Dict, Type
from typing_extensions import Self
import uuid
import operator

import discord
from discord.ext import vbu

from cogs.utils.profiles.field import Field
from cogs.utils.profiles.command_processor import CommandProcessor, InvalidCommandText

if TYPE_CHECKING:
    from .user_profile import UserProfile


def _(a: str) -> str:
    return a


# class TemplateNotFoundError(commands.BadArgument):
#     """
#     The template that the user has searched for isn't found.
#     """

#     def __init__(self, template_name: Optional[str] = None):
#         if template_name:
#             message = f"There's no template with the name `{template_name}` on this guild."
#         else:
#             message = "The given template could not be found."
#         super().__init__(message)


# class TemplateSendError(commands.BadArgument):
#     """
#     The bot failed to send the profile.
#     """

#     pass


# class TemplateVerificationChannelError(TemplateSendError):
#     """
#     The bot failed to send a profile to the verification channel.
#     """

#     pass


# class TemplateArchiveChannelError(TemplateSendError):
#     """
#     The bot failed to send a profile to the archive channel.
#     """

#     pass


# class TemplateRoleAddError(TemplateSendError):
#     """
#     The bot failed to add a role to the user.
#     """

#     pass


class Template(object):
    """
    A class for an abstract template object that's saved to guild.
    This contains no user data, but rather the metadata for the template itself.

    Parameters
    -----------
    id: Union[:class:`str`, :class:`uuid.UUID`]
        The ID of the template.
    colour: :class:`int`
        The colour to be used on all of the profiles. If the colour
        is ``0`` or ``None`` then a random colour is used.
    guild_id: :class:`int`
        The guild that the template is a part of.
    verification_channel_id: Optional[:class:`str`]
        The ID of the template's verification channel. Set as a string
        to allow for commands.
    name: :class:`str`
        The name of the template.
    archive_channel_id: Optional[:class:`str`]
        The ID of the template's archive channel. Set as a string
        to allow for commands.
    role_id: Optional[:class:`str`]
        The ID of the template's role. Set as a string
        to allow for commands.
    max_profile_count: :class:`int`
        The maximum number of profiles that users are allowed to
        create for this template.
    application_command_id: :class:`int`
        The ID of the application command associated with this template.

    Attributes
    -----------
    id: Union[:class:`str`, :class:`uuid.UUID`]
        The ID of the template.
    colour: :class:`int`
        The colour to be used on all of the profiles. If the colour
        is ``0`` or ``None`` then a random colour is used.
    guild_id: :class:`int`
        The guild that the template is a part of.
    verification_channel_id: :class:`str`
        The ID of the template's verification channel. Set as a string
        to allow for commands.
    name: :class:`str`
        The name of the template.
    archive_channel_id: :class:`str`
        The ID of the template's archive channel. Set as a string
        to allow for commands.
    role_id: :class:`str`
        The ID of the template's role. Set as a string
        to allow for commands.
    max_profile_count: :class:`int`
        The maximum number of profiles that users are allowed to
        create for this template.
    all_fields: Dict[:class:`str`, :class:`cogs.utils.profiles.field.Field`]
        All of the fields for the template.
    application_command_id: Optional[:class:`int`]
        The ID of the application command associated with this template.
    """

    __slots__ = (
        "_id",
        "colour",
        "guild_id",
        "verification_channel_id",
        "name",
        "archive_channel_id",
        "role_id",
        "max_profile_count",
        "all_fields",
        "application_command_id",
        "context_command_id",
        "deleted",
    )

    def __init__(
            self,
            id: Optional[uuid.UUID],
            name: str,
            guild_id: int,
            application_command_id: Optional[int] = None,
            context_command_id: Optional[int] = None,
            colour: Optional[int] = None,
            verification_channel_id: Optional[str] = None,
            archive_channel_id: Optional[str] = None,
            role_id: Optional[str] = None,
            max_profile_count: int = 5,
            deleted: bool = False):
        self._id: Optional[uuid.UUID] = id
        self.name: str = name
        self.guild_id: int = guild_id
        self.application_command_id: Optional[int] = application_command_id
        self.colour: Optional[int] = colour
        self.verification_channel_id: Optional[str] = verification_channel_id
        self.archive_channel_id: Optional[str] = archive_channel_id
        self.role_id: Optional[str] = role_id
        self.max_profile_count: int = max_profile_count
        self.context_command_id: Optional[int] = context_command_id
        self.deleted: bool = deleted

        self.all_fields: Dict[str, Field] = dict()

    @property
    def id(self) -> str:
        if self._id is None:
            self.id = uuid.uuid4()
        return str(self._id)

    @id.setter
    def id(self, value: Union[str, uuid.UUID]):
        if isinstance(value, uuid.UUID):
            self._id = value
        else:
            self._id = uuid.UUID(value)

    def get_verification_channel_id(
            self,
            member: discord.Member) -> Optional[int]:
        """
        Get the correct verification channel ID for the given member.

        Parameters
        -----------
        member: :class:`discord.Member`
            The member whose channel you want to get.

        Returns
        --------
        Optional[:class:`int`]
            The ID of the channel for this user's profile.
        """

        return self._get_id_from_command(
            self.verification_channel_id,
            member,
        )

    def get_archive_channel_id(
            self,
            member: discord.Member) -> Optional[int]:
        """
        Get the correct archive channel ID for a given member.

        Parameters
        -----------
        member: :class:`discord.Member`
            The member whose channel you want to get.

        Returns
        --------
        Optional[:class:`int`]
            The ID of the channel for this user's profile.
        """

        return self._get_id_from_command(
            self.archive_channel_id,
            member,
        )

    def get_role_id(
            self,
            member: discord.Member) -> Optional[int]:
        """
        Get the correct role ID for a given member.

        Parameters
        -----------
        member: :class:`discord.Member`
            The member whose role you want to get.

        Returns
        --------
        Optional[:class:`int`]
            The ID of the role for this user's profile.
        """

        return self._get_id_from_command(self.role_id, member)

    @staticmethod
    def _get_id_from_command(
            text: Optional[str],
            member: discord.Member) -> Optional[int]:
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
    def fields(self) -> Dict[str, Field]:
        """
        Returns a dict of non-deleted `Field` objects for the template.
        """

        return {
            i: o
            for i, o in self.all_fields.items()
            if o.deleted is False
        }

    @property
    def field_list(self) -> List[Field]:
        """
        Returns a list of `utils.Field` objects (in order) for the template.
        """

        return sorted(self.fields.values(), key=operator.attrgetter("index"))

    async def fetch_profile_for_user(
            self,
            db: vbu.Database,
            user_id:int,
            profile_name: Optional[str] = None,
            *,
            fetch_filled_fields: bool = True) -> Optional[UserProfile]:
        """
        Gets the filled profile for a given user.

        Parameters
        -----------
        db: :class:`vbu.Database`
            An active connection to the database.
        user_id: :class:`int`
            The ID of the user you want to grab the information for.
        profile_name: Optional[:class:`str`]
            The name of the profile you want to grab.
        fetch_filled_fields: Optional[:class:`bool`]
            Whether or not to populate the filled fields for the `UserProfile`.

        Raises
        -------
        :class:`ValueError`
            If no profile name was provided and multiple profiles were retrieved.

        Returns
        -------
        :class:`cogs.utils.profiles.user_profile.UserProfile`
            The user profile that you asked for.
        :class:`None`
            No profile mathcing the given name could be found.
        """

        # Grab our imports here to avoid circular importing
        from .user_profile import UserProfile

        # Grab the user profile
        if profile_name is None:
            profile_rows = await db.call(
                """
                SELECT
                    *
                FROM
                    created_profiles
                WHERE
                    template_id = $1
                AND
                    user_id = $2
                """,
                self.id, user_id,
            )
        else:
            profile_rows = await db.call(
                """
                SELECT
                    *
                FROM
                    created_profiles
                WHERE
                    template_id = $1
                AND
                    user_id = $2
                AND
                    LOWER(name) = LOWER($3)
                """,
                self.id, user_id, profile_name,
            )

        # See if there was nothing provided
        if not profile_rows:
            return None

        # See if multiple were provided and no search string was given
        if profile_name is None and len(profile_rows) > 1:
            raise ValueError()

        # Make a profile to return
        user_profile = UserProfile(**profile_rows[0], template=self)

        # Fetch the filled fields if the user requested them
        if fetch_filled_fields:
            await user_profile.fetch_filled_fields(db)

        # Return the profile
        return user_profile

    async def fetch_all_profiles_for_user(
            self,
            db: vbu.Database,
            user_id: int,
            *,
            fetch_filled_fields: bool = True) -> List[UserProfile]:
        """
        Gets the filled profile for a given user.

        Parameters
        -----------
        db: :class:`vbu.Database`
            An active connection to the database.
        user_id: :class:`int`
            The ID of the user you want to grab the information for.
        fetch_filled_fields: Optional[:class:`bool`]
            Whether or not to populate the filled fields for the UserProfile.

        Returns
        --------
        List[cogs.vbu.profiles.user_profile.UserProfile]
            A list of UserProfiles for the given user.
        """

        # Grab our imports here to avoid circular importing
        from .user_profile import UserProfile

        # Grab the user profile
        profile_rows = await db.call(
            """
            SELECT
                *
            FROM
                created_profiles
            WHERE
                template_id = $1
            AND
                user_id = $2
            """,
            self.id, user_id,
        )
        profiles = [
            UserProfile(**i, template=self)
            for i in profile_rows
        ]
        if fetch_filled_fields:
            [
                await i.fetch_filled_fields(db)
                for i in profiles
            ]
        return profiles

    async def fetch_all_profiles(
            self,
            db: vbu.Database,
            *,
            fetch_filled_fields: bool = True) -> List[UserProfile]:
        """
        Gets all of the filled profiles for this template.

        Parameters
        -----------
        db: :class:`vbu.Database`
            An active connection to the database.
        fetch_filled_fields: Optional[:class:`bool`]
            Whether or not to populate the filled fields for the UserProfile.

        Returns
        --------
        List[cogs.vbu.profiles.user_profile.UserProfile]
            A list of UserProfiles for the given template.
        """

        # Grab our imports here to avoid circular importing
        from .user_profile import UserProfile

        # Grab the user profile
        profile_rows = await db.call(
            """
            SELECT
                *
            FROM
                created_profiles
            WHERE
                template_id = $1
            """,
            self.id,
        )
        profiles = [
            UserProfile(**i, template=self)
            for i in profile_rows
        ]
        if fetch_filled_fields:
            [
                await i.fetch_filled_fields(db)
                for i in profiles
            ]
        return profiles

    @classmethod
    async def fetch_template_by_id(
            cls,
            db: vbu.Database,
            template_id: str,
            *,
            fetch_fields: bool = True,
            allow_deleted: bool = False) -> Optional[Template]:
        """
        Get a template from the database via its ID.
        """

        # Grab the template
        template_rows = await db.call(
            """
            SELECT
                *
            FROM
                templates
            WHERE
                id = $1
            """,
            template_id,
        )
        if not template_rows:
            return None
        template = cls(**template_rows[0])
        if template.deleted and not allow_deleted:
            return None
        if fetch_fields:
            await template.fetch_fields(db)
        return template

    @classmethod
    async def fetch_template_by_name(
            cls,
            db: vbu.Database,
            guild_id: int,
            template_name: str,
            *,
            fetch_fields: bool = True,
            allow_deleted: bool = False) -> Optional[Template]:
        """
        Get a template from the database via its name.
        """

        # Grab the template
        template_rows = await db.call(
            """
            SELECT
                *
            FROM
                templates
            WHERE
                guild_id = $1
            AND
                LOWER(name) = LOWER($2)
            """,
            guild_id, template_name,
        )
        if not template_rows:
            return None
        template = cls(**template_rows[0])
        if template.deleted and not allow_deleted:
            return None
        if fetch_fields:
            await template.fetch_fields(db)
        return template

    @classmethod
    async def fetch_all_templates_for_guild(
            cls: Type[Template],
            db: vbu.Database,
            guild_id: int,
            *,
            fetch_fields: bool = True,
            allow_deleted: bool = False) -> List[Template]:
        """
        Get all the templates for a given guild.
        """

        # Grab the template
        additional = "AND deleted = FALSE" if not allow_deleted else ""
        template_rows = await db.call(
            """
            SELECT
                *
            FROM
                templates
            WHERE
                guild_id = $1
            {0}
            """.format(additional),
            guild_id,
        )
        template_list = [
            cls(**i)
            for i in template_rows
        ]
        if fetch_fields:
            for t in template_list:
                await t.fetch_fields(db)
        return template_list

    async def fetch_fields(self, db: vbu.Database) -> Dict[str, Field]:
        """
        Fetch the fields for this template and store them in .all_fields.
        """

        field_rows = await db.call(
            """
            SELECT
                *
            FROM
                fields
            WHERE
                template_id = $1
            """,
            self.id,
        )
        self.all_fields.clear()
        for f in field_rows:
            field = Field(**f)
            self.all_fields[field.id] = field
        return self.all_fields

    async def update(self, db: vbu.Database, **kwargs) -> Self:
        """
        Update multiple attributes of the template instance both in cache
        and in the database.
        Will only work on instances that have an ID set.
        """

        for i, o in kwargs.items():
            setattr(self, i, o)
        await db.call(
            """
            INSERT INTO
                templates
                (
                    id,
                    name,
                    guild_id,
                    application_command_id,
                    colour,
                    verification_channel_id,
                    archive_channel_id,
                    role_id,
                    max_profile_count,
                    context_command_id,
                    deleted
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
                    $8,
                    $9,
                    $10,
                    $11
                )
            ON CONFLICT
                (id)
            DO UPDATE
            SET
                name = $2,
                guild_id = $3,
                application_command_id = $4,
                colour = $5,
                verification_channel_id = $6,
                archive_channel_id = $7,
                role_id = $8,
                max_profile_count = $9,
                context_command_id = $10,
                deleted = $11
            """,
            self.id,
            self.name,
            self.guild_id,
            self.application_command_id,
            self.colour,
            self.verification_channel_id,
            self.archive_channel_id,
            self.role_id,
            self.max_profile_count,
            self.context_command_id,
            self.deleted,
        )
        return self

    # @vbu.i18n(__name__, 2)
    def build_embed(
            self,
            bot: vbu.Bot,
            interaction: discord.Interaction) -> discord.Embed:
        """
        Create an embed to visualise all of the created fields and
        given information.
        """

        # Create the initial embed
        fields = self.field_list
        embed = vbu.Embed(use_random_colour=True, title=self.name)

        # Work out what goes in the description
        description_lines = [
            _("Template ID: `{0}`").format(self.id),
            _("Guild ID: `{0}`").format(self.guild_id),
            _("Maximum allowed profiles: {0}").format(self.max_profile_count),
        ]

        # Add archive channel ID
        archive_channel_str = _("Archive channel: {0}")
        if self.archive_channel_id:
            is_command, is_valid_command = CommandProcessor.get_is_command(
                self.archive_channel_id,
            )
            if is_command and is_valid_command:
                val = f"(COMMAND) `{self.archive_channel_id}`"
            elif is_command:
                val = f"(COMMAND::INVALID) `{self.archive_channel_id}`"
            else:
                val = (
                    f"`{self.archive_channel_id}` "
                    f"(<#{self.archive_channel_id}>)"
                )
        else:
            val = "N/A"
        description_lines.append(archive_channel_str.format(val))

        # Add verification channel ID
        verification_channel_str = _("Verification channel: {0}")
        if self.verification_channel_id:
            is_command, is_valid_command = CommandProcessor.get_is_command(
                self.verification_channel_id,
            )
            if is_command and is_valid_command:
                val = f"(COMMAND) `{self.verification_channel_id}`"
            elif is_command:
                val = f"(COMMAND::INVALID) `{self.verification_channel_id}`"
            else:
                val = (
                    f"`{self.verification_channel_id}` "
                    f"(<#{self.verification_channel_id}>)"
                )
        else:
            val = "N/A"
        description_lines.append(verification_channel_str.format(val))

        # Add given role ID
        role_str = _("Given role: {0}")
        if self.role_id:
            is_command, is_valid_command = CommandProcessor.get_is_command(
                self.role_id,
            )
            if is_command and is_valid_command:
                val = f"(COMMAND) `{self.role_id}`"
            elif is_command:
                val = f"(COMMAND::INVALID) `{self.role_id}`"
            else:
                val = (
                    f"`{self.role_id}` "
                    f"(<@&{self.role_id}>)"
                )
        else:
            val = "N/A"
        description_lines.append(role_str.format(val))

        # Add all of our lines
        embed.description = '\n'.join(description_lines)

        # Add a footer to our embed
        bot.set_footer_from_config(embed)

        # Return embed
        return embed
