from typing import Optional
from sqlalchemy.orm import Session

from app.models import UserStory
from app.enums import IssueType, StoryStatus
from app.exceptions import raise_bad_request, raise_circular_dependency

def validate_hierarchy(db: Session, parent_id: Optional[int], issue_type: str, current_issue_id: Optional[int] = None):
    try:
        current_type_enum = IssueType(issue_type)
    except ValueError:
        raise_bad_request(f"Invalid issue type: {issue_type}")

    if not parent_id:
        if current_type_enum == IssueType.SUBTASK:
            raise_bad_request("Subtask must belong to a Task (parent_issue_id required).")
        return

    parent_story = db.query(UserStory).filter(UserStory.id == parent_id).first()
    if not parent_story:
        raise_bad_request("Parent issue not found")
    
    if current_issue_id:
        if parent_id == current_issue_id:
            raise_bad_request("Cannot set issue as its own parent.")
        
        ancestor = parent_story
        depth = 0
        while ancestor.parent_issue_id and depth < 50:
            if ancestor.parent_issue_id == current_issue_id:
                raise_circular_dependency()
            ancestor = ancestor.parent 
            if not ancestor:
                break
            depth += 1
            
    try:
        parent_type_enum = IssueType(parent_story.issue_type)
    except ValueError:
        raise_bad_request(f"Parent issue has invalid type: {parent_story.issue_type}")
    
    # Use valid_parents property
    valid_parents = current_type_enum.valid_parents
    
    if not valid_parents:
        raise_bad_request(f"{current_type_enum.value} cannot have a parent issue.")

    if parent_type_enum not in valid_parents:
        allowed_str = " or ".join([t.value for t in valid_parents])
        raise_bad_request(f"{current_type_enum.value} must be a child of {allowed_str}, not {parent_type_enum.value}.")

def validate_status_transition(story: UserStory, new_status: str):
    if not new_status or new_status == story.status:
        return

    if new_status.lower() == StoryStatus.DONE.value.lower():
         pending_children = [
             child for child in story.children 
             if (child.status or "").lower() != StoryStatus.DONE.value.lower()
         ]
         if pending_children:
             raise_bad_request(f"Cannot mark as Done: Child issues are not Done ({len(pending_children)} pending).")

def validate_dates(start_date, end_date):
    """
    Validates that end_date is not earlier than start_date.
    Accepts date objects or None.
    """
    if start_date and end_date:
        if end_date < start_date:
            raise_bad_request("End date cannot be earlier than start date.")

