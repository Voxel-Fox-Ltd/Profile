import typing
import uuid

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

    __slots__ = ("user_id", "template_id", "verified", "all_filled_fields", "template")

    def __init__(self, user_id:int, template_id:uuid.UUID, verified:bool, template:Template=None):
        self.user_id: int = user_id
        self.template_id: uuid.UUID = template_id
        self.verified: bool = verified
        self.all_filled_fields: typing.Dict[uuid.UUID, FilledField] = dict()
        self.template: Template = template

    async def fetch_filled_fields(self, db) -> typing.Dict[uuid.UUID, FilledField]:
        """Fetch the fields for this profile and store them in .all_filled_fields"""

        if self.template is None:
            await self.fetch_template(db)
        field_rows = await db("SELECT * FROM filled_field WHERE user_id=$1 AND field_id=ANY($2::TEXT[])", self.user_id, [i.field_id for i in self.template.all_fields])
        self.all_filled_fields.clear()
        for f in field_rows:
            filled = FilledField(**f)
            filled.field = self.template.all_fields[filled.field_id]
            self.all_filled_fields[filled.field_id] = filled
        return self.all_filled_fields

    async def fetch_template(self, db) -> Template:
        """Fetch the template for this field and store it in .template"""

        template = Template.fetch_template_by_id(db, self.template_id)
        self.template = template
        return template

    @property
    def filled_fields(self) -> typing.Dict[uuid.UUID, FilledField]:
        return {i: o for i, o in self.all_filled_fields.items() if o.field.deleted is False}

    def build_embed(self) -> Embed:
        """Converts the filled profile into an embed"""

        # Create the initial embed
        fields: typing.List[FilledField] = sorted(self.filled_fields.values(), key=lambda x: x.field.index)
        embed = Embed(use_random_colour=True, title=self.template.name.title())

        # Add the user
        embed.add_field(name="Discord User", value=f"<@{self.user_id}>")

        # Set the colour if there is one to set
        if self.template.colour:
            embed.colour = self.template.colour

        # Add each of the fields
        for f in fields:

            # Filter deleted or unset data
            if f.field.deleted:
                continue
            if not f.value:
                continue

            # Set data
            if isinstance(f.field.field_type, ImageField) or f.field.field_type == ImageField:
                embed.set_image(url=f.value)
            else:
                embed.add_field(name=f.field.name, value=f.value)

        # Return embed
        return embed
