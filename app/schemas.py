from datetime import datetime
from decimal import Decimal
from pydantic import BaseModel, EmailStr, Field


class LoginIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)


class TokenOut(BaseModel):
    access_token: str
    refresh_token: str | None = None
    token_type: str = "bearer"
    must_change_password: bool = False


class PasswordChangeIn(BaseModel):
    current_password: str = Field(min_length=8)
    new_password: str = Field(min_length=8, max_length=128)


class MemberCreate(BaseModel):
    full_name: str = Field(min_length=2, max_length=160)
    email: EmailStr | None = None
    phone: str | None = None


class MemberUpdate(BaseModel):
    full_name: str | None = Field(default=None, min_length=2, max_length=160)
    email: EmailStr | None = None
    phone: str | None = None
    membership_status: str | None = Field(
        default=None,
        pattern="^(active|inactive|suspended)$",
    )


class ProfileSelfUpdate(BaseModel):
    """Fields a logged-in user may change on their own member profile."""
    full_name: str | None = Field(default=None, min_length=2, max_length=160)
    email: EmailStr | None = None
    phone: str | None = None


class RoleUpdate(BaseModel):
    role: str = Field(
        pattern="^(member|treasurer|executive|secretary|auditor|admin)$",
    )


class MemberAccountCreate(BaseModel):
    password: str = Field(min_length=12, max_length=128)
    role: str = Field(
        default="member",
        pattern="^(member|treasurer|executive|secretary|auditor|admin)$",
    )


class MemberAccountOut(BaseModel):
    status: str
    message: str
    member_id: str
    member_no: str
    email: str
    user_id: str
    role: str


class MemberOut(BaseModel):
    id: str
    member_no: str
    full_name: str
    email: str | None
    phone: str | None
    membership_status: str
    joined_at: datetime
    has_login_account: bool = False
    model_config = {"from_attributes": True}


class MeetingCreate(BaseModel):
    title: str
    meeting_date: datetime
    location: str | None = None


class MeetingUpdate(BaseModel):
    title: str | None = None
    meeting_date: datetime | None = None
    location: str | None = None


class AttendanceIn(BaseModel):
    member_id: str
    status: str = Field(pattern="^(present|absent|excused|late)$")


class DuesGenerationIn(BaseModel):
    year: int
    month: int = Field(ge=1, le=12)
    amount: Decimal


class TransactionIn(BaseModel):
    member_id: str
    account_type: str
    transaction_type: str
    amount: Decimal
    direction: str = Field(pattern="^(credit|debit)$")
    description: str | None = None


class DocumentUpdate(BaseModel):
    title: str | None = None
    category: str | None = None
    description: str | None = None


class MinutesCreate(BaseModel):
    content: str = Field(min_length=1)
    status: str = Field(default="draft", pattern="^(draft|submitted)$")


class AnnouncementCreate(BaseModel):
    title: str
    body: str
    status: str = Field(default="draft", pattern="^(draft|published)$")


class BroadcastIn(BaseModel):
    title: str
    body: str
    notification_type: str = "general"
    priority: str = Field(default="normal", pattern="^(low|normal|high|urgent)$")
