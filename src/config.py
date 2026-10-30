from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configurações da aplicação carregadas de variáveis de ambiente."""

    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"
    groq_api_key: str = ""
    groq_model: str = "openai/gpt-oss-20b"
    groq_base_url: str = "https://api.groq.com/openai/v1"
    redis_url: str = ""
    pokeapi_base_url: str = "https://pokeapi.co/api/v2"
    cache_db_path: str = "data/cache.db"
    cache_ttl_seconds: int = 86400
    request_timeout_seconds: float = 10.0
    max_turns_per_request: int = 8
    catalog_config: str = "default"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )


# Instância global de configurações
settings = Settings()
