from typing import List, Optional, Any, Dict
from sqlalchemy.orm import Session

from app.models import User, UserStory, Project, Team
from app.schemas.story_schema import StoryRepoCreate
from app.enums import IssueType, StoryAction
from app.constants import ErrorMessages, ADMIN, DEVELOPER
from app.exceptions import raise_forbidden, raise_bad_request
from app.utils.common import get_object_or_404, check_project_active
from app.utils.notification_service import create_notification, notify_issue_assigned
from app.auth.permissions import can_create_issue, can_update_issue

# New imports
from app.utils.story_repo import (
    get_next_story_code,
    get_story_by_id_db,
    get_user_story_activities_db,
    create_story_record,
    update_story_record,
    delete_story_record,
    search_stories_db,
    find_potential_parents_db,
    get_epics_db,
    get_distinct_project_ids_for_assignee,
    get_epics_accessible_by_user,
    get_assigned_stories_db,
    get_stories_by_project_db
)
from app.utils.story_validation import validate_hierarchy, validate_status_transition, validate_dates

def create_activity(db: Session, story_id: int, user_id: Optional[int], action: str, changes_dict: dict):
    from app.models import UserStoryActivity
    if not changes_dict and action == StoryAction.UPDATED.value:
        return

    change_lines = []
    if action == StoryAction.CREATED.value:
        change_lines.append("Issue Created")
    
    for field, vals in changes_dict.items():
        change_lines.append(f"{field}: {vals['old']} → {vals['new']}")
        
    changes_text = "\\n".join(change_lines)
    
    activity = UserStoryActivity(
        story_id=story_id,
        user_id=user_id,
        action=action,
        changes=changes_text,
        change_count=len(changes_dict)
    )
    db.add(activity)

# Re-exports or wrappers
def get_story_by_id(db: Session, story_id: int) -> Optional[UserStory]:
    return get_story_by_id_db(db, story_id)

def get_user_story_activities(db: Session, story_id: int) -> List[Any]:
    return get_user_story_activities_db(db, story_id)

def create_story(db: Session, user: User, story_in: Any, file_path: Optional[str] = None) -> UserStory:
    project_id = story_in.project_id
    assignee_id = story_in.assignee_id
    team_id = story_in.team_id
    assignee_name = story_in.assignee_name
    
    # Assignee Logic
    final_assignee_id = assignee_id
    final_assignee_name = assignee_name

    if user.role == DEVELOPER:
        is_team_lead = False
        if team_id:
             if any(t.id == team_id for t in user.led_teams):
                is_team_lead = True
        
        is_project_lead = any(t.project_id == project_id for t in user.led_teams)

        if is_team_lead or is_project_lead:
             if final_assignee_id:
                 target_user = get_object_or_404(db, User, final_assignee_id, ErrorMessages.USER_NOT_FOUND)
                 final_assignee_name = target_user.username
             else:
                 if not final_assignee_name or not final_assignee_name.strip():
                     final_assignee_name = "Unassigned"
        else:
             final_assignee_id = user.id
             final_assignee_name = user.username
    else:
        if final_assignee_id:
            target_user = get_object_or_404(db, User, final_assignee_id, ErrorMessages.USER_NOT_FOUND)
            final_assignee_name = target_user.username
        else:
            if not final_assignee_name or not final_assignee_name.strip():
                final_assignee_name = "Unassigned"

    project = get_object_or_404(db, Project, project_id, ErrorMessages.PROJECT_NOT_FOUND)
    check_project_active(project.is_active)

    if not can_create_issue(user, project_id, team_id, db):
        is_owner = project.owner_id == user.id
        if user.view_mode == DEVELOPER and is_owner:
            msg = "Project owners must switch to Admin mode to create issues in their own projects."
        elif user.view_mode == ADMIN and not is_owner:
            msg = "In Admin mode, you can only create issues in projects you own."
        else:
            msg = ErrorMessages.NO_PERMISSION_CREATE
        raise_forbidden(msg)

    validate_hierarchy(db, story_in.parent_issue_id, story_in.issue_type)
    validate_dates(story_in.start_date, story_in.end_date)
    
    try:
        story_code = get_next_story_code(db, project_id)
    except ValueError as e:
        raise_bad_request(str(e))

    if final_assignee_id and team_id:
        team = get_object_or_404(db, Team, team_id, ErrorMessages.TEAM_NOT_FOUND)
        member_ids = [m.id for m in (team.members or [])]
        if final_assignee_id not in member_ids:
            target_user = get_object_or_404(db, User, final_assignee_id, ErrorMessages.USER_NOT_FOUND)
            team.members.append(target_user)
            db.add(team)
            db.flush()

    # Prepare data for repo using Factory method
    create_data = StoryRepoCreate.create_from_request(
        project_id=project_id,
        user_id=user.id,
        story_in=story_in,
        story_code=story_code,
        assignee_name=final_assignee_name,
        assignee_id=final_assignee_id,
        file_path=file_path,
        team_id=team_id
    )
    
    new_story = create_story_record(db, create_data.model_dump())
    
    # Activity & Notification
    create_activity(db, new_story.id, user.id, StoryAction.CREATED.value, {"Status": {"old": "None", "new": story_in.status}})
    
    if new_story.assignee_id:
        notify_issue_assigned(db, new_story.assignee_id, new_story.title)
        
    return new_story

def update_story(db: Session, user: User, story_id: int, story_in: Any) -> UserStory:
    story = get_object_or_404(db, UserStory, story_id, ErrorMessages.STORY_NOT_FOUND)
    check_project_active(story.project.is_active)
    
    if not can_update_issue(user, story, db):
        raise_forbidden(ErrorMessages.NO_PERMISSION_EDIT)

    updates = story_in.model_dump(exclude_unset=True)

    if user.role == DEVELOPER:
        if 'assignee' in updates: del updates['assignee']
        if 'assignee_id' in updates: del updates['assignee_id']

    changes = {}
    
    if 'parent_issue_id' in updates:
        new_parent_id = updates['parent_issue_id']
        if new_parent_id != story.parent_issue_id:
            try:
                validate_hierarchy(db, new_parent_id, story.issue_type, current_issue_id=story.id)
            except Exception as e:
                raise_bad_request(f"{ErrorMessages.INVALID_PARENT}: {str(e)}")
            changes["parent_issue_id"] = {"old": str(story.parent_issue_id), "new": str(new_parent_id)}
            
    if 'status' in updates and updates['status'] != story.status:
        validate_status_transition(story, updates['status'])
        
    # [NEW] Validate dates if either changed
    final_start = updates.get('start_date', story.start_date)
    final_end = updates.get('end_date', story.end_date)
    validate_dates(final_start, final_end)

    for field, new_val in updates.items():
        if field == "parent_issue_id" and field in changes: 
             setattr(story, field, new_val)
             continue
             
        old_val = getattr(story, field, None)
        str_old = str(old_val) if old_val is not None else ""
        str_new = str(new_val) if new_val is not None else ""
        
        if str_old != str_new:
            changes[field] = {"old": str_old, "new": str_new}
            setattr(story, field, new_val)
            
            if field == "assignee_id":
                 assignee_user = db.query(User).filter(User.id == new_val).first()
                 story.assignee = assignee_user.username if assignee_user else "Unknown"
                 if new_val:
                     notify_issue_assigned(db, new_val, story.title)
                     
            if field == "status" and story.assignee_id:
                create_notification(db, story.assignee_id, "Status Updated", f"Story '{story.title}' is now {new_val}")
            
            if field == "priority" and story.assignee_id:
                create_notification(db, story.assignee_id, "Priority Updated", f"Priority for '{story.title}' changed to {new_val}")

    updated_story = update_story_record(db, story)
    
    create_activity(db, story.id, user.id, StoryAction.UPDATED.value, changes)
    
    return story

def delete_story(db: Session, story: UserStory):
    delete_story_record(db, story)

def search_stories(db: Session, user: User, query_str: str) -> List[UserStory]:
    if user.is_master_admin or user.role == ADMIN:
        return search_stories_db(db, query_str, apply_filters=False)
    
    # Logic for non-admin
    led_ids = [t.project_id for t in user.led_teams]
    member_team_ids = [t.id for t in user.teams]
    assigned_project_ids = get_distinct_project_ids_for_assignee(db, user.id)
    
    return search_stories_db(
        db, 
        query_str, 
        filter_assignee_id=user.id,
        filter_team_ids=member_team_ids,
        filter_project_ids=led_ids + assigned_project_ids,
        apply_filters=True
    )

def find_potential_parents(db: Session, project_id: int, target_types: List[str], exclude_id: Optional[int] = None) -> List[UserStory]:
    return find_potential_parents_db(db, project_id, target_types, exclude_id)

def get_available_parents(db: Session, user: User, project_id: int, issue_type: str, exclude_id: Optional[int]) -> List[UserStory]:
    project = get_object_or_404(db, Project, project_id, ErrorMessages.PROJECT_NOT_FOUND)
    is_owner = project.owner_id == user.id
    
    if not user.is_master_admin:
        if user.view_mode == ADMIN and not is_owner:
            raise_forbidden()
        elif user.view_mode == DEVELOPER and is_owner:
            raise_forbidden()
            
    target_type = None
    if issue_type == IssueType.STORY.value: target_type = IssueType.EPIC.value
    elif issue_type == IssueType.TASK.value: target_type = IssueType.STORY.value
    elif issue_type == IssueType.SUBTASK.value: target_type = IssueType.TASK.value
    elif issue_type == IssueType.BUG.value:
         return find_potential_parents(db, project_id, [IssueType.STORY.value, IssueType.TASK.value], exclude_id)
         
    if not target_type: return []
    
    return find_potential_parents(db, project_id, [target_type], exclude_id)

def get_epics(db: Session, user: User) -> List[UserStory]:
    if user.is_master_admin:
        return get_epics_db(db)
    
    owned_ids = [p.id for p in db.query(Project).filter(Project.owner_id == user.id).all()]
    
    return get_epics_accessible_by_user(db, user.id, owned_ids)

def get_my_assigned_stories(db: Session, user: User) -> List[UserStory]:
    if user.is_master_admin:
         return get_assigned_stories_db(db, user.id)
        
    owned_project_ids = [p.id for p in db.query(Project).filter(Project.owner_id == user.id).all()]
    
    if user.view_mode == ADMIN:
        if not owned_project_ids: return []
        return get_assigned_stories_db(db, user.id, project_ids_in=owned_project_ids)
    else:
        if owned_project_ids:
             return get_assigned_stories_db(db, user.id, project_ids_not_in=owned_project_ids)
        else:
             return get_assigned_stories_db(db, user.id)

def get_stories_by_project(db: Session, project_id: int) -> List[UserStory]:
    return get_stories_by_project_db(db, project_id)
