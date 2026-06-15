from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    async_database_url: str
    cors_origins: list[str] = ["http://localhost:5173"]

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
