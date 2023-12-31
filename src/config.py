# from pydantic import BaseSettings
from pydantic_settings import BaseSettings, SettingsConfigDict


# class Settings(BaseSettings):
#     WEAVIATE_URL: str
#     WEAVIATE_API_KEY: str
#     OPENAI_API_KEY: str 
#     class Config:
#         env_file = ".env"

class Settings(BaseSettings):
    WEAVIATE_URL: str
    WEAVIATE_API_KEY: str
    OPENAI_API_KEY: str
    SUPABASE_SECRET: str
    SUPABASE_URL: str
    SUPABASE_SERVICE_KEY: str
    HUGGINGFACE_API_URL: str
    HUGGINGFACE_API_KEY: str
    COHERE_API_KEY: str
    SENTRY_DSN: str
    KNOWLEDGE_SOURCE_CLASS: str = "KnowledgeSourceId_{}"
    CONTENT_CLASS: str = "ContentId_{}"
    LOOPS_URL: str = "https://app.loops.so/api/v1/contacts/create"
    LOOPS_API_KEY: str
    MIXPANEL_TOKEN: str
    JOBS_QUEUE: str
    LEMON_SQUEEZY_SECRET: str
    model_config = SettingsConfigDict(env_file=".env")

settings = Settings()