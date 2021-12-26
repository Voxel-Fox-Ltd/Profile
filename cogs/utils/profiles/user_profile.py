from __future__ import annotations

import typing
import uuid
import operator

import discord
from discord.ext import vbu

from cogs.utils.profiles.template import Template
from cogs.utils.profiles.filled_field import FilledField
from cogs.utils.profiles.field_type import ImageField
from cogs.utils.profiles.command_processor import CommandProcessor, InvalidCommandText


class UserProfile(object):
    """
    A filled user template.
    This represents a template filled by a user containing all of their relevant information.
    This class itself does not contain the user's data, but rather the metadata about their given profile,
    eg whether it's been verified etc; the user's data is stored inthe FilledField objects associated
    with this.

    Parameters
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
        The ID of the message that was posted into the archive or verification channel.
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
        The ID of the message that was posted into the archive or verification channel.
    posted_channel_id: Optional[:class:`int`]
        The ID of the message's channel that was posted into the
        archive or verification channel.
    template: Optional[:class:`cogs.utils.profiles.template.Template`]
        The template object associated with this profile.
    all_filled_fields: Dict[:class:`str`, :class:`cogs.utils.profiles.filled_field.FilledField`]
        The filled fields that are associated with this profile.
    """

    __slots__ = (
        "user_id", "name", "template_id", "verified", "all_filled_fields",
        "template", "posted_message_id", "posted_channel_id",
    )

    def __init__(
            self,
            user_id: int,
            name: str,
            template_id: typing.Union[str, uuid.UUID],
            verified: bool,
            posted_message_id: int = None,
            posted_channel_id: int = None,
            template: Template = None):
        self.user_id: int = user_id
        self.name: str = name
        self.template_id: str = str(template_id)
        self.verified: bool = verified
        self.posted_message_id = posted_message_id
        self.posted_channel_id = posted_channel_id
        self.all_filled_fields: typing.Dict[str, FilledField] = dict()
        self.template: typing.Optional[Template] = template

    async def fetch_filled_fields(self, db) -> typing.Dict[str, FilledField]:
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
            "SELECT * FROM filled_field WHERE user_id=$1 AND name=$2 AND field_id=ANY($3::UUID[])",
            self.user_id, self.name, self.template.all_fields.keys(),
        )
        self.all_filled_fields.clear()

        # Add them to the cache
        for f in field_rows:
            filled = FilledField(**f)
            filled.field = self.template.all_fields[filled.field_id]
            self.all_filled_fields[filled.field_id] = filled

        # And return
        return self.all_filled_fields

    async def fetch_template(self, db, *, fetch_fields: bool = True) -> typing.Optional[Template]:
        """
        Fetch the template for this field and store it in .template.
        """

        template = await Template.fetch_template_by_id(db, self.template_id, fetch_fields=fetch_fields)
        self.template = template
        return template

    async def fetch_message(self, bot: discord.Client) -> typing.Optional[discord.Message]:
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
            channel = bot.get_channel(self.posted_channel_id) or await bot.fetch_channel(self.posted_channel_id)
        except discord.HTTPException:
            return None

        # Get message
        try:
            return await channel.fetch_message(self.posted_message_id)  # type: ignore
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
    def filled_fields(self) -> typing.Dict[str, FilledField]:
        return {
            i: o
            for i, o in self.all_filled_fields.items()
            if o.field is not None and o.field.deleted is False and o.value is not None
        }

    def build_embed(self, bot, member: typing.Optional[discord.Member] = None) -> vbu.Embed:
        """
        Converts the filled profile into an embed.
        """

        # See if they're the right person
        if member and member.id != self.user_id:
            raise ValueError("Invalid user passed to build embed")
        if member and not isinstance(member, discord.Member):
            raise ValueError("Invalid member object passed to build embed")

        # Create the initial embed
        fields: typing.List[FilledField] = sorted(self.filled_fields.values(), key=operator.attrgetter("field.index"))
        embed = vbu.Embed(use_random_colour=True)
        if not self.template:
            raise AttributeError("Missing template field for user profile")
        embed.title = f"{self.template.name} | {self.name}"
        if self.template.colour:
            embed.colour = self.template.colour

        # Add the user
        embed.add_field(name="Discord User", value=f"<@{self.user_id}>")

        # Add each of the fields
        for f in fields:

            # Make sure we only do this for fields with values
            if not f.field:
                continue

            # Filter deleted or unset data
            if f.field.deleted:
                continue
            try:
                field_value = CommandProcessor.get_value(f.field.prompt, member)
            except InvalidCommandText:
                field_value = f.value
            if field_value is None:
                continue

            # Set data
            if isinstance(f.field.field_type, ImageField) or f.field.field_type == ImageField:
                embed.set_image(url=field_value)
            else:
                embed.add_field(name=f.field.name, value=field_value, inline=len(field_value) <= 100)

        # Add a footer to our embed
        bot.set_footer_from_config(embed)

        # Return embed
        return embed
