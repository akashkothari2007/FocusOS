from pydantic import BaseModel
from typing import Optional, Any


class UpdateProfile(BaseModel):
    projects: Optional[Any] = None
    experiences: Optional[Any] = None
    skills: Optional[str] = None
    newsletters: Optional[list] = None
