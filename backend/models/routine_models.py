from pydantic import BaseModel
from typing import Optional, List


class CreateRoutine(BaseModel):
    name: str
    items: List[str] = []


class UpdateRoutine(BaseModel):
    name: Optional[str] = None
    items: Optional[List[str]] = None


class ReorderRoutines(BaseModel):
    ids: List[int]
