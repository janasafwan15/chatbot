from __future__ import annotations
import html
import re
from typing import Optional

from pydantic import BaseModel, Field, field_validator, model_validator


# ── كلمة مرور قوية ─────────────────────────────────────────────
def _validate_strong_password(v: str) -> str:
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


# ── تنظيف النص من HTML/XSS ─────────────────────────────────────
_DANGEROUS_TAGS = re.compile(
    r"<\s*(script|iframe|object|embed|form|input|link|meta|style|svg|onload|onerror)[^>]*>",
    re.IGNORECASE,
)

def sanitize_text(v: str, max_len: int = 5000) -> str:
    """
    يحذف الـ HTML tags الخطرة ويهرب الأحرف الخاصة.
    يبقي النص العربي والأرقام والتنسيقات البسيطة سليمة.
    """
    if not v:
        return v
    v = v.strip()[:max_len]
    # إزالة التاغات الخطرة أولاً
    v = _DANGEROUS_TAGS.sub("", v)
    # هروب أحرف HTML الأساسية
    v = html.escape(v, quote=True)
    return v


# ── Schemas ────────────────────────────────────────────────────

class LoginRequest(BaseModel):
    username: str = Field(max_length=64)
    password: str = Field(max_length=256)


class LoginResponse(BaseModel):
    token: str
    refresh_token: str
    role: str
    full_name: str
    must_change_password: bool = False


class RefreshRequest(BaseModel):
    refresh_token: str


class ChangePasswordRequest(BaseModel):
    old_password: str
    new_password: str = Field(min_length=8)

    @field_validator("new_password")
    @classmethod
    def _strong(cls, v: str) -> str:
        return _validate_strong_password(v)


class CreateUserRequest(BaseModel):
    username: str = Field(min_length=3, max_length=64)
    password: str = Field(min_length=8)
    role: str
    full_name: str = Field(min_length=2, max_length=128)
    email: Optional[str] = Field(default=None, max_length=256)
    phone: Optional[str] = Field(default=None, max_length=32)
    department_code: Optional[str] = None

    @field_validator("password")
    @classmethod
    def _strong(cls, v: str) -> str:
        return _validate_strong_password(v)


class UpdateUserRequest(BaseModel):
    full_name: Optional[str] = Field(default=None, max_length=128)
    role: Optional[str] = None
    status: Optional[str] = None
    password: Optional[str] = Field(default=None, min_length=8)
    email: Optional[str] = Field(default=None, max_length=256)
    phone: Optional[str] = Field(default=None, max_length=32)
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


class KBCreate(BaseModel):
    title_ar: str = Field(min_length=3, max_length=500)
    content_ar: str = Field(min_length=5, max_length=10000)
    category: Optional[str] = Field(default=None, max_length=128)
    intent_code: Optional[str] = Field(default=None, max_length=64)
    external_links: Optional[str] = Field(default=None, max_length=2000)
    is_active: bool = True

    @field_validator("title_ar")
    @classmethod
    def _clean_title(cls, v: str) -> str:
        return sanitize_text(v, max_len=500)

    @field_validator("content_ar")
    @classmethod
    def _clean_content(cls, v: str) -> str:
        return sanitize_text(v, max_len=10000)

    @field_validator("external_links")
    @classmethod
    def _clean_links(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        return sanitize_text(v, max_len=2000)


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
    comment: Optional[str] = Field(default=None, max_length=2000)


class ConversationRatingIn(BaseModel):
    conversation_id: int
    stars: int
    comment: Optional[str] = Field(default=None, max_length=2000)

    @model_validator(mode="after")
    def _check_stars(self):
        if self.stars < 1 or self.stars > 5:
            raise ValueError("stars must be between 1 and 5")
        return self