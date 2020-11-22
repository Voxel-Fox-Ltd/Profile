import typing
import uuid

import discord
import voxelbotutils as utils

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
    """

    __slots__ = ("user_id", "name", "template_id", "verified", "all_filled_fields", "template", "posted_message_id", "posted_channel_id")

    def __init__(self, user_id:int, name:str, template_id:uuid.UUID, verified:bool, posted_message_id:int=None, posted_channel_id:int=None, template:Template=None):
        self.user_id: int = user_id
        self.name: str = name
        self.template_id: uuid.UUID = template_id
        self.verified: bool = verified
        self.posted_message_id = posted_message_id
        self.posted_channel_id = posted_channel_id
        self.all_filled_fields: typing.Dict[uuid.UUID, FilledField] = dict()
        self.template: Template = template

    async def fetch_filled_fields(self, db) -> typing.Dict[uuid.UUID, FilledField]:
        """Fetch the fields for this profile and store them in .all_filled_fields"""

        if self.template is None or len(self.template.all_fields) == 0:
            await self.fetch_template(db, fetch_fields=True)
        field_rows = await db("SELECT * FROM filled_field WHERE user_id=$1 AND name=$2 AND field_id=ANY($3::UUID[])", self.user_id, self.name, self.template.all_fields.keys())
        self.all_filled_fields.clear()
        for f in field_rows:
            filled = FilledField(**f)
            filled.field = self.template.all_fields[filled.field_id]
            self.all_filled_fields[filled.field_id] = filled
        return self.all_filled_fields

    async def fetch_template(self, db, *, fetch_fields:bool=True) -> Template:
        """
        Fetch the template for this field and store it in .template.
        """

        template = await Template.fetch_template_by_id(db, self.template_id, fetch_fields=fetch_fields)
        self.template = template
        return template

    async def fetch_message(self, bot) -> typing.Optional[discord.Message]:
        """
        Fetch the message associated with this profile's archivation/submission.

        Args:
            bot (discord.ext.commands.Bot): The bot instance that can fetch this message.

        Returns:
            typing.Optional[discord.Message]: The message associated with the profile. May be None.
        """

        # See if we should bother asking the API
        if self.posted_channel_id is None or self.posted_message_id is None:
            return None

        # I'm not even gonna bother fetching the channel, I'll just get request it right here
        try:
            return await bot.http.get_message(self.posted_channel_id, self.posted_message_id)
        except discord.HTTPException:
            pass
        return None

    @property
    def filled_fields(self) -> typing.Dict[uuid.UUID, FilledField]:
        return {i: o for i, o in self.all_filled_fields.items() if o.field is not None and o.field.deleted is False and o.value is not None}

    def build_embed(self, member:typing.Optional[discord.Member]=None) -> utils.Embed:
        """
        Converts the filled profile into an embed.
        """

        # See if they're the right person
        if member and member.id != self.user_id:
            raise ValueError("Invalid user passed to build embed")
        if member and not isinstance(member, discord.Member):
            raise ValueError("Invalid member object passed to build embed")

        # Create the initial embed
        fields: typing.List[FilledField] = sorted(self.filled_fields.values(), key=lambda x: x.field.index)
        embed = utils.Embed(use_random_colour=True)
        if not self.template:
            raise AttributeError("Missing template field for user profile")
        embed.title = f"{self.template.name} | {self.name}"
        if self.template.colour:
            embed.colour = self.template.colour

        # Add the user
        embed.add_field(name="Discord User", value=f"<@{self.user_id}>")

        # Add each of the fields
        for f in fields:

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

        # Return embed
        return embed
