from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Tüm ayarlar ortam değişkenlerinden okunur; anahtarlar yalnızca backend'de yaşar."""

    model_config = SettingsConfigDict(env_file=(".env", "../.env"), env_file_encoding="utf-8", extra="ignore")

    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.5-flash"
    groq_api_key: str = ""
    groq_model: str = "llama-3.3-70b-versatile"
    ors_api_key: str = ""

    osrm_foot_url: str = "https://routing.openstreetmap.de/routed-foot"
    osrm_car_url: str = "https://routing.openstreetmap.de/routed-car"
    overpass_urls: str = "https://overpass-api.de/api/interpreter,https://overpass.private.coffee/api/interpreter"
    nominatim_url: str = "https://nominatim.openstreetmap.org"
    user_agent: str = "Rota/0.1 (open-source AI city guide; https://github.com/your-username/rota)"

    cache_path: str = "data/rota_cache.sqlite3"
    cors_origins: str = "http://localhost:3000"
    rate_limit_per_minute: int = 6
    http_timeout: float = 25.0

    @property
    def cors_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def overpass_list(self) -> list[str]:
        return [u.strip() for u in self.overpass_urls.split(",") if u.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
