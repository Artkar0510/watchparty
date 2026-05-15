from functools import lru_cache
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class AppSettings(BaseModel):
    project_name: str = "content-service"
    debug: bool = False
    api_v1_prefix: str = "/api/v1"
    cache_expire_seconds: int = 300


class PostgreSQLSettings(BaseModel):
    host: str = "localhost"
    port: int = 5432
    user: str = "admin"
    password: str = "password"
    database: str = "content_db"

    @property
    def dsn(self) -> str:
        return f"postgresql://{self.user}:{self.password}@{self.host}:{self.port}/{self.database}"


class ElasticsearchSettings(BaseModel):
    host: str = "localhost"
    port: int = 9200
    scheme: str = "http"
    request_timeout: int = 10

    @property
    def url(self) -> str:
        return f"{self.scheme}://{self.host}:{self.port}"


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


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_nested_delimiter="__",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app: AppSettings = Field(default_factory=AppSettings)
    postgresql: PostgreSQLSettings = Field(default_factory=PostgreSQLSettings)
    elasticsearch: ElasticsearchSettings = Field(default_factory=ElasticsearchSettings)
    redis: RedisSettings = Field(default_factory=RedisSettings)
    auth: AuthSettings = Field(default_factory=AuthSettings)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
