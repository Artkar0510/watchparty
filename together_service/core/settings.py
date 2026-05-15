from functools import lru_cache
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class AppSettings(BaseModel):
    project_name: str = "together-service"
    debug: bool = False
    api_v1_prefix: str = "/api/v1"
    session_ttl: int = 86400  # seconds


class RedisSettings(BaseModel):
    host: str = "localhost"
    port: int = 6379
    password: str | None = None

    @property
    def url(self) -> str:
        if self.password:
            return f"redis://:{self.password}@{self.host}:{self.port}"
        return f"redis://{self.host}:{self.port}"


class AuthSettings(BaseModel):
    service_url: str = "http://localhost:8001"


class ContentSettings(BaseModel):
    service_url: str = "http://localhost:8002"


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
    redis: RedisSettings = Field(default_factory=RedisSettings)
    auth: AuthSettings = Field(default_factory=AuthSettings)
    content: ContentSettings = Field(default_factory=ContentSettings)
    rabbit: RabbitSettings = Field(default_factory=RabbitSettings)
    sentry: SentrySettings = Field(default_factory=SentrySettings)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
