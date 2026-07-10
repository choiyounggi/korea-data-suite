from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="KDS_", env_file=".env", extra="ignore")

    dev_mode: bool = False
    api_keys: str = ""
    proxy_secrets: str = ""
    db_path: str = "data/kds.db"
    data_go_kr_key: str = ""
    enable_scheduler: bool = True

    @property
    def allowed_keys(self) -> frozenset[str]:
        raw = f"{self.api_keys},{self.proxy_secrets}"
        return frozenset(k.strip() for k in raw.split(",") if k.strip())


@lru_cache
def get_settings() -> Settings:
    return Settings()
