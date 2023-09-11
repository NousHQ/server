from typing import Optional
from pydantic import BaseModel

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
    schema_name: str
    old_record: Optional[Record] = None
