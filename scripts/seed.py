import sys
import os

# Add the project root to the Python path so we can import 'app'
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import SessionLocal
from app.models import Plan, Tenant, Subscription


def seed():
    db = SessionLocal()
    try:
        # 1. Create Plans per the official Capstone PDF limits
        free_plan = db.query(Plan).filter(Plan.name == "Free").first()
        if not free_plan:
            free_plan = Plan(name="Free", api_call_limit=1000, ai_token_limit=100000)
            db.add(free_plan)

        pro_plan = db.query(Plan).filter(Plan.name == "Pro").first()
        if not pro_plan:
            pro_plan = Plan(name="Pro", api_call_limit=5000, ai_token_limit=500000)
            db.add(pro_plan)

        db.commit()
        db.refresh(free_plan)

        # 2. Create a Demo Tenant
        demo_tenant = db.query(Tenant).filter(Tenant.name == "Demo Company").first()
        if not demo_tenant:
            demo_tenant = Tenant(name="Demo Company", plan_id=free_plan.id)
            db.add(demo_tenant)
            db.commit()
            db.refresh(demo_tenant)

            # 3. Create an active subscription for the tenant
            sub = Subscription(tenant_id=demo_tenant.id, status="active")
            db.add(sub)
            db.commit()

        print(f"\n✅ SEED SUCCESSFUL! Demo Tenant ID: {demo_tenant.id} (Plan: {free_plan.name})\n")
    finally:
        db.close()


if __name__ == "__main__":
    seed()