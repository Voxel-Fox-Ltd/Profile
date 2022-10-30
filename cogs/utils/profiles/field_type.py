from __future__ import annotations

import re
from typing import ClassVar, Optional, TYPE_CHECKING

import yarl

if TYPE_CHECKING:
    from discord.ext import vbu


class FieldCheckFailure(Exception):

    def __init__(self, message):
        self.message = message


class FieldType:
    """
    The typing of a given profile field.
    """

    name: ClassVar[str] = ""
    bot: Optional[vbu.Bot] = None

    def __str__(self):
        return self.name

    @classmethod
    def convert_to_python(cls, value: str):
        """
        Converts the given value into the valid field type.
        """

        return str(value)

    @classmethod
    def convert_to_database(cls, value) -> str:
        """
        Converts the given value into a database-safe string.
        """

        return str(value)

    @classmethod
    def check(cls, value):
        """
        Returns true if the given value is valid for the field type, or raises FieldCheckFailure.
        """

        if len(value) > 1:
            return True
        raise FieldCheckFailure("No text was provided in the message.")

    @classmethod
    def get_from_message(cls, message):
        """
        Gets the content from the given message.
        """

        cls.check(message.content)
        return message.content

    @classmethod
    async def fix(cls, value: str) -> str:
        """
        Fix an input string to become a better input string.
        """

        return value


"""
The available types:

    '2000-CHAR',
    '200-CHAR',
    '50-CHAR',
    'INT',
    'IMAGE',
    'BOOLEAN'
"""


class TextField(FieldType):
    name = '1000-CHAR'

    @classmethod
    def check(cls, value):
        if 1000 >= len(value) >= 1:
            return True
        raise FieldCheckFailure("Length of value needs to be between 1 and 1000 characters.")


class NumberField(FieldType):
    name = 'INT'

    @classmethod
    def convert_to_python(cls, value):
        return int(value)

    @classmethod
    def check(cls, value):
        try:
            int(value)
        except ValueError:
            raise FieldCheckFailure("Could not convert value to an integer.")
        return True

    @classmethod
    def get_from_message(cls, message):
        cls.check(message.content)
        return message.content


class ImageField(FieldType):

    name = 'IMAGE'
    IMAGE_MATCHER = re.compile(r"^(http(?:s?))://(((?:[/|.|\w|\s|-])*)\.(jpg|gif|png|jpeg|webp))((?:\?|#)(.+))?$")

    @classmethod
    def check(cls, value):
        if cls.IMAGE_MATCHER.search(value):
            return True
        raise FieldCheckFailure("No valid image URL found.")

    @classmethod
    def get_from_message(cls, message):
        if message.attachments:
            content = message.attachments[0].url
        else:
            content = message.content
        cls.check(content)
        return content

    @classmethod
    async def fix(cls, value: str) -> str:
        """
        Fix an input string to become a better input string.

        In order:

        * Will remove `width` and `height` GET params if the URL is a Discord link.
        * Will take the first image if the given link is an Imgur album.
        """

        url = yarl.URL(value)
        if not url.scheme:
            return value

        # Fix media.discord links
        # if url.host == "media.discordapp.net":
        #     value = str(url).replace("//media.discordapp.net", "//cdn.discordapp.com", 1)
        #     url = yarl.URL(value)

        # Remove GET params
        if url.host in ["cdn.discordapp.com", "media.discordapp.net"] and "height" in url.query or "width" in url.query:
            url = url.update_query(height="", width="")

        # Check for Imgur links
        if url.host == "imgur.com" and url.path.startswith("/gallery") and cls.bot and cls.bot.config['imgur']['client_id']:
            gallery_id = url.path.split("/")[2]
            headers = {
                "Authorization": f"Client-ID {cls.bot.config['imgur']['client_id']}",
                "User-Agent": cls.bot.user_agent,
            }
            site = await cls.bot.session.get(f"https://api.imgur.com/3/album/{gallery_id}/images", headers=headers)
            if site.ok:
                data = await site.json()
                url = yarl.URL(data['data'][0]['link'])

        # And that should be done
        return str(url)


class BooleanField(FieldType):
    name = 'BOOLEAN'

    @classmethod
    def convert_to_python(cls, value):
        return bool(int(value))

    @classmethod
    def convert_to_database(cls, value):
        return str(int(value))


# FieldType.TEXTFIELD = TextField
# FieldType.NUMBERFIELD = NumberField
# FieldType.IMAGEFIELD = ImageField
# FieldType.BOOLEANFIELD = BooleanField
