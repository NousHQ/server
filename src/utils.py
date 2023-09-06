import weaviate
from functools import lru_cache
from config import settings
from fastapi import HTTPException, status


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

@lru_cache
def get_no_schema_failed_exception():
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="You haven't saved anything!")

@lru_cache
def get_failed_exception():
    return HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Something went wrong!")
