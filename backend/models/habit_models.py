from pydantic import BaseModel
from typing import Optional
from datetime import date


class CreateHabit(BaseModel):
    name: str
    frequency: int = 7


class UpdateHabit(BaseModel):
    name: Optional[str] = None
    is_active: Optional[bool] = None
    frequency: Optional[int] = None


class ToggleHabitLog(BaseModel):
    habit_id: int
    log_date: date
