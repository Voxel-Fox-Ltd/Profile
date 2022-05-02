from __future__ import annotations

from typing import TYPE_CHECKING, Union, Optional, List, Dict, Type
import uuid
import re
import operator

import discord
from discord.ext import commands, vbu

from cogs.utils.profiles.field import Field
from cogs.utils.profiles.command_processor import CommandProcessor, InvalidCommandText

if TYPE_CHECKING:
    from .user_profile import UserProfile


class TemplateNotFoundError(commands.BadArgument):
    """
    The template that the user has searched for isn't found.
    """

    def __init__(self, template_name: Optional[str] = None):
        if template_name:
            message = f"There's no template with the name `{template_name}` on this guild."
        else:
            message = "The given template could not be found."
        super().__init__(message)


class TemplateSendError(commands.BadArgument):
    """
    The bot failed to send the profile.
    """

    pass


class TemplateVerificationChannelError(TemplateSendError):
    """
    The bot failed to send a profile to the verification channel.
    """

    pass


class TemplateArchiveChannelError(TemplateSendError):
    """
    The bot failed to send a profile to the archive channel.
    """

    pass


class TemplateRoleAddError(TemplateSendError):
    """
    The bot failed to add a role to the user.
    """

    pass


class Template(object):
    """
    A class for an abstract template object that's saved to guild.
    This contains no user data, but rather the metadata for the template itself.

    Parameters
    -----------
    template_id: Union[:class:`str`, :class:`uuid.UUID`]
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
    template_id: Union[:class:`str`, :class:`uuid.UUID`]
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
        "template_id", "colour", "guild_id", "verification_channel_id", "name",
        "archive_channel_id", "role_id", "max_profile_count", "all_fields",
        "application_command_id",
    )
    TEMPLATE_ID_REGEX = re.compile(r"^(?P<uuid>.{8}-.{4}-.{4}-.{4}-.{12})$")
    SLASH_COMMAND_ARG_TYPE = discord.ApplicationCommandOptionType.string

    def __init__(
            self,
            template_id: uuid.UUID,
            colour: int,
            guild_id: int,
            verification_channel_id: Optional[str],
            name: str,
            archive_channel_id: Optional[str],
            role_id: Optional[str],
            max_profile_count: int,
            max_field_count: Optional[int] = None,
            application_command_id: Optional[int] = None,
            ):
        self.template_id: str = str(template_id)
        self.colour: int = colour
        self.guild_id: int = guild_id
        self.verification_channel_id: Optional[str] = verification_channel_id
        self.name: str = name
        self.archive_channel_id: Optional[str] = archive_channel_id
        self.role_id: Optional[str] = role_id
        self.max_profile_count: int = max_profile_count
        self.application_command_id: Optional[int] = application_command_id

        self.all_fields: Dict[str, Field] = dict()

    @property
    def id(self) -> str:
        """
        The ID of the template.
        """

        return self.template_id

    @property
    def should_send_message(self) -> bool:
        """
        Says whether or not this template should send a message
        (verification/archivation) on its submission.
        """

        return bool(self.verification_channel_id or self.archive_channel_id)

    def get_verification_channel_id(self, member: discord.Member) -> Optional[int]:
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

        return self._get_id_from_command(self.verification_channel_id, member)

    def get_archive_channel_id(self, member: discord.Member) -> Optional[int]:
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

        return self._get_id_from_command(self.archive_channel_id, member)

    def get_role_id(self, member: discord.Member) -> Optional[int]:
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
    def _get_id_from_command(text: Optional[str], member: discord.Member) -> Optional[int]:
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
        Returns a dict of `Field` objects for this particular profile.
        """

        return {
            i: o
            for i, o in self.all_fields.items()
            if o.deleted is False
        }

    @property
    def field_list(self) -> List[Field]:
        """
        Returns a list of `Field` objects - in order - for this profile.
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
            profile_rows = await db(
                """SELECT * FROM created_profile WHERE template_id=$1 AND user_id=$2""",
                self.template_id, user_id,
            )
        else:
            profile_rows = await db(
                """SELECT * FROM created_profile WHERE template_id=$1 AND user_id=$2 AND LOWER(name)=LOWER($3)""",
                self.template_id, user_id, profile_name,
            )

        # See if there was nothing provided
        if not profile_rows:
            return None

        # See if multiple were provided and no search string was given
        if profile_name is None and len(profile_rows) > 1:
            raise ValueError("Too many saved profiles to have no set profile name")

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
        profile_rows = await db(
            "SELECT * FROM created_profile WHERE template_id=$1 AND user_id=$2",
            self.template_id, user_id,
        )
        profiles = [UserProfile(**i, template=self) for i in profile_rows]
        if fetch_filled_fields:
            [await i.fetch_filled_fields(db) for i in profiles]
        return profiles

    async def fetch_all_profiles(
            self,
            db: vbu.Database,
            *,
            fetch_filled_fields: bool = True) -> List[UserProfile]:
        """
        Gets the filled profile for a given user

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
        profile_rows = await db(
            "SELECT * FROM created_profile WHERE template_id=$1",
            self.template_id,
        )
        profiles = [UserProfile(**i, template=self) for i in profile_rows]
        if fetch_filled_fields:
            [await i.fetch_filled_fields(db) for i in profiles]
        return profiles

    @classmethod
    async def fetch_template_by_id(
            cls,
            db: vbu.Database,
            template_id: str,
            *,
            fetch_fields: bool = True) -> Optional[Template]:
        """
        Get a template from the database via its ID.
        """

        # Grab the template
        template_rows = await db(
            "SELECT * FROM template WHERE template_id=$1",
            template_id,
        )
        if not template_rows:
            return None
        template = cls(**template_rows[0])
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
            fetch_fields: bool = True) -> Optional[Template]:
        """
        Get a template from the database via its name.
        """

        # Grab the template
        template_rows = await db(
            "SELECT * FROM template WHERE guild_id=$1 AND LOWER(name)=LOWER($2)",
            guild_id, template_name,
        )
        if not template_rows:
            return None
        template = cls(**template_rows[0])
        if fetch_fields:
            await template.fetch_fields(db)
        return template

    @classmethod
    async def fetch_all_templates_for_guild(
            cls: Type[Template],
            db: vbu.Database,
            guild_id: int,
            *,
            fetch_fields: bool = True) -> List[Template]:
        """
        Get all the templates for a given guild.
        """

        # Grab the template
        template_rows = await db("SELECT * FROM template WHERE guild_id=$1", guild_id)
        template_list = [cls(**i) for i in template_rows]
        if fetch_fields:
            for t in template_list:
                await t.fetch_fields(db)
        return template_list

    async def fetch_fields(self, db) -> Dict[str, Field]:
        """
        Fetch the fields for this template and store them in .all_fields.
        """

        field_rows = await db(
            "SELECT * FROM field WHERE template_id=$1",
            self.id,
        )
        self.all_fields.clear()
        for f in field_rows:
            field = Field(**f)
            self.all_fields[field.id] = field
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

    def build_embed(
            self,
            bot: vbu.Bot,
            ctx: Union[discord.Interaction, commands.Context, str],
            brief: bool = False) -> discord.Embed:
        """
        Create an embed to visualise all of the created fields and given information.
        """

        # Create the initial embed
        fields: List[Field] = self.field_list
        embed = vbu.Embed(use_random_colour=True, title=self.name)

        # Work out what goes in the description
        description_lines = [
            vbu.translation(ctx, "template", use_guild=True).gettext(
                "Template ID: `{template_id}`"
            ).format(template_id=self.template_id),
            vbu.translation(ctx, "template", use_guild=True).gettext(
                "Guild ID: `{guild_id}`"
            ).format(guild_id=self.guild_id),
            vbu.translation(ctx, "template", use_guild=True).gettext(
                "Maximum allowed profiles: `{max_profile_count}`"
            ).format(max_profile_count=self.max_profile_count),
            vbu.translation(ctx, "template", use_guild=True).gettext(
                "Application command ID: `{application_command_id}`"
            ).format(application_command_id=self.application_command_id),
        ]

        # Add verification channel ID
        verification_channel_str = vbu.translation(ctx, "template", use_guild=True).gettext("Verification channel: {value}")
        if self.verification_channel_id:
            is_command, is_valid_command = CommandProcessor.get_is_command(self.verification_channel_id)
            if is_command:
                if is_valid_command:
                    description_lines.append(verification_channel_str.format(value=f"(COMMAND) `{self.verification_channel_id}`"))
                else:
                    description_lines.append(verification_channel_str.format(value=f"(COMMAND::INVALID) `{self.verification_channel_id}`"))
            else:
                description_lines.append(verification_channel_str.format(value=f"`{self.verification_channel_id}` (<#{self.verification_channel_id}>)"))
        else:
            description_lines.append(verification_channel_str.format(value="N/A"))

        # Add archive channel ID
        archive_channel_str = vbu.translation(ctx, "template", use_guild=True).gettext("Archive channel: {value}")
        if self.archive_channel_id:
            is_command, is_valid_command = CommandProcessor.get_is_command(self.archive_channel_id)
            if is_command:
                if is_valid_command:
                    description_lines.append(archive_channel_str.format(value=f"(COMMAND) `{self.archive_channel_id}`"))
                else:
                    description_lines.append(archive_channel_str.format(value=f"(COMMAND::INVALID) `{self.archive_channel_id}`"))
            else:
                description_lines.append(archive_channel_str.format(value=f"`{self.archive_channel_id}` (<#{self.archive_channel_id}>)"))
        else:
            description_lines.append(archive_channel_str.format(value="N/A"))

        # Add given role ID
        given_role_str = vbu.translation(ctx, "template", use_guild=True).gettext("Given role: {value}")
        if self.role_id:
            is_command, is_valid_command = CommandProcessor.get_is_command(self.role_id)
            if is_command:
                if is_valid_command:
                    description_lines.append(given_role_str.format(value=f"(COMMAND) `{self.role_id}`"))
                else:
                    description_lines.append(given_role_str.format(value=f"(COMMAND::INVALID) `{self.role_id}`"))
            else:
                description_lines.append(given_role_str.format(value=f"`{self.role_id}` (<@&{self.role_id}>)"))
        else:
            description_lines.append(given_role_str.format(value="N/A"))

        # Add all our lines dab
        embed.description = '\n'.join(description_lines)

        # Add the user
        if brief is False:
            embed.add_field(
                name=vbu.translation(ctx, "template", use_guild=True).gettext(
                    "Discord User",
                ),
                value=vbu.translation(ctx, "template", use_guild=True).gettext(
                    "In this field, the owner of the created profile will be pinged.",
                ),
                inline=False,
            )

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
                    value=vbu.translation(ctx, "template", use_guild=True).gettext(
                        "Field ID `{field_id}` at position {position_index} with index "
                        "{field_index}, type `{type}`.```\n{prompt}```",
                    ).format(
                        field_id=f.field_id,
                        position_index=index,
                        field_index=f.index,
                        type=field_type_string,
                        prompt=f.prompt,
                    ),
                    inline=False,
                )

        # If we're being brief, then just add all the field text at once
        if brief:
            if not text:
                text = [vbu.translation(ctx, "template", use_guild=True).gettext("No fields have been added to this template.")]
            if len('\n'.join(text)) > 1000:
                for index, name, ftype in char_limit_text:
                    embed.add_field(
                        name=name,
                        value=f"#{index} ({ftype})",
                        inline=False,
                    )
            else:
                embed.add_field(
                    name=vbu.translation(ctx, "template", use_guild=True).gettext("Fields"),
                    value='\n'.join(text),
                    inline=False,
                )

        # Add a footer to our embed
        bot.set_footer_from_config(embed)

        # Return embed
        return embed
