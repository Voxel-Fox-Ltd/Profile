import typing
import uuid

from cogs.utils.profiles.profile import Profile
from cogs.utils.profiles.field import Field
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

    __slots__ = ("user_id", "profile_id", "verified")

    def __init__(self, user_id:int, profile_id:uuid.UUID, verified:bool):
        self.user_id = user_id
        self.profile_id = profile_id
        self.verified = verified
        self.all_profiles[(self.user_id, self.profile.guild_id, self.profile.name)] = self

    @property
    def profile(self) -> Profile:
        return Profile.all_profiles.get(self.profile_id)

    @property
    def filled_fields(self) -> typing.List[FilledField]:
        try:
            return [FilledField.all_filled_fields[(self.user_id, i.field_id)] for i in self.profile.fields]
        except KeyError:
            return []

    def build_embed(self) -> Embed:
        """Converts the filled profile into an embed"""

        fields: typing.List[Field] = sorted(self.filled_fields, key=lambda x: x.field.index)
        with Embed(use_random_colour=True) as embed:
            # embed.colour = self.profile.colour
            embed.title = self.profile.name.title()
            embed.add_field(name="Discord User", value=f"<@{self.user_id}>")
            for f in fields:
                if isinstance(f.field.field_type, ImageField) or f.field.field_type == ImageField:
                    embed.set_image(url=f.value)
                else:
                    embed.add_field(name=f.field.name, value=f.value)
        return embed
