from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Boolean, UniqueConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database.base import Base

class Project(Base):
    __tablename__ = "project"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    project_prefix = Column(String(5), nullable=False)
    current_story_number = Column(Integer, default=1)
    owner_id = Column(Integer, ForeignKey("users.id"), nullable=True) # Temporarily nullable for migration
    is_active = Column(Boolean, default=True, nullable=False)

    __table_args__ = (
        UniqueConstraint('name', 'owner_id', name='_project_name_owner_uc'),
    )

    stories = relationship(
        "UserStory",
        back_populates="project",
        cascade="all, delete-orphan"
    )

    owner = relationship("User")

    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, onupdate=func.now())

    teams = relationship("Team", back_populates="project", cascade="all, delete-orphan")
    epics = relationship("Epic", back_populates="project", cascade="all, delete-orphan")

