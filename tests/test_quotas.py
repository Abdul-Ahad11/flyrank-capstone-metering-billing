import pytest
import uuid
from fastapi import HTTPException
from app.database import SessionLocal
from app.services import QuotaService, MeterService
from app.models import Tenant, Plan


def test_quota_boundaries():
    """
    PROBE 2 PREPARATION:
    Drive a tenant to its exact quota. Test the boundary, and verify
    the correct status code and clear message are returned.
    """
    db = SessionLocal()
    try:
        # 1. Create an isolated Test Plan with a very small limit (10 API calls)
        # FIX: We add a UUID to the plan name so it never clashes with previous test runs
        unique_plan_name = f"Test Free - {uuid.uuid4()}"
        test_plan = Plan(name=unique_plan_name, api_call_limit=10, ai_token_limit=10)
        db.add(test_plan)
        db.commit()

        # 2. Create an isolated Test Tenant
        test_tenant = Tenant(name="Quota Boundary Tester", plan_id=test_plan.id)
        db.add(test_tenant)
        db.commit()

        # 3. UNDER LIMIT: Request 9 out of 10. Should pass perfectly.
        QuotaService.check_quota(db, test_tenant, "api_call", 9)
        MeterService.record_usage(db, test_tenant, "api_call", 9, str(uuid.uuid4()))

        # 4. EXACTLY AT LIMIT: Request 1 more. Reaches 10/10. Should pass perfectly.
        QuotaService.check_quota(db, test_tenant, "api_call", 1)
        MeterService.record_usage(db, test_tenant, "api_call", 1, str(uuid.uuid4()))

        # 5. OVER LIMIT: Request 1 more (11/10). MUST fail with HTTPException.
        with pytest.raises(HTTPException) as exc_info:
            QuotaService.check_quota(db, test_tenant, "api_call", 1)

        # 6. Verify the capstone requirements: Honest code (402) and clear message
        assert exc_info.value.status_code == 402
        assert "Payment Required" in exc_info.value.detail
        assert "upgrade" in exc_info.value.detail.lower()

    finally:
        db.close()