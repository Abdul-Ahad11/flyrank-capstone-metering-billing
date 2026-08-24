import uuid
from app.database import SessionLocal
from app.services import MeterService
from app.models import Tenant


def test_duplicate_idempotency_key_prevents_double_count():
    """
    PROBE 1 PREPARATION:
    Prove that calling record_usage twice with the same idempotency key
    only creates ONE usage event and returns the original result.
    """
    db = SessionLocal()
    try:
        # 1. Get our demo tenant from the seed data
        tenant = db.query(Tenant).filter(Tenant.id == 1).first()
        assert tenant is not None, "Demo tenant not found. Did you run the seed script?"

        # 2. Generate a totally unique idempotency key for this test run
        idem_key = f"test-key-{uuid.uuid4()}"

        # 3. First attempt -> Should successfully create the event
        event1 = MeterService.record_usage(
            db=db, tenant=tenant, usage_type="api_call", quantity=1, idempotency_key=idem_key
        )
        assert event1.id is not None
        assert event1.quantity == 1

        # 4. Second attempt with SAME key -> Should NOT double-count.
        # Even though we asked to record 100 quantity, it should return the original event of 1.
        event2 = MeterService.record_usage(
            db=db, tenant=tenant, usage_type="api_call", quantity=100, idempotency_key=idem_key
        )

        # 5. Assertions that prove exactly-once guarantees
        assert event1.id == event2.id, "The service created a duplicate row instead of returning the original!"
        assert event2.quantity == 1, "The service incorrectly updated the quantity on a duplicate request!"

    finally:
        db.close()