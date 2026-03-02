from pydantic import BaseModel
from typing import Optional


class CreateDoc(BaseModel):
    title: str
    content: str
    is_primary: Optional[bool] = False


class UpdateDoc(BaseModel):
    title: Optional[str] = None
    content: Optional[str] = None
