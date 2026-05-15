from functools import lru_cache
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class AppSettings(BaseModel):
    project_name: str = "auth-service"
    debug: bool = False
    api_v1_prefix: str = "/api/v1"
    secret_key: str = "supersecretkey"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 30


class PostgreSQLSettings(BaseModel):
    host: str = "localhost"
    port: int = 5432
    user: str = "admin"
    password: str = "password"
    database: str = "auth_db"

    @property
    def dsn(self) -> str:
        return f"postgresql://{self.user}:{self.password}@{self.host}:{self.port}/{self.database}"


class RedisSettings(BaseModel):
    host: str = "localhost"
    port: int = 6379
    password: str | None = None
    token_ttl: int = 1800  # seconds

    @property
    def url(self) -> str:
        if self.password:
            return f"redis://:{self.password}@{self.host}:{self.port}"
        return f"redis://{self.host}:{self.port}"


class RabbitSettings(BaseModel):
    host: str = "localhost"
    port: int = 5672
    user: str = "guest"
    password: str = "guest"
    enabled: bool = True

    @property
    def url(self) -> str:
        return f"amqp://{self.user}:{self.password}@{self.host}:{self.port}/"


class SentrySettings(BaseModel):
    dsn: str | None = None
    environment: str = "development"
    traces_sample_rate: float = 0.0


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_nested_delimiter="__",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app: AppSettings = Field(default_factory=AppSettings)
    postgresql: PostgreSQLSettings = Field(default_factory=PostgreSQLSettings)
    redis: RedisSettings = Field(default_factory=RedisSettings)
    rabbit: RabbitSettings = Field(default_factory=RabbitSettings)
    sentry: SentrySettings = Field(default_factory=SentrySettings)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
