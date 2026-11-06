from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql://billing:billing@localhost:5432/billing"
    pool_min_size: int = 1
    pool_max_size: int = 10
    pool_timeout_seconds: float = 5.0


settings = Settings()
