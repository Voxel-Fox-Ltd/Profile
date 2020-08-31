import typing
import uuid

import discord
from discord.ext import commands

from cogs.utils.profiles.field import Field
from cogs.utils.profiles.filled_field import FilledField


class TemplateNotFoundError(commands.BadArgument):

    def __init__(self, template_name:str=None):
        self.template_name = template_name

    def __str__(self):
        if not self.template_name:
            return "The given template could not be found."
        return f"There's no template with the name `{self.template_name}` on this guild."


class Template(object):
    """A class for an abstract template object that's saved to guild
    This contains no user data, but rather the metadata for the template itself
    """

    __slots__ = ("template_id", "colour", "guild_id", "verification_channel_id", "name", "archive_channel_id", "role_id", "all_fields")

    def __init__(self, template_id:uuid.UUID, colour:int, guild_id:int, verification_channel_id:int, name:str, archive_channel_id:int, role_id:int):
        self.template_id: uuid.UUID = template_id
        self.colour: int = colour
        self.guild_id: int = guild_id
        self.verification_channel_id: int = verification_channel_id
        self.name: str = name
        self.archive_channel_id: int = archive_channel_id
        self.role_id: int = role_id
        self.all_fields: typing.Dict[uuid.UUID, Field] = dict()

    @property
    def fields(self) -> typing.Dict[uuid.UUID, Field]:
        """Returns a list of utils.Field objects for this particular profile"""

        return {i: o for i, o in self.all_fields.items() if o.deleted is False}

    async def get_profile_for_user(self, db, user_id:int) -> 'cogs.utils.profiles.user_profile.UserProfile':
        """Gets the filled profile for a given user"""

        # Grab our imports here to avoid circular importing
        from cogs.utils.profiles.user_profile import UserProfile

        # Grab the user profile
        profile_rows = await db("SELECT * FROM created_profile WHERE template_id=$1 AND user_id=$2", self.template_id, user_id)
        if not profile_rows:
            return None
        user_profile = UserProfile(**profile_rows[0])

        # Grab their filled fields
        field_rows = await db("SELECT * FROM filled_field WHERE user_id=$1 AND field_id=ANY($2::TEXT[])", user_id, [i.field_id for i in self.all_fields])
        for f in field_rows:
            filled = FilledField(**f)
            filled.field = self.all_fields[filled.field_id]
            user_profile._all_filled_fields.append()
        user_profile.template = self
        return user_profile

    @classmethod
    async def get_template_by_id(cls, db, template_id:uuid.UUID) -> typing.Optional['Template']:
        """Get a template from the database via its ID"""

        # Grab the template
        template_rows = await db("SELECT * FROM template WHERE template_id=$1", template_id)
        if not template_rows:
            return None
        template = cls(**template_rows[0])

        # Grab the template's fields
        field_rows = await db("SELECT * FROM field WHERE template_id=$1", template_id)
        for f in field_rows:
            field = Field(**f)
            template.all_fields[field.field_id] = field
        return template

    @classmethod
    async def get_template_by_name(cls, db, guild_id:int, template_name:str) -> typing.Optional['Template']:
        """Get a template from the database via its name"""

        # Grab the template
        template_rows = await db("SELECT * FROM template WHERE guild_id=$1 AND name=$2", guild_id, template_name.lower())
        if not template_rows:
            return None
        template = cls(**template_rows[0])

        # Grab the template's fields
        field_rows = await db("SELECT * FROM field WHERE template_id=$1", template.template_id)
        for f in field_rows:
            field = Field(**f)
            template.all_fields[field.field_id] = field
        return template

    @classmethod
    async def convert(cls, ctx, argument:str):
        """The Discord.py convert method for getting a template"""

        async with ctx.bot.database() as db:
            v = await cls.get_template_by_name(db, ctx.guild.id, argument)
        if v is None:
            raise TemplateNotFoundError(argument.lower())
        return v
