from __future__ import annotations
from fastapi import HTTPException

# الـ roles المتاحة:
#   admin      → كل الصلاحيات
#   supervisor → تعديل KB + كل التقارير، بدون إدارة المستخدمين
#   employee   → تعديل KB فقط، بدون تقارير

def require_roles(user: dict, allowed: list[str]) -> None:
    if user.get("role") not in allowed:
        raise HTTPException(status_code=403, detail="Forbidden")