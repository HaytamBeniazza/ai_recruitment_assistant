"""
Configuration management for RecruitAI Pro
Handles environment variables and application settings
"""

from pydantic_settings import BaseSettings
from typing import List, Optional
import os
from pathlib import Path

class Settings(BaseSettings):
    """Application settings loaded from environment variables"""
    
    # Application Configuration
    app_name: str = "RecruitAI Pro"
    app_version: str = "1.0.0"
    app_description: str = "AI-Powered Recruitment Assistant"
    debug: bool = True
    environment: str = "development"
    
    # Database Configuration  
    database_url: str = "sqlite:///./recruitai_dev.db"  # SQLite for Phase 1 development
    database_host: str = "localhost"
    database_port: int = 5432
    database_name: str = "recruitai_db"
    database_user: str = "recruiter"
    database_password: str = "password"
    
    # Redis Configuration (Message Broker)
    redis_url: str = "redis://localhost:6379/0"
    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_db: int = 0
    
    # AI Services
    openai_api_key: Optional[str] = None
    anthropic_api_key: Optional[str] = None
    
    # Email Services
    sendgrid_api_key: Optional[str] = None
    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 587
    smtp_user: Optional[str] = None
    smtp_password: Optional[str] = None
    
    # Calendar Integration
    google_calendar_credentials_file: Optional[str] = None
    google_calendar_scopes: str = "https://www.googleapis.com/auth/calendar"
    
    # Security
    secret_key: str = "your_super_secret_key_here_change_in_production"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    
    # File Upload
    max_file_size: int = 10485760  # 10MB in bytes
    allowed_file_types: List[str] = ["pdf", "docx", "doc"]
    upload_folder: str = "./uploads"
    
    # Resume Processing Configuration
    min_resume_score: int = 50
    auto_schedule_threshold: int = 75
    human_review_threshold: int = 85
    
    # Rate Limiting
    rate_limit_per_minute: int = 60
    rate_limit_per_hour: int = 1000
    
    # CORS
    allowed_origins: List[str] = ["http://localhost:3000", "http://127.0.0.1:3000"]
    
    # Agent Configuration
    resume_analyzer_enabled: bool = True
    scheduler_enabled: bool = True
    communication_enabled: bool = True
    
    # Performance Settings
    max_concurrent_processing: int = 10
    processing_timeout: int = 300  # 5 minutes
    
    class Config:
        env_file = ".env"
        case_sensitive = False
        
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        
        # Create upload directory if it doesn't exist
        upload_path = Path(self.upload_folder)
        upload_path.mkdir(parents=True, exist_ok=True)
        
        # Validate critical settings
        self._validate_settings()
    
    def _validate_settings(self):
        """Validate critical configuration settings"""
        warnings = []
        
        # Check AI service keys
        if not self.openai_api_key:
            warnings.append("OpenAI API key not configured - Resume analysis will be limited")
            
        # Check email configuration
        if not self.sendgrid_api_key and not (self.smtp_user and self.smtp_password):
            warnings.append("Email service not configured - Communication agent will be limited")
            
        # Check file upload limits
        if self.max_file_size > 50 * 1024 * 1024:  # 50MB
            warnings.append("File upload limit very high - consider reducing for performance")
            
        # Print warnings
        for warning in warnings:
            print(f"⚠️  CONFIG WARNING: {warning}")
    
    @property
    def database_url_sync(self) -> str:
        """Get synchronous database URL (for migrations)"""
        if "sqlite:" in self.database_url:
            return self.database_url
        return self.database_url.replace("postgresql://", "postgresql+psycopg2://")
    
    @property
    def database_url_async(self) -> str:
        """Get asynchronous database URL (for FastAPI)"""
        if "sqlite:" in self.database_url:
            return self.database_url
        return self.database_url.replace("postgresql://", "postgresql+asyncpg://")
    
    @property
    def is_production(self) -> bool:
        """Check if running in production environment"""
        return self.environment.lower() == "production"
    
    @property
    def is_development(self) -> bool:
        """Check if running in development environment"""
        return self.environment.lower() == "development"

# Create global settings instance
settings = Settings()

# Print configuration summary
print(f"🔧 RecruitAI Pro Configuration Loaded")
print(f"   Environment: {settings.environment}")
print(f"   Debug Mode: {settings.debug}")
if "sqlite:" in settings.database_url:
    print(f"   Database: SQLite (./recruitai_dev.db) - Phase 1 Development")
else:
    print(f"   Database: {settings.database_host}:{settings.database_port}/{settings.database_name}")
print(f"   Redis: {settings.redis_host}:{settings.redis_port}/{settings.redis_db}")
print(f"   Upload Folder: {settings.upload_folder}")
print(f"   Max File Size: {settings.max_file_size // 1024 // 1024}MB")
print(f"   Agents Enabled: Resume={settings.resume_analyzer_enabled}, Scheduler={settings.scheduler_enabled}, Communication={settings.communication_enabled}") 