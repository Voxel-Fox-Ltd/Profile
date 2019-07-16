import re


class FieldCheckFailure(Exception):
    def __init__(self, message):
        self.message = message


class FieldType(object):
    '''The typing of a given profile field'''

    @classmethod
    def convert_to_python(self, value:str):
        '''Converts the given value into the valid field type'''
        return str(value)

    @classmethod
    def convert_to_database(self, value) -> str:
        '''Converts the given value into a database-safe string'''
        return str(value)

    @classmethod
    def check(self, value):
        '''Returns true if the given value is valid for the field type, or raises FieldCheckFailure'''
        return True

'''
The available types:

    '2000-CHAR',
    '200-CHAR',
    '50-CHAR',
    'INT',
    'IMAGE',
    'BOOLEAN'
'''


class TextField(FieldType):
    name = '1000-CHAR'

    @classmethod
    def check(self, value):
        if 1000 >= len(value) >= 1:
            return True 
        raise FieldCheckFailure("Length of value needs to be between 1 and 1000 characters.")


class NumberField(FieldType):
    name = 'INT'

    @classmethod
    def convert_to_python(self, value):
        return int(value)

    @classmethod
    def check(self, value):
        try:
            int(value)
        except ValueError:
            raise FieldCheckFailure("Could not convert value to an integer.")
        return True


class ImageField(FieldType):
    name = 'IMAGE'
    matcher = re.compile(r"(http(s?):)([/|.|\w|\s|-])*\.(?:jpg|gif|png|jpeg|gif)")

    @classmethod
    def check(self, value):
        if self.matcher.search(value):
            return True
        raise FieldCheckFailure("No valid image URL found.")


class BooleanField(FieldType):
    name = 'BOOLEAN'

    @classmethod
    def convert_to_python(self, value):
        return bool(int(value))

    @classmethod
    def convert_to_database(self, value):
        return str(int(value))


# FieldType.TEXTFIELD = TextField
# FieldType.NUMBERFIELD = NumberField
# FieldType.IMAGEFIELD = ImageField
# FieldType.BOOLEANFIELD = BooleanField
