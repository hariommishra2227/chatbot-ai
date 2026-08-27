from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.main_state import limiter
from app.models import Conversation, Lead
from app.schemas import LeadCreate, LeadResponse

router = APIRouter(prefix="/api/leads", tags=["leads"])


@router.post("", response_model=LeadResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit(lambda: f"{get_settings().rate_limit_per_minute}/minute")
def create_lead(request: Request, payload: LeadCreate, db: Session = Depends(get_db)) -> Lead:
    if payload.conversation_id and not db.get(Conversation, payload.conversation_id):
        raise HTTPException(status_code=404, detail="Conversation not found")
    lead = Lead(**payload.model_dump())
    db.add(lead)
    db.commit()
    db.refresh(lead)
    return lead

