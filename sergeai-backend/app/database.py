from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import os
from dotenv import load_dotenv

load_dotenv()

# Database configuration
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./sergeai.db")

# SQLite specific configuration
if DATABASE_URL.startswith("sqlite"):
    engine = create_engine(
        DATABASE_URL, 
        connect_args={"check_same_thread": False},
        echo=False  # Set to True for SQL query logging
    )
else:
    # PostgreSQL configuration
    engine = create_engine(DATABASE_URL, echo=False)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

def get_db():
    """Database dependency"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def init_db():
    """Initialize database tables"""
    from app.models import Base
    Base.metadata.create_all(bind=engine)

def create_sample_data():
    """Create sample data for testing"""
    from app.models import SystemStats
    from datetime import datetime
    
    db = SessionLocal()
    try:
        # Check if sample data already exists
        existing_stats = db.query(SystemStats).first()
        if not existing_stats:
            # Create initial system stats
            sample_stats = SystemStats(
                date=datetime.utcnow(),
                active_users=1247,
                total_sessions=156,
                crisis_interventions=3,
                positive_feedback_rate=0.89,
                average_mood_score=3.2
            )
            db.add(sample_stats)
            db.commit()
            print("Sample system stats created")
    except Exception as e:
        print(f"Error creating sample data: {e}")
        db.rollback()
    finally:
        db.close()

# ✅ Add this function for testing DB connection
def test_connection():
    """Test the database connection"""
    try:
        conn = engine.connect()
        print("✅ Database connection successful!")
        conn.close()
    except Exception as e:
        print("❌ Database connection failed:", e)
