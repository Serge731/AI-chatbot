from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import func, desc, and_
from app.database import get_db
from app.models import User, ChatSession, ChatMessage, MoodEntry, CrisisLog, BreathingSession, SystemStats
from app.schemas import DashboardStats, SystemStatsResponse, APIResponse
from app.routers.users import get_current_active_user
from datetime import datetime, timedelta
from typing import List, Dict, Any
import statistics

router = APIRouter()

# Simple admin check - in production, you'd want proper role-based access control
async def check_admin_access(current_user: User = Depends(get_current_active_user)):
    """Check if user has admin access (demo implementation)"""
    # In production, you'd check user roles/permissions
    # For demo, we'll allow any authenticated user to access admin features
    return current_user

@router.get("/dashboard", response_model=DashboardStats)
async def get_admin_dashboard(
    db: Session = Depends(get_db),
    admin_user: User = Depends(check_admin_access)
):
    """Get comprehensive admin dashboard statistics"""
    try:
        # Get current stats
        today = datetime.now().date()
        
        # Active users (users who logged in within last 30 days)
        thirty_days_ago = datetime.now() - timedelta(days=30)
        active_users = db.query(User).filter(
            User.is_active == True,
            User.updated_at >= thirty_days_ago
        ).count()
        
        # Total sessions today
        total_sessions_today = db.query(ChatSession).filter(
            func.date(ChatSession.created_at) == today
        ).count()
        
        # Crisis interventions today
        crisis_interventions_today = db.query(CrisisLog).filter(
            func.date(CrisisLog.timestamp) == today
        ).count()
        
        # Calculate positive feedback rate (mock calculation)
        total_sessions = db.query(ChatSession).count()
        positive_feedback_rate = 0.89  # Mock value - in real app, calculate from feedback data
        
        # Average mood score (last 7 days)
        week_ago = datetime.now() - timedelta(days=7)
        recent_moods = db.query(MoodEntry).filter(
            MoodEntry.created_at >= week_ago
        ).all()
        
        average_mood_score = 0.0
        if recent_moods:
            average_mood_score = statistics.mean([entry.mood_score for entry in recent_moods])
        
        current_stats = SystemStatsResponse(
            date=datetime.now(),
            active_users=active_users,
            total_sessions=total_sessions_today,
            crisis_interventions=crisis_interventions_today,
            positive_feedback_rate=positive_feedback_rate,
            average_mood_score=round(average_mood_score, 2)
        )
        
        # User growth data (last 30 days)
        user_growth = []
        for i in range(30):
            date = datetime.now() - timedelta(days=i)
            daily_users = db.query(User).filter(
                func.date(User.created_at) == date.date()
            ).count()
            
            user_growth.append({
                "date": date.date().isoformat(),
                "new_users": daily_users,
                "day_name": date.strftime("%a")
            })
        
        user_growth.reverse()  # Show oldest to newest
        
        # Mood trends (last 14 days)
        mood_trends = []
        for i in range(14):
            date = datetime.now() - timedelta(days=i)
            daily_moods = db.query(MoodEntry).filter(
                func.date(MoodEntry.created_at) == date.date()
            ).all()
            
            avg_mood = 0
            if daily_moods:
                avg_mood = statistics.mean([entry.mood_score for entry in daily_moods])
            
            mood_trends.append({
                "date": date.date().isoformat(),
                "average_mood": round(avg_mood, 2),
                "entry_count": len(daily_moods),
                "day_name": date.strftime("%a")
            })
        
        mood_trends.reverse()
        
        # Crisis statistics
        total_crisis_logs = db.query(CrisisLog).count()
        resolved_crisis = db.query(CrisisLog).filter(CrisisLog.resolved == True).count()
        
        crisis_stats = {
            "total_interventions": total_crisis_logs,
            "resolved_count": resolved_crisis,
            "resolution_rate": round((resolved_crisis / total_crisis_logs * 100), 1) if total_crisis_logs > 0 else 0,
            "needs_follow_up": db.query(CrisisLog).filter(CrisisLog.follow_up_needed == True).count()
        }
        
        # System health
        total_users = db.query(User).count()
        active_user_percentage = round((active_users / total_users * 100), 1) if total_users > 0 else 0
        
        system_health = {
            "total_users": total_users,
            "active_user_percentage": active_user_percentage,
            "database_status": "healthy",
            "uptime": "99.9%",  # Mock value
            "response_time": "245ms"  # Mock value
        }
        
        return DashboardStats(
            current_stats=current_stats,
            user_growth=user_growth,
            mood_trends=mood_trends,
            crisis_stats=crisis_stats,
            system_health=system_health
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get dashboard stats: {str(e)}"
        )

@router.get("/users", response_model=APIResponse)
async def get_admin_user_overview(
    page: int = 1,
    per_page: int = 20,
    db: Session = Depends(get_db),
    admin_user: User = Depends(check_admin_access)
):
    """Get user overview for admin"""
    try:
        skip = (page - 1) * per_page
        users = db.query(User).order_by(desc(User.created_at)).offset(skip).limit(per_page).all()
        total_users = db.query(User).count()
        
        user_data = []
        for user in users:
            # Get user stats
            mood_entries = db.query(MoodEntry).filter(MoodEntry.user_id == user.id).count()
            chat_sessions = db.query(ChatSession).filter(ChatSession.user_id == user.id).count()
            
            user_data.append({
                "id": user.id,
                "username": user.username,
                "email": user.email,
                "full_name": user.full_name,
                "is_active": user.is_active,
                "created_at": user.created_at.isoformat(),
                "mood_entries": mood_entries,
                "chat_sessions": chat_sessions,
                "last_activity": user.updated_at.isoformat()
            })
        
        return APIResponse(
            success=True,
            message="User overview retrieved successfully",
            data={
                "users": user_data,
                "pagination": {
                    "page": page,
                    "per_page": per_page,
                    "total": total_users,
                    "pages": (total_users + per_page - 1) // per_page
                }
            }
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get user overview: {str(e)}"
        )

@router.get("/crisis-logs", response_model=APIResponse)
async def get_crisis_logs(
    page: int = 1,
    per_page: int = 50,
    unresolved_only: bool = False,
    db: Session = Depends(get_db),
    admin_user: User = Depends(check_admin_access)
):
    """Get crisis intervention logs"""
    try:
        skip = (page - 1) * per_page
        query = db.query(CrisisLog)
        
        if unresolved_only:
            query = query.filter(CrisisLog.resolved == False)
        
        logs = query.order_by(desc(CrisisLog.timestamp)).offset(skip).limit(per_page).all()
        total_logs = query.count()
        
        log_data = []
        for log in logs:
            # Get user info if available
            user_info = None
            if log.user_id:
                user = db.query(User).filter(User.id == log.user_id).first()
                if user:
                    user_info = {
                        "username": user.username,
                        "email": user.email
                    }
            
            log_data.append({
                "id": log.id,
                "crisis_type": log.crisis_type,
                "service_used": log.service_used,
                "timestamp": log.timestamp.isoformat(),
                "resolved": log.resolved,
                "follow_up_needed": log.follow_up_needed,
                "user_info": user_info
            })
        
        return APIResponse(
            success=True,
            message="Crisis logs retrieved successfully",
            data={
                "logs": log_data,
                "pagination": {
                    "page": page,
                    "per_page": per_page,
                    "total": total_logs,
                    "pages": (total_logs + per_page - 1) // per_page
                }
            }
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get crisis logs: {str(e)}"
        )

@router.put("/crisis-logs/{log_id}/resolve", response_model=APIResponse)
async def resolve_crisis_log(
    log_id: int,
    db: Session = Depends(get_db),
    admin_user: User = Depends(check_admin_access)
):
    """Mark a crisis log as resolved"""
    log = db.query(CrisisLog).filter(CrisisLog.id == log_id).first()
    
    if not log:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Crisis log not found"
        )
    
    try:
        log.resolved = True
        log.follow_up_needed = False
        db.commit()
        
        return APIResponse(
            success=True,
            message="Crisis log marked as resolved",
            data={"log_id": log_id}
        )
        
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to resolve crisis log: {str(e)}"
        )

@router.get("/analytics", response_model=APIResponse)
async def get_analytics(
    days: int = 30,
    db: Session = Depends(get_db),
    admin_user: User = Depends(check_admin_access)
):
    """Get detailed analytics"""
    try:
        start_date = datetime.now() - timedelta(days=days)
        
        # User engagement
        total_users = db.query(User).count()
        active_users = db.query(User).filter(
            User.is_active == True,
            User.updated_at >= start_date
        ).count()
        
        # Chat analytics
        total_sessions = db.query(ChatSession).filter(
            ChatSession.created_at >= start_date
        ).count()
        
        total_messages = db.query(ChatMessage).join(ChatSession).filter(
            ChatSession.created_at >= start_date,
            ChatMessage.role == "user"
        ).count()
        
        # Mood analytics
        mood_entries = db.query(MoodEntry).filter(
            MoodEntry.created_at >= start_date
        ).all()
        
        mood_distribution = {i: 0 for i in range(1, 6)}
        for entry in mood_entries:
            mood_distribution[entry.mood_score] += 1
        
        # Breathing sessions
        breathing_sessions = db.query(BreathingSession).filter(
            BreathingSession.created_at >= start_date
        ).count()
        
        completed_breathing = db.query(BreathingSession).filter(
            BreathingSession.created_at >= start_date,
            BreathingSession.completed == True
        ).count()
        
        return APIResponse(
            success=True,
            message="Analytics retrieved successfully",
            data={
                "period_days": days,
                "user_engagement": {
                    "total_users": total_users,
                    "active_users": active_users,
                    "engagement_rate": round((active_users / total_users * 100), 1) if total_users > 0 else 0
                },
                "chat_analytics": {
                    "total_sessions": total_sessions,
                    "total_messages": total_messages,
                    "avg_messages_per_session": round(total_messages / total_sessions, 1) if total_sessions > 0 else 0
                },
                "mood_analytics": {
                    "total_entries": len(mood_entries),
                    "distribution": mood_distribution,
                    "average_mood": round(statistics.mean([e.mood_score for e in mood_entries]), 2) if mood_entries else 0
                },
                "wellness_tools": {
                    "breathing_sessions": breathing_sessions,
                    "completed_sessions": completed_breathing,
                    "completion_rate": round((completed_breathing / breathing_sessions * 100), 1) if breathing_sessions > 0 else 0
                }
            }
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get analytics: {str(e)}"
        )

@router.get("/", response_model=APIResponse)
async def admin_overview(
    db: Session = Depends(get_db),
    admin_user: User = Depends(check_admin_access)
):
    """Get admin panel overview"""
    try:
        # Quick stats
        total_users = db.query(User).count()
        active_users = db.query(User).filter(User.is_active == True).count()
        total_crisis_logs = db.query(CrisisLog).count()
        unresolved_crisis = db.query(CrisisLog).filter(CrisisLog.resolved == False).count()
        
        # Recent activity
        recent_users = db.query(User).order_by(desc(User.created_at)).limit(5).all()
        recent_crisis = db.query(CrisisLog).order_by(desc(CrisisLog.timestamp)).limit(5).all()
        
        return APIResponse(
            success=True,
            message="Admin overview retrieved successfully",
            data={
                "quick_stats": {
                    "total_users": total_users,
                    "active_users": active_users,
                    "total_crisis_interventions": total_crisis_logs,
                    "unresolved_crisis": unresolved_crisis
                },
                "recent_activity": {
                    "new_users": [
                        {
                            "username": user.username,
                            "created_at": user.created_at.isoformat()
                        } for user in recent_users
                    ],
                    "recent_crisis": [
                        {
                            "crisis_type": log.crisis_type,
                            "service_used": log.service_used,
                            "timestamp": log.timestamp.isoformat(),
                            "resolved": log.resolved
                        } for log in recent_crisis
                    ]
                },
                "admin_user": admin_user.username
            }
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get admin overview: {str(e)}"
        )