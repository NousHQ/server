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
                    query_weaviate_client, get_mixpanel_client)
from config import settings
from indexer import indexer
from logger import get_logger
from schemas import SaveRequest, TokenData, WebhookRequestSchema
from searcher import searcher
from utils import convert_user_id, get_current_user, get_weaviate_schemas, get_failed_exception, get_delete_failed_exception


# sentry_sdk.init(
#     dsn=settings.SENTRY_DSN,
#     # Set traces_sample_rate to 1.0 to capture 100%
#     # of transactions for performance monitoring.
#     # We recommend adjusting this value in production.
#     traces_sample_rate=1.0,
#     # Set profiles_sample_rate to 1.0 to profile 100%
#     # of sampled transactions.
#     # We recommend adjusting this value in production.
#     profiles_sample_rate=1.0,
# )



logger = get_logger(__name__)

app = FastAPI()

origins = [
    "https://app.nous.fyi",
    "http://localhost:3000"
]

test_origins = "^https://nous-frontend-.*\.vercel\.app"

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
    r = get_redis_connection()
    client = indexer_weaviate_client()
    mp = get_mixpanel_client()
    user_id = convert_user_id(webhookData.record.id)
    r_key = f"user:{user_id}"
    knowledge_source, content = get_weaviate_schemas(user_id)
    client.schema.create({"classes": [knowledge_source, content]})
    logger.info(f"New schema initialized for user {user_id}")
    with open("presaved.json", "r") as f:
        data_list = json.load(f)
        for bookmark in data_list:
            background_tasks.add_task(indexer, data=bookmark, user_id=user_id, r_conn=r)
    logger.info(f"Presaved bookmarks for user {user_id}")
    mp.track(webhookData.record.id, 'Registered')
    return {"user_id": webhookData.record.id, "status": "schema_initialised"}


@app.post("/api/healthcheck")
async def test(request: Request, current_user: TokenData = Depends(get_current_user)):
    return {"status": "ok"}


@app.post("/api/save")
async def save(saveRequest: SaveRequest, background_tasks: BackgroundTasks, current_user: TokenData = Depends(get_current_user)):
    r = get_redis_connection()
    mp = get_mixpanel_client()
    user_id = convert_user_id(current_user.sub)
    r_key = f"user:{user_id}"
    if r.sismember(r_key, saveRequest.pageData.url):
        logger.info(f"{user_id} already saved {saveRequest.pageData.url}")
        return {"status": "ok"}

    data = saveRequest.model_dump()
    background_tasks.add_task(indexer, data=data, user_id=user_id, r_conn=r)
    logger.info(f"{user_id} is saving data")
    mp.track(current_user.sub, 'Saved', {
        'uri': saveRequest.pageData.url,
        'title': saveRequest.pageData.title
    })
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
    mp = get_mixpanel_client()
    mp.track(current_user.sub, 'Search', {
        'search_query': query
    })
    return {'query': query, 'results': results}

# TODO: has to be shifted to postgres on supabase
@app.get("/api/all_saved")
async def allSaved(current_user: TokenData = Depends(get_current_user)):
    logger.info(f"sending all saved to {current_user.sub}")
    user_id = convert_user_id(current_user.sub)
    source_class = settings.KNOWLEDGE_SOURCE_CLASS.format(user_id)
    try:
        client = query_weaviate_client()
        response = (
            client.query.get(source_class, ["title", "uri"])
            .with_additional(['creationTimeUnix','id'])
            .do()
        )
        results = []
        for i, source in enumerate(sorted(response['data']['Get'][source_class],
                                          key=lambda x: x['_additional']['creationTimeUnix'], reverse=True)):
            results.append({
                    "index": i,
                    "id": source['_additional']['id'],
                    "uri": source['uri'],
                    "title": source['title']
                })
        return results
    except Exception as e:
        logger.error(f"Error getting all saved for {user_id}: {e}")
        raise get_failed_exception()


@app.delete("/api/delete/{id}")
async def delete_data(id: str, current_user: TokenData = Depends(get_current_user)):
    logger.info(f"deleting data with id {id} for user {current_user.sub}")
    user_id = convert_user_id(current_user.sub)
    source_class = settings.KNOWLEDGE_SOURCE_CLASS.format(user_id)
    content_class = settings.CONTENT_CLASS.format(user_id)
    client = query_weaviate_client()
    try:
        # get all the chunks of the source object
        chunk_ids = []
        source_obj = (
            client.query.get(
                source_class,
                ["uri", f"chunk_refs {{ ... on {content_class} {{ _additional {{ id }} }} }}"])
                .with_where(
                    {
                        "path": ["id"],
                        "operator": "Equal",
                        "valueString": id
                    }
                )
                .do()
        )
        uri = source_obj["data"]["Get"][source_class][0]["uri"]

        chunk_refs = source_obj["data"]["Get"][source_class][0]["chunk_refs"]
        if chunk_refs is not None:
            for ref in chunk_refs:
                chunk_ids.append(ref["_additional"]["id"])

        # delete all the chunks
        client.batch.delete_objects(
            content_class,
            where={
                "path": ["id"],
                "operator": "ContainsAny",
                "valueTextArray": chunk_ids 
            },
            output="verbose",
            # dry_run=True
        )

        logger.info(f"Deleted {len(chunk_ids)} chunks for {user_id}")
        # delete the source object
        client.data_object.delete(class_name=source_class, uuid=id)

        # delete the uri from redis for that user
        r_key = f"user:{user_id}"
        r_conn = get_redis_connection()
        r_conn.srem(r_key, uri)

        return {"message": f"Bookmark with id:{id} deleted successfully"}

    except Exception as e:
        logger.error(f"Error deleting data with id {id} for {user_id}: {e}")
        raise get_delete_failed_exception()
    

@app.delete("/api/user/{id}")
async def delete_user(id: str, current_user: TokenData = Depends(get_current_user)):
    user_id = convert_user_id(current_user.sub)
    source_class = settings.KNOWLEDGE_SOURCE_CLASS.format(user_id)
    content_class = settings.CONTENT_CLASS.format(user_id)

    client = query_weaviate_client()
    client.schema.delete_class(source_class)
    client.schema.delete_class(content_class)

    return {"message": f"User {user_id} deleted successfully"}


def get_urls(data):
    urls = []
    if 'url' in data:
        urls.append(data['url'])
    if 'links' in data:
        for link in data['links']:
            urls.extend(get_urls(link))
    return urls


@app.post("/api/import")
async def import_bookmarks(request: Request, current_user: TokenData = Depends(get_current_user)):
    bookmarks = await request.json()
    pprint(bookmarks)
    urls = get_urls(bookmarks[0])
    pprint(urls)
    with open("bookmarks.txt", "w") as f:
        for url in urls:
            f.write(url + "\n")
    return {"status": "ok"}
