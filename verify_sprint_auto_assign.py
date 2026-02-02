
import sys
import os
from datetime import date
from sqlalchemy.orm import Session

# Add the app directory to the python path
sys.path.append(os.path.join(os.getcwd()))

from app.database.session import SessionLocal
from app.models import UserStory, User, Project
from app.utils import story_service
from app.enums import StoryStatus, Priority, IssueType

def verify():
    db = SessionLocal()
    try:
        # 1. Get a user and project for testing
        user = db.query(User).first()
        project = db.query(Project).first()
        
        if not user or not project:
            print("Error: Need at least one user and one project in DB to run test.")
            return

        print(f"Testing with User: {user.username}, Project: {project.name}")

        # 2. Create three stories in the same project
        # We'll use story_service.create_story to simulate real usage
        class MockForm:
            def __init__(self, **kwargs):
                self.__dict__.update(kwargs)
                self.project_id = project.id
                self.assignee_id = user.id
                self.assignee_name = user.username
                self.team_id = None
                self.status = StoryStatus.TODO.value
                self.priority = Priority.MEDIUM.value
                self.start_date = date.today()
                self.end_date = None
                self.issue_type = IssueType.TASK.value
                self.parent_issue_id = None
                self.title = kwargs.get("title", "Test Story")
                self.description = "Test Description"
                self.release_number = None
                self.sprint_number = None
                self.epic_id = None
                self.story_pointer = None
                self.support_doc = None
                self.reviewer = None # Added missing field
            
            def to_create_request(self):
                return self

        print("Creating 3 test stories...")
        story1 = story_service.create_story(db, user, MockForm(title="Story 1"))
        story2 = story_service.create_story(db, user, MockForm(title="Story 2"))
        story3 = story_service.create_story(db, user, MockForm(title="Story 3"))
        
        # Ensure they are saved
        db.commit()

        # 3. Update story1 with an end date
        target_date = date(2026, 2, 15)
        print(f"Setting end date {target_date} for Story 1...")
        class MockUpdateForm:
            def __init__(self, **kwargs):
                self.__dict__.update(kwargs)
            def model_dump(self, **kwargs):
                # Ensure all fields expected by story_service are present or handled
                # The backend calls model_dump(exclude_unset=True)
                data = {
                    "title": self.__get_attr("title"),
                    "description": self.__get_attr("description"),
                    "project_id": self.__get_attr("project_id"),
                    "assignee_id": self.__get_attr("assignee_id"),
                    "team_id": self.__get_attr("team_id"),
                    "status": self.__get_attr("status"),
                    "priority": self.__get_attr("priority"),
                    "start_date": self.__get_attr("start_date"),
                    "end_date": self.__get_attr("end_date"),
                    "issue_type": self.__get_attr("issue_type"),
                    "parent_issue_id": self.__get_attr("parent_issue_id"),
                    "release_number": self.__get_attr("release_number"),
                    "sprint_number": self.__get_attr("sprint_number"),
                    "epic_id": self.__get_attr("epic_id"),
                    "story_pointer": self.__get_attr("story_pointer"),
                    "support_doc": self.__get_attr("support_doc"),
                    "reviewer": self.__get_attr("reviewer"),
                }
                
                if kwargs.get("exclude_unset"):
                    # For simplicity, we only include the keys that were passed to __init__
                    return {k: v for k, v in data.items() if k in self.__dict__}
                return data

            def __get_attr(self, name):
                return self.__dict__.get(name)
            
            def to_update_request(self):
                return self

        story_service.update_story(db, user, story1.id, MockUpdateForm(end_date=target_date))
        db.commit()
        
        db.refresh(story1)
        print(f"Story 1 sprint: {story1.sprint_number}")

        # 4. Update story2 with the SAME end date
        print(f"Setting SAME end date {target_date} for Story 2...")
        story_service.update_story(db, user, story2.id, MockUpdateForm(end_date=target_date))
        db.commit()

        db.refresh(story1)
        db.refresh(story2)
        print(f"Story 1 sprint: {story1.sprint_number}")
        print(f"Story 2 sprint: {story2.sprint_number}")

        if story1.sprint_number == story2.sprint_number and story1.sprint_number is not None:
            print("SUCCESS: Stories 1 and 2 assigned to the same sprint!")
        else:
            print("FAILURE: Stories 1 and 2 NOT assigned to the same sprint.")

        # 5. Update story3 with the SAME end date
        print(f"Setting SAME end date {target_date} for Story 3...")
        story_service.update_story(db, user, story3.id, MockUpdateForm(end_date=target_date))
        db.commit()

        db.refresh(story3)
        print(f"Story 3 sprint: {story3.sprint_number}")

        if story3.sprint_number == story1.sprint_number:
            print("SUCCESS: Story 3 also assigned to the same sprint!")
        else:
            print("FAILURE: Story 3 NOT assigned to the same sprint.")

        # 6. Verify activity log for story2 (which was auto-updated)
        db.commit() # Ensure everything is flushed and committed
        activities = story_service.get_user_story_activities(db, story2.id)
        print(f"Activities for Story 2 (count: {len(activities)}):")
        for a in activities:
            print(f" - Action: {a.action}, Changes: {a.changes}")
        
        auto_update_logged = any("Auto-assigned to sprint" in a.changes for a in activities)
        if auto_update_logged:
            print("SUCCESS: Activity log correctly recorded auto-assignment.")
        else:
            print("FAILURE: Activity log did NOT record auto-assignment.")

    finally:
        db.close()

if __name__ == "__main__":
    verify()
