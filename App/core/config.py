from pydantic import BaseModel
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional

class Settings(BaseSettings):
    # Amadeus API settings
    amadeus_api_key: str
    amadeus_api_secret: str
    amadeus_base_url: str 
    
    # Add the missing groq_api_key field
    groq_api_key: str

    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8"
    )

settings = Settings()