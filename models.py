from sqlalchemy import Column, Integer, String, ForeignKey, Date, Text, DateTime, Boolean
from extensions import db  # Use `db` from extensions.py
from sqlalchemy.orm import relationship
import uuid  # Import UUID for generating unique tokens
from datetime import datetime

class Grade(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(20), nullable=False, unique=True)  # Like 'Grade 1', 'Grade 2'


class Subject(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False, unique=True)  # Like 'Math', 'Science'


class School(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False, unique=True)  # School name
    code = db.Column(db.String(20), nullable=False, unique=True)  # School code like 'AUES'
    level1_admin_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)  # Reference to Level 1 Admin


# Association table for User <-> Grade (Many-to-Many)
user_grades = db.Table('user_grades',
    db.Column('user_id', db.Integer, db.ForeignKey('user.id'), primary_key=True),
    db.Column('grade_id', db.Integer, db.ForeignKey('grade.id'), primary_key=True)
)


# Association table for User <-> Subject (Many-to-Many)
user_subjects = db.Table('user_subjects',
    db.Column('user_id', db.Integer, db.ForeignKey('user.id'), primary_key=True),
    db.Column('subject_id', db.Integer, db.ForeignKey('subject.id'), primary_key=True)
)


# Association table for User <-> School (Many-to-Many)
user_schools = db.Table('user_schools',
    db.Column('user_id', db.Integer, db.ForeignKey('user.id'), primary_key=True),
    db.Column('school_id', db.Integer, db.ForeignKey('school.id'), primary_key=True)
)


class User(db.Model):
    id = Column(Integer, primary_key=True)
    name = db.Column(db.String(120))
    email = Column(String(120), unique=True, nullable=False)
    role = Column(String(20), nullable=False)  # 'teacher', 'substitute', 'admin_l1', 'admin_l2'
    phone = Column(String(20), nullable=True)
    timezone = Column(String(50), nullable=True, default='UTC')  # User's timezone
    
    # Track who created this user (for admin hierarchy)
    created_by = Column(Integer, ForeignKey('user.id'), nullable=True)
    
    # Many-to-Many relationships
    grades = db.relationship('Grade', secondary=user_grades, backref='users')
    subjects = db.relationship('Subject', secondary=user_subjects, backref='users')
    schools = db.relationship('School', secondary=user_schools, backref='associated_users')


class SubstituteUnavailability(db.Model):
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('user.id'), nullable=False)
    date = Column(Date, nullable=False)
    all_day = Column(Boolean, default=True)  # True if unavailable all day, False if specific hours
    time_range = Column(String(50), nullable=True)  # Format: "08:00-12:00" (if all_day is False)
    repeat_pattern = Column(String(20), nullable=True)  # e.g., "Monday", "Tuesday", etc.
    repeat_until = Column(Date, nullable=True)  # Date until which the pattern repeats
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Relationship to User
    user = relationship("User", foreign_keys=[user_id], backref="unavailability")


class SubstituteRequest(db.Model):
    id = Column(Integer, primary_key=True)
    teacher_id = Column(Integer, ForeignKey('user.id'), nullable=False)
    date = Column(Date, nullable=False)
    time = Column(String(50), nullable=False)
    details = Column(Text, nullable=True)
    reason = Column(String(20), nullable=True)  # Options: Personal, Medical, Sickness, School Business
    status = Column(String(20), default='Open')
    substitute_id = Column(Integer, ForeignKey('user.id'), nullable=True)
    substitute_user = relationship("User", foreign_keys=[substitute_id])
    grade_id = Column(Integer, ForeignKey('grade.id'), nullable=True)
    subject_id = Column(Integer, ForeignKey('subject.id'), nullable=True)
    school_id = Column(Integer, ForeignKey('school.id'), nullable=True)  # School for this request (from teacher's schools)
    grade = relationship("Grade", foreign_keys=[grade_id])
    subject = relationship("Subject", foreign_keys=[subject_id])
    school = relationship("School", foreign_keys=[school_id])
    token = Column(String(36), unique=True, nullable=False, default=lambda: str(uuid.uuid4()))  # Unique Token
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)  # When the request was made
    
    # Get the teacher user
    teacher = relationship("User", foreign_keys=[teacher_id], backref="substitute_requests")
