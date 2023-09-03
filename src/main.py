from functools import lru_cache
from pprint import pprint
from typing import Optional

from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from pydantic import BaseModel
import weaviate

from config import settings
from indexer import indexer
from searcher import searcher


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

app = FastAPI()

origins = [
    "https://nous-frontend.vercel.app",
    "http://localhost",
    "http://localhost:5173",
    "http://localhost:3000"
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


@app.post("/api/healthcheck")
async def test(request: Request, current_user: TokenData = Depends(get_current_user)):
    return {"status": "ok"}


from fastapi import BackgroundTasks

@app.post("/api/save")
async def save(request: Request, background_tasks: BackgroundTasks, current_user: TokenData = Depends(get_current_user)):
    user_id = current_user.sub.replace("-", "_")
    data = await request.json()
    pprint(user_id)

    def save_data():
        if (indexer(client=get_weaviate_client(), data=data, user_id=user_id)):
            print("Data saved successfully")
        else:
            print("Failed to save data")

    background_tasks.add_task(save_data)

    return {"status": "ok"}


@app.get("/api/search")
async def query(query: str, current_user: TokenData = Depends(get_current_user)):
    # response = searcher(query)
    user_id = current_user.sub.replace("-", "_")
    results = searcher(client=get_weaviate_client(), query=query, user_id=user_id)
    return {'query': query, 'results': results}
