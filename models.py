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

from sqlalchemy import Text

class Course(Base):
    __tablename__ = "courses"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))

    title = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    level = Column(String, default="beginner")     # beginner/intermediate/advanced
    status = Column(String, default="draft")       # draft/generated


class Chapter(Base):
    __tablename__ = "chapters"

    id = Column(Integer, primary_key=True, index=True)
    course_id = Column(Integer, ForeignKey("courses.id"))

    title = Column(String, nullable=False)
    order_index = Column(Integer, default=0)


class Unit(Base):
    __tablename__ = "units"

    id = Column(Integer, primary_key=True, index=True)
    chapter_id = Column(Integer, ForeignKey("chapters.id"))

    title = Column(String, nullable=False)
    order_index = Column(Integer, default=0)

    content = Column(Text, nullable=True)          # generated lesson text
    status = Column(String, default="pending")     # pending/generated
    estimated_minutes = Column(Integer, default=10)

