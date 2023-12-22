import asyncio
import json

import sentry_sdk
from aiofiles import open as aio_open
from contextlib import asynccontextmanager
from fastapi import (BackgroundTasks, Depends, FastAPI, Request)
from fastapi.middleware.cors import CORSMiddleware
from client import (get_redis_connection, indexer_weaviate_client,
                    query_weaviate_client, get_mixpanel_client, get_supabase_client)
from config import settings
from indexer import indexer
from logger import get_logger
from schemas import  Payload, SaveRequest, TokenData, WebhookRequestSchema, DeleteSchema
from searcher import searcher
from utils import convert_user_id, get_current_user, get_weaviate_schemas, get_failed_exception, get_delete_failed_exception
from payment_routes import router as payment_router
import requests


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


@asynccontextmanager
async def lifespan(app: FastAPI):
    asyncio.create_task(writer_worker())
    yield

origins = [
    "https://app.nous.fyi",
    "https://nous-revamp.vercel.app",
    "http://localhost:3000",
]
test_origins = "^https://nous-revamp-.*\.vercel\.app"
app = FastAPI(lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_origin_regex=test_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.include_router(payment_router)

@app.post("/api/init_schema")
async def init_schema(webhookData: WebhookRequestSchema):
    user_id = webhookData.record.id
    email = webhookData.record.email

    client = indexer_weaviate_client()
    mp = get_mixpanel_client()
    knowledge_source, content = get_weaviate_schemas(convert_user_id(user_id))
    client.schema.create({"classes": [knowledge_source, content]})
    # mp.people_set(user_id, {
    #     '$email': email,
    # }, meta = {'$ignore_time' : False}
    # )

    mp.track(user_id, 'Registered', {
        '$distinct_id': user_id,
        '$email': email,
    })
    loops_payload = {
        "email": email,
        "source": "Sign Up",
        "userId": user_id,
    }
    headers = {
        "Authorization": f"Bearer {settings.LOOPS_API_KEY}",
        "Content-Type": "application/json"
    }
    response = requests.request("POST", settings.LOOPS_URL, json=loops_payload, headers=headers)
    logger.info(f"Added user {user_id}:{email} to Loops:: {response.text}")

    return {"user_id": webhookData.record.id, "status": "schema_initialised"}



# @app.post("/api/save")
# async def save(saveRequest: SaveRequest, background_tasks: BackgroundTasks, current_user: TokenData = Depends(get_current_user)):
#     mp = get_mixpanel_client()
#     user_id = convert_user_id(current_user.sub)
#     supabase = get_supabase_client()
#     data = supabase.table("all_saved").select("url").eq("user_id", current_user.sub).eq("url", saveRequest.pageData.url).execute()
#     if (len(data.data) > 0):
#         logger.info(f"{user_id} already saved {saveRequest.pageData.url}")
#         return {"status": "ok"}
#     data = saveRequest.model_dump()
#     background_tasks.add_task(indexer, data=data, user_id=user_id)
#     logger.info(f"{user_id} is saving data")
#     mp.track(current_user.sub, 'Saved', {
#         'uri': saveRequest.pageData.url,
#         'title': saveRequest.pageData.title
#     })
#     return {"status": "ok"}


@app.post("/api/save")
async def save(saveRequest: SaveRequest, background_tasks: BackgroundTasks, current_user: TokenData = Depends(get_current_user)):
    mp = get_mixpanel_client()
    user_id = convert_user_id(current_user.sub)
    supabase = get_supabase_client()
    saved_uris = supabase.table("saved_uris").select("url").eq("user_id", current_user.sub).eq("url", saveRequest.pageData.url).execute()
    if (len(saved_uris.data) > 0):
        logger.info(f"{user_id} already saved {saveRequest.pageData.url}")
        return {"status": "ok"}
    
    # user_limit = supabase.table("user_profiles").select("user_limit").eq("id", current_user.sub).execute().data[0].get("user_limit")
    # count = supabase.table("saved_uris").select("*", count='exact').eq("user_id", current_user.sub).execute().count

    # if count >= user_limit:
    #     logger.info(f"{user_id} has hit the limit. Current limit: {user_limit}")
    #     return {"status": "limit_reached"}

    if not saveRequest.pageData.content.readabilityContent.textContent:
        textContent = saveRequest.pageData.content.readabilityContent.textContent
    else:
        textContent = saveRequest.pageData.content.rawText

    raw_doc = {
        "url": saveRequest.pageData.url,
        "title": saveRequest.pageData.title,
        "content": textContent,
    }

    background_tasks.add_task(indexer, document=raw_doc, user_id=user_id)
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
        'search_query': query,
        'results': results
    })
    return {'query': query, 'results': results}


# TODO: has to been shifted on to postgres supabase.
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

        return {"message": f"Bookmark with id:{id} deleted successfully"}

    except Exception as e:
        logger.error(f"Error deleting data with id {id} for {user_id}: {e}")
        raise get_delete_failed_exception()


@app.post("/api/delete")
async def delete_uri(deleteRequest: DeleteSchema):
    user_id = convert_user_id(deleteRequest.old_record.user_id)
    uri_id = deleteRequest.old_record.id
    uri = deleteRequest.old_record.url
    logger.info(f"[!] Deleting {uri} for {user_id}")
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
                        "valueString": uri_id
                    }
                )
                .do()
        )

        chunk_refs = source_obj["data"]["Get"][source_class][0]["chunk_refs"]
        if chunk_refs is not None:
            for ref in chunk_refs:
                chunk_ids.append(ref["_additional"]["id"])

    #     # delete all the chunks
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

        logger.info(f"[!] Deleted {len(chunk_ids)} chunks for {user_id}")

    except Exception as e:
        logger.error(f"Error deleting data with id {id} for {user_id}: {e}")
        raise get_delete_failed_exception()

    logger.info(f"[!] Deleted {uri} for {user_id}")
    
    return {"message": f"Bookmark with id:{uri_id} deleted successfully"}


@app.delete("/api/user/{id}")
async def delete_user(id: str, current_user: TokenData = Depends(get_current_user)):
    user_id = convert_user_id(current_user.sub)
    source_class = settings.KNOWLEDGE_SOURCE_CLASS.format(user_id)
    content_class = settings.CONTENT_CLASS.format(user_id)

    client = query_weaviate_client()
    client.schema.delete_class(source_class)
    client.schema.delete_class(content_class)

    return {"message": f"User {user_id} deleted successfully"}

@app.post("/api/import")
async def import_bookmarks(webhookData: Payload):
    from redis import Redis
    from rq import Queue, Retry

    redis_conn = Redis(host=settings.JOBS_QUEUE, port=6379, db=0)
    q = Queue('default', connection=redis_conn, default_timeout=1200)
    job = q.enqueue('main.importer', webhookData.model_dump(), retry=Retry(max=3, interval=60))
    logger.info(f"Job {job.id} enqueued")