from __future__ import annotations

from typing import Generic, TypeVar, Union, Optional, Dict, List
from typing_extensions import Self
import uuid
import operator

import discord
from discord.ext import commands, vbu

from .template import Template
from .filled_field import FilledField
from .field import Field
from .field_type import ImageField
from .command_processor import CommandProcessor
from ..utils import pad_field_prompt_value


T = TypeVar('T', Template, None)


class UserProfile(Generic[T]):
    """
    A filled user template.
    This represents a template filled by a user containing all of their
    relevant information.
    This class itself does not contain the user's data, but rather the
    metadata about their given profile,
    eg whether it's been verified etc; the user's data is stored inthe
    FilledField objects associated
    with this.

    Parameters
    -----------
    id: Union[:class:`str`, :class:`uuid.UUID`]
        The ID of the profile.
    user_id: :class:`int`
        The ID of the user whose profile this is.
    name: :class:`str`
        The name of the profile.
    template_id: Union[:class:`str`, :class:`uuid.UUID`]
        The template ID of the profile.
    verified: :class:`bool`
        Whether or not the profile has been verified.
    posted_message_id: Optional[:class:`int`]
        The ID of the message that was posted into the archive or
        verification channel.
    posted_channel_id: Optional[:class:`int`]
        The ID of the message's channel that was posted into the
        archive or verification channel.
    template: Optional[:class:`cogs.utils.profiles.template.Template`]
        The template object associated with this profile.

    Attributes
    -----------
    user_id: :class:`int`
        The ID of the user whose profile this is.
    name: :class:`str`
        The name of the profile.
    template_id: Union[:class:`str`, :class:`uuid.UUID`]
        The template ID of the profile.
    verified: :class:`bool`
        Whether or not the profile has been verified.
    posted_message_id: Optional[:class:`int`]
        The ID of the message that was posted into the archive or
        verification channel.
    posted_channel_id: Optional[:class:`int`]
        The ID of the message's channel that was posted into the
        archive or verification channel.
    template: Optional[:class:`cogs.utils.profiles.template.Template`]
        The template object associated with this profile.
    all_filled_fields: Dict[:class:`str`, :class:`cogs.utils.profiles.filled_field.FilledField`]
        The filled fields that are associated with this profile.
    """

    __slots__ = (
        "_id",
        "user_id",
        "name",
        "_template_id",
        "verified",
        "all_filled_fields",
        "template",
        "posted_message_id",
        "posted_channel_id",
        "deleted",
        "draft",
    )

    def __init__(
            self,
            *,
            id: Union[str, uuid.UUID, None] = None,
            user_id: Optional[int] = None,
            name: Optional[str] = None,
            template_id: Union[str, uuid.UUID, None] = None,
            verified: bool = False,
            posted_message_id: Optional[int] = None,
            posted_channel_id: Optional[int] = None,
            template: T = None,
            deleted: bool = False,
            draft: bool = True):
        self._id = id
        self.user_id: Optional[int] = user_id
        self.name: Optional[str] = name
        self._template_id = template_id
        self.verified: bool = verified
        self.posted_message_id = posted_message_id
        self.posted_channel_id = posted_channel_id
        self.deleted: bool = deleted
        self.draft: bool = draft  # Whether or not the profile has left the editing stage
        self.all_filled_fields: Dict[str, FilledField] = dict()
        self.template: T = template

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

    @property
    def template_id(self) -> str:
        if self._template_id is None:
            self._template_id = uuid.uuid4()
        return str(self._template_id)

    @template_id.setter
    def template_id(self, value: Union[str, uuid.UUID]):
        if isinstance(value, uuid.UUID):
            self.template_id = value
        else:
            self.template_id = uuid.UUID(value)

    @property
    def display_name(self) -> Optional[str]:
        if self.name is None:
            return None
        return self.name.split(" ")[-1]

    @classmethod
    async def fetch_profile_by_id(
            cls,
            db: vbu.Database,
            profile_id: str) -> Optional[Self]:
        """
        Fetch the fields for this profile and store them in .all_filled_fields.
        """

        # Get the fields that have been filled in
        profile_rows = await db(
            """
            SELECT
                *
            FROM
                created_profiles
            WHERE
                id = $1
            """,
            profile_id,
        )
        if not profile_rows:
            return None
        return cls(**profile_rows[0])

    async def fetch_filled_fields(self, db) -> Dict[str, FilledField]:
        """
        Fetch the fields for this profile and store them in .all_filled_fields.
        """

        # Check if there's a template
        if self.template is None or len(self.template.all_fields) == 0:
            await self.fetch_template(db, fetch_fields=True)

        # Make SURE there's a template
        if self.template is None:
            return {}

        # Get the fields that have been filled in
        field_rows = await db(
            """
            SELECT
                *
            FROM
                filled_fields
            WHERE
                profile_id = $1
            AND
                field_id = ANY($2::UUID[])
            """,
            self.id, self.template.all_fields.keys(),
        )
        self.all_filled_fields.clear()

        # Add them to the cache
        for f in field_rows:
            filled = FilledField(**f)
            filled.field = self.template.all_fields[filled.field_id]
            self.all_filled_fields[filled.field_id] = filled

        # And return
        return self.all_filled_fields

    async def fetch_template(
            self,
            db: vbu.Database,
            *,
            fetch_fields: bool = True,
            allow_deleted: bool = False) -> Optional[Template]:
        """
        Fetch the template for this field and store it in .template.
        """

        template = await Template.fetch_template_by_id(
            db,
            self.template_id,
            fetch_fields=fetch_fields,
            allow_deleted=allow_deleted,
        )
        self.template = template  # pyright: ignore
        return template

    async def fetch_message(
            self,
            bot: discord.Client) -> discord.Message | None:
        """
        Fetch the message associated with this profile's archivation/submission.

        Parameters
        -----------
        bot: :class:`discord.Client`
            The bot instance that can fetch this message.

        Returns
        --------
        Optional[:class:`discord.Message`]
            The message associated with the profile.
        """

        # See if we should bother asking the API
        if self.posted_channel_id is None or self.posted_message_id is None:
            return None

        # Get channel
        try:
            channel = (
                bot.get_channel(self.posted_channel_id)
                or
                await bot.fetch_channel(self.posted_channel_id)
            )
        except discord.HTTPException:
            return None
        assert isinstance(channel, discord.abc.MessageableChannel)

        # Get message
        try:
            return await channel.fetch_message(self.posted_message_id)
        except discord.HTTPException:
            pass

        # Oh well
        return None

    async def delete_message(self, bot) -> None:
        """
        Delete the posted archive message.
        """

        m = await self.fetch_message(bot)
        if not m:
            return
        try:
            await m.delete()
        except discord.HTTPException:
            pass

    @property
    def filled_fields(self) -> Dict[str, FilledField]:
        return {
            i: o
            for i, o in self.all_filled_fields.items()
            if
                o.field is not None
            and
                o.field.deleted is False
            and
                o.value is not None
        }

    @vbu.i18n(__name__, 2)
    def build_embed(
            self,
            bot: vbu.Bot,
            ctx: discord.Interaction | commands.Context | str,
            member: discord.Member | None = None) -> vbu.Embed:
        """
        Converts the filled profile into an embed.
        """

        # See if they're the right person
        if member and member.id != self.user_id:
            raise ValueError("Invalid user passed to build embed - wrong person for this profile")
        if member and not isinstance(member, discord.Member):
            raise ValueError("Invalid member object passed to build embed - not a guild member")

        # Create the initial embed
        embed = vbu.Embed(use_random_colour=True)
        if self.template is None:
            raise AttributeError("Missing template field for user profile")
        embed.title = f"{self.template.display_name} | {self.display_name}"
        if self.template.colour:
            embed.colour = self.template.colour

        # Add the user
        embed.add_field(
            name=_("Discord User"),
            value=f"<@{self.user_id}>",
        )

        # Add the fields
        fields: List[FilledField[Field] | Field]
        fields = sorted(
            self.filled_fields.values(),
            key=operator.attrgetter("field.index"),
        )
        for f in self.template.field_list:
            if f.deleted:
                continue
            if f.is_command:
                fields.append(f)

        # Add each of the fields
        for f in fields:

            # Make it easier to iterate
            field = f if isinstance(f, Field) else f.field

            # Make sure we only do this for fields with values
            if not field:
                continue
            field_value: str
            if field.deleted:
                continue

            # Filter deleted or unset data
            if isinstance(f, Field):
                field_value = CommandProcessor.get_value(field.prompt, member)
                if field_value is None or field_value == "":
                    continue
            else:
                if "\n" in f.field.prompt.strip():
                    field_value = ""
                    for x, y in zip(*pad_field_prompt_value(f.field.prompt, f.value)):
                        field_value += f"{x.strip()}: {y.strip()}\n"
                else:
                    field_value = f.value
            field_value = field_value.strip()

            # Set data
            if field.field_type == ImageField:
                embed.set_image(url=field_value)
            elif field_value:
                embed.add_field(
                    name=field.name,
                    value=field_value,
                    inline=len(field_value) <= 100,
                )

        # Add a footer to our embed
        bot.set_footer_from_config(embed)

        # Return embed
        return embed

    async def update(self, db: vbu.Database, **kwargs) -> Self:
        """
        Update multiple attributes of the profile instance both in cache
        and in the database.
        """

        for i, o in kwargs.items():
            setattr(self, i, o)
        await db.call(
            """
            INSERT INTO
                created_profiles
                (
                    id,
                    user_id,
                    name,
                    template_id,
                    verified,
                    posted_message_id,
                    posted_channel_id,
                    deleted,
                    draft
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
                    $9
                )
            ON CONFLICT
                (id)
            DO UPDATE
            SET
                user_id = $2,
                name = $3,
                template_id = $4,
                verified = $5,
                posted_message_id = $6,
                posted_channel_id = $7,
                deleted = $8,
                draft = $9
            """,
            self.id,
            self.user_id,
            self.name,
            self.template_id,
            self.verified,
            self.posted_message_id,
            self.posted_channel_id,
            self.deleted,
            self.draft,
        )
        return self
