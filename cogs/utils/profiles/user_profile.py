import typing
import uuid
import re

import discord

from cogs.utils.profiles.template import Template
from cogs.utils.profiles.filled_field import FilledField
from cogs.utils.profiles.field_type import ImageField
from cogs.utils.context_embed import ContextEmbed as Embed


class UserProfile(object):
    """A filled user template
    This represents a template filled by a user containing all of their relevant information
    This class itself does not contain the user's data, but rather the metadata about their given profile,
    eg whether it's been verified etc; the user's data is stored inthe FilledField objects associated
    with this
    """

    COMMAND_REGEX = re.compile(r'^{{.+?}}$', re.IGNORECASE)
    HAS_ROLE_REGEX = re.compile(r'^{{HASROLE (?:DEFAULT \"(?P<default>.+?)\")( HAS\(((?:\d{16,23}(?:, ?)?)+)\) SAYS \"(?P<text>.+?)\")+}}$', re.IGNORECASE)
    HAS_ROLE_PARAMETER_REGEX = re.compile(r'(?:HAS\((?P<roleids>(?:\d{16,23}(?:, ?)?)+)\) SAYS \"(?P<text>.+?)\")', re.IGNORECASE)

    __slots__ = ("user_id", "name", "template_id", "verified", "all_filled_fields", "template")

    def __init__(self, user_id:int, name:str, template_id:uuid.UUID, verified:bool, template:Template=None):
        self.user_id: int = user_id
        self.name: str = name
        self.template_id: uuid.UUID = template_id
        self.verified: bool = verified
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
        """Fetch the template for this field and store it in .template"""

        template = await Template.fetch_template_by_id(db, self.template_id, fetch_fields=fetch_fields)
        self.template = template
        return template

    @property
    def filled_fields(self) -> typing.Dict[uuid.UUID, FilledField]:
        return {i: o for i, o in self.all_filled_fields.items() if o.field is not None and o.field.deleted is False and o.value is not None}

    def build_embed(self, member:discord.Member=None) -> Embed:
        """Converts the filled profile into an embed"""

        # See if they're the right person
        if member and member.id != self.user_id:
            raise RuntimeError("You passed the wrong person into this method")

        # Create the initial embed
        fields: typing.List[FilledField] = sorted(self.filled_fields.values(), key=lambda x: x.field.index)
        embed = Embed(use_random_colour=True)
        if self.template:
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
            if f.value is None:
                continue

            # Set data
            if isinstance(f.field.field_type, ImageField) or f.field.field_type == ImageField:
                embed.set_image(url=f.value)
            else:
                if member:
                    has_role_match = self.HAS_ROLE_REGEX.search(f.field.prompt)
                    if has_role_match:
                        text = has_role_match.group("default")
                        for match in self.HAS_ROLE_PARAMETER_REGEX.finditer(f.field.prompt):
                            role_ids = [int(i.strip()) for i in match.group("roleids").split(',')]
                            if [i for i in member._roles if i in role_ids]:
                                text = match.group("text")
                                break
                        embed.add_field(name=f.field.name, value=text, inline=len(text) <= 100)
                    else:
                        embed.add_field(name=f.field.name, value=f.value, inline=len(f.value) <= 100)
                else:
                    embed.add_field(name=f.field.name, value=f.value, inline=len(f.value) <= 100)

        # Return embed
        return embed
