# test_connection.py
import os
from dotenv import load_dotenv
from sqlalchemy import create_engine

load_dotenv()

try:
    engine = create_engine(os.getenv("DATABASE_URL"))
    connection = engine.connect()
    print("✓ Database connection successful!")
    connection.close()
except Exception as e:
    print(f"✗ Database connection failed: {e}")