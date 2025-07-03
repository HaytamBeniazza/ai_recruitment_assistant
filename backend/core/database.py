"""
Database configuration and setup for RecruitAI Pro
Handles PostgreSQL connection and SQLAlchemy models
"""

from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy.engine import Engine
import os

# Import settings
from .config import settings

# Create SQLAlchemy engine
engine = create_engine(
    settings.database_url_sync,
    echo=settings.debug,  # Log SQL queries in debug mode
    pool_pre_ping=True,   # Verify connections before use
    pool_recycle=300,     # Recycle connections every 5 minutes
)

# Create sessionmaker
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Create declarative base for models
Base = declarative_base()

def get_db():
    """
    Dependency to get database session
    Used with FastAPI's Depends()
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def init_db() -> None:
    """
    Initialize database tables
    Creates all tables defined in models
    """
    print("🗄️  Initializing database...")
    
    # Import all models here to ensure they are registered
    # from models import candidates, jobs, applications, communications
    
    # Create all tables
    Base.metadata.create_all(bind=engine)
    print("✅ Database tables created successfully")

def check_db_connection() -> bool:
    """
    Check if database connection is working
    Returns True if connection successful, False otherwise
    """
    try:
        # Test connection
        with engine.connect() as connection:
            connection.execute("SELECT 1")
        print("✅ Database connection successful")
        return True
    except Exception as e:
        print(f"❌ Database connection failed: {e}")
        return False

# Database utilities
class DatabaseManager:
    """Database management utilities"""
    
    @staticmethod
    def create_database_if_not_exists():
        """Create database if it doesn't exist"""
        try:
            # Create engine without database name to connect to PostgreSQL server
            db_url_without_db = settings.database_url_sync.rsplit('/', 1)[0]
            temp_engine = create_engine(db_url_without_db + '/postgres')
            
            with temp_engine.connect() as conn:
                # Check if database exists
                result = conn.execute(
                    f"SELECT 1 FROM pg_database WHERE datname = '{settings.database_name}'"
                )
                
                if not result.fetchone():
                    # Create database
                    conn.execute("COMMIT")  # End any existing transaction
                    conn.execute(f"CREATE DATABASE {settings.database_name}")
                    print(f"✅ Created database: {settings.database_name}")
                else:
                    print(f"📊 Database already exists: {settings.database_name}")
                    
        except Exception as e:
            print(f"❌ Error creating database: {e}")
    
    @staticmethod
    def drop_all_tables():
        """Drop all tables (use with caution!)"""
        if not settings.is_development:
            raise RuntimeError("Cannot drop tables in production environment")
            
        print("⚠️  Dropping all tables...")
        Base.metadata.drop_all(bind=engine)
        print("✅ All tables dropped")
    
    @staticmethod
    def reset_database():
        """Reset database (drop and recreate all tables)"""
        if not settings.is_development:
            raise RuntimeError("Cannot reset database in production environment")
            
        print("🔄 Resetting database...")
        DatabaseManager.drop_all_tables()
        init_db()
        print("✅ Database reset complete")

# Print database configuration
print(f"🗄️  Database Configuration:")
print(f"   Host: {settings.database_host}:{settings.database_port}")
print(f"   Database: {settings.database_name}")
print(f"   User: {settings.database_user}")
print(f"   Connection Pool: Enabled")
print(f"   Echo SQL: {settings.debug}") 