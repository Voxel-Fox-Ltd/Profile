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
    pass


class NumberField(FieldType):

    @classmethod
    def convert_to_python(self, value):
        return int(value)


class ImageField(FieldType):
    pass 


class BooleanField(FieldType):

    @classmethod
    def convert_to_python(self, value):
        return bool(int(value))

    @classmethod
    def convert_to_database(self, value):
        return str(int(value))
