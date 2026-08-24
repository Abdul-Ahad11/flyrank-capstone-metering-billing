from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from app.models import UsageEvent, Tenant


class MeterService:
    @staticmethod
    def record_usage(db: Session, tenant: Tenant, usage_type: str, quantity: int, idempotency_key: str) -> UsageEvent:
        """
        Records a billable usage event.
        Guarantees idempotency: if the key exists for this tenant, returns the original event safely.
        """
        new_event = UsageEvent(
            tenant_id=tenant.id,
            usage_type=usage_type,
            quantity=quantity,
            idempotency_key=idempotency_key
        )
        db.add(new_event)

        try:
            # Attempt to save to the database
            db.commit()
            db.refresh(new_event)
            return new_event

        except IntegrityError:
            # An IntegrityError means our UniqueConstraint caught a duplicate key.
            # 1. We MUST rollback the session so the database connection remains usable.
            db.rollback()

            # 2. Fetch and return the original event that already existed.
            existing_event = db.query(UsageEvent).filter(
                UsageEvent.tenant_id == tenant.id,
                UsageEvent.idempotency_key == idempotency_key
            ).first()

            return existing_event