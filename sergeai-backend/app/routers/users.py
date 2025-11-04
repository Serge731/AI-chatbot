import secrets
import string
from typing import Optional
import uuid
import bcrypt
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from app.database import get_db
from app.models import User
from app.schemas import ForgotPasswordRequest
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from app.core.config import SECRET_KEY, ALGORITHM
from app.utils import create_access_token
from app.utils import hash_password, verify_password, create_access_token
from app.schemas import (
    UserCreate, UserLogin, UserResponse, Token, UserSettings, APIResponse
)
from datetime import datetime, timedelta

# Add OAuth2 scheme
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/v1/login")

# Add the missing authentication functions
class AuthService:
    @staticmethod
    def get_current_user(
        token: str = Depends(oauth2_scheme), 
        db: Session = Depends(get_db)
    ):
        print(f"🔐 Validating token: {token}")
        
        credentials_exception = HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
        
        try:
            payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
            print(f"✅ Token decoded successfully: {payload}")
            
            user_id: str = payload.get("sub")
            if user_id is None:
                print("❌ No user_id in token payload")
                raise credentials_exception

            # 🔑 Cast sub → int safely
            try:
                user_id = int(user_id)
            except ValueError:
                print(f"❌ Invalid user_id format in token: {user_id}")
                raise credentials_exception

            print(f"✅ User ID from token (int): {user_id}")
            
        except JWTError as e:
            print(f"❌ JWT Error: {e}")
            raise credentials_exception
        
        user = db.query(User).filter(User.id == user_id).first()
        if user is None:
            print(f"❌ User not found for ID: {user_id}")
            raise credentials_exception
            
        print(f"✅ User found: {user.username}")
        return user

    @staticmethod
    def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
        return create_access_token(data, expires_delta)


def get_current_active_user(current_user: User = Depends(AuthService.get_current_user)):
    """Get current active user"""
    print(f"🔐 Checking active user: {current_user.username}")
    
    if not current_user.is_active:
        print("❌ User is not active")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Inactive user account"
        )
    
    print("✅ User is active")
    return current_user

def authenticate_user(db: Session, username: str, password: str):
    """Authenticate a user with username/email and password"""
    user = (
        db.query(User)
        .filter((User.username == username) | (User.email == username))
        .first()
    )
    if not user or not verify_password(password, user.hashed_password):
        return False
    return user

def create_user(db: Session, user_data: dict):
    """Create a new user"""
    new_user = User(
        username=user_data["username"],
        email=user_data["email"],
        full_name=user_data.get("full_name", ""),
        hashed_password=hash_password(user_data["password"])
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return new_user

def update_user_settings(db: Session, user: User, settings_data: dict):
    """Update user settings"""
    for key, value in settings_data.items():
        if hasattr(user, key):
            setattr(user, key, value)
    db.commit()
    db.refresh(user)
    return user

router = APIRouter()

@router.post("/register", response_model=Token, status_code=status.HTTP_201_CREATED)
async def register_user(user_data: UserCreate, db: Session = Depends(get_db)):
    """Register a new user account"""
    try:
        # Check if user already exists
        existing_user = db.query(User).filter(
            (User.email == user_data.email) | (User.username == user_data.username)
        ).first()
        
        if existing_user:
            if existing_user.email == user_data.email:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Email already registered"
                )
            else:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Username already taken"
                )
        
        # Create new user
        new_user = create_user(db, {
            "username": user_data.username,
            "email": user_data.email,
            "full_name": user_data.full_name,
            "password": user_data.password
        })
        
        # Create access token
        access_token_expires = timedelta(minutes=30)
        access_token = AuthService.create_access_token(
            data={"sub": str(new_user.id)}, expires_delta=access_token_expires
        )
        
        return {
            "access_token": access_token,
            "token_type": "bearer",
            "user": UserResponse.from_orm(new_user)
        }
        
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User registration failed due to data constraints"
        )

@router.post("/login", response_model=Token)
async def login_user(user_credentials: UserLogin, db: Session = Depends(get_db)):
    """Authenticate user and return access token"""
    user = authenticate_user(db, user_credentials.username, user_credentials.password)
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Inactive user account"
        )
    
    access_token_expires = timedelta(minutes=30)
    access_token = AuthService.create_access_token(
        data={"sub": str(user.id)}, expires_delta=access_token_expires
    )
    
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": UserResponse.from_orm(user)
    }

@router.post("/auth/forgot-password")
def forgot_password(payload: ForgotPasswordRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == payload.email).first()
    if not user:
        # Security best practice: don’t reveal if user exists
        return {"message": "If an account with that email exists, we’ve sent a reset link."}

    reset_token = str(uuid.uuid4())
    user.reset_token = reset_token
    user.reset_token_expires = datetime.utcnow() + timedelta(hours=1)
    db.commit()

    # TODO: send email with reset link
    # Example: send_password_reset_email(user.email, reset_token)

    return {"message": "If an account with that email exists, we’ve sent a reset link."}


@router.post("/auth/verify-reset-token")
def verify_reset_token(payload: dict, db: Session = Depends(get_db)):
    token = payload.get("token")
    email = payload.get("email")

    user = db.query(User).filter(User.email == email, User.reset_token == token).first()
    if not user or not user.reset_token_expires or user.reset_token_expires < datetime.utcnow():
        raise HTTPException(status_code=400, detail="Invalid or expired token")

    return {"message": "Token is valid"}


@router.post("/auth/reset-password")
def reset_password(payload: dict, db: Session = Depends(get_db)):
    token = payload.get("token")
    email = payload.get("email")
    new_password = payload.get("password")

    user = db.query(User).filter(User.email == email, User.reset_token == token).first()
    if not user or not user.reset_token_expires or user.reset_token_expires < datetime.utcnow():
        raise HTTPException(status_code=400, detail="Invalid or expired token")

    # Hash the new password
    user.hashed_password = bcrypt.hash(new_password)
    user.reset_token = None
    user.reset_token_expires = None
    db.commit()

    return {"message": "Password reset successfully"}

@router.get("/me", response_model=UserResponse)
async def get_current_user_profile(current_user: User = Depends(get_current_active_user)):
    """Get current user's profile information"""
    print(f"✅ /api/v1/users/me called successfully")
    print(f"✅ User: {current_user.username} ({current_user.email})")
    return UserResponse.from_orm(current_user)

@router.put("/me", response_model=UserResponse)
async def update_user_profile(
    user_data: UserSettings,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Update current user's profile settings"""
    try:
        # Convert Pydantic model to dict, excluding None values
        settings_data = user_data.dict(exclude_unset=True, exclude_none=True)
        
        if not settings_data:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No valid settings provided"
            )
        
        updated_user = update_user_settings(db, current_user, settings_data)
        return UserResponse.from_orm(updated_user)
        
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to update user settings: {str(e)}"
        )

@router.delete("/me", response_model=APIResponse)
async def delete_user_account(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Delete current user's account (soft delete by deactivating)"""
    try:
        current_user.is_active = False
        db.commit()
        
        return APIResponse(
            success=True,
            message="Account deactivated successfully",
            data={"user_id": current_user.id}
        )
        
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to deactivate account: {str(e)}"
        )

@router.post("/social-login", response_model=Token)
async def social_login(provider: str, token: str, db: Session = Depends(get_db)):
    """Handle social media login (Google, Apple, etc.) - Demo endpoint"""
    # In a real implementation, you would:
    # 1. Verify the token with the provider (Google, Apple, etc.)
    # 2. Extract user information from the token
    # 3. Create or update user account
    # 4. Generate your own JWT token
    
    # For demo purposes, we'll create a mock response
    if provider not in ["google", "apple"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unsupported social login provider"
        )
    
    # Mock user data (in real app, this comes from the social provider)
    mock_user_data = {
        "username": f"social_user_{provider}",
        "email": f"user@{provider}.com",
        "full_name": f"{provider.capitalize()} User",
        "password": "social_login_placeholder"
    }
    
    # Check if user exists, create if not
    existing_user = db.query(User).filter(User.email == mock_user_data["email"]).first()
    
    if not existing_user:
        existing_user = create_user(db, mock_user_data)
    
    # Create access token
    access_token_expires = timedelta(minutes=30)
    access_token = AuthService.create_access_token(
        data={"sub": str(existing_user.id)}, expires_delta=access_token_expires
    )
    
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": UserResponse.from_orm(existing_user)
    }

@router.post("/logout", response_model=APIResponse)
async def logout_user(current_user: User = Depends(get_current_active_user)):
    """Logout user (client should remove token)"""
    # In a real implementation, you might want to:
    # 1. Add token to a blacklist
    # 2. Update user's last_logout timestamp
    # 3. Clear any server-side sessions
    
    return APIResponse(
        success=True,
        message="Successfully logged out",
        data={"user_id": current_user.id, "username": current_user.username}
    )

def generate_reset_token(length=32):
    alphabet = string.ascii_letters + string.digits
    return ''.join(secrets.choice(alphabet) for _ in range(length))

def generate_token_expiry(hours=1):
    return datetime.now() + timedelta(hours=hours)

@router.get("/", response_model=list[UserResponse])
async def get_users(
    skip: int = 0, 
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Get list of users (admin or demo purposes)"""
    users = db.query(User).filter(User.is_active == True).offset(skip).limit(limit).all()
    return [UserResponse.from_orm(user) for user in users]