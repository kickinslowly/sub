from sqlalchemy import Column, Integer, String, ForeignKey, Date, Text, DateTime
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


class User(db.Model):
    id = Column(Integer, primary_key=True)
    name = db.Column(db.String(120))
    email = Column(String(120), unique=True, nullable=False)
    role = Column(String(20), nullable=False)  # 'teacher', 'substitute', 'admin_l1', 'admin_l2'
    phone = Column(String(20), nullable=True)
    
    # Track who created this user (for admin hierarchy)
    created_by = Column(Integer, ForeignKey('user.id'), nullable=True)
    
    # Many-to-Many relationships
    grades = db.relationship('Grade', secondary=user_grades, backref='users')
    subjects = db.relationship('Subject', secondary=user_subjects, backref='users')


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
    grade = relationship("Grade", foreign_keys=[grade_id])
    subject = relationship("Subject", foreign_keys=[subject_id])
    token = Column(String(36), unique=True, nullable=False, default=lambda: str(uuid.uuid4()))  # Unique Token
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)  # When the request was made
