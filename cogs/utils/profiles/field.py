import uuid

from cogs.utils.profiles.field_type import FieldType, TextField, ImageField, NumberField, BooleanField


class Field(object):
    """The abstract field object for a given template
    This itself does not store any user information, but rather the meta information associated with
    a field from a template

    Args:
        field_id (uuid.UUID): the ID of the field
        name (str): the name of the field
        index (int): the index of the field - may not specifically refer to its location in the embed
        prompt (str): the prompt shown to the user when they're asked to fill in this field information
        timeout (int): how long the user has (in seconds) to fill in this field
        field_type (cogs.utils.profiles.field_type.FieldType): the type given to this field
        template_id (uuid.UUID): the ID of the template that this field is part of
        optional (bool): whether or not this field is optional
        deleted (bool): whether or not this field is deleted
    """

    __slots__ = ("field_id", "index", "name", "prompt", "timeout", "field_type", "template_id", "optional", "deleted")

    def __init__(self, field_id:uuid.UUID, name:str, index:int, prompt:str, timeout:int, field_type:FieldType, template_id:uuid.UUID, optional:bool, deleted:bool):
        self.field_id: uuid.UUID = field_id
        self.index: int = index
        self.name: str = name
        self.prompt: str = prompt
        self.timeout: int = timeout
        self.field_type: FieldType = {
            '1000-CHAR': TextField(),
            'INT': NumberField(),
            'IMAGE': ImageField(),
            'BOOLEAN': BooleanField(),
        }[getattr(field_type, 'name', field_type)]
        self.template_id: uuid.UUID = template_id
        self.optional: bool = optional
        self.deleted: bool = deleted
