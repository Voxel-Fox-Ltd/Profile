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

    all_profiles = {}

    __slots__ = ("user_id", "template_id", "verified")

    def __init__(self, user_id:int, template_id:uuid.UUID, verified:bool):
        self.user_id = user_id
        self.template_id = template_id
        self.verified = verified
        self.all_profiles[(self.user_id, self.template.guild_id, self.template.name)] = self

    @property
    def template(self) -> Template:
        return Template.all_profiles.get(self.template_id)

    @property
    def filled_fields(self) -> typing.List[FilledField]:
        try:
            return [FilledField.all_filled_fields[(self.user_id, i.field_id)] for i in self.template.fields]
        except KeyError:
            return []

    def build_embed(self) -> Embed:
        """Converts the filled profile into an embed"""

        fields: typing.List[FilledField] = sorted(self.filled_fields, key=lambda x: x.field.index)
        with Embed(use_random_colour=True) as embed:
            embed.title = self.template.name.title()
            embed.add_field(name="Discord User", value=f"<@{self.user_id}>")
            if self.template.colour:
                embed.colour = self.template.colour
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
