from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache
from typing import Literal

class Settings(BaseSettings):
    PINECONE_API_KEY: str
    GROQ_API_KEY: str
    TAVILY_API_KEY: str | None = None
    ES_URL: str | None = None
    PROJECT_NAME: str = "moodle-virtual-assistant"
    LOG_LEVEL: Literal["DEBUG", "INFO", "WARNING"] = "INFO"
    
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore"
    )
    
@lru_cache()
def get_settings() -> Settings:
    return Settings()

settings = get_settings()