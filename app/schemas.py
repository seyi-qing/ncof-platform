from datetime import datetime, timedelta, timezone
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


class WithdrawalCreate(BaseModel):
    member_id: str
    amount: Decimal
    account_type: str = "savings"
    reason: str | None = None


class DecisionIn(BaseModel):
    decision: str = Field(pattern="^(approved|rejected)$")
    note: str | None = None


class LoanApplicationCreate(BaseModel):
    member_id: str
    amount: Decimal
    purpose: str | None = None
    tenure_months: int | None = None


class LoanRepaymentIn(BaseModel):
    amount: Decimal
    note: str | None = None


class WelfareClaimCreate(BaseModel):
    member_id: str
    amount: Decimal
    claim_type: str | None = None
    description: str | None = None


class WebhookIn(BaseModel):
    event: str
    payload: dict | None = None


class CommitteeCreate(BaseModel):
    name: str
    description: str | None = None


class CommitteeMemberCreate(BaseModel):
    member_id: str
    role: str | None = None


class AgendaCreate(BaseModel):
    item_no: int
    title: str
    description: str | None = None
    presenter: str | None = None


class MinutesCreate(BaseModel):
    content: str = Field(min_length=1)
    status: str = Field(default="draft", pattern="^(draft|submitted)$")


class ResolutionCreate(BaseModel):
    title: str
    body: str
    meeting_id: str | None = None


class ActionItemCreate(BaseModel):
    title: str
    assignee_id: str | None = None
    due_date: datetime | None = None


class ActionItemUpdate(BaseModel):
    title: str | None = None
    status: str | None = None
    due_date: datetime | None = None


class ElectionCreate(BaseModel):
    title: str
    description: str | None = None
    opens_at: datetime | None = None
    closes_at: datetime | None = None


class ElectionPositionCreate(BaseModel):
    title: str
    seats: int = 1


class CandidateCreate(BaseModel):
    member_id: str
    manifesto: str | None = None


class VoteSelection(BaseModel):
    position_id: str
    candidate_id: str


class CastVoteIn(BaseModel):
    selections: list[VoteSelection]


class DocumentUpdate(BaseModel):
    title: str | None = None
    category: str | None = None
    description: str | None = None


class DocumentCreate(BaseModel):
    title: str
    category: str | None = None
    description: str | None = None
    file_url: str | None = None


class AnnouncementCreate(BaseModel):
    title: str
    body: str
    status: str = Field(default="draft", pattern="^(draft|published)$")


class NotificationPreferenceUpdate(BaseModel):
    dues_enabled: bool | None = None
    meetings_enabled: bool | None = None
    elections_enabled: bool | None = None
    general_enabled: bool | None = None


class RefreshIn(BaseModel):
    refresh_token: str


class BroadcastNotificationIn(BaseModel):
    title: str
    body: str
    notification_type: str = "general"
    priority: str = Field(default="normal", pattern="^(low|normal|high|urgent)$")
