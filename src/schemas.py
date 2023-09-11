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
    phone: str
    created_at: str
    deleted_at: str
    invited_at: str
    updated_at: str
    instance_id: str
    is_sso_user: bool
    banned_until: str
    confirmed_at: str
    email_change: str
    phone_change: str
    is_super_admin: bool
    recovery_token: str
    last_sign_in_at: str
    recovery_sent_at: str
    raw_app_meta_data: dict
    confirmation_token: str
    email_confirmed_at: str
    encrypted_password: str
    phone_change_token: str
    phone_confirmed_at: str
    raw_user_meta_data: dict
    confirmation_sent_at: str
    email_change_sent_at: str
    phone_change_sent_at: str
    email_change_token_new: str
    reauthentication_token: str
    reauthentication_sent_at: str
    email_change_token_current: str
    email_change_confirm_status: int


class WebhookRequestSchema(BaseModel):
    type: str
    table: str
    record: Record
    schema: str
    old_record: Record    
