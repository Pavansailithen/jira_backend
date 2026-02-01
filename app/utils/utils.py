from typing import Optional
from app.utils.activity_logger import log_activity
from app.utils.logger import get_logger

logger = get_logger(__name__)

def story_to_dict(s):
    """
    Converts a UserStory model instance to a dictionary.
    Handles None checks for relationships.
    """
    if not s: return None
    
    # Safely get team info
    team_info = None
    try:
        if s.team_id and s.team:
            team_info = {"id": s.team.id, "name": s.team.name}
    except Exception:
        # Team relationship not loaded or failed to load
        pass
    
    return {
        "id": s.id,
        "project_id": s.project_id,
        "project_name": s.project.name if s.project else "Unknown",
        "story_pointer": s.story_pointer,
        "release_number": s.release_number,
        "sprint_number": s.sprint_number,
        "assignee_id": s.assignee_id,
        "team_id": s.team_id,
        "team": team_info,
        "assignee": s.assignee,
        "reviewer": s.reviewer,
        "title": s.title,
        "description": s.description,
        "issue_type": s.issue_type,
        "priority": s.priority,
        "status": s.status,
        "support_doc": s.support_doc,
        "start_date": str(s.start_date) if s.start_date else None,
        "end_date": str(s.end_date) if s.end_date else None,
        "parent_issue_id": s.parent_issue_id,
        "epic_id": s.epic_id
    }

def track_change(db, story, user_id, field, old_value, new_value):
    """
    Tracks changes to a story field and logs activity if the value changed.
    
    Args:
        db: Database session
        story: The user story object
        user_id: ID of the user making changes
        field: Name of the changed field
        old_value: Previous value
        new_value: New value
    """
    norm_old = "" if old_value is None else str(old_value).strip()
    norm_new = "" if new_value is None else str(new_value).strip()
    if field in ["start_date", "end_date"]:
        try:
            o_date = str(old_value)[:10] if old_value else ""
            n_date = str(new_value)[:10] if new_value else ""
            if o_date == n_date:
                return
        except:
            pass
    if norm_old == norm_new:
        return
    log_activity(
        db=db,
        issue_id=story.id,
        user_id=user_id,
        action_type="FIELD_UPDATED",
        field_changed=field,
        old_value=old_value,
        new_value=new_value
    )
