from pydantic import BaseModel
from typing import Optional, Literal


class CreateJob(BaseModel):
    title: str
    company: str
    status: Optional[Literal["saved", "applied", "interview", "rejected"]] = "saved"
    link: Optional[str] = None
    description: Optional[str] = None


class UpdateJob(BaseModel):
    title: Optional[str] = None
    company: Optional[str] = None
    status: Optional[Literal["saved", "applied", "interview", "rejected"]] = None
    link: Optional[str] = None
    description: Optional[str] = None
    summary: Optional[str] = None


class AnalyzeJob(BaseModel):
    input_doc_id: int


class GenerateResumeBody(BaseModel):
    experience_plan: Optional[list] = None
    project_plan: Optional[list] = None
    selected_experiences: Optional[list] = None  # new format: [{role, company}]
    selected_projects: Optional[list] = None     # new format: [{title}]
