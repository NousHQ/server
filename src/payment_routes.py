from fastapi import APIRouter, Request, HTTPException
from pydantic import BaseModel
from typing import Optional, Dict
import hmac
import hashlib
from config import settings

from client import get_supabase_client


router = APIRouter()

async def verify_signature(request):
    secret = settings.LEMON_SQUEEZY_SECRET
    signature = request.headers.get('x-signature')
    body = await request.body()
    digest = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()

    if not hmac.compare_digest(digest, signature):
        raise HTTPException(status_code=400, detail='Invalid signature.')

class MetaData(BaseModel):
    test_mode: bool
    event_name: str
    webhook_id: str
    custom_data: Dict[str, Optional[str]]

class Root(BaseModel):
    meta: MetaData


@router.post("/api/subscription-created")
async def subscription_created(request: Request):
    await verify_signature(request)

    data = await request.json()
    root = Root(**data)
    # if root.meta.test_mode:
    #     return {"status": "ok"}
    
    supabase = get_supabase_client()
    user_id = root.meta.custom_data.get('user_id')
    supabase.table("user_profiles").update({"is_subscribed": True, "user_limit": 1000}).eq("id", user_id).execute()

    print(f"Subscription created for user {user_id}")
    return {"status": "ok"}


@router.post("/api/subscription-expired")
async def subscription_expired(request: Request):
    await verify_signature(request)
    data = await request.json()
    root = Root(**data)
    # if root.meta.test_mode:
    #     return {"status": "ok"}
    
    supabase = get_supabase_client()
    user_id = root.meta.custom_data.get('user_id')
    supabase.table("user_profiles").update({"is_subscribed": False, "user_limit": 250}).eq("id", user_id).execute()
    print(f"Subscription expired for user {user_id}")
    return {"status": "ok"}