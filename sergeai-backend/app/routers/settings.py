from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import User, BreathingSession
from app.schemas import (
    UserSettings, APIResponse, BreathingSessionCreate, BreathingSessionResponse,
    NotificationSettings, PrivacySettings, AppSettings
)
from app.routers.users import get_current_active_user, update_user_settings
from datetime import datetime, timedelta
from typing import List, Dict, Any

router = APIRouter()

@router.get("/", response_model=AppSettings)
async def get_user_settings(
    current_user: User = Depends(get_current_active_user)
):
    """Get current user's settings"""
    try:
        notifications = NotificationSettings(
            daily_checkins=current_user.daily_checkins,
            wellness_tips=current_user.wellness_tips,
            breathing_reminders=current_user.breathing_reminders
        )
        
        privacy = PrivacySettings(
            data_sharing=False,  # Default values for privacy settings
            analytics_tracking=True,
            biometric_lock=current_user.biometric_lock
        )
        
        settings = AppSettings(
            theme_preference=current_user.theme_preference,
            notifications=notifications,
            privacy=privacy
        )
        
        return settings
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get user settings: {str(e)}"
        )

@router.put("/", response_model=APIResponse)
async def update_settings(
    settings_data: UserSettings,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Update user settings"""
    try:
        # Convert Pydantic model to dict, excluding None values
        settings_dict = settings_data.dict(exclude_unset=True, exclude_none=True)
        
        if not settings_dict:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No valid settings provided"
            )
        
        # Update user settings
        updated_user = update_user_settings(db, current_user, settings_dict)
        
        return APIResponse(
            success=True,
            message="Settings updated successfully",
            data={
                "updated_fields": list(settings_dict.keys()),
                "user_id": updated_user.id
            }
        )
        
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update settings: {str(e)}"
        )

@router.put("/theme", response_model=APIResponse)
async def update_theme(
    theme: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Update user's theme preference"""
    if theme not in ["light", "dark"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Theme must be 'light' or 'dark'"
        )
    
    try:
        current_user.theme_preference = theme
        current_user.updated_at = datetime.utcnow()
        db.commit()
        
        return APIResponse(
            success=True,
            message=f"Theme updated to {theme}",
            data={"theme": theme}
        )
        
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update theme: {str(e)}"
        )

@router.put("/notifications", response_model=APIResponse)
async def update_notification_settings(
    notifications: NotificationSettings,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Update notification preferences"""
    try:
        current_user.daily_checkins = notifications.daily_checkins
        current_user.wellness_tips = notifications.wellness_tips
        current_user.breathing_reminders = notifications.breathing_reminders
        current_user.updated_at = datetime.utcnow()
        
        db.commit()
        
        return APIResponse(
            success=True,
            message="Notification settings updated successfully",
            data={
                "daily_checkins": notifications.daily_checkins,
                "wellness_tips": notifications.wellness_tips,
                "breathing_reminders": notifications.breathing_reminders
            }
        )
        
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update notification settings: {str(e)}"
        )

@router.put("/privacy", response_model=APIResponse)
async def update_privacy_settings(
    privacy: PrivacySettings,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Update privacy preferences"""
    try:
        current_user.biometric_lock = privacy.biometric_lock
        current_user.updated_at = datetime.utcnow()
        
        # In a real app, you'd store additional privacy settings in a separate table
        # or add more columns to the user table
        
        db.commit()
        
        return APIResponse(
            success=True,
            message="Privacy settings updated successfully",
            data={
                "biometric_lock": privacy.biometric_lock,
                "data_sharing": privacy.data_sharing,
                "analytics_tracking": privacy.analytics_tracking
            }
        )
        
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update privacy settings: {str(e)}"
        )

# Breathing exercise endpoints
@router.post("/breathing-sessions", response_model=BreathingSessionResponse, status_code=status.HTTP_201_CREATED)
async def start_breathing_session(
    session_data: BreathingSessionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Start a new breathing exercise session"""
    try:
        new_session = BreathingSession(
            user_id=current_user.id,
            technique=session_data.technique.value,
            duration_minutes=session_data.duration_minutes,
            completed=False
        )
        
        db.add(new_session)
        db.commit()
        db.refresh(new_session)
        
        return BreathingSessionResponse.from_orm(new_session)
        
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to start breathing session: {str(e)}"
        )

@router.put("/breathing-sessions/{session_id}/complete", response_model=APIResponse)
async def complete_breathing_session(
    session_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Mark a breathing session as completed"""
    session = db.query(BreathingSession).filter(
        BreathingSession.id == session_id,
        BreathingSession.user_id == current_user.id
    ).first()
    
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Breathing session not found"
        )
    
    try:
        session.completed = True
        db.commit()
        
        return APIResponse(
            success=True,
            message="Breathing session completed successfully",
            data={
                "session_id": session_id,
                "technique": session.technique,
                "duration_minutes": session.duration_minutes
            }
        )
        
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to complete breathing session: {str(e)}"
        )

@router.get("/breathing-sessions", response_model=List[BreathingSessionResponse])
async def get_breathing_sessions(
    skip: int = 0,
    limit: int = 20,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Get user's breathing exercise history"""
    sessions = db.query(BreathingSession).filter(
        BreathingSession.user_id == current_user.id
    ).order_by(BreathingSession.created_at.desc()).offset(skip).limit(limit).all()
    
    return [BreathingSessionResponse.from_orm(session) for session in sessions]

@router.get("/breathing-stats", response_model=APIResponse)
async def get_breathing_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Get breathing exercise statistics"""
    try:
        # Get all breathing sessions
        sessions = db.query(BreathingSession).filter(
            BreathingSession.user_id == current_user.id
        ).all()
        
        completed_sessions = [s for s in sessions if s.completed]
        total_minutes = sum(s.duration_minutes for s in completed_sessions)
        
        # Get this week's stats
        week_ago = datetime.now() - timedelta(days=7)
        this_week_sessions = [
            s for s in completed_sessions 
            if s.created_at >= week_ago
        ]
        
        return APIResponse(
            success=True,
            message="Breathing statistics retrieved successfully",
            data={
                "total_sessions": len(sessions),
                "completed_sessions": len(completed_sessions),
                "total_minutes": total_minutes,
                "sessions_this_week": len(this_week_sessions),
                "average_session_length": round(total_minutes / len(completed_sessions), 1) if completed_sessions else 0
            }
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get breathing stats: {str(e)}"
        )

@router.post("/export-data", response_model=APIResponse)
async def export_user_data(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Export user's data (GDPR compliance)"""
    try:
        # In a real implementation, this would generate a comprehensive data export
        # including all user data, mood entries, chat history, etc.
        
        from app.models import MoodEntry, ChatSession, ChatMessage
        
        # Get basic stats for the export
        mood_entries_count = db.query(MoodEntry).filter(
            MoodEntry.user_id == current_user.id
        ).count()
        
        chat_sessions_count = db.query(ChatSession).filter(
            ChatSession.user_id == current_user.id
        ).count()
        
        breathing_sessions_count = db.query(BreathingSession).filter(
            BreathingSession.user_id == current_user.id
        ).count()
        
        return APIResponse(
            success=True,
            message="Data export initiated (demo)",
            data={
                "user_id": current_user.user_uuid,
                "export_timestamp": datetime.utcnow().isoformat(),
                "data_summary": {
                    "mood_entries": mood_entries_count,
                    "chat_sessions": chat_sessions_count,
                    "breathing_sessions": breathing_sessions_count
                },
                "note": "In production, this would generate and email a complete data export"
            }
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to export data: {str(e)}"
        )

@router.delete("/delete-account", response_model=APIResponse)
async def delete_account_request(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Request account deletion (soft delete)"""
    try:
        # In a real implementation, you might:
        # 1. Send a confirmation email
        # 2. Set a deletion date in the future
        # 3. Allow user to cancel the deletion
        
        current_user.is_active = False
        current_user.updated_at = datetime.utcnow()
        db.commit()
        
        return APIResponse(
            success=True,
            message="Account deletion requested. Your account has been deactivated.",
            data={
                "user_id": current_user.user_uuid,
                "deletion_requested_at": datetime.utcnow().isoformat()
            }
        )
        
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process account deletion: {str(e)}"
        )

@router.get("/help", response_model=APIResponse)
async def get_help_resources():
    """Get help and support resources"""
    help_resources = {
        "faq": [
            {
                "question": "How do I track my mood?",
                "answer": "Use the Mood tab to log your daily mood on a scale of 1-5, along with factors affecting your mood."
            },
            {
                "question": "Is my data secure?",
                "answer": "Yes, all your data is encrypted and stored securely. We never share your personal information."
            },
            {
                "question": "How do I contact support?",
                "answer": "You can reach our support team through the app settings or email support@sergeai.com"
            }
        ],
        "contact": {
            "support_email": "support@sergeai.com",
            "crisis_hotline": "988",
            "text_crisis": "741741"
        },
        "resources": [
            {
                "title": "National Suicide Prevention Lifeline",
                "number": "988",
                "description": "24/7 crisis support"
            },
            {
                "title": "Crisis Text Line",
                "number": "741741",
                "description": "Text HOME for crisis support"
            },
            {
                "title": "NAMI Support",
                "url": "https://nami.org",
                "description": "Mental health education and support"
            }
        ]
    }
    
    return APIResponse(
        success=True,
        message="Help resources retrieved successfully",
        data=help_resources
    )