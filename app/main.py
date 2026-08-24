from fastapi import FastAPI, Depends, Header
from sqlalchemy.orm import Session
from app.database import get_db
from app.dependencies import get_current_tenant
from app.models import Tenant
from app.schemas import GenerateRequest
from app.services import MeterService, QuotaService

app = FastAPI(
    title="FlyRank Billing Engine",
    description="Usage Metering & Billing Engine Capstone",
    version="1.0.0"
)


@app.get("/health")
def health_check():
    return {"status": "ok", "message": "Billing engine is running"}


@app.get("/me")
def get_my_tenant_info(tenant: Tenant = Depends(get_current_tenant)):
    return {"tenant_id": tenant.id, "tenant_name": tenant.name, "plan": tenant.plan.name}


@app.post("/generate")
def generate_content(
        request: GenerateRequest,
        idempotency_key: str = Header(..., description="Unique key to prevent double billing"),
        tenant: Tenant = Depends(get_current_tenant),
        db: Session = Depends(get_db)
):
    """Dummy billable endpoint simulating an AI model call."""

    # 1. Calculate total AI tokens requested (for quota purposes)
    total_tokens = request.input_tokens + request.cached_input_tokens + request.output_tokens + request.reasoning_tokens

    # 2. Check Quotas BEFORE doing any work
    QuotaService.check_quota(db, tenant, "api_call", 1)
    if total_tokens > 0:
        QuotaService.check_quota(db, tenant, "ai_token", total_tokens)

    # 3. Record Usage (Appending suffixes to the idempotency key to keep them unique in the DB)
    MeterService.record_usage(db, tenant, "api_call", 1, f"{idempotency_key}-api")

    if request.input_tokens > 0:
        MeterService.record_usage(db, tenant, "input_token", request.input_tokens, f"{idempotency_key}-in")
    if request.cached_input_tokens > 0:
        MeterService.record_usage(db, tenant, "cached_input_token", request.cached_input_tokens,
                                  f"{idempotency_key}-cache")
    if request.output_tokens > 0:
        MeterService.record_usage(db, tenant, "output_token", request.output_tokens, f"{idempotency_key}-out")
    if request.reasoning_tokens > 0:
        MeterService.record_usage(db, tenant, "reasoning_token", request.reasoning_tokens, f"{idempotency_key}-reason")

    # 4. Return success (We will add the money calculation later in Stage 11/12)
    return {
        "status": "success",
        "message": "AI content generated successfully.",
        "usage_recorded": {
            "api_calls": 1,
            "total_ai_tokens": total_tokens
        }
    }