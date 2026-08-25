import pytest
import uuid
from app.database import SessionLocal
from app.services import CostService, MeterService
from app.models import Tenant, Plan
from app.pricing import PRICING


def test_ai_token_pricing_rules():
    """
    PROBE 5 PREPARATION:
    Prove that AI token pricing math handles cached inputs, reasoning tokens,
    and returns exact integer totals.
    """
    db = SessionLocal()
    try:
        # 1. Setup isolated test data
        test_plan = Plan(name=f"Pricing Plan - {uuid.uuid4()}", api_call_limit=1000, ai_token_limit=100000)
        db.add(test_plan)
        db.commit()

        tenant = Tenant(name="Pricing Tester", plan_id=test_plan.id)
        db.add(tenant)
        db.commit()

        # 2. Record 100 of EACH token type
        MeterService.record_usage(db, tenant, "input_token", 100, str(uuid.uuid4()))
        MeterService.record_usage(db, tenant, "cached_input_token", 100, str(uuid.uuid4()))
        MeterService.record_usage(db, tenant, "output_token", 100, str(uuid.uuid4()))
        MeterService.record_usage(db, tenant, "reasoning_token", 100, str(uuid.uuid4()))

        # 3. Calculate expected manual cost
        expected_cost = (
                (100 * PRICING["input_token"]) +
                (100 * PRICING["cached_input_token"]) +
                (100 * PRICING["output_token"]) +
                (100 * PRICING["reasoning_token"])
        )

        # 4. Get cost from our automated service
        actual_cost = CostService.calculate_cost(db, tenant.id, "ai_token")

        # 5. Assertions verifying capstone requirements
        assert actual_cost == expected_cost, f"Math is wrong! Expected {expected_cost}, got {actual_cost}"
        assert PRICING["cached_input_token"] < PRICING["input_token"], "Rule violated: Cached input must be cheaper!"
        assert PRICING["reasoning_token"] == PRICING["output_token"], "Rule violated: Reasoning must equal output!"
        assert isinstance(actual_cost, int), "Rule violated: Money must be an integer!"

    finally:
        db.close()