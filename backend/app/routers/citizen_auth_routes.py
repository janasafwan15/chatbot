# backend/app/routers/citizen_auth_routes.py
"""
نظام التحقق من هوية المواطن (Mock Data)
=========================================
المرحلة الأولى: داتا وهمية للتجربة
المرحلة الثانية: ربط بقاعدة بيانات حقيقية (HEPCO)

Endpoints:
  POST /citizen/request-otp    — المواطن يُدخل رقم هويته
  POST /citizen/verify-otp     — المواطن يُدخل رمز OTP
  GET  /citizen/account        — عرض بيانات الحساب (يتطلب citizen_token)
  GET  /citizen/invoices       — قائمة الفواتير
  GET  /citizen/balance        — الرصيد المتبقي
  POST /citizen/logout         — إلغاء الجلسة
"""
from __future__ import annotations

import logging
import random
import secrets
import time
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/citizen", tags=["citizen-auth"])


# ═══════════════════════════════════════════════════════════
#  الداتا الوهمية — Mock Database
#  عند الربط الحقيقي: استبدل _MOCK_CITIZENS بـ DB query
# ═══════════════════════════════════════════════════════════

_MOCK_CITIZENS: dict[str, dict] = {
    "9871234567": {
        "national_id":  "9871234567",
        "full_name":    "محمد أحمد أبو علي",
        "phone":        "0599123456",   # آخر 4 أرقام تظهر للمستخدم: ****3456
        "address":      "الخليل — حي الشيخ — شارع الملك فيصل",
        "meter_number": "HE-2024-00123",
        "account_number": "ACC-0012345",
        "subscription_type": "سكني",
        "subscription_status": "نشط",
        "connection_date": "2018-03-15",
        "balance": -85.50,             # سالب = عليه ديون، موجب = رصيد دائن
        "invoices": [
            {
                "invoice_id":   "INV-2025-0341",
                "period":       "مارس 2025",
                "issue_date":   "2025-03-01",
                "due_date":     "2025-03-31",
                "amount":       142.75,
                "status":       "مسدد",
                "consumption_kwh": 380,
            },
            {
                "invoice_id":   "INV-2025-0228",
                "period":       "فبراير 2025",
                "issue_date":   "2025-02-01",
                "due_date":     "2025-02-28",
                "amount":       128.00,
                "status":       "مسدد",
                "consumption_kwh": 340,
            },
            {
                "invoice_id":   "INV-2025-0131",
                "period":       "يناير 2025",
                "issue_date":   "2025-01-01",
                "due_date":     "2025-01-31",
                "amount":       156.50,
                "status":       "غير مسدد",
                "consumption_kwh": 415,
            },
            {
                "invoice_id":   "INV-2024-1231",
                "period":       "ديسمبر 2024",
                "issue_date":   "2024-12-01",
                "due_date":     "2024-12-31",
                "amount":        85.50,
                "status":       "غير مسدد",
                "consumption_kwh": 227,
            },
        ],
    },
    "9876543210": {
        "national_id":  "9876543210",
        "full_name":    "فاطمة خليل الجعبري",
        "phone":        "0598765432",
        "address":      "الخليل — الحي الجنوبي — عمارة النور",
        "meter_number": "HE-2022-00789",
        "account_number": "ACC-0078901",
        "subscription_type": "تجاري",
        "subscription_status": "نشط",
        "connection_date": "2022-07-20",
        "balance": 320.00,
        "invoices": [
            {
                "invoice_id":   "INV-2025-0342",
                "period":       "مارس 2025",
                "issue_date":   "2025-03-01",
                "due_date":     "2025-03-31",
                "amount":       480.00,
                "status":       "مسدد",
                "consumption_kwh": 1200,
            },
            {
                "invoice_id":   "INV-2025-0229",
                "period":       "فبراير 2025",
                "issue_date":   "2025-02-01",
                "due_date":     "2025-02-28",
                "amount":       390.50,
                "status":       "مسدد",
                "consumption_kwh": 980,
            },
        ],
    },
    "1234567890": {
        "national_id":  "1234567890",
        "full_name":    "يوسف سالم العمر",
        "phone":        "0592345678",
        "address":      "الخليل — وسط البلد — بناية التجار",
        "meter_number": "HE-2019-00456",
        "account_number": "ACC-0045678",
        "subscription_type": "سكني",
        "subscription_status": "موقوف مؤقتاً",
        "connection_date": "2019-11-05",
        "balance": -340.25,
        "invoices": [
            {
                "invoice_id":   "INV-2025-0343",
                "period":       "مارس 2025",
                "issue_date":   "2025-03-01",
                "due_date":     "2025-03-31",
                "amount":       210.00,
                "status":       "غير مسدد",
                "consumption_kwh": 560,
            },
            {
                "invoice_id":   "INV-2025-0230",
                "period":       "فبراير 2025",
                "issue_date":   "2025-02-01",
                "due_date":     "2025-02-28",
                "amount":       130.25,
                "status":       "غير مسدد",
                "consumption_kwh": 347,
            },
        ],
    },
}


# ═══════════════════════════════════════════════════════════
#  OTP Store — في الإنتاج استبدله بـ Redis
# ═══════════════════════════════════════════════════════════

_OTP_STORE: dict[str, dict] = {}
_CITIZEN_SESSIONS: dict[str, dict] = {}

OTP_TTL_SECONDS  = 300   # 5 دقائق
OTP_MAX_ATTEMPTS = 3     # محاولات قبل الحجب
SESSION_TTL_SECONDS = 3600  # ساعة واحدة


def _cleanup_expired() -> None:
    """تنظيف OTPs وجلسات المواطنين المنتهية."""
    now = time.time()
    expired_otp = [k for k, v in _OTP_STORE.items() if v["expires_at"] < now]
    for k in expired_otp:
        del _OTP_STORE[k]

    expired_sess = [k for k, v in _CITIZEN_SESSIONS.items() if v["expires_at"] < now]
    for k in expired_sess:
        del _CITIZEN_SESSIONS[k]


def _mask_phone(phone: str) -> str:
    """يخفي وسط رقم الهاتف: 0599123456 → 0599***456"""
    if len(phone) < 7:
        return "****"
    return phone[:4] + "***" + phone[-3:]


def _get_citizen_from_token(token: str) -> dict:
    """يستخرج بيانات المواطن من التوكن، أو يرفع 401."""
    _cleanup_expired()
    session = _CITIZEN_SESSIONS.get(token)
    if not session:
        raise HTTPException(status_code=401, detail="انتهت الجلسة أو التوكن غير صالح. أعد التحقق.")
    return session["citizen"]


# ═══════════════════════════════════════════════════════════
#  Schemas
# ═══════════════════════════════════════════════════════════

class RequestOtpIn(BaseModel):
    national_id: str = Field(..., min_length=9, max_length=12, description="رقم الهوية")

class VerifyOtpIn(BaseModel):
    national_id: str = Field(..., min_length=9, max_length=12)
    otp_code:    str = Field(..., min_length=4, max_length=8)

class CitizenTokenIn(BaseModel):
    citizen_token: str


# ═══════════════════════════════════════════════════════════
#  Endpoints
# ═══════════════════════════════════════════════════════════

@router.post("/request-otp")
def request_otp(body: RequestOtpIn, request: Request):
    """
    الخطوة 1: المواطن يُدخل رقم هويته.
    النظام يبحث عنه ويرسل OTP إلى هاتفه.
    """
    _cleanup_expired()

    national_id = body.national_id.strip()

    # ── البحث في الداتا (Mock أو حقيقية مستقبلاً) ──────────
    citizen = _MOCK_CITIZENS.get(national_id)
    if not citizen:
        # لأسباب أمنية: لا نُخبر إن كان الرقم موجوداً أم لا
        raise HTTPException(
            status_code=404,
            detail="رقم الهوية غير مسجل في النظام. تأكد من الرقم أو تواصل معنا على 02-2282882."
        )

    # ── توليد OTP ───────────────────────────────────────────
    otp = str(random.randint(100000, 999999))  # 6 أرقام
    _OTP_STORE[national_id] = {
        "otp":        otp,
        "expires_at": time.time() + OTP_TTL_SECONDS,
        "attempts":   0,
        "phone":      citizen["phone"],
    }

    # ── في الإنتاج: أرسل OTP عبر SMS gateway ────────────────
    # sms_gateway.send(citizen["phone"], f"رمز التحقق الخاص بك: {otp}")
    # هنا نُرجعه مباشرة للتجربة فقط ⚠️
    logger.info(f"[OTP-MOCK] national_id={national_id[-4:]}**** → OTP={otp}")

    masked = _mask_phone(citizen["phone"])

    return {
        "success":      True,
        "message":      f"تم إرسال رمز التحقق إلى الهاتف {masked}",
        "masked_phone": masked,
        "expires_in":   OTP_TTL_SECONDS,
        # ⚠️ للتجربة فقط — أزل هذا السطر في الإنتاج
        "dev_otp":      otp,
    }


@router.post("/verify-otp")
def verify_otp(body: VerifyOtpIn):
    """
    الخطوة 2: المواطن يُدخل الرمز.
    عند النجاح: يُعطى citizen_token صالح لساعة.
    """
    _cleanup_expired()

    national_id = body.national_id.strip()
    entry = _OTP_STORE.get(national_id)

    if not entry:
        raise HTTPException(
            status_code=400,
            detail="انتهت صلاحية الرمز أو لم يُطلب بعد. اضغط 'إرسال رمز جديد'."
        )

    # فحص عدد المحاولات
    if entry["attempts"] >= OTP_MAX_ATTEMPTS:
        del _OTP_STORE[national_id]
        raise HTTPException(
            status_code=429,
            detail="تم تجاوز الحد المسموح من المحاولات. اطلب رمزاً جديداً."
        )

    # انتهاء الصلاحية
    if time.time() > entry["expires_at"]:
        del _OTP_STORE[national_id]
        raise HTTPException(status_code=400, detail="انتهت صلاحية الرمز. اطلب رمزاً جديداً.")

    entry["attempts"] += 1

    if body.otp_code.strip() != entry["otp"]:
        remaining = OTP_MAX_ATTEMPTS - entry["attempts"]
        raise HTTPException(
            status_code=400,
            detail=f"الرمز غير صحيح. المحاولات المتبقية: {remaining}"
        )

    # ── نجاح التحقق ─────────────────────────────────────────
    del _OTP_STORE[national_id]

    citizen = _MOCK_CITIZENS[national_id]
    token   = secrets.token_urlsafe(32)

    _CITIZEN_SESSIONS[token] = {
        "citizen":    citizen,
        "expires_at": time.time() + SESSION_TTL_SECONDS,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "national_id": national_id,
    }

    logger.info(f"[CITIZEN-AUTH] Successful login for national_id={national_id[-4:]}****")

    return {
        "success":       True,
        "citizen_token": token,
        "expires_in":    SESSION_TTL_SECONDS,
        "full_name":     citizen["full_name"],
        "message":       f"مرحباً {citizen['full_name']}"
    }


@router.post("/account")
def get_account(body: CitizenTokenIn):
    """عرض بيانات الحساب الكاملة بعد التحقق."""
    citizen = _get_citizen_from_token(body.citizen_token)

    # إخفاء رقم الهاتف الكامل
    masked_phone = _mask_phone(citizen["phone"])

    # حساب إجمالي المبالغ غير المسددة
    unpaid_total = sum(
        inv["amount"] for inv in citizen["invoices"] if inv["status"] == "غير مسدد"
    )

    return {
        "success": True,
        "account": {
            "full_name":          citizen["full_name"],
            "national_id":        citizen["national_id"][:3] + "****" + citizen["national_id"][-3:],
            "phone":              masked_phone,
            "address":            citizen["address"],
            "meter_number":       citizen["meter_number"],
            "account_number":     citizen["account_number"],
            "subscription_type":  citizen["subscription_type"],
            "subscription_status": citizen["subscription_status"],
            "connection_date":    citizen["connection_date"],
            "balance":            citizen["balance"],
            "unpaid_total":       unpaid_total,
            "last_invoice":       citizen["invoices"][0] if citizen["invoices"] else None,
        }
    }


@router.post("/invoices")
def get_invoices(body: CitizenTokenIn):
    """قائمة الفواتير للمواطن."""
    citizen = _get_citizen_from_token(body.citizen_token)

    invoices = citizen["invoices"]
    unpaid   = [inv for inv in invoices if inv["status"] == "غير مسدد"]
    paid     = [inv for inv in invoices if inv["status"] == "مسدد"]

    return {
        "success":       True,
        "account_number": citizen["account_number"],
        "meter_number":   citizen["meter_number"],
        "invoices":       invoices,
        "summary": {
            "total_invoices":  len(invoices),
            "unpaid_count":    len(unpaid),
            "unpaid_amount":   sum(i["amount"] for i in unpaid),
            "paid_count":      len(paid),
        }
    }


@router.post("/balance")
def get_balance(body: CitizenTokenIn):
    """الرصيد المتبقي ومعلومات العداد."""
    citizen = _get_citizen_from_token(body.citizen_token)

    balance = citizen["balance"]
    status_msg = (
        "لديك رصيد دائن ✅" if balance >= 0
        else f"يوجد مبلغ مستحق عليك: {abs(balance):.2f} شيكل ⚠️"
    )

    last_invoice = citizen["invoices"][0] if citizen["invoices"] else None

    return {
        "success":        True,
        "meter_number":   citizen["meter_number"],
        "account_number": citizen["account_number"],
        "balance":        balance,
        "status_message": status_msg,
        "subscription_status": citizen["subscription_status"],
        "last_invoice":   last_invoice,
    }


@router.post("/logout")
def citizen_logout(body: CitizenTokenIn):
    """إلغاء جلسة المواطن."""
    if body.citizen_token in _CITIZEN_SESSIONS:
        del _CITIZEN_SESSIONS[body.citizen_token]
    return {"success": True, "message": "تم تسجيل الخروج"}