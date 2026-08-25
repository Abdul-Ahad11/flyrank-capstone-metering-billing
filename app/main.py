from fastapi import FastAPI, Depends, Header , Request, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.database import get_db
from app.dependencies import get_current_tenant
from app.models import Tenant, UsageEvent
from app.schemas import GenerateRequest, UsageResponse
from app.providers import payment_provider
from app.services import MeterService, QuotaService ,WebhookService
from app.config import settings


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


@app.get("/usage", response_model=UsageResponse)
def get_usage(tenant: Tenant = Depends(get_current_tenant), db: Session = Depends(get_db)):
    """Returns the rolled-up monthly usage and limits for the tenant."""

    # Sum API Calls
    api_calls_used = db.query(func.sum(UsageEvent.quantity)).filter(
        UsageEvent.tenant_id == tenant.id,
        UsageEvent.usage_type == "api_call"
    ).scalar() or 0

    # Sum AI Tokens (input + cached + output + reasoning)
    ai_tokens_used = db.query(func.sum(UsageEvent.quantity)).filter(
        UsageEvent.tenant_id == tenant.id,
        UsageEvent.usage_type.in_(["input_token", "cached_input_token", "output_token", "reasoning_token"])
    ).scalar() or 0

    return {
        "api_calls": {
            "used": api_calls_used,
            "limit": tenant.plan.api_call_limit,
            "cost": 0  # We will implement strict money math in Stage 11!
        },
        "ai_tokens": {
            "used": ai_tokens_used,
            "limit": tenant.plan.ai_token_limit,
            "cost": 0
        }
    }


@app.post("/webhooks/safepay")
async def safepay_webhook(request: Request, db: Session = Depends(get_db)):
    """Receives and securely processes payment webhooks."""

    # 1. Get the raw bytes (needed for crypto) and the signature header
    payload = await request.body()
    signature = request.headers.get("X-Sfp-Signature", "")

    # 2. Verify Cryptography (Rejects forgeries with ValueError)
    try:
        event = payment_provider.verify_webhook(payload, signature, settings.WEBHOOK_SECRET)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # 3. Extract Webhook Data
    event_id = event.get("event_id")
    event_type = event.get("type")
    # Safepay normally passes your internal ID in a metadata object
    tenant_id = event.get("metadata", {}).get("tenant_id")

    if not event_id or not tenant_id:
        raise HTTPException(status_code=400, detail="Malformed webhook payload")

    # 4. Process the specific event type
    if event_type == "subscription.upgraded":
        processed = WebhookService.process_upgrade_event(db, event_id, int(tenant_id))
        if not processed:
            # We return 200 OK so Safepay stops retrying, but we don't do the work again!
            return {"status": "ignored", "message": "Duplicate event"}

    return {"status": "success", "message": "Webhook processed"}