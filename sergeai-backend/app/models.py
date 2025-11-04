from sqlalchemy import Column, Integer, String, DateTime, Text, Float, Boolean, ForeignKey, JSON
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid

Base = declarative_base()

class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    user_uuid = Column(String, unique=True, default=lambda: str(uuid.uuid4()))
    username = Column(String, unique=True, index=True, nullable=False)
    email = Column(String, unique=True, index=True, nullable=False)
    full_name = Column(String, nullable=False)
    hashed_password = Column(String, nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    reset_token = Column(String, nullable=True)
    reset_token_expires = Column(DateTime, nullable=True)
    
    # Profile settings
    theme_preference = Column(String, default="light")  # light/dark
    notifications_enabled = Column(Boolean, default=True)
    daily_checkins = Column(Boolean, default=True)
    wellness_tips = Column(Boolean, default=True)
    breathing_reminders = Column(Boolean, default=False)
    biometric_lock = Column(Boolean, default=False)
    
    # Relationships
    chat_sessions = relationship("ChatSession", back_populates="user", cascade="all, delete-orphan")
    mood_entries = relationship("MoodEntry", back_populates="user", cascade="all, delete-orphan")
    crisis_logs = relationship("CrisisLog", back_populates="user", cascade="all, delete-orphan")
    breathing_sessions = relationship("BreathingSession", back_populates="user", cascade="all, delete-orphan")


class ChatSession(Base):
    __tablename__ = "chat_sessions"
    
    id = Column(Integer, primary_key=True, index=True)
    session_uuid = Column(String, unique=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    title = Column(String, default="New Chat")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    is_active = Column(Boolean, default=True)
    
    # Relationships
    user = relationship("User", back_populates="chat_sessions")
    messages = relationship("ChatMessage", back_populates="session", cascade="all, delete-orphan")


class ChatMessage(Base):
    __tablename__ = "chat_messages"
    
    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey("chat_sessions.id"), nullable=False)
    role = Column(String, nullable=False)  # "user" or "assistant"
    content = Column(Text, nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow)
    message_metadata = Column(JSON, nullable=True)  # Store additional info like sentiment, etc.
    
    # Relationships
    session = relationship("ChatSession", back_populates="messages")


class MoodEntry(Base):
    __tablename__ = "mood_entries"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    mood_score = Column(Integer, nullable=False)  # 1-5 scale
    energy_level = Column(String, nullable=True)  # very_low, low, moderate, high, very_high
    affecting_factors = Column(JSON, nullable=True)  # Array of factors
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    user = relationship("User", back_populates="mood_entries")


class CrisisLog(Base):
    __tablename__ = "crisis_logs"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)  # Nullable for anonymous access
    crisis_type = Column(String, nullable=False)  # call, text, emergency, ai_chat
    service_used = Column(String, nullable=False)  # 988, 741741, 911, ai_assistant
    timestamp = Column(DateTime, default=datetime.utcnow)
    resolved = Column(Boolean, default=False)
    follow_up_needed = Column(Boolean, default=True)

    # Relationships
    user = relationship("User", back_populates="crisis_logs")


class BreathingSession(Base):
    __tablename__ = "breathing_sessions"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    technique = Column(String, default="4-7-8")  # Type of breathing technique
    duration_minutes = Column(Integer, nullable=False)
    completed = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    user = relationship("User", back_populates="breathing_sessions")


class SystemStats(Base):
    __tablename__ = "system_stats"
    
    id = Column(Integer, primary_key=True, index=True)
    date = Column(DateTime, default=datetime.utcnow)
    active_users = Column(Integer, default=0)
    total_sessions = Column(Integer, default=0)
    crisis_interventions = Column(Integer, default=0)
    positive_feedback_rate = Column(Float, default=0.0)
    average_mood_score = Column(Float, default=0.0)
