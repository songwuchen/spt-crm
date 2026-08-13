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
    AI_BASE_URL: str = ""          # 留空则用 CHAT_PROVIDERS[AI_PROVIDER] 的预设地址
    AI_THINKING: str = "auto"      # auto/off,仅对支持 enable_thinking 的供应商生效
    REDIS_URL: str = ""
    MAX_EXPORT_ROWS: int = 5000
    # 线索 180 天重激活：计时天数；每日扫描时刻(北京时间 HH:MM)；跳过申报人待办的姓名(逗号分隔，如张贺)
    LEAD_REACTIVATION_DAYS: int = 180
    LEAD_REACTIVATION_SCAN_TIME: str = "09:00"
    LEAD_REACT_SKIP_REPORTER_NAMES: str = "张贺"

    model_config = {"env_file": ".env", "extra": "ignore"}


settings = Settings()
