from sqlalchemy import Column, Integer, String, Boolean, ForeignKey
from database import Base

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    password = Column(String)

class SkillProgress(Base):
    __tablename__ = "skill_progress"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    skill = Column(String)
    attempts = Column(Integer, default=0)
    weak = Column(Boolean, default=False)

from sqlalchemy import DateTime
from datetime import datetime

class InterviewAttempt(Base):
    __tablename__ = "interview_attempts"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer)
    role = Column(String)
    topic = Column(String)
    difficulty = Column(String)
    answer = Column(String)
    feedback = Column(String)
    timestamp = Column(DateTime, default=datetime.utcnow)
