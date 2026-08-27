from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import UsageRecord


def month_usage(db: Session) -> int:
    now = datetime.now(timezone.utc)
    start = datetime(now.year, now.month, 1, tzinfo=timezone.utc)
    return int(db.scalar(select(func.coalesce(func.sum(UsageRecord.input_tokens + UsageRecord.output_tokens), 0)).where(UsageRecord.created_at >= start)) or 0)


def record_usage(db: Session, input_tokens: int, output_tokens: int = 0) -> None:
    db.add(UsageRecord(input_tokens=input_tokens, output_tokens=output_tokens))
