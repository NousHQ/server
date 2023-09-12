from functools import lru_cache
from pprint import pprint
from typing import Optional

from fastapi import Depends, FastAPI, HTTPException, Request, status, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer
from fastapi.concurrency import run_in_threadpool
from jose import JWTError, jwt
from aiofiles import open as aio_open
import asyncio
import json

from config import settings
from indexer import indexer
from searcher import searcher
from logger import get_logger
from client import get_weaviate_client
from schemas import TokenData, Record, WebhookRequestSchema
from utils import get_current_user, convert_user_id, get_weaviate_schemas

logger = get_logger(__name__)

app = FastAPI()

queue = asyncio.Queue()


origins = [
    "https://app.nous.fyi"
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


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
    client = get_weaviate_client()
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
async def save(request: Request, background_tasks: BackgroundTasks, current_user: TokenData = Depends(get_current_user)):
    user_id = convert_user_id(current_user.sub)
    data = await request.json()
    logger.info(f"{current_user.sub} is saving data")
    background_tasks.add_task(indexer, data=data, user_id=user_id)
    return {"status": "ok"}


@app.get("/api/search")
async def query(query: str, current_user: TokenData = Depends(get_current_user)):
    # response = searcher(query)
    logger.info(f"{current_user.sub} queried: {query}")
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
    client = get_weaviate_client()
    response = client.query.get(source_class, ["title", "uri"]).do()
    results = []
    for i, source in enumerate(response['data']['Get'][source_class]):
        results.append({
            "index": i,
            "uri": source['uri'],
            "title": source['title']
            })
    
    return results