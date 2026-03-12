from pydantic import BaseModel
from typing import Optional


class EndSession(BaseModel):
    notes: Optional[str] = None


class StartFreeformSession(BaseModel):
    title: str
    notes: Optional[str] = None


class QuickSession(BaseModel):
    project: str
