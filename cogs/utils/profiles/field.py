from uuid import UUID
from collections import defaultdict

from cogs.utils.profiles.field_type import FieldType


class Field(object):

    all_profile_fields = defaultdict(list)
    all_fields = {}

    def __init__(self, id:UUID, name:str, index:int, prompt:str, timeout:int, field_type:FieldType, profile_id:UUID, optional:bool):
        self.id = id
        self.index = index 
        self.name = name
        self.prompt = prompt 
        self.timeout = timeout 
        self.field_type = field_type 
        self.profile_id = profile_id
        self.optional = optional

        self.all_profile_fields[self.profile_id].append(self)
        self.all_fields[self.id] = self
