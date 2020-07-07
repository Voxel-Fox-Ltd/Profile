import uuid
import collections
import typing

from cogs.utils.profiles.field_type import FieldType, TextField, ImageField, NumberField, BooleanField


class Field(object):
    """The abstract field object for a given template
    This itself does not store any user information, but rather the meta information associated with
    a field from a template
    """

    all_profile_fields: typing.Dict[uuid.UUID, typing.List['Field']] = collections.defaultdict(list)
    all_fields: typing.Dict[uuid.UUID, 'Field'] = {}

    __slots__ = ("field_id", "index", "name", "prompt", "timeout", "field_type", "template_id", "optional", "deleted")

    def __init__(self, field_id:uuid.UUID, name:str, index:int, prompt:str, timeout:int, field_type:FieldType, template_id:uuid.UUID, optional:bool, deleted:bool):
        self.field_id = field_id
        self.index = index
        self.name = name
        self.prompt = prompt
        self.timeout = timeout
        self.field_type = field_type if isinstance(field_type, FieldType) else {
            '1000-CHAR': TextField(),
            'INT': NumberField(),
            'IMAGE': ImageField(),
            'BOOLEAN': BooleanField(),
        }[field_type]
        self.template_id = template_id
        self.optional = optional
        self.deleted = deleted

        self.all_profile_fields[self.template_id].append(self)
        self.all_fields[self.field_id] = self
