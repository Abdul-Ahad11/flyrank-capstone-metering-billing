import hmac
import hashlib
import json
from fastapi.testclient import TestClient
from app.main import app
from app.config import settings
from app.database import SessionLocal
from app.models import Tenant

client = TestClient(app)


def generate_valid_signature(payload_dict: dict) -> tuple[bytes, str]:
    """Helper to generate a cryptographically valid webhook just like Safepay would."""
    payload_bytes = json.dumps(payload_dict).encode("utf-8")
    signature = hmac.new(
        key=settings.WEBHOOK_SECRET.encode("utf-8"),
        msg=payload_bytes,
        digestmod=hashlib.sha256
    ).hexdigest()
    return payload_bytes, signature


def test_webhook_security_and_idempotency():
    """
    PROBE 3 & 4 PREPARATION:
    Prove that forged webhooks are rejected (400), valid webhooks upgrade the tenant,
    and duplicate webhooks are safely ignored.
    """
    db = SessionLocal()
    tenant_id = 1  # Our demo tenant

    # Verify tenant is currently on Free plan
    tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
    assert tenant.plan.name == "Free", "Tenant should start on Free plan"
    db.close()

    valid_event_payload = {
        "event_id": "evt_test_12345",
        "type": "subscription.upgraded",
        "metadata": {"tenant_id": tenant_id}
    }
    payload_bytes, valid_sig = generate_valid_signature(valid_event_payload)

    # 1. FORGERY TEST (Probe 4) -> Must return 400
    response_forged = client.post(
        "/webhooks/safepay",
        content=payload_bytes,
        headers={"X-Sfp-Signature": "totally_fake_signature_123"}
    )
    assert response_forged.status_code == 400

    # 2. VALID UPGRADE TEST (Probe 3) -> Must succeed
    response_valid = client.post(
        "/webhooks/safepay",
        content=payload_bytes,
        headers={"X-Sfp-Signature": valid_sig}
    )
    assert response_valid.status_code == 200
    assert response_valid.json()["status"] == "success"

    # Verify database actually flipped to Pro!
    db = SessionLocal()
    tenant_after = db.query(Tenant).filter(Tenant.id == tenant_id).first()
    assert tenant_after.plan.name == "Pro", "Tenant was NOT upgraded to Pro!"
    db.close()

    # 3. DUPLICATE EVENT TEST (Probe 4) -> Must be safely ignored
    response_duplicate = client.post(
        "/webhooks/safepay",
        content=payload_bytes,
        headers={"X-Sfp-Signature": valid_sig}
    )
    assert response_duplicate.status_code == 200
    assert response_duplicate.json()["status"] == "ignored", "Duplicate was not caught!"