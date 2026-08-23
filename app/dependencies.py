from fastapi import Header, HTTPException, Depends
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import Tenant


def get_current_tenant(
        x_tenant_id: int = Header(..., description="The ID of the tenant making the request"),
        db: Session = Depends(get_db)
) -> Tenant:
    """
    This enforces Tenant Isolation at the HTTP boundary.
    If a request doesn't have a valid X-Tenant-ID header, it is rejected immediately.
    """
    tenant = db.query(Tenant).filter(Tenant.id == x_tenant_id).first()
    if not tenant:
        raise HTTPException(status_code=401, detail="Invalid X-Tenant-ID header. Tenant not found.")

    return tenant