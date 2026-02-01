from pydantic import BaseModel, Field
from fastapi import Form, File, UploadFile
from typing import Optional, Union, List
from datetime import datetime, date
from typing import Optional
from app.schemas.project_schema import TeamSimple

from app.enums import IssueType

class StorySimpleResponse(BaseModel):
    id: int
    title: str
    story_code: Optional[str] = None
    
    class Config:
        from_attributes = True

class EpicResponse(BaseModel):
    id: int
    title: str
    story_code: Optional[str] = None
    project_id: int
    project_name: str
    
    class Config:
        from_attributes = True

class UserStoryResponse(BaseModel):
    id: int
    project_id: int
    project_name: Optional[str] = None
    story_pointer: Optional[str] = None # Support existing
    story_code: Optional[str] = None # New standard

    team: Optional[TeamSimple] = None

    release_number: Optional[str] = None
    sprint_number: Optional[str] = None

    assignee_id: Optional[int] = None
    team_id: Optional[int] = None

    assignee: Optional[str] = "Unassigned"
    reviewer: Optional[str] = None

    title: str
    description: str
    issue_type: Optional[str]
    priority: Optional[str]
    status: str

    support_doc: Optional[str]
    start_date: Optional[date]
    end_date: Optional[date]
    parent_issue_id: Optional[int] = None
    epic_id: Optional[int] = None

    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True

class UserStoryActivityResponse(BaseModel):
    """
    Aggregated activity log response.
    Represents ONE save action with multiple field changes.
    """
    id: int
    story_id: int
    user_id: Optional[int]
    action: str  # UPDATED, CREATED, STATUS_CHANGED
    changes: str  # Human-readable text
    change_count: Optional[int] = 0  # Number of fields changed
    username: Optional[str] = "System"
    created_at: datetime

    class Config:
        from_attributes = True

class UserStoryCreateRequest(BaseModel):
    project_id: int
    title: str
    description: str
    status: str
    
    release_number: Optional[str] = None
    sprint_number: Optional[str] = None
    assignee_id: Optional[int] = None
    assignee_name: Optional[str] = None
    reviewer: Optional[str] = None
    issue_type: Optional[str] = None
    priority: Optional[str] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    team_id: Optional[int] = None
    parent_issue_id: Optional[int] = None
    epic_id: Optional[int] = None

class UserStoryUpdateRequest(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    sprint_number: Optional[str] = None
    assignee: Optional[str] = None
    assignee_id: Optional[int] = None # Added for consistency
    reviewer: Optional[str] = None
    status: Optional[str] = None
    parent_issue_id: Optional[int] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    priority: Optional[str] = None
    issue_type: Optional[str] = None

    
class UserStoryCreateForm:
    def __init__(
        self,
        project_id: int = Form(...),
        release_number: Optional[str] = Form(None),
        sprint_number: Optional[str] = Form(None),
        assignee: str = Form(...),
        assignee_id: Optional[str] = Form(None),
        assigned_to: Optional[str] = Form(None),
        reviewer: Optional[str] = Form(None),
        title: str = Form(...),
        description: str = Form(...),
        issue_type: Optional[IssueType] = Form(None),
        priority: Optional[str] = Form(None),
        status: str = Form(...),
        support_doc: Optional[Union[UploadFile, str]] = File(None), 
        start_date: Optional[date] = Form(None),
        end_date: Optional[date] = Form(None),
        team_id: Optional[str] = Form(None),
        parent_issue_id: Optional[str] = Form(None),
        epic_id: Optional[str] = Form(None),
    ):
        self.project_id = project_id
        self.release_number = release_number
        self.sprint_number = sprint_number
        self.assignee = assignee
        self.assignee_id = assignee_id
        self.assigned_to = assigned_to
        self.reviewer = reviewer
        self.title = title
        self.description = description
        self.issue_type = issue_type
        self.priority = priority
        self.status = status
        self.support_doc = support_doc
        self.start_date = start_date
        self.end_date = end_date
        self.team_id = team_id
        self.parent_issue_id = parent_issue_id
        self.epic_id = epic_id

    def to_create_request(self) -> "UserStoryCreateRequest":
        def parse_optional_int(val):
            if val is None: return None
            if not val or (isinstance(val, str) and not val.strip()): return None
            try: return int(val)
            except: return None

        p_assignee_id = parse_optional_int(self.assigned_to) if self.assigned_to is not None else parse_optional_int(self.assignee_id)
        p_team_id = parse_optional_int(self.team_id)
        p_parent_id = parse_optional_int(self.parent_issue_id)
        p_epic_id = parse_optional_int(self.epic_id)
        
        return UserStoryCreateRequest(
            project_id=self.project_id,
            release_number=self.release_number,
            sprint_number=self.sprint_number,
            assignee_id=p_assignee_id,
            assignee_name=self.assignee,
            reviewer=self.reviewer,
            title=self.title,
            description=self.description,
            issue_type=self.issue_type.value if self.issue_type else None,
            priority=self.priority,
            status=self.status,
            start_date=self.start_date,
            end_date=self.end_date,
            team_id=p_team_id,
            parent_issue_id=p_parent_id,
            epic_id=p_epic_id
        )

class UserStoryUpdateForm:
    def __init__(
        self,
        title: Optional[str] = Form(None),
        description: Optional[str] = Form(None),
        sprint_number: Optional[str] = Form(None),
        assignee: Optional[str] = Form(None),
        assignee_id: Optional[str] = Form(None),
        reviewer: Optional[str] = Form(None),
        status: Optional[str] = Form(None),
        parent_issue_id: Optional[str] = Form(None),
        start_date: Optional[str] = Form(None),
        end_date: Optional[str] = Form(None),
        priority: Optional[str] = Form(None),
        issue_type: Optional[str] = Form(None),
    ):
        self.title = title
        self.description = description
        self.sprint_number = sprint_number
        self.assignee = assignee
        self.assignee_id = assignee_id
        self.reviewer = reviewer
        self.status = status
        self.parent_issue_id = parent_issue_id
        self.start_date = start_date
        self.end_date = end_date
        self.priority = priority
        self.issue_type = issue_type

    def to_update_request(self) -> "UserStoryUpdateRequest":
        def clean_str(val):
            if val == "" or val == "null" or val == "undefined": return None
            return val
            
        def clean_int(val):
            if not val: return None
            try: return int(val)
            except: return None
        
        def parse_date_str(dstr):
            if not dstr: return None
            return dstr[:10]

        from datetime import datetime
        updates = {}
        if self.title is not None: updates['title'] = self.title
        if self.description is not None: updates['description'] = self.description
        if self.sprint_number is not None: updates['sprint_number'] = clean_str(self.sprint_number)
        if self.assignee is not None: updates['assignee'] = self.assignee
        if self.assignee_id is not None: updates['assignee_id'] = clean_int(self.assignee_id)
        if self.reviewer is not None: updates['reviewer'] = clean_str(self.reviewer)
        if self.status is not None: updates['status'] = self.status
        if self.parent_issue_id is not None: updates['parent_issue_id'] = clean_int(self.parent_issue_id)
        if self.priority is not None: updates['priority'] = self.priority
        if self.issue_type is not None: updates['issue_type'] = self.issue_type
        
        if self.start_date is not None:
             dval = parse_date_str(self.start_date)
             updates['start_date'] = datetime.strptime(dval, "%Y-%m-%d").date() if dval else None
        if self.end_date is not None:
             dval = parse_date_str(self.end_date)
             updates['end_date'] = datetime.strptime(dval, "%Y-%m-%d").date() if dval else None
             
        return UserStoryUpdateRequest(**updates)


class StoryRepoCreate(BaseModel):
    project_id: int
    release_number: Optional[str] = None
    sprint_number: Optional[str] = None
    story_pointer: str
    assignee: str
    assignee_id: Optional[int]
    reviewer: Optional[str] = None
    title: str
    description: str
    issue_type: Optional[str]
    priority: Optional[str]
    status: Optional[str]
    support_doc: Optional[str] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    team_id: Optional[int] = None
    parent_issue_id: Optional[int] = None
    epic_id: Optional[int] = None
    created_by: int

    @classmethod
    def create_from_request(
        cls, 
        project_id: int, 
        user_id: int, 
        story_in: UserStoryCreateRequest, 
        story_code: str, 
        assignee_name: str, 
        assignee_id: Optional[int], 
        file_path: Optional[str],
        team_id: Optional[int]
    ) -> "StoryRepoCreate":
        return cls(
            project_id=project_id,
            release_number=story_in.release_number,
            sprint_number=story_in.sprint_number,
            story_pointer=story_code,
            assignee=assignee_name,
            assignee_id=assignee_id,
            reviewer=story_in.reviewer,
            title=story_in.title,
            description=story_in.description,
            issue_type=story_in.issue_type,
            priority=story_in.priority,
            status=story_in.status,
            support_doc=file_path,
            start_date=story_in.start_date,
            end_date=story_in.end_date,
            team_id=team_id,
            parent_issue_id=story_in.parent_issue_id,
            epic_id=story_in.epic_id,
            created_by=user_id
        )