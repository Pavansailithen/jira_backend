from typing import Optional, List
from fastapi import APIRouter, Depends, Form
from sqlalchemy.orm import Session
from sqlalchemy import or_

from sqlalchemy.exc import IntegrityError

from app.database.session import get_db
from app.models import Project, UserStory, User, Team
from app.schemas import ProjectResponse
from app.auth.dependencies import get_current_user
from app.constants import ErrorMessages, SuccessMessages
from app.constants import ADMIN, DEVELOPER
from app.utils.common import get_object_or_404
from app.exceptions import raise_forbidden, raise_not_found, raise_bad_request
from app.utils.logger import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/projects", tags=["projects"])

@router.post("", response_model=ProjectResponse)
def create_project(
    name: str = Form(...),
    project_prefix: str = Form(...),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """
    Creates a new project.
    Only accessible in Admin mode.
    """
    # Check if user is in ADMIN mode
    # Master Admin is always in ADMIN mode as per auth_api update
    if user.view_mode != ADMIN:
        raise_forbidden("Developers cannot create projects. Please switch to Admin Mode.")

    try:
        # Any user in ADMIN mode can create projects
        project = Project(
            name=name,
            project_prefix=project_prefix.upper(),
            owner_id=user.id
        )
        if project.current_story_number is None:
                project.current_story_number = 1
        db.add(project)
        # db.commit() handled by dependency
        db.flush() # ensure ID is generated if needed, though refresh covers it? refresh needs flush if autocommit=False.
        db.refresh(project)
    except IntegrityError:
        raise_bad_request("Project with this name already exists")

    return project

@router.put("/{id}")
def update_project(
    id: int,
    name: Optional[str] = Form(None),
    project_prefix: Optional[str] = Form(None),
    is_active: Optional[bool] = Form(None),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """
    Updates an existing project.
    Only project owners in ADMIN mode or master admin can update.
    """
    # Refactored to use generic util
    project = get_object_or_404(db, Project, id, ErrorMessages.PROJECT_NOT_FOUND)
    
    # Permission check
    if not user.is_master_admin:
        if user.view_mode != ADMIN:
            raise_forbidden("Projects can only be updated in Admin mode.")
        if project.owner_id != user.id:
            raise_forbidden("Only the project owner can update this project.")
        
    # Check for Inactive Lock
    if not project.is_active:
        # If project is inactive, the ONLY allowed change is to Activate it (is_active=True)
        if is_active is True:
            # Re-activating. Allow other changes too
            pass
        else:
            # Not re-activating
            raise_forbidden("Project is inactive. You must activate it to make changes.")

    if name is not None:
        project.name = name
    if project_prefix is not None:
        project.project_prefix = project_prefix.upper()
    if is_active is not None:
        project.is_active = is_active
        
    # db.commit() handled by dependency
    db.flush() # Ensure changes are sent to DB so refresh sees them (autoflush is False)
    db.refresh(project)
    return project

@router.delete("/{id}")
def delete_project(
    id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """
    Deletes a project and all its associated stories.
    Only project owners in ADMIN mode or master admin can delete.
    """
    project = get_object_or_404(db, Project, id, ErrorMessages.PROJECT_NOT_FOUND)
    
    # Permission check
    if not user.is_master_admin:
        if user.view_mode != ADMIN:
            raise_forbidden("Projects can only be deleted in Admin mode.")
        if project.owner_id != user.id:
            raise_forbidden("Only the project owner can delete this project.")
    
    # Delete all stories of project
    db.query(UserStory).filter(UserStory.project_id == id).delete()
    db.delete(project)
    # db.commit() handled by dependency
    return {"message": SuccessMessages.PROJECT_DELETED}

@router.get("/inactive")
def get_inactive_projects(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """
    Retrieves inactive projects based on user role and permissions.
    """
    from sqlalchemy.orm import joinedload
    query = db.query(Project).options(joinedload(Project.owner))

    if user.is_master_admin:
        # Master Admin sees all inactive projects
        projects = query.filter(Project.is_active == False).all()
    elif user.view_mode == ADMIN:
        # ADMIN mode: Shows inactive projects you own
        projects = query.filter(
            Project.owner_id == user.id,
            Project.is_active == False
        ).all()
    else:
        # DEVELOPER mode: Shows inactive projects where you're a member/assignee
        assigned_project_ids = [pid[0] for pid in db.query(UserStory.project_id)
            .filter(or_(
                UserStory.assignee_id == user.id,
                UserStory.assignee == user.username,
                UserStory.assignee == user.email
            ))
            .distinct()
            .all()]
        
        team_project_ids = [t.project_id for t in user.teams]
        led_project_ids = [t.project_id for t in user.led_teams]
            
        all_ids = list(set(assigned_project_ids + led_project_ids + team_project_ids))
        
        projects = query.filter(
            Project.id.in_(all_ids),
            Project.owner_id != user.id,
            Project.is_active == False
        ).all()
        
    return projects

@router.get("")
def get_projects(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """
    Retrieves active projects viewable by the user.
    Admins see their owned projects.
    Developers see projects they are assigned to or members of.
    """
    from sqlalchemy.orm import joinedload
    query = db.query(Project).options(joinedload(Project.owner))

    if user.is_master_admin:
        # Master Admin sees everything
        projects = query.all()
    elif user.view_mode == ADMIN:
        # ADMIN mode: Shows projects you own
        projects = query.filter(Project.owner_id == user.id).all()
    else:
        # DEVELOPER mode: Shows projects where you're a member/assignee (excluding owned projects)
        
        # Projects where user is assigned stories
        assigned_project_ids = [pid[0] for pid in db.query(UserStory.project_id)
            .filter(or_(
                UserStory.assignee_id == user.id,
                UserStory.assignee == user.username,
                UserStory.assignee == user.email
            ))
            .distinct()
            .all()]
        
        # Projects where user is a Team Lead or Member
        team_project_ids = [t.project_id for t in user.teams]
        led_project_ids = [t.project_id for t in user.led_teams]
            
        # Combine unique project IDs
        all_ids = list(set(assigned_project_ids + led_project_ids + team_project_ids))
        
        # Exclude projects user owns as specified
        projects = query.filter(
            Project.id.in_(all_ids),
            Project.owner_id != user.id
        ).all()
        
    return projects