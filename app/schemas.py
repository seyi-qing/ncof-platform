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


class ChangePasswordIn(BaseModel):
    current_password: str = Field(min_length=8, max_length=128)
    new_password: str = Field(min_length=12, max_length=128)


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


class MemberAccountCreate(BaseModel):
    password: str = Field(min_length=12, max_length=128)
    # Admin picks role at login-create time. Default remains member.
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


class AttendanceIn(BaseModel):
    member_id: str
    status: str = Field(
        default="present",
        pattern="^(present|absent|excused|late)$",
    )


class DuesGenerationIn(BaseModel):
    year: int = Field(ge=2020, le=2100)
    month: int = Field(ge=1, le=12)
    amount: Decimal = Field(gt=0, max_digits=18, decimal_places=2)


class TransactionIn(BaseModel):
    member_id: str
    account_type: str = Field(
        pattern="^(dues|savings|welfare|loan)$"
    )
    transaction_type: str
    amount: Decimal = Field(gt=0, max_digits=18, decimal_places=2)
    direction: str = Field(pattern="^(credit|debit)$")
    description: str | None = None
    reference: str | None = None


class WithdrawalCreate(BaseModel):
    member_id: str
    amount: Decimal = Field(gt=0, max_digits=18, decimal_places=2)
    reason: str | None = None


class LoanApplicationCreate(BaseModel):
    member_id: str
    amount: Decimal = Field(gt=0, max_digits=18, decimal_places=2)
    tenure_months: int = Field(ge=1, le=120)
    purpose: str | None = None


class DecisionIn(BaseModel):
    decision: str = Field(pattern="^(approved|rejected)$")
    note: str | None = None


class LoanRepaymentIn(BaseModel):
    amount: Decimal = Field(gt=0, max_digits=18, decimal_places=2)
    note: str | None = None


class WelfareClaimCreate(BaseModel):
    member_id: str
    amount: Decimal = Field(gt=0, max_digits=18, decimal_places=2)
    category: str | None = None
    reason: str | None = None


class AgendaItemIn(BaseModel):
    title: str
    description: str | None = None
    sort_order: int = 0


class MinutesIn(BaseModel):
    content: str


class ResolutionIn(BaseModel):
    meeting_id: str
    title: str
    body: str


class CommitteeCreate(BaseModel):
    name: str
    description: str | None = None


class CommitteeMemberIn(BaseModel):
    member_id: str
    role: str | None = None


class AnnouncementCreate(BaseModel):
    title: str
    body: str
    audience: str = "all"


class DocumentCreate(BaseModel):
    title: str
    url: str
    category: str | None = None


class ElectionCreate(BaseModel):
    title: str
    description: str | None = None


class ElectionPositionIn(BaseModel):
    title: str
    seats: int = 1


class ElectionCandidateIn(BaseModel):
    position_id: str
    member_id: str | None = None
    display_name: str


class VoteIn(BaseModel):
    position_id: str
    candidate_id: str


class ActionItemCreate(BaseModel):
    meeting_id: str | None = None
    title: str
    assignee_member_id: str | None = None
    due_date: datetime | None = None


class ActionItemUpdate(BaseModel):
    status: str = Field(pattern="^(open|in_progress|done|cancelled)$")
    note: str | None = None


class NotificationBroadcastIn(BaseModel):
    title: str
    body: str
    audience: str = "all"


class NotificationPrefsIn(BaseModel):
    email_enabled: bool | None = None
    in_app_enabled: bool | None = None
