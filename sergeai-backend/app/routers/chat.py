from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import desc
from app.database import get_db
from app.models import User, ChatSession, ChatMessage
from app.schemas import (
    ChatMessageCreate, ChatMessageResponse, ChatSessionResponse,
    ChatSessionWithMessages, APIResponse
)
from app.routers.users import get_current_active_user
from datetime import datetime
from typing import List
import openai
import os
from dotenv import load_dotenv

load_dotenv()

router = APIRouter()

# Configure OpenAI (optional - for AI responses)
openai.api_key = os.getenv("OPENAI_API_KEY")

@router.get("/sessions", response_model=List[ChatSessionResponse])
async def get_user_chat_sessions(
    skip: int = 0,
    limit: int = 20,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Get user's chat sessions"""
    sessions = db.query(ChatSession).filter(
        ChatSession.user_id == current_user.id,
        ChatSession.is_active == True
    ).order_by(desc(ChatSession.updated_at)).offset(skip).limit(limit).all()
    
    # Add message count to each session
    session_responses = []
    for session in sessions:
        session_dict = {
            "id": session.id,
            "session_uuid": session.session_uuid,
            "title": session.title,
            "created_at": session.created_at,
            "updated_at": session.updated_at,
            "is_active": session.is_active,
            "message_count": len(session.messages)
        }
        session_responses.append(ChatSessionResponse(**session_dict))
    
    return session_responses

@router.post("/sessions", response_model=ChatSessionResponse, status_code=status.HTTP_201_CREATED)
async def create_chat_session(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Create a new chat session"""
    new_session = ChatSession(
        user_id=current_user.id,
        title="New Chat"
    )
    
    db.add(new_session)
    db.commit()
    db.refresh(new_session)
    
    # Add welcome message from AI
    welcome_message = ChatMessage(
        session_id=new_session.id,
        role="assistant",
        content=f"Hello {current_user.full_name.split()[0]}! I'm your SergeAI assistant. I'm here to support you through any challenges you're facing. How are you feeling today?",
        metadata={"type": "welcome", "automated": True}
    )
    
    db.add(welcome_message)
    db.commit()
    
    return ChatSessionResponse.from_orm(new_session)

@router.get("/sessions/{session_id}", response_model=ChatSessionWithMessages)
async def get_chat_session(
    session_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Get specific chat session with messages"""
    session = db.query(ChatSession).filter(
        ChatSession.id == session_id,
        ChatSession.user_id == current_user.id,
        ChatSession.is_active == True
    ).first()
    
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Chat session not found"
        )
    
    # Get messages ordered by timestamp
    messages = db.query(ChatMessage).filter(
        ChatMessage.session_id == session.id
    ).order_by(ChatMessage.timestamp).all()
    
    return ChatSessionWithMessages(
        id=session.id,
        session_uuid=session.session_uuid,
        title=session.title,
        created_at=session.created_at,
        updated_at=session.updated_at,
        is_active=session.is_active,
        messages=[ChatMessageResponse.from_orm(msg) for msg in messages]
    )

@router.post("/sessions/{session_id}/messages", response_model=ChatMessageResponse, status_code=status.HTTP_201_CREATED)
async def send_message(
    session_id: int,
    message_data: ChatMessageCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Send a message in a chat session and get AI response"""
    # Verify session belongs to user
    session = db.query(ChatSession).filter(
        ChatSession.id == session_id,
        ChatSession.user_id == current_user.id,
        ChatSession.is_active == True
    ).first()
    
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Chat session not found"
        )
    
    try:
        # Add user message
        user_message = ChatMessage(
            session_id=session_id,
            role="user",
            content=message_data.content,
            metadata={"user_id": current_user.id}
        )
        
        db.add(user_message)
        db.commit()
        db.refresh(user_message)
        
        # Generate AI response
        ai_response_content = await generate_ai_response(message_data.content, session_id, db)
        
        # Add AI response
        ai_message = ChatMessage(
            session_id=session_id,
            role="assistant",
            content=ai_response_content,
            metadata={"type": "response", "automated": True}
        )
        
        db.add(ai_message)
        
        # Update session timestamp
        session.updated_at = datetime.utcnow()
        
        # Update session title if it's the first user message
        if session.title == "New Chat":
            session.title = message_data.content[:50] + "..." if len(message_data.content) > 50 else message_data.content
        
        db.commit()
        db.refresh(ai_message)
        
        return ChatMessageResponse.from_orm(ai_message)
        
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to send message: {str(e)}"
        )

@router.delete("/sessions/{session_id}", response_model=APIResponse)
async def delete_chat_session(
    session_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Delete a chat session (soft delete)"""
    session = db.query(ChatSession).filter(
        ChatSession.id == session_id,
        ChatSession.user_id == current_user.id
    ).first()
    
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Chat session not found"
        )
    
    try:
        session.is_active = False
        db.commit()
        
        return APIResponse(
            success=True,
            message="Chat session deleted successfully",
            data={"session_id": session_id}
        )
        
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete session: {str(e)}"
        )

@router.get("/", response_model=APIResponse)
async def get_chat_overview(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Get chat overview and statistics"""
    total_sessions = db.query(ChatSession).filter(
        ChatSession.user_id == current_user.id,
        ChatSession.is_active == True
    ).count()
    
    total_messages = db.query(ChatMessage).join(ChatSession).filter(
        ChatSession.user_id == current_user.id,
        ChatSession.is_active == True,
        ChatMessage.role == "user"
    ).count()
    
    recent_session = db.query(ChatSession).filter(
        ChatSession.user_id == current_user.id,
        ChatSession.is_active == True
    ).order_by(desc(ChatSession.updated_at)).first()
    
    return APIResponse(
        success=True,
        message="Chat overview retrieved successfully",
        data={
            "total_sessions": total_sessions,
            "total_messages": total_messages,
            "recent_session": {
                "id": recent_session.id,
                "title": recent_session.title,
                "updated_at": recent_session.updated_at
            } if recent_session else None
        }
    )

async def generate_ai_response(user_message: str, session_id: int, db: Session) -> str:
    """Generate AI response using OpenAI or fallback to predefined responses"""
    
    # Mental health supportive responses
    supportive_responses = [
        "I understand how you're feeling. Would you like to explore some coping strategies together?",
        "That sounds challenging. Remember that it's okay to feel this way, and you're taking a positive step by reaching out.",
        "I'm here to support you. Would you like to try a quick mindfulness exercise?",
        "Your feelings are valid. Let's work through this together. What would be most helpful right now?",
        "Thank you for sharing that with me. How long have you been experiencing these feelings?",
        "It's completely normal to have these thoughts. Would you like to practice some grounding techniques?",
        "I appreciate you opening up to me. Sometimes talking through our feelings can really help.",
        "You're being very brave by reaching out. Would you like me to suggest some helpful resources?",
        "I hear that you're struggling. Remember that seeking help is a sign of strength, not weakness.",
        "Let's take this one step at a time. What's the most pressing thing on your mind right now?"
    ]
    
    # Crisis-related keywords that need special handling
    crisis_keywords = ['suicide', 'kill myself', 'end it all', 'harm myself', 'die', 'hurt myself']
    anxiety_keywords = ['anxious', 'anxiety', 'panic', 'worried', 'stressed', 'overwhelmed']
    depression_keywords = ['depressed', 'sad', 'hopeless', 'empty', 'worthless', 'lonely']
    
    user_message_lower = user_message.lower()
    
    # Check for crisis situations
    if any(keyword in user_message_lower for keyword in crisis_keywords):
        return ("I'm really concerned about what you're sharing with me. Your life has value and meaning. Please reach out to a crisis helpline immediately - you can call 988 (Suicide & Crisis Lifeline) or text HOME to 741741. You don't have to go through this alone. Would you like me to help you find additional professional support resources?")
    
    # Check for anxiety-related content
    elif any(keyword in user_message_lower for keyword in anxiety_keywords):
        return ("I understand that anxiety can be really overwhelming. Would you like to try a quick breathing exercise together, or would you prefer to talk about what's been making you feel anxious? Remember, these feelings are temporary and manageable.")
    
    # Check for depression-related content
    elif any(keyword in user_message_lower for keyword in depression_keywords):
        return ("I hear that you're going through a difficult time. These feelings of sadness are valid, and I want you to know that you're not alone. Would you like to explore some small steps that might help you feel a bit better today?")
    
    # Try OpenAI API if available
    if openai.api_key:
        try:
            # Get conversation context
            recent_messages = db.query(ChatMessage).filter(
                ChatMessage.session_id == session_id
            ).order_by(desc(ChatMessage.timestamp)).limit(10).all()
            
            # Build context for AI
            context = "You are SergeAI, a compassionate mental health support assistant. Always prioritize user safety and well-being. If someone expresses suicidal thoughts or crisis, direct them to professional help immediately.\n\nConversation history:\n"
            
            for msg in reversed(recent_messages):
                context += f"{msg.role}: {msg.content}\n"
            
            context += f"user: {user_message}\nassistant:"
            
            response = openai.ChatCompletion.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "You are SergeAI, a supportive mental health assistant. Be empathetic, helpful, and always prioritize user safety. Keep responses conversational and supportive."},
                    {"role": "user", "content": user_message}
                ],
                max_tokens=200,
                temperature=0.7
            )
            
            return response.choices[0].message.content.strip()
            
        except Exception as e:
            print(f"OpenAI API error: {e}")
            # Fall back to predefined responses
    
    # Fallback to predefined responses
    import random
    return random.choice(supportive_responses)