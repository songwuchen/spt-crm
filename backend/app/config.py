from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/spt_crm"
    JWT_SECRET_KEY: str = "change-me-in-production"
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    JWT_REFRESH_TOKEN_EXPIRE_MINUTES: int = 10080
    UPLOAD_DIR: str = "uploads"
    CORS_ORIGINS: str = "http://localhost:5173,http://localhost:5175,http://localhost:3000,http://127.0.0.1:5173,http://127.0.0.1:5175"
    AI_PROVIDER: str = "mock"
    AI_API_KEY: str = ""
    AI_MODEL: str = ""
    AI_BASE_URL: str = "https://api.openai.com/v1"
    REDIS_URL: str = ""

    model_config = {"env_file": ".env", "extra": "ignore"}


settings = Settings()
