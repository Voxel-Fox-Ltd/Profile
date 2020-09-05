import typing
import uuid
import re

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

    TEMPLATE_ID_REGEX = re.compile(r"^(?P<uuid>.{8}-.{4}-.{4}-.{4}-.{12})$")

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
        """Gets the filled profile for a given user

        Args:
            db (cogs.utils.database.DatabaseConnection): Description
            user_id (int): Description
            fetch_filled_fields (bool, optional): Description

        Returns:
            cogs.utils.profiles.user_profile.UserProfile: Description
        """

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
        template_rows = await db("SELECT * FROM template WHERE guild_id=$1 AND LOWER(name)=LOWER($2)", guild_id, template_name)
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

    def build_embed(self, brief:bool=False) -> Embed:
        """Create an embed to visualise all of the created fields and given information"""

        # Create the initial embed
        fields: typing.List[Field] = sorted(self.fields.values(), key=lambda x: x.index)
        embed = Embed(use_random_colour=True, title=self.name)
        embed.description = '\n'.join([
            f"Template ID `{self.template_id}` for guild {self.guild_id}",
            f"Verification channel: {'none' if self.verification_channel_id is None else '<#' + str(self.verification_channel_id) + '>'}",
            f"Archive channel: {'none' if self.archive_channel_id is None else '<#' + str(self.archive_channel_id) + '>'}",
            f"Given role: {'none' if self.role_id is None else '<@&' + str(self.role_id) + '>'}",
        ])

        # Add the user
        if brief is False:
            embed.add_field(name="Discord User", value="In this field, the owner of the created profile will be pinged.", inline=False)

        # Set the colour if there is one to set
        if self.colour:
            embed.colour = self.colour

        # Add each of the fields
        text = []
        for index, f in enumerate(fields):
            if f.deleted:
                continue
            if brief:
                text.append(f"#{f.index} **{f.name}** ({f.field_type!s})")
            else:
                embed.add_field(
                    name=f.name,
                    value=f'Field ID `{f.field_id}` at position {index} with index {f.index}, type `{f.field_type!s}`.\n"{f.prompt}"',
                    inline=False
                )

        # If we're being brief, then just add all the field text at once
        if brief and text:
            embed.add_field(
                name="Fields",
                value='\n'.join(text),
                inline=False,
            )

        # Return embed
        return embed
