from fastapi import APIRouter, Depends, HTTPException, status
from typing import List

from app.models.epic import Epic
from app.models.team import Team
from app.schemas.epic_schema import EpicCreate, EpicUpdate, EpicResponse
from app.utils.deps import APIContext

router = APIRouter()

@router.post("/", response_model=EpicResponse, status_code=status.HTTP_201_CREATED)
def create_epic(
    epic_in: EpicCreate,
    ctx: APIContext = Depends()
):
    new_epic = Epic(
        title=epic_in.title,
        description=epic_in.description,
        status=epic_in.status,
        start_date=epic_in.start_date,
        end_date=epic_in.end_date,
        project_id=epic_in.project_id,
        created_by=ctx.user.id
    )
    
    # Handle Teams
    if epic_in.team_ids:
        teams = ctx.db.query(Team).filter(Team.id.in_(epic_in.team_ids)).all()
        # Verify all found (optional, but good)
        if len(teams) != len(epic_in.team_ids):
             # Or just assign what we found, or raise error. 
             # For robustness, let's just assign what exists, unless critical.
             pass 
        new_epic.teams = teams

    ctx.db.add(new_epic)
    ctx.db.commit()
    ctx.db.refresh(new_epic)
    return new_epic

@router.get("/project/{project_id}", response_model=List[EpicResponse])
def get_epics_by_project(
    project_id: int,
    ctx: APIContext = Depends()
):
    epics = ctx.db.query(Epic).filter(Epic.project_id == project_id).all()
    return epics

@router.get("/", response_model=List[EpicResponse])
def get_all_epics(
    ctx: APIContext = Depends()
):
    epics = ctx.db.query(Epic).all()
    return epics

@router.get("/{epic_id}", response_model=EpicResponse)
def get_epic(
    epic_id: int,
    ctx: APIContext = Depends()
):
    epic = ctx.db.query(Epic).filter(Epic.id == epic_id).first()
    if not epic:
        raise HTTPException(status_code=404, detail="Epic not found")
    return epic

@router.put("/{epic_id}", response_model=EpicResponse)
def update_epic(
    epic_id: int,
    epic_in: EpicUpdate,
    ctx: APIContext = Depends()
):
    epic = ctx.db.query(Epic).filter(Epic.id == epic_id).first()
    if not epic:
        raise HTTPException(status_code=404, detail="Epic not found")
    
    # Update fields
    if epic_in.title is not None:
        epic.title = epic_in.title
    if epic_in.description is not None:
        epic.description = epic_in.description
    if epic_in.status is not None:
        epic.status = epic_in.status
    if epic_in.start_date is not None:
        epic.start_date = epic_in.start_date
    if epic_in.end_date is not None:
        epic.end_date = epic_in.end_date
    
    # Handle Teams Update
    if epic_in.team_ids is not None:
        teams = ctx.db.query(Team).filter(Team.id.in_(epic_in.team_ids)).all()
        epic.teams = teams # Replaces existing collection
        
    ctx.db.commit()
    ctx.db.refresh(epic)
    return epic

@router.delete("/{epic_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_epic(
    epic_id: int,
    ctx: APIContext = Depends()
):
    epic = ctx.db.query(Epic).filter(Epic.id == epic_id).first()
    if not epic:
        raise HTTPException(status_code=404, detail="Epic not found")
        
    ctx.db.delete(epic)
    ctx.db.commit()
    return None
