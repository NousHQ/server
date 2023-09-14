import asyncio
import json
from functools import lru_cache
from pprint import pprint
from typing import Optional

import sentry_sdk
from aiofiles import open as aio_open
from fastapi import (BackgroundTasks, Depends, FastAPI, HTTPException, Request,
                     status)
from fastapi.concurrency import run_in_threadpool
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt

from client import (get_redis_connection, indexer_weaviate_client,
                    searcher_weaviate_client)
from config import settings
from indexer import indexer
from logger import get_logger
from schemas import SaveRequest, TokenData, WebhookRequestSchema
from searcher import searcher
from utils import convert_user_id, get_current_user, get_weaviate_schemas


sentry_sdk.init(
    dsn=settings.SENTRY_DSN,
    # Set traces_sample_rate to 1.0 to capture 100%
    # of transactions for performance monitoring.
    # We recommend adjusting this value in production.
    traces_sample_rate=1.0,
    # Set profiles_sample_rate to 1.0 to profile 100%
    # of sampled transactions.
    # We recommend adjusting this value in production.
    profiles_sample_rate=1.0,
)


logger = get_logger(__name__)

app = FastAPI()

origins = [
    "https://app.nous.fyi"
]

test_origins = "^https:\/\/nous-frontend-.*\.vercel\.app\/$"

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_origin_regex=test_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

queue = asyncio.Queue()


async def writer_worker():
    """Asynchronous worker to handle writes."""
    while True:
        data, filename = await queue.get()  # Wait for an item from the queue
        async with aio_open(filename, 'a') as f:
            await f.write(json.dumps(data) + '\n')
        queue.task_done()


async def write_to_log(data: dict, filename: str = 'search_logs.json'):
    await queue.put((data, filename))  # Just put the data in the queue and return immediately


@app.on_event("startup")
async def startup_event():
    asyncio.create_task(writer_worker())


@app.post("/api/init_schema")
async def init_schema(webhookData: WebhookRequestSchema, background_tasks: BackgroundTasks):
    user_id = convert_user_id(webhookData.record.id)
    knowledge_source, content = get_weaviate_schemas(user_id)
    client = indexer_weaviate_client()
    client.schema.create({"classes": [knowledge_source, content]})
    logger.info(f"New schema initialized for user {user_id}")
    with open("presaved.json", "r") as f:
        data_list = json.load(f)
        for bookmark in data_list:
            background_tasks.add_task(indexer, data=bookmark, user_id=user_id)
    logger.info(f"Presaved bookmarks for user {user_id}")
    return {"user_id": webhookData.record.id, "status": "schema_initialised"}


@app.post("/api/healthcheck")
async def test(request: Request, current_user: TokenData = Depends(get_current_user)):
    return {"status": "ok"}


@app.post("/api/save")
async def save(saveRequest: SaveRequest, background_tasks: BackgroundTasks, current_user: TokenData = Depends(get_current_user)):
    r = get_redis_connection()
    user_id = convert_user_id(current_user.sub)
    r_key = f"user:{user_id}"
    if r.sismember(r_key, saveRequest.pageData.url):
        logger.info(f"{user_id} already saved {saveRequest.pageData.url}")
        return {"status": "ok"}

    data = saveRequest.model_dump()
    background_tasks.add_task(indexer, data=data, user_id=user_id, r_conn=r)
    logger.info(f"{user_id} is saving data")
    return {"status": "ok"}


@app.get("/api/search")
async def query(query: str, current_user: TokenData = Depends(get_current_user)):
    # response = searcher(query)
    user_id = convert_user_id(current_user.sub)
    logger.info(f"{user_id} queried: {query}")
    user_id = convert_user_id(current_user.sub)
    raw_response, results = searcher(query=query, user_id=user_id)

    entry_dict = {
        "user_id": user_id,
        "query": query,
        "response": raw_response
    }

    await write_to_log(entry_dict)

    return {'query': query, 'results': results}


@app.get("/api/all_saved")
async def allSaved(current_user: TokenData = Depends(get_current_user)):
    logger.info(f"sending all saved to {current_user.sub}")
    user_id = convert_user_id(current_user.sub)
    source_class = settings.KNOWLEDGE_SOURCE_CLASS.format(user_id)
    client = searcher_weaviate_client()
    response = client.query.get(source_class, ["title", "uri"]).do()
    results = []
    for i, source in enumerate(response['data']['Get'][source_class]):
        results.append({
            "index": i,
            "uri": source['uri'],
            "title": source['title']
            })
    
    return results