from pydantic import BaseModel
from typing import Optional


class EndSession(BaseModel):
    notes: Optional[str] = None
