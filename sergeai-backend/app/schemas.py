from pydantic import BaseModel, EmailStr, validator
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum

# User Schemas
class UserCreate(BaseModel):
    username: str
    email: EmailStr
    full_name: str
    password: str
    
    @validator('username')
    def validate_username(cls, v):
        if len(v) < 3:
            raise ValueError('Username must be at least 3 characters')
        return v
    
    @validator('password')
    def validate_password(cls, v):
        if len(v) < 8:
            raise ValueError('Password must be at least 8 characters')
        return v

class UserLogin(BaseModel):
    username: str  # Can be username or email
    password: str

class PasswordResetRequest(BaseModel):
    email: EmailStr

class PasswordReset(BaseModel):
    token: str
    new_password: str

class PasswordResetResponse(BaseModel):
    success: bool
    message: str

class ForgotPasswordRequest(BaseModel):
    email: EmailStr

class UserSettings(BaseModel):
    theme_preference: Optional[str] = None
    notifications_enabled: Optional[bool] = None
    daily_checkins: Optional[bool] = None
    wellness_tips: Optional[bool] = None
    breathing_reminders: Optional[bool] = None
    biometric_lock: Optional[bool] = None

class UserResponse(BaseModel):
    id: int
    user_uuid: str
    username: str
    email: str
    full_name: str
    is_active: bool
    created_at: datetime
    theme_preference: str
    notifications_enabled: bool
    daily_checkins: bool
    wellness_tips: bool
    breathing_reminders: bool
    biometric_lock: bool
    
    class Config:
        from_attributes = True

class Token(BaseModel):
    access_token: str
    token_type: str
    user: UserResponse

# Chat Schemas
class ChatMessageCreate(BaseModel):
    content: str
    
    @validator('content')
    def validate_content(cls, v):
        if not v.strip():
            raise ValueError('Message content cannot be empty')
        if len(v) > 2000:
            raise ValueError('Message content too long')
        return v.strip()

class ChatMessageResponse(BaseModel):
    id: int
    role: str
    content: str
    timestamp: datetime
    metadata: Optional[Dict[str, Any]] = None
    
    class Config:
        from_attributes = True

class ChatSessionResponse(BaseModel):
    id: int
    session_uuid: str
    title: str
    created_at: datetime
    updated_at: datetime
    is_active: bool
    message_count: Optional[int] = None
    
    class Config:
        from_attributes = True

class ChatSessionWithMessages(BaseModel):
    id: int
    session_uuid: str
    title: str
    created_at: datetime
    updated_at: datetime
    is_active: bool
    messages: List[ChatMessageResponse]
    
    class Config:
        from_attributes = True

# Mood Schemas
class EnergyLevel(str, Enum):
    VERY_LOW = "very_low"
    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"
    VERY_HIGH = "very_high"

class MoodEntryCreate(BaseModel):
    mood_score: int
    energy_level: Optional[EnergyLevel] = None
    affecting_factors: Optional[List[str]] = []
    notes: Optional[str] = None
    
    @validator('mood_score')
    def validate_mood_score(cls, v):
        if v < 1 or v > 5:
            raise ValueError('Mood score must be between 1 and 5')
        return v

class MoodEntryResponse(BaseModel):
    id: int
    mood_score: int
    energy_level: Optional[str]
    affecting_factors: Optional[List[str]]
    notes: Optional[str]
    created_at: datetime
    
    class Config:
        from_attributes = True

class MoodAnalytics(BaseModel):
    average_mood: float
    mood_trend: str  # improving, declining, stable
    total_entries: int
    most_common_factors: List[str]
    recent_entries: List[MoodEntryResponse]

# Self-Help Schemas
class BreathingTechnique(str, Enum):
    FOUR_SEVEN_EIGHT = "4-7-8"
    BOX_BREATHING = "box_breathing"
    DEEP_BREATHING = "deep_breathing"

class BreathingSessionCreate(BaseModel):
    technique: BreathingTechnique = BreathingTechnique.FOUR_SEVEN_EIGHT
    duration_minutes: int
    
    @validator('duration_minutes')
    def validate_duration(cls, v):
        if v < 1 or v > 60:
            raise ValueError('Duration must be between 1 and 60 minutes')
        return v

class BreathingSessionResponse(BaseModel):
    id: int
    technique: str
    duration_minutes: int
    completed: bool
    created_at: datetime
    
    class Config:
        from_attributes = True

# Crisis Schemas
class CrisisType(str, Enum):
    CALL = "call"
    TEXT = "text"
    EMERGENCY = "emergency"
    AI_CHAT = "ai_chat"

class CrisisLogCreate(BaseModel):
    crisis_type: CrisisType
    service_used: str

class CrisisLogResponse(BaseModel):
    id: int
    crisis_type: str
    service_used: str
    timestamp: datetime
    resolved: bool
    follow_up_needed: bool
    
    class Config:
        from_attributes = True

# Admin Schemas
class SystemStatsResponse(BaseModel):
    date: datetime
    active_users: int
    total_sessions: int
    crisis_interventions: int
    positive_feedback_rate: float
    average_mood_score: float
    
    class Config:
        from_attributes = True

class DashboardStats(BaseModel):
    current_stats: SystemStatsResponse
    user_growth: List[Dict[str, Any]]
    mood_trends: List[Dict[str, Any]]
    crisis_stats: Dict[str, Any]
    system_health: Dict[str, Any]

# Settings Schemas
class NotificationSettings(BaseModel):
    daily_checkins: bool
    wellness_tips: bool
    breathing_reminders: bool

class PrivacySettings(BaseModel):
    data_sharing: bool
    analytics_tracking: bool
    biometric_lock: bool

class AppSettings(BaseModel):
    theme_preference: str
    notifications: NotificationSettings
    privacy: PrivacySettings

# Response Schemas
class APIResponse(BaseModel):
    success: bool
    message: str
    data: Optional[Any] = None

class ErrorResponse(BaseModel):
    success: bool = False
    message: str
    error_code: Optional[str] = None
    details: Optional[Dict[str, Any]] = None
