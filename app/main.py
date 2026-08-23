from fastapi import FastAPI, Depends
from app.dependencies import get_current_tenant
from app.models import Tenant

app = FastAPI(
    title="FlyRank Billing Engine",
    description="Usage Metering & Billing Engine Capstone",
    version="1.0.0"
)

@app.get("/health")
def health_check():
    """Health check endpoint to verify the API is running."""
    return {"status": "ok", "message": "Billing engine is running"}

@app.get("/me")
def get_my_tenant_info(tenant: Tenant = Depends(get_current_tenant)):
    """Protected endpoint to verify tenant isolation."""
    return {"tenant_id": tenant.id, "tenant_name": tenant.name}