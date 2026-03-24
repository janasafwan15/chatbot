# routers/auth_routes.py
# هذا الملف stub فقط — جميع Auth endpoints في app/main.py
# لا تُدرج هذا الـ router في app

from fastapi import APIRouter

router = APIRouter(prefix="/auth", tags=["auth"])

# POST /auth/login        → main.py
# POST /auth/logout       → main.py
# POST /auth/change-password → main.py