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


class NumberField(FieldType):
    name = 'INT'

    @classmethod
    def convert_to_python(self, value):
        return int(value)


class ImageField(FieldType):
    name = 'IMAGE'


class BooleanField(FieldType):
    name = 'BOOLEAN'

    @classmethod
    def convert_to_python(self, value):
        return bool(int(value))

    @classmethod
    def convert_to_database(self, value):
        return str(int(value))
