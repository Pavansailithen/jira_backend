from pydantic import BaseModel
from typing import Optional, List
from datetime import date, datetime

class EpicBase(BaseModel):
    title: str
    description: Optional[str] = None
    status: Optional[str] = "TODO"
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    project_id: int

class TeamSimple(BaseModel):
    id: int
    name: str
    class Config:
        from_attributes = True

class EpicCreate(EpicBase):
    team_ids: Optional[List[int]] = []

class EpicUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    team_ids: Optional[List[int]] = None

class EpicResponse(EpicBase):
    id: int
    created_by: Optional[int] = None
    created_at: datetime
    updated_at: datetime
    teams: List[TeamSimple] = []

    class Config:
        from_attributes = True
