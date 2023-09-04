import weaviate
from functools import lru_cache
from config import settings

@lru_cache()
def get_weaviate_client():
    return weaviate.Client(
        url=settings.WEAVIATE_URL,
        auth_client_secret=weaviate.AuthApiKey(api_key=settings.WEAVIATE_API_KEY),
        additional_headers={
            "X-OpenAI-Api-Key": settings.OPENAI_API_KEY,
            "X-Huggingface-Api-Key": settings.HUGGINGFACE_API_KEY
        }
    )