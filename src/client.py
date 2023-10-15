import weaviate
from functools import lru_cache
from config import settings
import redis
from mixpanel import Mixpanel, Consumer


def indexer_weaviate_client():
    return weaviate.Client(
        url=settings.WEAVIATE_URL,
        auth_client_secret=weaviate.AuthApiKey(api_key=settings.WEAVIATE_API_KEY),
        additional_headers={
            "X-OpenAI-Api-Key": settings.OPENAI_API_KEY,
            "X-Huggingface-Api-Key": settings.HUGGINGFACE_API_KEY,
            "X-Cohere-Api-Key": settings.COHERE_API_KEY
        }
    )

# @lru_cache
def query_weaviate_client():
    return weaviate.Client(
        url=settings.WEAVIATE_URL,
        auth_client_secret=weaviate.AuthApiKey(api_key=settings.WEAVIATE_API_KEY),
        additional_headers={
            "X-OpenAI-Api-Key": settings.OPENAI_API_KEY,
            "X-Huggingface-Api-Key": settings.HUGGINGFACE_API_KEY,
            "X-Cohere-Api-Key": settings.COHERE_API_KEY
        }
    )


def get_redis_connection():
    return redis.StrictRedis(host='localhost', port=6379, db=0)

def get_mixpanel_client():
    return Mixpanel(settings.MIXPANEL_TOKEN, consumer=Consumer(api_host="api-eu.mixpanel.com"))