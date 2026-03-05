from pydantic import BaseModel
from typing import Optional
from datetime import date


class CreateHabit(BaseModel):
    name: str


class UpdateHabit(BaseModel):
    name: Optional[str] = None
    is_active: Optional[bool] = None


class ToggleHabitLog(BaseModel):
    habit_id: int
    log_date: date
