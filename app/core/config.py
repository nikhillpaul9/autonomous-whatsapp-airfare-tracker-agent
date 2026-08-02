from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional

class Settings(BaseSettings):
    OPENAI_API_KEY: str
    GEMINI_API_KEY: str
    SERPAPI_KEY: str
    TWILIO_ACCOUNT_SID: str
    TWILIO_AUTH_TOKEN: str
    TWILIO_WHATSAPP_NUMBER: str
    POSTGRES_URI: str
    NGROK_URL: Optional[str] = None

    # We use ONLY model_config for Pydantic V2, dropping the old class Config:
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

settings = Settings()