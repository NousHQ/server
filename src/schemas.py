from datetime import datetime
from typing import List, Optional, Dict
from pydantic import BaseModel
'''
Schema for NEW USER webhook data
'''
class TokenData(BaseModel):
    aud: str
    exp: int
    iat: int
    iss: str
    sub: str
    email: Optional[str] = None
    role: Optional[str] = None

class Record(BaseModel):
    id: str
    aud: str
    role: str
    email: str
    phone: Optional[str] = None
    created_at: str
    deleted_at: Optional[str] = None
    invited_at: Optional[str] = None
    updated_at: str
    instance_id: str
    is_sso_user: bool
    banned_until: Optional[str] = None
    confirmed_at: Optional[str] = None
    email_change: str
    phone_change: str
    is_super_admin: Optional[bool] = None
    recovery_token: str
    last_sign_in_at: Optional[str] = None
    recovery_sent_at: Optional[str] = None
    raw_app_meta_data: dict
    confirmation_token: str
    email_confirmed_at: Optional[str] = None
    encrypted_password: str
    phone_change_token: str
    phone_confirmed_at: Optional[str] = None
    raw_user_meta_data: dict
    confirmation_sent_at: Optional[str] = None
    email_change_sent_at: Optional[str] = None
    phone_change_sent_at: Optional[str] = None
    email_change_token_new: str
    reauthentication_token: str
    reauthentication_sent_at: Optional[str] = None
    email_change_token_current: str
    email_change_confirm_status: int


class WebhookRequestSchema(BaseModel):
    type: str
    table: str
    record: Record
    schema: str
    record: Optional[Record] = None

'''
Schema for SAVE request
'''

class Readability(BaseModel):
    title: Optional[str] = None
    byline: Optional[str] = None
    dir: Optional[str] = None
    lang: Optional[str] = None
    content: Optional[str] = None
    textContent: Optional[str] = None
    length: Optional[int] = None
    excerpt: Optional[str] = None
    siteName: Optional[str] = None

class Content(BaseModel):
    rawText: Optional[str] = None
    readable: Optional[bool] = None
    readabilityContent: Optional[Readability] = None

class PageData(BaseModel):
    favIconUrl: Optional[str] = None
    url: str
    title: str
    content: Content

class SaveRequest(BaseModel):
    pageData: PageData


'''
Schema for IMPORT webhook data
'''

# a bookmark link
class Link(BaseModel):
    id: str
    name: Optional[str] = None
    open: Optional[bool] = None
    links: Optional[List['Link']] = None
    url: Optional[str] = None
    checked: Optional[bool] = None

Link.model_rebuild()

class Bookmark(BaseModel):
    id: str
    name: Optional[str] = None
    open: Optional[bool] = None
    links: Optional[List[Link]] = None
    checked: Optional[bool] = None

class Record(BaseModel):
    id: str
    user_id: str
    bookmarks: Optional[List[Bookmark]] = None
    created_at: str

class Payload(BaseModel):
    type: str
    table: str
    record: Record
    schema: str
    old_record: Optional[Record] = None


'''
Schema for DELETE webhook data
'''
class OldRecord(BaseModel):
    id: str
    url: str
    tags: Optional[str]
    title: str
    img_url: str
    user_id: str
    metadata: Optional[str]
    created_at: datetime

class DeleteSchema(BaseModel):
    type: str
    table: str
    record: Optional[str]
    schema: str
    old_record: OldRecord

# ''' 
# Schema for lemon squeezy webhook data
# '''
# class CustomData(BaseModel):
#     user_id: str

# class Meta(BaseModel):
#     test_mode: bool
#     event_name: str
#     custom_data: CustomData
#     webhook_id: str

# class URLs(BaseModel):
#     update_payment_method: HttpUrl
#     customer_portal: HttpUrl

# class Links(BaseModel):
#     related: HttpUrl
#     self: HttpUrl

# # Generic Type for Relationship
# T = TypeVar('T')

# # Generic Relationship model
# class Relationship(GenericModel, Generic[T]):
#     links: Links

# class FirstSubscriptionItem(BaseModel):
#     id: int
#     subscription_id: int
#     price_id: int
#     quantity: int
#     is_usage_based: bool
#     created_at: str
#     updated_at: str

# class Attributes(BaseModel):
#     store_id: int
#     customer_id: int
#     order_id: int
#     order_item_id: int
#     product_id: int
#     variant_id: int
#     product_name: str
#     variant_name: str
#     user_name: str
#     user_email: str
#     status: str
#     status_formatted: str
#     card_brand: str
#     card_last_four: str
#     pause: Optional[bool] = None
#     cancelled: bool
#     trial_ends_at: Optional[datetime] = None
#     billing_anchor: int
#     first_subscription_item: FirstSubscriptionItem
#     urls: URLs
#     renews_at: Optional[datetime] = None
#     ends_at: Optional[datetime] = None
#     created_at: datetime
#     updated_at: datetime
#     test_mode: bool

# class Data(BaseModel):
#     type: str
#     id: str
#     attributes: Attributes
#     relationships: Dict[str, Relationship]
#     links: Links

# class LemonSqueezy(BaseModel):
#     meta: Meta
#     data: Data