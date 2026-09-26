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

class MemberCreate(BaseModel):
    full_name: str = Field(min_length=2, max_length=160)
    email: EmailStr | None = None
    phone: str | None = None

class MemberAccountCreate(BaseModel):
    password: str = Field(min_length=12, max_length=128)

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
    status: str = Field(default="present", pattern="^(present|absent|excused|late)$")

class DuesGenerationIn(BaseModel):
    year: int = Field(ge=2020, le=2100)
    month: int = Field(ge=1, le=12)
    amount: Decimal = Field(gt=0, max_digits=18, decimal_places=2)

class TransactionIn(BaseModel):
    member_id: str
    account_type: str = Field(pattern="^(dues|savings|welfare|loan)$")
    transaction_type: str
    amount: Decimal = Field(gt=0, max_digits=18, decimal_places=2)
    direction: str = Field(default="credit", pattern="^(credit|debit)$")
    description: str | None = None

class WithdrawalCreate(BaseModel):
    member_id: str
    amount: Decimal = Field(gt=0, max_digits=18, decimal_places=2)
    reason: str | None = Field(default=None, max_length=1000)

class DecisionIn(BaseModel):
    decision: str = Field(pattern="^(approved|rejected)$")
    note: str | None = Field(default=None, max_length=1000)

class LoanApplicationCreate(BaseModel):
    member_id: str
    amount: Decimal = Field(gt=0, max_digits=18, decimal_places=2)
    term_months: int = Field(ge=1, le=120)
    purpose: str = Field(min_length=5, max_length=2000)

class LoanRepaymentIn(BaseModel):
    amount: Decimal = Field(gt=0, max_digits=18, decimal_places=2)
    note: str | None = Field(default=None, max_length=1000)

class WelfareClaimCreate(BaseModel):
    member_id: str
    amount: Decimal = Field(gt=0, max_digits=18, decimal_places=2)
    category: str = Field(min_length=2, max_length=80)
    reason: str = Field(min_length=5, max_length=2000)

class WebhookIn(BaseModel):
    event_id: str = Field(min_length=3, max_length=160)
    provider: str = Field(min_length=2, max_length=50)
    payload_json: str = Field(min_length=2)

class CommitteeCreate(BaseModel):
    name: str = Field(min_length=2, max_length=160)
    description: str | None = Field(default=None, max_length=2000)
class CommitteeMemberCreate(BaseModel):
    member_id: str
    position: str = Field(default="member", max_length=80)
    start_date: datetime | None = None
    end_date: datetime | None = None
class AgendaCreate(BaseModel):
    item_no: int = Field(ge=1)
    title: str = Field(min_length=2, max_length=200)
    description: str | None = None
    presenter: str | None = None
class MinutesCreate(BaseModel):
    content: str = Field(min_length=10)
class ResolutionCreate(BaseModel):
    meeting_id: str | None = None
    reference: str = Field(min_length=2, max_length=80)
    title: str = Field(min_length=2, max_length=200)
    text: str = Field(min_length=5)
class ActionItemCreate(BaseModel):
    resolution_id: str | None = None
    meeting_id: str | None = None
    title: str = Field(min_length=2, max_length=200)
    description: str | None = None
    assignee_member_id: str
    due_date: datetime | None = None
class ActionItemUpdate(BaseModel):
    status: str | None = Field(default=None, pattern="^(open|in_progress|completed|cancelled)$")
    notes: str | None = None
    due_date: datetime | None = None
class ElectionCreate(BaseModel):
    title: str = Field(min_length=2, max_length=200)
    description: str | None = None
    opens_at: datetime
    closes_at: datetime
class ElectionPositionCreate(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    description: str | None = Field(default=None, max_length=1000)
    sort_order: int = Field(default=0, ge=0, le=10000)
    max_selections: int = Field(default=1, ge=1, le=1)

class CandidateCreate(BaseModel):
    member_id: str
    position_id: str

class VoteSelection(BaseModel):
    position_id: str
    candidate_id: str

class CastVoteIn(BaseModel):
    selections: list[VoteSelection] = Field(min_length=1, max_length=100)
class DocumentCreate(BaseModel):
    title: str = Field(min_length=2, max_length=200)
    document_type: str = Field(min_length=2, max_length=80)
    storage_url: str = Field(min_length=5, max_length=1000)
    description: str | None = None
class AnnouncementCreate(BaseModel):
    title: str = Field(min_length=2, max_length=200)
    body: str = Field(min_length=2)
    audience: str = Field(default="all_members", max_length=50)
    published: bool = False


class NotificationPreferenceUpdate(BaseModel):
    in_app_enabled: bool | None = None
    email_enabled: bool | None = None
    dues_enabled: bool | None = None
    savings_enabled: bool | None = None
    loans_enabled: bool | None = None
    welfare_enabled: bool | None = None
    governance_enabled: bool | None = None

class RefreshIn(BaseModel):
    refresh_token: str


class BroadcastNotificationIn(BaseModel):
    title: str = Field(min_length=2, max_length=200)
    body: str = Field(min_length=2, max_length=5000)
    notification_type: str = Field(default="general", min_length=2, max_length=50)
    priority: str = Field(default="normal", pattern="^(low|normal|high|urgent)$")
