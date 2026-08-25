from fastapi import HTTPException
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from sqlalchemy import func
from app.models import UsageEvent, Tenant
from app.pricing import PRICING


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
            db.commit()
            db.refresh(new_event)
            return new_event

        except IntegrityError:
            db.rollback()
            existing_event = db.query(UsageEvent).filter(
                UsageEvent.tenant_id == tenant.id,
                UsageEvent.idempotency_key == idempotency_key
            ).first()
            return existing_event


class QuotaService:
    @staticmethod
    def check_quota(db: Session, tenant: Tenant, usage_type: str, requested_quantity: int):
        """
        Checks if requested usage exceeds the tenant's plan limit.
        Raises 402 or 429 if the limit is exceeded.
        """
        # 1. Sum up all current usage of this type for this tenant
        current_usage = db.query(func.sum(UsageEvent.quantity)).filter(
            UsageEvent.tenant_id == tenant.id,
            UsageEvent.usage_type == usage_type
        ).scalar() or 0

        # 2. Determine the correct limit based on the type
        limit = 0
        if usage_type == "api_call":
            limit = tenant.plan.api_call_limit
        elif usage_type == "ai_token":
            limit = tenant.plan.ai_token_limit
        else:
            raise HTTPException(status_code=400, detail=f"Unknown usage type: {usage_type}")

        # 3. Check the boundary!
        if current_usage + requested_quantity > limit:
            remaining = limit - current_usage

            # FIX: Use 'in' so it matches both "Free" and our dynamic "Test Free - <uuid>"
            if "Free" in tenant.plan.name:
                raise HTTPException(
                    status_code=402,
                    detail=f"Payment Required: Quota exceeded. You have {remaining} {usage_type}s remaining, but requested {requested_quantity}. Please upgrade to Pro."
                )
            # Use 429 for general rate/usage limits on Pro plans
            else:
                raise HTTPException(
                    status_code=429,
                    detail=f"Too Many Requests: Quota exceeded. You have {remaining} {usage_type}s remaining."
                )

        return True


class CostService:
    @staticmethod
    def calculate_cost(db: Session, tenant_id: int, usage_category: str) -> int:
        """
        Calculates the exact cost in integer micro-units for a specific category.
        """
        if usage_category == "api_call":
            usage = db.query(func.sum(UsageEvent.quantity)).filter(
                UsageEvent.tenant_id == tenant_id,
                UsageEvent.usage_type == "api_call"
            ).scalar() or 0
            return usage * PRICING["api_call"]

        elif usage_category == "ai_token":
            # Query all token types grouped by their specific type so we can price them differently
            results = db.query(UsageEvent.usage_type, func.sum(UsageEvent.quantity)).filter(
                UsageEvent.tenant_id == tenant_id,
                UsageEvent.usage_type.in_(["input_token", "cached_input_token", "output_token", "reasoning_token"])
            ).group_by(UsageEvent.usage_type).all()

            total_cost = 0
            for usage_type, quantity in results:
                total_cost += quantity * PRICING[usage_type]

            return total_cost

        return 0