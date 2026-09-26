from fastapi import APIRouter

from app.api.v1.auth import router as auth_router
from app.api.v1.members import router as members_router
from app.api.v1.finance import router as finance_router
from app.api.v1.meetings import router as meetings_router
from app.api.v1.admin import router as admin_router
from app.api.v1.operations import router as operations_router
from app.api.v1.controls import router as controls_router
from app.api.v1.governance import router as governance_router
from app.api.v1.governance_extra import router as governance_extra_router
from app.api.v1.member_experience import router as member_experience_router

api_router = APIRouter()
api_router.include_router(auth_router, prefix="/auth", tags=["auth"])
api_router.include_router(members_router, prefix="/members", tags=["members"])
api_router.include_router(finance_router, prefix="/finance", tags=["finance"])
api_router.include_router(meetings_router, prefix="/meetings", tags=["meetings"])
api_router.include_router(admin_router, prefix="/admin", tags=["admin"])
api_router.include_router(operations_router, prefix="/operations", tags=["operations"])
api_router.include_router(controls_router, prefix="/controls", tags=["controls"])
api_router.include_router(governance_router, prefix="/governance", tags=["governance"])
api_router.include_router(governance_extra_router, prefix="/governance", tags=["governance"])
api_router.include_router(member_experience_router, prefix="/member-portal", tags=["member-portal"])
