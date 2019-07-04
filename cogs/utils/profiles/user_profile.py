from typing import List
from uuid import UUID

from cogs.utils.profiles.profile import Profile
from cogs.utils.profiles.field import Field


class UserProfile(object):

    def __init__(self, user_id:int, profile_id:UUID, verified:bool):
        self.user_id = user_id 
        self.profile_id = profile_id 
        self.verified = verified 

    @property 
    def profile(self) -> Profile:
        return Profile.all_profiles.get(self.profile_id)

    @property 
    def fields(self) -> List[Field]:
        return Field.all_profile_fields.get(self.profile_id)
