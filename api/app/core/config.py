from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="CLICKHOUSE_")

    host: str = "clickhouse"
    port: int = 8123
    user: str = "default"
    password: str = ""
    db: str = "shib"
    pool_size: int = 8


settings = Settings()
