"""Configuration settings for SmartPlayFPL backend."""

import os
from typing import Optional
from dotenv import load_dotenv
from pydantic import field_validator
from pydantic_settings import BaseSettings

load_dotenv()


class Settings(BaseSettings):
    """Application settings loaded from environment variables with validation."""

    # ==========================================================================
    # Environment Identifier
    # ==========================================================================
    ENVIRONMENT: str = "development"  # "development" or "production"

    # ==========================================================================
    # FPL API Settings
    # ==========================================================================
    FPL_BASE_URL: str = "https://fantasy.premierleague.com/api"
    FPL_CACHE_TTL: int = 300  # 5 minutes
    FPL_REQUEST_TIMEOUT: float = 30.0  # 30 seconds for FPL API calls
    FPL_MAX_RETRIES: int = 3
    FPL_RETRY_DELAY: float = 1.0  # Initial delay between retries

    # ==========================================================================
    # Server Settings
    # ==========================================================================
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    DEBUG: bool = False
    LOG_LEVEL: str = "INFO"

    # ==========================================================================
    # CORS Settings
    # ==========================================================================
    FRONTEND_URL: str = "http://localhost:3000"
    CORS_ORIGINS: str = ""  # Comma-separated list of additional origins

    # ==========================================================================
    # Claude AI Settings
    # ==========================================================================
    ANTHROPIC_API_KEY: str = ""
    CLAUDE_REQUEST_TIMEOUT: float = 120.0  # 2 minutes for AI calls
    CLAUDE_MAX_RETRIES: int = 2
    CLAUDE_CACHE_TTL: int = 86400  # 24 hours

    # ==========================================================================
    # Self-Healing AI Settings (dedicated key for self-healing)
    # ==========================================================================
    SELF_HEALING_API_KEY: str = ""  # Separate API key for self-healing service

    # ==========================================================================
    # Database Settings
    # ==========================================================================
    DATABASE_URL: str = "sqlite:///./smartplayfpl.db"
    DB_POOL_SIZE: int = 5
    DB_MAX_OVERFLOW: int = 10
    DB_POOL_TIMEOUT: int = 30
    DB_POOL_RECYCLE: int = 1800  # 30 minutes
    DB_ECHO: bool = False  # SQL query logging

    # ==========================================================================
    # Circuit Breaker Settings
    # ==========================================================================
    CB_FAILURE_THRESHOLD: int = 5  # Failures before opening circuit
    CB_RECOVERY_TIMEOUT: int = 60  # Seconds before attempting recovery
    CB_HALF_OPEN_REQUESTS: int = 3  # Requests to test in half-open state

    # ==========================================================================
    # Rate Limiting
    # ==========================================================================
    RATE_LIMIT_DEFAULT: str = "100/minute"
    RATE_LIMIT_AI: str = "20/minute"  # More strict for AI endpoints

    # ==========================================================================
    # Feature Flags
    # ==========================================================================
    SKIP_KG: bool = False  # Skip Knowledge Graph initialization
    SKIP_SCHEDULER: bool = False  # Skip ML scheduler

    @field_validator("DEBUG", "DB_ECHO", "SKIP_KG", "SKIP_SCHEDULER", mode="before")
    @classmethod
    def parse_bool(cls, v):
        if isinstance(v, bool):
            return v
        if isinstance(v, str):
            return v.lower() in ("true", "1", "yes")
        return bool(v)

    @field_validator("PORT", "DB_POOL_SIZE", "DB_MAX_OVERFLOW", "DB_POOL_TIMEOUT",
                     "DB_POOL_RECYCLE", "CB_FAILURE_THRESHOLD", "CB_RECOVERY_TIMEOUT",
                     "CB_HALF_OPEN_REQUESTS", mode="before")
    @classmethod
    def parse_int(cls, v):
        if isinstance(v, int):
            return v
        return int(v)

    @field_validator("FPL_REQUEST_TIMEOUT", "CLAUDE_REQUEST_TIMEOUT",
                     "FPL_RETRY_DELAY", mode="before")
    @classmethod
    def parse_float(cls, v):
        if isinstance(v, float):
            return v
        return float(v)

    def get_cors_origins(self) -> list[str]:
        """Get all CORS origins as a list."""
        origins = [self.FRONTEND_URL]
        if self.CORS_ORIGINS:
            origins.extend([o.strip() for o in self.CORS_ORIGINS.split(",")])
        return origins

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True


# Global settings instance
settings = Settings()


# ==========================================================================
# Timeout Presets for Different Operations
# ==========================================================================

class TimeoutPresets:
    """Predefined timeout configurations for different operation types."""

    # Quick operations (simple data fetches)
    QUICK = 10.0

    # Standard operations (most API calls)
    STANDARD = 30.0

    # Long operations (complex calculations, multiple API calls)
    LONG = 60.0

    # AI operations (Claude API calls)
    AI = 120.0

    # Batch operations (bulk data processing)
    BATCH = 300.0


timeouts = TimeoutPresets()
