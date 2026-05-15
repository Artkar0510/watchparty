from functools import lru_cache
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class PostgreSQLSettings(BaseModel):
    host: str = "localhost"
    port: int = 5432
    user: str = "admin"
    password: str = "password"
    database: str = "content_db"

    @property
    def dsn(self) -> str:
        return f"host={self.host} port={self.port} dbname={self.database} user={self.user} password={self.password}"


class ElasticsearchSettings(BaseModel):
    host: str = "localhost"
    port: int = 9200
    scheme: str = "http"

    @property
    def url(self) -> str:
        return f"{self.scheme}://{self.host}:{self.port}"


class ETLSettings(BaseModel):
    batch_size: int = 100
    poll_interval: int = 30  # seconds between full syncs
    state_file: str = "/tmp/etl_state.json"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_nested_delimiter="__",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    postgresql: PostgreSQLSettings = Field(default_factory=PostgreSQLSettings)
    elasticsearch: ElasticsearchSettings = Field(default_factory=ElasticsearchSettings)
    etl: ETLSettings = Field(default_factory=ETLSettings)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
