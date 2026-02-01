from sqlalchemy import Column, Integer, String, Text, ForeignKey, TIMESTAMP, Date
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database.base import Base
from app.enums import Priority

class Epic(Base):
    __tablename__ = "epics"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    
    project_id = Column(
        Integer,
        ForeignKey("project.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    
    status = Column(String(50), default="TODO") # TODO, IN_PROGRESS, DONE
    
    start_date = Column(Date, nullable=True)
    end_date = Column(Date, nullable=True)
    
    created_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    
    created_at = Column(TIMESTAMP, server_default=func.now())
    updated_at = Column(TIMESTAMP, server_default=func.now(), onupdate=func.now())

    # Relationships
    project = relationship("Project", back_populates="epics")
    creator = relationship("User", foreign_keys=[created_by])
    stories = relationship("UserStory", back_populates="epic", cascade="all, delete-orphan")
    teams = relationship("Team", secondary="epic_teams", back_populates="epics")

# Association Table for Epic-Teams
class EpicTeam(Base):
    __tablename__ = "epic_teams"

    epic_id = Column(Integer, ForeignKey("epics.id", ondelete="CASCADE"), primary_key=True)
    team_id = Column(Integer, ForeignKey("teams.id", ondelete="CASCADE"), primary_key=True)

epic_teams = EpicTeam.__table__
