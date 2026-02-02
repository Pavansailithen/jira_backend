from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func, or_
from datetime import datetime, timedelta
from typing import List

from app.database.session import get_db
from app.models import User, Project, ModeSwitchRequest, Team, UserStory
from app.models.user_story_activity import UserStoryActivity
from app.auth.dependencies import get_current_user
from app.enums import UserRole
from app.exceptions import raise_forbidden
from app.utils.logger import get_logger
from app.enums import UserRole

logger = get_logger(__name__)

router = APIRouter(prefix="/stats", tags=["Statistics"])

@router.get("/master-admin/summary")
def get_master_admin_summary(
    month: int = None,
    year: int = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """
    Retrieves statistical summary for the Master Admin dashboard.
    Includes total projects, admin breakdown, and weekly project creation stats.
    """
    if not (user.is_master_admin or user.role == UserRole.ADMIN):
        raise_forbidden("Only Master Admin can access dashboard statistics")

    # 1. Total Projects
    total_projects = db.query(Project).count()

    # 2. Breakdown by Admin
    admin_breakdown = db.query(
        User.username,
        User.email,
        func.count(Project.id).label("project_count")
    ).join(Project, User.id == Project.owner_id)\
     .group_by(User.id).all()

    admins = [
        {"username": row[0], "email": row[1], "count": row[2]}
        for row in admin_breakdown
    ]

    # 3. Weekly Statistics
    now = datetime.now()
    target_month = month if month is not None else now.month
    target_year = year if year is not None else now.year
    
    # Calculate start of the month
    start_of_month = datetime(target_year, target_month, 1)
    # Calculate end of the month (approximate or precise)
    if target_month == 12:
        end_of_month = datetime(target_year + 1, 1, 1)
    else:
        end_of_month = datetime(target_year, target_month + 1, 1)

    weekly_stats = []
    # Divide month into 4 weeks
    current_start = start_of_month
    for i in range(4):
        # Last week takes the remainder of the month
        if i == 3:
            next_start = end_of_month
        else:
            next_start = current_start + timedelta(days=7)
            
        count = db.query(Project).filter(
            Project.created_at >= current_start,
            Project.created_at < next_start
        ).count()
        
        weekly_stats.append({
            "week": f"Week {i+1}",
            "projects": count,
            "range": f"{current_start.strftime('%b %d')} - {next_start.strftime('%b %d')}"
        })
        current_start = next_start

    return {
        "total_projects": total_projects,
        "admin_breakdown": admins,
        "weekly_stats": weekly_stats,
        "selected_month": target_month,
        "selected_year": target_year
    }

@router.get("/master-admin/mode-switch-history")
def get_mode_switch_history(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """
    Retrieves history of mode switch requests.
    Only accessible by Master Admin.
    """
    if not user.is_master_admin:
        raise_forbidden("Only Master Admin can access history")

    requests = db.query(ModeSwitchRequest).order_by(ModeSwitchRequest.created_at.desc()).all()
    
    result = []
    for r in requests:
        result.append({
            "id": r.id,
            "username": r.user.username,
            "email": r.user.email,
            "requested_mode": r.requested_mode,
            "status": r.status,
            "created_at": r.created_at,
            "reason": r.reason
        })
    return result

@router.get("/activity")
def get_recent_activity(
    limit: int = 50,
    project_id: int = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """
    Retrieves recent activity across projects based on user role/view_mode.
    Optionally filters by project_id.
    """
    query = db.query(UserStoryActivity).join(UserStory).join(Project)

    if project_id:
        query = query.filter(UserStory.project_id == project_id)

    if user.is_master_admin:
        pass # Master Admin sees all activity
    elif user.view_mode == UserRole.ADMIN:
        # Admin sees activity in projects they own
        query = query.filter(Project.owner_id == user.id)
    else:
        # Developer sees activity in:
        # 1. Projects they are a team member of
        # 2. Stories they are assigned to
        
        # Get project IDs where user is a team member
        member_project_ids = db.query(Team.project_id).filter(
            Team.members.any(id=user.id)
        ).scalar_subquery()
        
        query = query.filter(
            or_(
                Project.id.in_(member_project_ids),
                UserStory.assignee_id == user.id
            )
        )
    
    # Eager load relationships
    from sqlalchemy.orm import joinedload
    activities = query.options(
        joinedload(UserStoryActivity.user),
        joinedload(UserStoryActivity.story).joinedload(UserStory.project)
    ).order_by(UserStoryActivity.created_at.desc()).limit(limit).all()

    return [
        {
            "id": a.id,
            "action": a.action, # CREATED, UPDATED, etc.
            "changes": a.changes,
            "created_at": a.created_at,
            "actor": {
                "id": a.user.id if a.user else None,
                "username": a.user.username if a.user else "Unknown",
                "email": a.user.email if a.user else ""
            },
            "issue": {
                "id": a.story.id,
                "key": f"{a.story.project.project_prefix}-{a.story.story_pointer}" if a.story.project else str(a.story.id),
                "title": a.story.title,
                "project_id": a.story.project_id,
                "project_name": a.story.project.name if a.story.project else "Unknown"
            }
        }
        for a in activities
    ]

@router.get("/landing")
def get_landing_stats(db: Session = Depends(get_db)):
    """
    Retrieves user statistics for the landing page.
    Public endpoint.
    """
    total_users = db.query(User).count()
    # Note: Using _role because role is a hybrid property and we want DB side filtering
    # Also considering Master Admin as Admin for this stat or just standard Admins? 
    # Let's count standard admins + master admin if we want, but simpler to just count by stored role for now.
    # Master admin has email check in model, so might have None or 'ADMIN' in _role.
    # Let's simple count based on _role content.
    
    total_admins = db.query(User).filter(User._role == UserRole.ADMIN.value).count()
    # Check for master admin separately if needed, but typically they are just 1. 
    # If we want to be precise:
    # total_admins = db.query(User).filter(or_(User._role == UserRole.ADMIN.value, User.email == "admin@jira.local")).count()
    # But let's stick to the simple requirement first.
    
    total_developers = db.query(User).filter(User._role == UserRole.DEVELOPER.value).count()
    total_testers = db.query(User).filter(User._role == UserRole.TESTER.value).count()
    
    return {
        "total_users": total_users,
        "total_admins": total_admins,
        "total_developers": total_developers,
        "total_testers": total_testers
    }
