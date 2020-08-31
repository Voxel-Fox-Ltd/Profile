import typing
import uuid

from discord.ext import commands

from cogs.utils.profiles.field import Field
from cogs.utils.profiles.filled_field import FilledField
from cogs.utils.context_embed import ContextEmbed as Embed


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

    async def fetch_profile_for_user(self, db, user_id:int, *, fetch_filled_fields:bool=True) -> 'cogs.utils.profiles.user_profile.UserProfile':
        """Gets the filled profile for a given user"""

        # Grab our imports here to avoid circular importing
        from cogs.utils.profiles.user_profile import UserProfile

        # Grab the user profile
        profile_rows = await db("SELECT * FROM created_profile WHERE template_id=$1 AND user_id=$2", self.template_id, user_id)
        if not profile_rows:
            return None
        user_profile = UserProfile(**profile_rows[0])
        user_profile.template = self
        if fetch_filled_fields:
            await user_profile.fetch_filled_fields(db)
        return user_profile

    @classmethod
    async def fetch_template_by_id(cls, db, template_id:uuid.UUID, *, fetch_fields:bool=True) -> typing.Optional['Template']:
        """Get a template from the database via its ID"""

        # Grab the template
        template_rows = await db("SELECT * FROM template WHERE template_id=$1", template_id)
        if not template_rows:
            return None
        template = cls(**template_rows[0])
        if fetch_fields:
            await template.fetch_fields(db)
        return template

    @classmethod
    async def fetch_template_by_name(cls, db, guild_id:int, template_name:str, *, fetch_fields:bool=True) -> typing.Optional['Template']:
        """Get a template from the database via its name"""

        # Grab the template
        template_rows = await db("SELECT * FROM template WHERE guild_id=$1 AND name=$2", guild_id, template_name.lower())
        if not template_rows:
            return None
        template = cls(**template_rows[0])
        if fetch_fields:
            await template.fetch_fields(db)
        return template

    async def fetch_fields(self, db) -> typing.Dict[uuid.UUID, FilledField]:
        """Fetch the fields for this template and store them in .all_fields"""

        field_rows = await db("SELECT * FROM field WHERE template_id=$1", self.template_id)
        self.all_fields.clear()
        for f in field_rows:
            field = Field(**f)
            self.all_fields[field.field_id] = field
        return self.all_fields

    @classmethod
    async def convert(cls, ctx, argument:str):
        """The Discord.py convert method for getting a template"""

        async with ctx.bot.database() as db:
            v = await cls.fetch_template_by_name(db, ctx.guild.id, argument)
        if v is None:
            raise TemplateNotFoundError(argument.lower())
        return v

    def build_embed(self) -> Embed:
        """Create an embed to visualise all of the created fields and given information"""

        # Create the initial embed
        fields: typing.List[Field] = sorted(self.fields.values(), key=lambda x: x.field.index)
        embed = Embed(use_random_colour=True, title=self.template.name.title())
        embed.description = '\n'.join([
            f"Template ID {self.id} for guild {self.guild_id}",
            f"Verification channel: {'none' if self.verification_channel_id is None else '<#' + self.verification_channel_id + '>'}",
            f"Archive channel: {'none' if self.archive_channel_id is None else '<#' + self.archive_channel_id + '>'}",
            f"Given role: {'none' if self.role_id is None else '<@&' + self.role_id + '>'}",
        ])

        # Add the user
        embed.add_field(name="Discord User", value="In this field, the owner of the created profile will be pinged.")

        # Set the colour if there is one to set
        if self.template.colour:
            embed.colour = self.template.colour

        # Add each of the fields
        for index, f in enumerate(fields):
            if f.deleted:
                continue
            embed.add_field(name=f.name, value=f"Field question {index} at index {f.index}, type {f.type!s}\n{f.prompt}")

        # Return embed
        return embed
