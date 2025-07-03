from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    amadeus_api_key: str
    amadeus_api_secret: str
    amadeus_api_url: str

    class Config:
        env_file = ".env"

settings = Settings()