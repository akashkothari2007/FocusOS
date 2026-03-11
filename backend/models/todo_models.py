from pydantic import BaseModel
from typing import Optional, Literal, List
from datetime import datetime


class Subtask(BaseModel):
    id: int
    title: str
    status: Literal["pending", "done"] = "pending"


class Link(BaseModel):
    id: int
    url: str
    label: Optional[str] = None


#title is required, everything else optional
class CreateTodo(BaseModel):
    title: str
    description: Optional[str] = None
    subtasks: Optional[List[Subtask]] = []
    due_date: Optional[datetime] = None

#everything optional, only update what changes
class UpdateTodo(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    status: Optional[Literal["pending", "done"]] = None
    subtasks: Optional[List[Subtask]] = None
    links: Optional[List[Link]] = None
    due_date: Optional[datetime] = None


class ReorderTodos(BaseModel):
    ids: List[int]
