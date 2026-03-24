from __future__ import annotations
from pydantic import BaseModel, Field, field_validator, model_validator
from typing import Optional
import re

#kjhgfhjretuuyt
def _validate_strong_password(v: str) -> str:
    """كلمة مرور قوية: 8+ أحرف، حرف كبير، رقم، رمز خاص"""
    errors = []
    if len(v) < 8:
        errors.append("8 أحرف على الأقل")
    if not re.search(r"[A-Z]", v):
        errors.append("حرف كبير واحد على الأقل")
    if not re.search(r"\d", v):
        errors.append("رقم واحد على الأقل")
    if not re.search(r"[^A-Za-z0-9]", v):
        errors.append("رمز خاص واحد على الأقل مثل !@#$")
    if errors:
        raise ValueError("كلمة المرور ضعيفة: " + "، ".join(errors))
    return v


class LoginRequest(BaseModel):
    username: str
    password: str

class LoginResponse(BaseModel):
    token: str
    role: str
    full_name: str
    must_change_password: bool = False

class ChangePasswordRequest(BaseModel):
    old_password: str
    new_password: str = Field(min_length=8)

    @field_validator("new_password")
    @classmethod
    def _strong(cls, v: str) -> str:
        return _validate_strong_password(v)

class CreateUserRequest(BaseModel):
    username: str
    password: str = Field(min_length=8)
    role: str
    full_name: str
    email: Optional[str] = None
    phone: Optional[str] = None
    department_code: Optional[str] = None

    @field_validator("password")
    @classmethod
    def _strong(cls, v: str) -> str:
        return _validate_strong_password(v)

class UpdateUserRequest(BaseModel):
    full_name: Optional[str] = None
    role: Optional[str] = None
    status: Optional[str] = None
    password: Optional[str] = Field(default=None, min_length=8)
    email: Optional[str] = None
    phone: Optional[str] = None
    department_code: Optional[str] = None

    @field_validator("password", mode="before")
    @classmethod
    def _strong(cls, v):
        if v is not None:
            return _validate_strong_password(str(v))
        return v

class UserOut(BaseModel):
    user_id: int
    username: str
    role: str
    full_name: str
    email: Optional[str] = None
    phone: Optional[str] = None
    status: str
    last_login: Optional[str] = None

class KBCreate(BaseModel):
    title_ar: str
    content_ar: str
    category: Optional[str] = None
    intent_code: Optional[str] = None
    external_links: Optional[str] = None
    is_active: bool = True

class KBItemOut(BaseModel):
    kb_id: int
    title_ar: str
    content_ar: str
    category: Optional[str] = None
    intent_code: Optional[str] = None
    is_active: bool

class FeedbackIn(BaseModel):
    conversation_id: Optional[int] = None
    message_id: Optional[int] = None
    is_positive: bool
    comment: Optional[str] = None

class ConversationRatingIn(BaseModel):
    conversation_id: int
    stars: int
    comment: Optional[str] = None

    @model_validator(mode="after")
    def _check_stars(self):
        if self.stars < 1 or self.stars > 5:
            raise ValueError("stars must be between 1 and 5")
        return self