import re


class FieldCheckFailure(Exception):

    def __init__(self, message):
        self.message = message


class FieldType:
    """
    The typing of a given profile field.
    """

    name = None

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
    matcher = re.compile(r"^(http(s?):)([/|.|\w|\s|-])*\.(?:jpg|gif|png|jpeg|gif)$")

    @classmethod
    def check(cls, value):
        if cls.matcher.search(value):
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
