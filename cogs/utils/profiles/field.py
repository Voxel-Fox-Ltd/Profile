from uuid import UUID
from collections import defaultdict
from typing import Dict, List

from cogs.utils.profiles.field_type import FieldType, TextField, ImageField, NumberField, BooleanField


class Field(object):

    all_profile_fields: Dict['profile_id', List['Field']] = defaultdict(list)
    all_fields: Dict['field_id', 'Field'] = {}

    def __init__(self, field_id:UUID, name:str, index:int, prompt:str, timeout:int, field_type:FieldType, profile_id:UUID, optional:bool):
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
        self.profile_id = profile_id
        self.optional = optional

        self.all_profile_fields[self.profile_id].append(self)
        self.all_fields[self.field_id] = self
