from fastapi.testclient import TestClient
from app.main import app

# TestClient allows us to test our FastAPI app without starting a real web server
client = TestClient(app)

def test_missing_tenant_header():
    """If no header is provided, FastAPI should reject it with 422 Unprocessable Entity."""
    response = client.get("/me")
    assert response.status_code == 422
    assert "x-tenant-id" in response.text.lower()

def test_invalid_tenant_header():
    """If a fake tenant ID is provided, our dependency should reject it with 401."""
    response = client.get("/me", headers={"X-Tenant-ID": "9999"})
    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid X-Tenant-ID header. Tenant not found."

def test_valid_tenant_header():
    """If a valid tenant ID is provided, the request should succeed and return the correct tenant."""
    response = client.get("/me", headers={"X-Tenant-ID": "1"})
    assert response.status_code == 200
    assert response.json()["tenant_id"] == 1
    assert response.json()["tenant_name"] == "Demo Company"