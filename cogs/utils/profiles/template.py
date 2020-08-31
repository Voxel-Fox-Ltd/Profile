import typing
import uuid

from discord.ext import commands

from cogs.utils.profiles.field import Field
from cogs.utils.profiles.filled_field import FilledField
from cogs.utils.profiles.field_type import ImageField
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
