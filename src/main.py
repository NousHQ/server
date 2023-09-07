from functools import lru_cache
from pprint import pprint
from typing import Optional

from fastapi import Depends, FastAPI, HTTPException, Request, status, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer
from fastapi.concurrency import run_in_threadpool
from jose import JWTError, jwt
from pydantic import BaseModel
from aiofiles import open as aio_open
import asyncio
import json

from config import settings
from indexer import indexer
from searcher import searcher
from logger import get_logger


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

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

SECRET_KEY = settings.SUPABASE_SECRET
ALGORITHM = "HS256"

class TokenData(BaseModel):
    aud: str
    exp: int
    iat: int
    iss: str
    sub: str
    email: Optional[str] = None
    role: Optional[str] = None


def get_current_user(token: str = Depends(oauth2_scheme)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_403_FORBIDDEN, detail="Could not validate credentials"
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM], audience="authenticated")
        user_data = TokenData(**payload)
    except JWTError:
        raise credentials_exception
    return user_data


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


@app.post("/api/healthcheck")
async def test(request: Request, current_user: TokenData = Depends(get_current_user)):
    return {"status": "ok"}


@app.post("/api/save")
async def save(request: Request, background_tasks: BackgroundTasks, current_user: TokenData = Depends(get_current_user)):
    user_id = current_user.sub.replace("-", "_")
    data = await request.json()
    logger.info(f"{current_user.sub} is saving data")
    background_tasks.add_task(indexer, data=data, user_id=user_id)
    return {"status": "ok"}


@app.get("/api/search")
async def query(query: str, current_user: TokenData = Depends(get_current_user)):
    # response = searcher(query)
    logger.info(f"{current_user.sub} queried: {query}")
    user_id = current_user.sub.replace("-", "_")
    raw_response, results = searcher(query=query, user_id=user_id)

    entry_dict = {
        "user_id": user_id,
        "query": query,
        "response": raw_response
    }

    await write_to_log(entry_dict)

    return {'query': query, 'results': results}