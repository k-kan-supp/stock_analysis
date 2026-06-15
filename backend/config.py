from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://user:pass@localhost:5432/stockdb"
    cors_origins: list[str] = ["http://localhost:5173"]

    model_config = {"env_file": ".env"}


settings = Settings()
