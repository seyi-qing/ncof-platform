from datetime import datetime, timezone
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, func
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import (
    User, Member, Committee, CommitteeMember, MeetingAgendaItem, MeetingMinute,
    Resolution, ActionItem, Election, ElectionPosition, ElectionCandidate, ElectionParticipation, ElectionBallot, ElectionBallotSelection, AssociationDocument,
    Announcement, Notification,
)
from app.schemas import (
    CommitteeCreate, CommitteeMemberCreate, AgendaCreate, MinutesCreate,
    ResolutionCreate, ActionItemCreate, ActionItemUpdate, ElectionCreate,
    CandidateCreate, ElectionPositionCreate, CastVoteIn, DocumentCreate, AnnouncementCreate,
)
from app.security import require_roles, current_user
import hashlib
import secrets

router = APIRouter()
MANAGERS = ("admin", "executive", "secretary")


def now():
    return datetime.now(timezone.utc)


def ensure_member(db, member_id):
    if not db.get(Member, member_id):
        raise HTTPException(404, "Member not found")


def ensure_meeting(db, meeting_id):
    from app.models import Meeting
    if not db.get(Meeting, meeting_id):
        raise HTTPException(404, "Meeting not found")


@router.post("/committees", status_code=201)
def create_committee(payload: CommitteeCreate, db: Session = Depends(get_db), _: User = Depends(require_roles(*MANAGERS))):
    item = Committee(id=str(uuid4()), name=payload.name, description=payload.description, status="active")
    db.add(item); db.commit(); db.refresh(item); return item


@router.get("/committees")
def list_committees(db: Session = Depends(get_db), _: User = Depends(require_roles(*MANAGERS, "member"))):
    return list(db.scalars(select(Committee).order_by(Committee.name)).all())


@router.post("/committees/{committee_id}/members", status_code=201)
def add_committee_member(committee_id: str, payload: CommitteeMemberCreate, db: Session = Depends(get_db), _: User = Depends(require_roles(*MANAGERS))):
    if not db.get(Committee, committee_id): raise HTTPException(404, "Committee not found")
    ensure_member(db, payload.member_id)
    existing = db.scalar(select(CommitteeMember).where(CommitteeMember.committee_id == committee_id, CommitteeMember.member_id == payload.member_id))
    if existing: raise HTTPException(409, "Member is already on this committee")
    item = CommitteeMember(id=str(uuid4()), committee_id=committee_id, member_id=payload.member_id, position=payload.position, start_date=payload.start_date, end_date=payload.end_date)
    db.add(item); db.commit(); db.refresh(item); return item


@router.post("/meetings/{meeting_id}/agenda", status_code=201)
def create_agenda(meeting_id: str, payload: AgendaCreate, db: Session = Depends(get_db), _: User = Depends(require_roles(*MANAGERS))):
    ensure_meeting(db, meeting_id)
    item = MeetingAgendaItem(id=str(uuid4()), meeting_id=meeting_id, item_no=payload.item_no, title=payload.title, description=payload.description, presenter=payload.presenter)
    db.add(item); db.commit(); db.refresh(item); return item


@router.get("/meetings/{meeting_id}/agenda")
def list_agenda(meeting_id: str, db: Session = Depends(get_db), _: User = Depends(require_roles(*MANAGERS, "member"))):
    ensure_meeting(db, meeting_id)
    return list(db.scalars(select(MeetingAgendaItem).where(MeetingAgendaItem.meeting_id == meeting_id).order_by(MeetingAgendaItem.item_no)).all())


@router.post("/meetings/{meeting_id}/minutes", status_code=201)
def create_minutes(meeting_id: str, payload: MinutesCreate, db: Session = Depends(get_db), user: User = Depends(require_roles(*MANAGERS))):
    ensure_meeting(db, meeting_id)
    existing = db.scalar(select(MeetingMinute).where(MeetingMinute.meeting_id == meeting_id))
    if existing: raise HTTPException(409, "Minutes already exist for this meeting")
    item = MeetingMinute(id=str(uuid4()), meeting_id=meeting_id, prepared_by=user.id, content=payload.content, status="draft")
    db.add(item); db.commit(); db.refresh(item); return item


@router.post("/meetings/{meeting_id}/minutes/approve")
def approve_minutes(meeting_id: str, db: Session = Depends(get_db), user: User = Depends(require_roles("admin", "executive"))):
    item = db.scalar(select(MeetingMinute).where(MeetingMinute.meeting_id == meeting_id))
    if not item: raise HTTPException(404, "Minutes not found")
    item.status = "approved"; item.approved_by = user.id; item.approved_at = now()
    db.commit(); return item


@router.post("/resolutions", status_code=201)
def create_resolution(payload: ResolutionCreate, db: Session = Depends(get_db), user: User = Depends(require_roles(*MANAGERS))):
    if payload.meeting_id: ensure_meeting(db, payload.meeting_id)
    item = Resolution(id=str(uuid4()), meeting_id=payload.meeting_id, reference=payload.reference, title=payload.title, text=payload.text, status="proposed", proposed_by=user.id)
    db.add(item); db.commit(); db.refresh(item); return item


@router.post("/resolutions/{resolution_id}/adopt")
def adopt_resolution(resolution_id: str, db: Session = Depends(get_db), user: User = Depends(require_roles("admin", "executive"))):
    item = db.get(Resolution, resolution_id)
    if not item: raise HTTPException(404, "Resolution not found")
    if item.status == "adopted": raise HTTPException(409, "Resolution already adopted")
    item.status = "adopted"; item.adopted_by = user.id; item.adopted_at = now()
    db.commit(); return item


@router.post("/action-items", status_code=201)
def create_action(payload: ActionItemCreate, db: Session = Depends(get_db), _: User = Depends(require_roles(*MANAGERS))):
    ensure_member(db, payload.assignee_member_id)
    if payload.resolution_id and not db.get(Resolution, payload.resolution_id): raise HTTPException(404, "Resolution not found")
    item = ActionItem(id=str(uuid4()), resolution_id=payload.resolution_id, meeting_id=payload.meeting_id, title=payload.title, description=payload.description, assignee_member_id=payload.assignee_member_id, due_date=payload.due_date, status="open")
    db.add(item); db.commit(); db.refresh(item); return item


@router.patch("/action-items/{action_id}")
def update_action(action_id: str, payload: ActionItemUpdate, db: Session = Depends(get_db), _: User = Depends(require_roles(*MANAGERS))):
    item = db.get(ActionItem, action_id)
    if not item: raise HTTPException(404, "Action item not found")
    if payload.status is not None: item.status = payload.status
    if payload.notes is not None: item.notes = payload.notes
    if payload.due_date is not None: item.due_date = payload.due_date
    if item.status == "completed": item.completed_at = now()
    db.commit(); db.refresh(item); return item


@router.post("/elections", status_code=201)
def create_election(payload: ElectionCreate, db: Session = Depends(get_db), _: User = Depends(require_roles("admin", "executive"))):
    if payload.closes_at <= payload.opens_at:
        raise HTTPException(400, "Election closing time must be after opening time")
    item = Election(id=str(uuid4()), title=payload.title, description=payload.description, opens_at=payload.opens_at, closes_at=payload.closes_at, status="draft")
    db.add(item); db.commit(); db.refresh(item); return item

@router.post("/elections/{election_id}/positions", status_code=201)
def add_position(election_id: str, payload: ElectionPositionCreate, db: Session = Depends(get_db), _: User = Depends(require_roles("admin", "executive"))):
    election = db.get(Election, election_id)
    if not election: raise HTTPException(404, "Election not found")
    if election.status != "draft": raise HTTPException(409, "Positions can only be changed while the election is in draft")
    if db.scalar(select(ElectionPosition).where(ElectionPosition.election_id == election_id, ElectionPosition.name == payload.name)):
        raise HTTPException(409, "Position already exists")
    item = ElectionPosition(id=str(uuid4()), election_id=election_id, name=payload.name, description=payload.description, sort_order=payload.sort_order, max_selections=payload.max_selections)
    db.add(item); db.commit(); db.refresh(item); return item

@router.get("/elections/{election_id}")
def get_election(election_id: str, db: Session = Depends(get_db), _: User = Depends(require_roles(*MANAGERS, "member"))):
    election = db.get(Election, election_id)
    if not election: raise HTTPException(404, "Election not found")
    positions = list(db.scalars(select(ElectionPosition).where(ElectionPosition.election_id == election_id).order_by(ElectionPosition.sort_order, ElectionPosition.name)).all())
    candidates = list(db.scalars(select(ElectionCandidate).where(ElectionCandidate.election_id == election_id).order_by(ElectionCandidate.position, ElectionCandidate.created_at)).all())
    return {"election": election, "positions": positions, "candidates": candidates}

@router.post("/elections/{election_id}/candidates", status_code=201)
def add_candidate(election_id: str, payload: CandidateCreate, db: Session = Depends(get_db), _: User = Depends(require_roles("admin", "executive"))):
    election = db.get(Election, election_id)
    if not election: raise HTTPException(404, "Election not found")
    if election.status != "draft": raise HTTPException(409, "Candidates can only be changed while the election is in draft")
    ensure_member(db, payload.member_id)
    position = db.get(ElectionPosition, payload.position_id)
    if not position or position.election_id != election_id: raise HTTPException(400, "Position does not belong to this election")
    existing = db.scalar(select(ElectionCandidate).where(ElectionCandidate.election_id == election_id, ElectionCandidate.member_id == payload.member_id, ElectionCandidate.position_id == position.id))
    if existing: raise HTTPException(409, "Member is already a candidate for this position")
    item = ElectionCandidate(id=str(uuid4()), election_id=election_id, member_id=payload.member_id, position=position.name, position_id=position.id)
    db.add(item); db.commit(); db.refresh(item); return item

@router.post("/elections/{election_id}/open")
def open_election(election_id: str, db: Session = Depends(get_db), _: User = Depends(require_roles("admin", "executive"))):
    item = db.get(Election, election_id)
    if not item: raise HTTPException(404, "Election not found")
    now_ = now()
    if item.status != "draft": raise HTTPException(409, "Election is not in draft state")
    if item.opens_at >= item.closes_at: raise HTTPException(400, "Invalid election window")
    if not db.scalar(select(ElectionPosition.id).where(ElectionPosition.election_id == election_id)):
        raise HTTPException(400, "Election must have at least one position")
    if not db.scalar(select(ElectionCandidate.id).where(ElectionCandidate.election_id == election_id)):
        raise HTTPException(400, "Election must have at least one candidate")
    item.status = "open"; db.commit(); return item

@router.post("/elections/{election_id}/close")
def close_election(election_id: str, db: Session = Depends(get_db), _: User = Depends(require_roles("admin", "executive"))):
    item = db.get(Election, election_id)
    if not item: raise HTTPException(404, "Election not found")
    if item.status != "open": raise HTTPException(409, "Election is not open")
    item.status = "closed"; db.commit(); return item

@router.get("/elections/{election_id}/ballot")
def get_ballot(election_id: str, db: Session = Depends(get_db), _: User = Depends(current_user)):
    election = db.get(Election, election_id)
    if not election: raise HTTPException(404, "Election not found")
    if election.status != "open": raise HTTPException(409, "Election is not open")
    member = db.scalar(select(Member).where(Member.user_id == _.id, Member.membership_status == "active"))
    if not member: raise HTTPException(403, "Only active members may vote")
    already = db.scalar(select(ElectionParticipation.id).where(ElectionParticipation.election_id == election_id, ElectionParticipation.member_id == member.id))
    if already: raise HTTPException(409, "You have already voted in this election")
    positions = list(db.scalars(select(ElectionPosition).where(ElectionPosition.election_id == election_id).order_by(ElectionPosition.sort_order, ElectionPosition.name)).all())
    candidates = list(db.scalars(select(ElectionCandidate).where(ElectionCandidate.election_id == election_id).order_by(ElectionCandidate.position, ElectionCandidate.created_at)).all())
    return {"election_id": election_id, "positions": positions, "candidates": candidates, "voting_method": "single_choice_per_position"}

@router.post("/elections/{election_id}/vote")
def cast_vote(election_id: str, payload: CastVoteIn, db: Session = Depends(get_db), user: User = Depends(current_user)):
    election = db.get(Election, election_id)
    if not election: raise HTTPException(404, "Election not found")
    now_ = now()
    if election.status != "open" or now_ < election.opens_at or now_ >= election.closes_at:
        raise HTTPException(409, "Voting is not currently open")
    member = db.scalar(select(Member).where(Member.user_id == user.id, Member.membership_status == "active"))
    if not member: raise HTTPException(403, "Only active members may vote")

    participation = db.scalar(select(ElectionParticipation).where(ElectionParticipation.election_id == election_id, ElectionParticipation.member_id == member.id).with_for_update())
    if participation: raise HTTPException(409, "You have already voted in this election")

    positions = {p.id: p for p in db.scalars(select(ElectionPosition).where(ElectionPosition.election_id == election_id)).all()}
    if len(payload.selections) != len(set(x.position_id for x in payload.selections)):
        raise HTTPException(400, "Each position may be selected only once")
    if set(x.position_id for x in payload.selections) != set(positions):
        raise HTTPException(400, "A selection is required for every position")

    candidate_ids = [x.candidate_id for x in payload.selections]
    candidates = list(db.scalars(select(ElectionCandidate).where(ElectionCandidate.id.in_(candidate_ids), ElectionCandidate.election_id == election_id)).all())
    by_id = {c.id: c for c in candidates}
    if len(by_id) != len(candidate_ids): raise HTTPException(400, "Invalid candidate for this election")
    for selection in payload.selections:
        c = by_id[selection.candidate_id]
        if c.position_id != selection.position_id:
            raise HTTPException(400, "Candidate does not belong to the selected position")

    participation = ElectionParticipation(id=str(uuid4()), election_id=election_id, member_id=member.id, voted_at=now_)
    ballot_id = str(uuid4())
    # Receipt is intentionally not derived from member identity; it cannot be used to recover voter identity.
    receipt_hash = hashlib.sha256(secrets.token_bytes(32)).hexdigest()
    ballot = ElectionBallot(id=ballot_id, election_id=election_id, receipt_hash=receipt_hash, cast_at=now_)
    db.add(participation); db.add(ballot); db.flush()
    db.add_all([ElectionBallotSelection(id=str(uuid4()), ballot_id=ballot_id, position_id=x.position_id, candidate_id=x.candidate_id, created_at=now_) for x in payload.selections])
    try:
        db.commit()
    except Exception:
        db.rollback()
        raise HTTPException(409, "Vote could not be recorded; please try again")
    return {"status": "accepted", "receipt": receipt_hash}

@router.get("/elections/{election_id}/results")
def election_results(election_id: str, db: Session = Depends(get_db), _: User = Depends(require_roles(*MANAGERS, "member"))):
    election = db.get(Election, election_id)
    if not election: raise HTTPException(404, "Election not found")
    if election.status != "closed": raise HTTPException(409, "Results are available only after the election is closed")
    positions = list(db.scalars(select(ElectionPosition).where(ElectionPosition.election_id == election_id).order_by(ElectionPosition.sort_order, ElectionPosition.name)).all())
    result = []
    total_ballots = db.scalar(select(func.count(ElectionBallot.id)).where(ElectionBallot.election_id == election_id)) or 0
    for position in positions:
        rows = db.execute(select(ElectionCandidate.id, ElectionCandidate.member_id, ElectionCandidate.position, func.count(ElectionBallotSelection.id).label("votes")).join(ElectionBallotSelection, ElectionBallotSelection.candidate_id == ElectionCandidate.id, isouter=True).where(ElectionCandidate.election_id == election_id, ElectionCandidate.position_id == position.id).group_by(ElectionCandidate.id, ElectionCandidate.member_id, ElectionCandidate.position).order_by(func.count(ElectionBallotSelection.id).desc(), ElectionCandidate.id)).all()
        result.append({"position_id": position.id, "position": position.name, "candidates": [{"candidate_id": r.id, "member_id": r.member_id, "votes": int(r.votes)} for r in rows]})
    return {"election_id": election_id, "status": election.status, "total_ballots": int(total_ballots), "results": result}

@router.get("/elections/{election_id}/participation")
def election_participation(election_id: str, db: Session = Depends(get_db), _: User = Depends(require_roles("admin", "executive"))):
    election = db.get(Election, election_id)
    if not election: raise HTTPException(404, "Election not found")
    active_members = db.scalar(select(func.count(Member.id)).where(Member.membership_status == "active")) or 0
    voted = db.scalar(select(func.count(ElectionParticipation.id)).where(ElectionParticipation.election_id == election_id)) or 0
    return {"election_id": election_id, "eligible_active_members": int(active_members), "voted_members": int(voted), "participation_rate": (float(voted) / float(active_members) if active_members else 0.0)}

@router.post("/documents", status_code=201)
def create_document(payload: DocumentCreate, db: Session = Depends(get_db), user: User = Depends(require_roles(*MANAGERS))):
    item = AssociationDocument(id=str(uuid4()), title=payload.title, document_type=payload.document_type, storage_url=payload.storage_url, description=payload.description, uploaded_by=user.id)
    db.add(item); db.commit(); db.refresh(item); return item


@router.get("/documents")
def list_documents(db: Session = Depends(get_db), _: User = Depends(require_roles(*MANAGERS, "member"))):
    return list(db.scalars(select(AssociationDocument).order_by(AssociationDocument.created_at.desc())).all())


@router.post("/announcements", status_code=201)
def create_announcement(payload: AnnouncementCreate, db: Session = Depends(get_db), user: User = Depends(require_roles(*MANAGERS))):
    item = Announcement(id=str(uuid4()), title=payload.title, body=payload.body, audience=payload.audience, published=payload.published, published_by=user.id, published_at=now() if payload.published else None)
    db.add(item)
    if payload.published:
        members = list(db.scalars(select(Member).where(Member.membership_status == "active", Member.user_id.is_not(None))).all())
        db.flush()
        db.add_all([Notification(id=str(uuid4()), member_id=m.id, user_id=m.user_id, title=payload.title, body=payload.body, notification_type="governance", priority="normal") for m in members])
    db.commit(); db.refresh(item); return item


@router.get("/announcements")
def list_announcements(db: Session = Depends(get_db), _: User = Depends(require_roles(*MANAGERS, "member"))):
    return list(db.scalars(select(Announcement).where(Announcement.published.is_(True)).order_by(Announcement.published_at.desc())).all())
