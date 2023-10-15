import weaviate
from functools import lru_cache
from config import settings
from fastapi import HTTPException, status, Depends
from jose import JWTError, jwt
from fastapi.security import OAuth2PasswordBearer
from schemas import TokenData


@lru_cache
def get_no_schema_failed_exception():
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Your search did not match any documents.")

@lru_cache
def get_failed_exception():
    return HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Something went wrong!")

@lru_cache
def get_bad_search_exception():
    return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Couldn't search for that! It wasn't saved properly.")

@lru_cache
def get_delete_failed_exception():
    return HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Couldn't delete that!")

@lru_cache
def get_current_user(token: str = Depends(OAuth2PasswordBearer(tokenUrl="token"))):
    credentials_exception = HTTPException(
        status_code=status.HTTP_403_FORBIDDEN, detail="Could not validate credentials"
    )
    try:
        payload = jwt.decode(token, settings.SUPABASE_SECRET, algorithms=["HS256"], audience="authenticated")
        user_data = TokenData(**payload)
    except JWTError:
        raise credentials_exception
    return user_data


@lru_cache
def convert_user_id(user_id: str):
    if "-" in user_id:
        return user_id.replace("-", "_")
    elif "_" in user_id:
        return user_id.replace("_", "-")
    else:
        return user_id


@lru_cache
def get_weaviate_schemas(user_id):
    source_class = settings.KNOWLEDGE_SOURCE_CLASS.format(user_id)
    content_class = settings.CONTENT_CLASS.format(user_id)
    
    knowledge_source = {
        "class": source_class,
        "description": "A source saved by the user",
        "properties": [
            {
                "name": "uri",
                "description": "The URI of the source",
                "dataType": ["text"],
            },
            {
                "name": "title",
                "description": "The title of the source",
                "dataType": ["text"]
            },
            {
                "name": "chunk_refs",
                "dataType": [content_class],
                "description": "Reference IDs to chunks",
            }
        ]
    }

    content = {
        "class": content_class,
        "description": "The content of a source",
        "properties": [
            {
                "name": "source_content",
                "dataType": ["text"]
            },
            {
                "name": "hasCategory",
                "dataType": [source_class],
                "description": "The source of the knowledge"
            }
        ],
        "vectorizer": "text2vec-openai",
        "moduleConfig": {
            "reranker-cohere": {
                "model": "rerank-english-v2.0"
            },
            "text2vec-openai": {
                "model": "ada",
                "modelVersion": "002",
                "type": "text"
            }
        }
    }

    return knowledge_source, content