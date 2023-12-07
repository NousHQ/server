from fastapi import APIRouter

router = APIRouter()

@router.post("/webhook/subscription")
async def webhook():
    pass

# @app.post("/api/healthcheck")
# async def test(request: Request):
#     from pprint import pprint
#     import hashlib
#     import hmac

#     signature = request.headers.get('x-signature')
#     secret = 'pissing'

#     digest = hmac.new(secret.encode(), await request.body(), hashlib.sha256).hexdigest()

#     if not hmac.compare_digest(digest, signature):
#         raise Exception('Invalid signature.')
#     pprint(await request.json())
#     # pprint(await webhookData.model_dump())
#     return {"status": "ok"}