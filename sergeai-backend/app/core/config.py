# app/core/config.py
import os
from dotenv import load_dotenv

load_dotenv()

# ---------------------------
# JWT Configuration
# ---------------------------
SECRET_KEY = os.getenv("SECRET_KEY")
if not SECRET_KEY:
    # Generate a fallback for development only - NEVER use in production
    import secrets
    SECRET_KEY = secrets.token_urlsafe(32)
    print(f"WARNING: Using auto-generated SECRET_KEY for development: {SECRET_KEY}")

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

# ---------------------------
# Database Configuration
# ---------------------------
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./test.db")

# ---------------------------
# Other Configurations (add as needed)
# ---------------------------