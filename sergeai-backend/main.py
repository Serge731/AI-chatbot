import datetime
from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from requests import Session
from app.models import User
from app.routers import users, chat, mood, settings, admin
from app.database import get_db, init_db, create_sample_data
from contextlib import asynccontextmanager
import uvicorn
import os
from pathlib import Path
from dotenv import load_dotenv
import smtplib
from email.mime.text import MIMEText

load_dotenv()

# Get the absolute path to the out/ directory
BASE_DIR = Path(__file__).parent.parent
OUT_DIR = BASE_DIR / "sergeai-frontend" / "out"  # This should point to your Next.js build output

print(f"📁 Serving static files from: {OUT_DIR}")
print(f"📁 Directory exists: {OUT_DIR.exists()}")
if OUT_DIR.exists():
    print(f"📁 Contents: {list(OUT_DIR.glob('*'))}")

# Startup and shutdown events
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    print("🚀 Initializing SergeAI Backend...")
    init_db()
    create_sample_data()
    print("✅ Database initialized successfully")
    yield
    # Shutdown
    print("🛑 Shutting down SergeAI Backend...")

# Create FastAPI app
app = FastAPI(
    title="SergeAI Backend",
    version="1.0.0",
    description="AI-powered mental health support backend API",
    lifespan=lifespan
)

# Get allowed origins from environment variable
allowed_origins = os.getenv("ALLOWED_ORIGINS", "").split(",")
# Filter out any empty strings
allowed_origins = [origin.strip() for origin in allowed_origins if origin.strip()]

# Debug print to see what's being loaded
print(f"🎯 Environment ALLOWED_ORIGINS: {os.getenv('ALLOWED_ORIGINS')}")
print(f"🎯 Parsed allowed_origins: {allowed_origins}")

# ✅ Serve static files from the out/ directory - ONLY IF THEY EXIST
if OUT_DIR.exists():
    # Mount _next directory if it exists (Next.js static assets)
    next_static_dir = OUT_DIR / "_next"
    if next_static_dir.exists():
        app.mount("/_next", StaticFiles(directory=next_static_dir), name="next-static")
        print("✅ _next static files mounted")
    else:
        print("ℹ️  _next directory not found")
    
    # Mount other static directories only if they exist
    for static_dir in ["static", "public", "assets"]:
        potential_dir = OUT_DIR / static_dir
        if potential_dir.exists():
            app.mount(f"/{static_dir}", StaticFiles(directory=potential_dir), name=f"{static_dir}-files")
            print(f"✅ {static_dir} directory mounted")
else:
    print("❌ out/ directory not found! Frontend will not be served.")

# ✅ CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"]
)

# Include routers - these will be available at /api/v1/*
app.include_router(users.router, prefix="/api/v1/users", tags=["Users and Authentication"])
app.include_router(chat.router, prefix="/api/v1/chat", tags=["Chat"])
app.include_router(mood.router, prefix="/api/v1/mood", tags=["Mood"])
app.include_router(settings.router, prefix="/api/v1/settings", tags=["Settings"])
app.include_router(admin.router, prefix="/api/v1/admin", tags=["Admin"])

# ✅ Serve SPA routes - handle Next.js routing
@app.get("/{full_path:path}")
async def serve_spa(full_path: str):
    if not OUT_DIR.exists():
        raise HTTPException(status_code=404, detail="Frontend not built. Run 'npm run build' first.")
    
    # Don't interfere with API routes, docs, or static files
    if (full_path.startswith('api/') or 
        full_path.startswith('docs') or 
        full_path.startswith('redoc') or
        full_path.startswith('_next/') or
        full_path.startswith('static/') or
        full_path.startswith('public/') or
        full_path.startswith('assets/')):
        raise HTTPException(status_code=404, detail="Not Found")
    
    # Check if the path exists as a file
    potential_file = OUT_DIR / full_path
    if potential_file.exists() and potential_file.is_file():
        return FileResponse(potential_file)
    
    # Check if the path exists as a directory with index.html
    potential_dir = OUT_DIR / full_path
    potential_index = potential_dir / "index.html"
    if potential_index.exists():
        return FileResponse(potential_index)
    
    # Check if the path is a Next.js route (file without extension)
    if not Path(full_path).suffix:  # No file extension
        potential_html = OUT_DIR / f"{full_path}.html"
        if potential_html.exists():
            return FileResponse(potential_html)
    
    # Fallback: serve main index.html for SPA routing
    index_path = OUT_DIR / "index.html"
    if index_path.exists():
        return FileResponse(index_path)
    
    raise HTTPException(status_code=404, detail="Page not found")

# ✅ Root endpoint
@app.get("/", tags=["Root"])
async def root():
    index_path = OUT_DIR / "index.html"
    if index_path.exists():
        return FileResponse(index_path)
    return {
        "message": "SergeAI Backend is running 🚀 (Frontend not built)",
        "version": "1.0.0",
        "status": "healthy",
        "docs": "/docs",
        "redoc": "/redoc"
    }

# Health check endpoint
@app.get("/health", tags=["Health"])
async def health_check():
    return {
        "status": "healthy",
        "message": "SergeAI Backend is operational",
        "frontend_served": OUT_DIR.exists(),
        "timestamp": "2024-01-01T00:00:00Z"
    }

# In your backend (main.py or auth.py)
@app.post("/api/v1/users/auth/forgot-password")
async def forgot_password(
    email: str,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    # 1. Check if user exists (optional - for security)
    user = db.query(User).filter(User.email == email).first()
    if not user:
        # Still return success for security reasons
        return {"message": "If an account with that email exists, we've sent a reset link."}
    
    # 2. Generate reset token
    reset_token = users.generate_reset_token()  # You need to create this function
    
    # 3. Store token in database with expiration (e.g., 1 hour)
    user.reset_token = reset_token
    user.reset_token_expires = datetime.now() + datetime.timedelta(hours=1)
    db.commit()
    
    # 4. Send email (in background)
    background_tasks.add_task(send_password_reset_email, email, reset_token)
    
    return {"message": "If an account with that email exists, we've sent a reset link."}

# Email sending function
async def send_password_reset_email(email: str, token: str):
    try:
        # Create reset link
        frontend_url = os.getenv('FRONTEND_URL', 'http://localhost:3000')
        reset_link = f"{frontend_url}/auth/reset-password?token={token}"
        
        # Email content
        subject = "Password Reset Request"
        body = f"""
        Hello,
        
        You requested a password reset. Click the link below to reset your password:
        
        {reset_link}
        
        This link will expire in 1 hour.
        
        If you didn't request this, please ignore this email.
        """
        
        # Send email
        send_email(email, subject, body)  # You need to implement this
        
        print(f"✅ Password reset email sent to: {email}")
        
    except Exception as e:
        print(f"❌ Failed to send email to {email}: {e}")

# Email sending helper
def send_email(to_email: str, subject: str, body: str):
    
    msg = MIMEText(body)
    msg['Subject'] = subject
    msg['From'] = os.getenv('SMTP_USERNAME')
    msg['To'] = to_email
    
    server = smtplib.SMTP(os.getenv('SMTP_SERVER'), int(os.getenv('SMTP_PORT')))
    server.starttls()
    server.login(os.getenv('SMTP_USERNAME'), os.getenv('SMTP_PASSWORD'))
    server.send_message(msg)
    server.quit()

# Crisis endpoint for immediate help
@app.post("/api/v1/crisis", tags=["Crisis"])
async def log_crisis_intervention(
    crisis_type: str,
    service_used: str,
    user_id: int = None
):
    """Log crisis intervention for monitoring"""
    try:
        from app.models import CrisisLog
        from app.database import SessionLocal
        
        db = SessionLocal()
        
        crisis_log = CrisisLog(
            user_id=user_id,
            crisis_type=crisis_type,
            service_used=service_used
        )
        
        db.add(crisis_log)
        db.commit()
        db.close()
        
        return {
            "success": True,
            "message": "Crisis intervention logged",
            "emergency_resources": {
                "crisis_lifeline": "988",
                "crisis_text": "741741",
                "emergency": "911"
            }
        }
        
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "message": "Failed to log crisis intervention",
                "error": str(e)
            }
        )

# Global exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    return JSONResponse(
        status_code=500,
        content={
            "success": False,
            "message": "An unexpected error occurred",
            "error": str(exc)
        }
    )

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )