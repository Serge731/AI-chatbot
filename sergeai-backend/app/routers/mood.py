from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import desc, func, and_
from app.database import get_db
from app.models import User, MoodEntry
from app.schemas import (
    MoodEntryCreate, MoodEntryResponse, MoodAnalytics, APIResponse
)
from app.routers.users import get_current_active_user
from datetime import datetime, timedelta
from typing import List, Optional
import statistics

router = APIRouter()

@router.post("/entries", response_model=MoodEntryResponse, status_code=status.HTTP_201_CREATED)
async def create_mood_entry(
    mood_data: MoodEntryCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Create a new mood entry"""
    try:
        # Check if user already has a mood entry today
        today = datetime.now().date()
        existing_entry = db.query(MoodEntry).filter(
            MoodEntry.user_id == current_user.id,
            func.date(MoodEntry.created_at) == today
        ).first()
        
        if existing_entry:
            # Update existing entry instead of creating new one
            existing_entry.mood_score = mood_data.mood_score
            existing_entry.energy_level = mood_data.energy_level.value if mood_data.energy_level else None
            existing_entry.affecting_factors = mood_data.affecting_factors
            existing_entry.notes = mood_data.notes
            existing_entry.created_at = datetime.utcnow()  # Update timestamp
            
            db.commit()
            db.refresh(existing_entry)
            
            return MoodEntryResponse.from_orm(existing_entry)
        
        # Create new mood entry
        new_entry = MoodEntry(
            user_id=current_user.id,
            mood_score=mood_data.mood_score,
            energy_level=mood_data.energy_level.value if mood_data.energy_level else None,
            affecting_factors=mood_data.affecting_factors,
            notes=mood_data.notes
        )
        
        db.add(new_entry)
        db.commit()
        db.refresh(new_entry)
        
        return MoodEntryResponse.from_orm(new_entry)
        
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create mood entry: {str(e)}"
        )

@router.get("/entries", response_model=List[MoodEntryResponse])
async def get_mood_entries(
    skip: int = 0,
    limit: int = 30,
    days: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Get user's mood entries with optional date filtering"""
    query = db.query(MoodEntry).filter(MoodEntry.user_id == current_user.id)
    
    # Filter by date range if specified
    if days:
        start_date = datetime.now() - timedelta(days=days)
        query = query.filter(MoodEntry.created_at >= start_date)
    
    entries = query.order_by(desc(MoodEntry.created_at)).offset(skip).limit(limit).all()
    return [MoodEntryResponse.from_orm(entry) for entry in entries]

@router.get("/entries/{entry_id}", response_model=MoodEntryResponse)
async def get_mood_entry(
    entry_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Get specific mood entry"""
    entry = db.query(MoodEntry).filter(
        MoodEntry.id == entry_id,
        MoodEntry.user_id == current_user.id
    ).first()
    
    if not entry:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Mood entry not found"
        )
    
    return MoodEntryResponse.from_orm(entry)

@router.put("/entries/{entry_id}", response_model=MoodEntryResponse)
async def update_mood_entry(
    entry_id: int,
    mood_data: MoodEntryCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Update existing mood entry"""
    entry = db.query(MoodEntry).filter(
        MoodEntry.id == entry_id,
        MoodEntry.user_id == current_user.id
    ).first()
    
    if not entry:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Mood entry not found"
        )
    
    try:
        entry.mood_score = mood_data.mood_score
        entry.energy_level = mood_data.energy_level.value if mood_data.energy_level else None
        entry.affecting_factors = mood_data.affecting_factors
        entry.notes = mood_data.notes
        
        db.commit()
        db.refresh(entry)
        
        return MoodEntryResponse.from_orm(entry)
        
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update mood entry: {str(e)}"
        )

@router.delete("/entries/{entry_id}", response_model=APIResponse)
async def delete_mood_entry(
    entry_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Delete mood entry"""
    entry = db.query(MoodEntry).filter(
        MoodEntry.id == entry_id,
        MoodEntry.user_id == current_user.id
    ).first()
    
    if not entry:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Mood entry not found"
        )
    
    try:
        db.delete(entry)
        db.commit()
        
        return APIResponse(
            success=True,
            message="Mood entry deleted successfully",
            data={"entry_id": entry_id}
        )
        
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete mood entry: {str(e)}"
        )

@router.get("/analytics", response_model=MoodAnalytics)
async def get_mood_analytics(
    days: int = 30,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Get mood analytics and insights"""
    try:
        # Get mood entries for the specified period
        start_date = datetime.now() - timedelta(days=days)
        entries = db.query(MoodEntry).filter(
            MoodEntry.user_id == current_user.id,
            MoodEntry.created_at >= start_date
        ).order_by(desc(MoodEntry.created_at)).all()
        
        if not entries:
            return MoodAnalytics(
                average_mood=0.0,
                mood_trend="no_data",
                total_entries=0,
                most_common_factors=[],
                recent_entries=[]
            )
        
        # Calculate average mood
        mood_scores = [entry.mood_score for entry in entries]
        average_mood = statistics.mean(mood_scores)
        
        # Calculate mood trend
        recent_entries = entries[:7]  # Last 7 entries
        older_entries = entries[7:14] if len(entries) > 7 else []
        
        mood_trend = "stable"
        if recent_entries and older_entries:
            recent_avg = statistics.mean([e.mood_score for e in recent_entries])
            older_avg = statistics.mean([e.mood_score for e in older_entries])
            
            if recent_avg > older_avg + 0.5:
                mood_trend = "improving"
            elif recent_avg < older_avg - 0.5:
                mood_trend = "declining"
        
        # Get most common affecting factors
        all_factors = []
        for entry in entries:
            if entry.affecting_factors:
                all_factors.extend(entry.affecting_factors)
        
        factor_counts = {}
        for factor in all_factors:
            factor_counts[factor] = factor_counts.get(factor, 0) + 1
        
        most_common_factors = sorted(
            factor_counts.items(), 
            key=lambda x: x[1], 
            reverse=True
        )[:5]
        most_common_factors = [factor[0] for factor in most_common_factors]
        
        # Get recent entries for display
        recent_entries_response = [
            MoodEntryResponse.from_orm(entry) for entry in entries[:10]
        ]
        
        return MoodAnalytics(
            average_mood=round(average_mood, 2),
            mood_trend=mood_trend,
            total_entries=len(entries),
            most_common_factors=most_common_factors,
            recent_entries=recent_entries_response
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get mood analytics: {str(e)}"
        )

@router.get("/today", response_model=Optional[MoodEntryResponse])
async def get_today_mood(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Get today's mood entry if it exists"""
    today = datetime.now().date()
    entry = db.query(MoodEntry).filter(
        MoodEntry.user_id == current_user.id,
        func.date(MoodEntry.created_at) == today
    ).first()
    
    if entry:
        return MoodEntryResponse.from_orm(entry)
    return None

@router.get("/streak", response_model=APIResponse)
async def get_mood_streak(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Get user's mood logging streak"""
    try:
        # Get all mood entries ordered by date
        entries = db.query(MoodEntry).filter(
            MoodEntry.user_id == current_user.id
        ).order_by(desc(MoodEntry.created_at)).all()
        
        if not entries:
            return APIResponse(
                success=True,
                message="No mood entries found",
                data={"current_streak": 0, "longest_streak": 0}
            )
        
        # Calculate current streak
        current_streak = 0
        today = datetime.now().date()
        check_date = today
        
        for entry in entries:
            entry_date = entry.created_at.date()
            if entry_date == check_date:
                current_streak += 1
                check_date = check_date - timedelta(days=1)
            else:
                break
        
        # Calculate longest streak (simplified version)
        longest_streak = current_streak  # In a real implementation, you'd want to calculate this properly
        
        return APIResponse(
            success=True,
            message="Mood streak calculated successfully",
            data={
                "current_streak": current_streak,
                "longest_streak": longest_streak,
                "total_entries": len(entries)
            }
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to calculate mood streak: {str(e)}"
        )

@router.get("/", response_model=APIResponse)
async def get_mood_overview(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Get mood tracking overview"""
    try:
        # Get today's mood
        today = datetime.now().date()
        today_mood = db.query(MoodEntry).filter(
            MoodEntry.user_id == current_user.id,
            func.date(MoodEntry.created_at) == today
        ).first()
        
        # Get total entries
        total_entries = db.query(MoodEntry).filter(
            MoodEntry.user_id == current_user.id
        ).count()
        
        # Get average mood for last 7 days
        week_ago = datetime.now() - timedelta(days=7)
        recent_entries = db.query(MoodEntry).filter(
            MoodEntry.user_id == current_user.id,
            MoodEntry.created_at >= week_ago
        ).all()
        
        average_mood = 0.0
        if recent_entries:
            average_mood = statistics.mean([entry.mood_score for entry in recent_entries])
        
        return APIResponse(
            success=True,
            message="Mood overview retrieved successfully",
            data={
                "today_logged": today_mood is not None,
                "today_mood": today_mood.mood_score if today_mood else None,
                "total_entries": total_entries,
                "weekly_average": round(average_mood, 2),
                "entries_this_week": len(recent_entries)
            }
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get mood overview: {str(e)}"
        )