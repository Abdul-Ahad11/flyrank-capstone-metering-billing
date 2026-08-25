# FlyRank Capstone: Usage Metering and Billing Engine

A robust, multi-tenant usage metering and billing backend built with **FastAPI, PostgreSQL, and Docker**. The engine is designed to handle API calls and AI token usage while enforcing tenant isolation, exactly-once idempotent metering, quota limits, accurate money calculations, and secure payment webhooks.

---

## Architectural Decisions and Core Features

This project was designed to satisfy strict enterprise billing requirements and Capstone acceptance probes.

### 1. Idempotent Metering — Exactly-Once Guarantee

* **Mechanism:** A PostgreSQL `UniqueConstraint` on `(tenant_id, idempotency_key)` in the `UsageEvent` table prevents duplicate usage records.
* **Resilience:** `MeterService` handles `IntegrityError` exceptions, rolls back safely, and returns the existing usage event when the same idempotency key is submitted again.
* **Result:** Network retries or duplicate requests cannot cause the same usage to be billed twice.

### 2. Multi-Tenant Isolation

* **Mechanism:** Tenant identification is enforced at the HTTP boundary using the FastAPI `get_current_tenant` dependency.
* **Security:** Every tenant-specific request requires an `X-Tenant-ID` header.
* Missing or invalid tenant information is rejected before the request reaches the core business logic.
* Usage, quotas, and billing calculations are always associated with the authenticated tenant.

### 3. Quota Engine and HTTP Status Codes

The `QuotaService` strictly enforces plan limits.

* **Free-tier limit reached:** Returns `402 Payment Required`, indicating that an upgrade is required.
* **Paid-tier hard limit reached:** Returns `429 Too Many Requests`.
* Quota checks are performed **before billable work is recorded**.

### 4. Money Math and AI Token Pricing

All billing calculations are designed to avoid floating-point precision errors.

* **No floating-point money calculations:** Prices are represented as integer micro-units.
* **Regular input tokens:** Use the standard input-token price.
* **Cached input tokens:** Are billed at a lower rate than regular input tokens.
* **Output tokens:** Use the configured output-token price.
* **Reasoning tokens:** Are billed at exactly the same rate as output tokens.
* Pricing rules are centralized in the pricing configuration and verified through automated tests.

### 5. Payment Webhook Security and Deduplication

The payment layer uses a provider abstraction so the core billing logic is not tightly coupled to one payment provider.

* **Provider:** Safepay Sandbox is used for the current implementation because Stripe does not officially support account creation in Pakistan under the project's compliance constraints.
* **Abstraction:** A generic `PaymentProvider` interface allows provider-specific implementations such as `SafepayProvider` without changing the core billing logic.
* **Cryptographic verification:** Webhook signatures are verified using HMAC SHA-256 and `hmac.compare_digest`.
* **Replay protection:** The `ProcessedWebhook` table prevents the same webhook event from being processed more than once.
* **Retry safety:** Provider retries are handled idempotently.

---

## Tech Stack

* **Framework:** FastAPI
* **Language:** Python
* **Database:** PostgreSQL
* **Database Runtime:** Docker / Docker Compose
* **ORM:** SQLAlchemy 2.0
* **Migrations:** Alembic
* **Testing:** Pytest and HTTPX
* **Configuration:** Pydantic Settings

---

## Project Structure

```text
.
├── app/
│   ├── main.py
│   ├── database.py
│   ├── models.py
│   ├── schemas.py
│   ├── config.py
│   ├── pricing.py
│   ├── dependencies.py
│   ├── services.py
│   └── payment_provider.py
│
├── scripts/
│   └── seed.py
│
├── tests/
│   ├── test_tenant.py
│   ├── test_metering.py
│   ├── test_quotas.py
│   ├── test_cost.py
│   └── test_webhooks.py
│
├── alembic/
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
└── README.md
```

---

## Local Setup and Installation

### 1. Clone the Repository

Clone the repository and move into the project directory.

Create a `.env` file in the project root:

```env
POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres
POSTGRES_DB=billing_db
WEBHOOK_SECRET=whsec_test_secret_for_local_dev
```

> **Security:** Never commit the real `.env` file or production webhook secrets to Git.

---

### 2. Start PostgreSQL with Docker

```bash
docker compose up -d
```

This starts the PostgreSQL database in the background.

---

### 3. Create and Activate a Virtual Environment

```bash
python -m venv .venv
source .venv/bin/activate
```

On Windows:

```bash
.venv\Scripts\activate
```

Install the project dependencies:

```bash
pip install -r requirements.txt
```

---

### 4. Run Database Migrations

Apply the SQLAlchemy models and database schema using Alembic:

```bash
alembic upgrade head
```

---

### 5. Seed Demo Data

Populate the database with:

* Free Plan
* Pro Plan
* Demo Tenant

Run:

```bash
python scripts/seed.py
```

The demo tenant is created with ID `1`.

---

### 6. Start the API Server

```bash
uvicorn app.main:app --reload
```

The API will be available at:

```text
http://127.0.0.1:8000
```

FastAPI's interactive documentation is available at:

```text
http://127.0.0.1:8000/docs
```

---

# API Endpoints

## 1. `GET /health`

Checks whether the billing engine is running.

### Response

```json
{
  "status": "ok",
  "message": "Billing engine is running"
}
```

---

## 2. `GET /me`

Returns information about the current tenant.

### Required Header

```text
X-Tenant-ID: 1
```

### Example Response

```json
{
  "tenant_id": 1,
  "tenant_name": "Demo Tenant",
  "plan": "Free"
}
```

---

## 3. `POST /generate`

A dummy billable endpoint that simulates an AI model request.

The endpoint:

1. Identifies the tenant.
2. Calculates total AI token usage.
3. Checks API-call and token quotas.
4. Records usage idempotently.
5. Calculates usage cost.
6. Returns the recorded usage information.

### Required Headers

```text
X-Tenant-ID: 1
Idempotency-Key: unique-request-key
```

### Example Request

```json
{
  "input_tokens": 100,
  "cached_input_tokens": 0,
  "output_tokens": 50,
  "reasoning_tokens": 0
}
```

### Example Response

```json
{
  "status": "success",
  "message": "AI content generated successfully.",
  "usage_recorded": {
    "api_calls": 1,
    "total_ai_tokens": 150
  }
}
```

---

## 4. `GET /usage`

Provides the tenant's usage dashboard.

It returns:

* Monthly API usage
* AI token usage
* Plan limits
* Remaining quota
* Calculated costs

### Required Header

```text
X-Tenant-ID: 1
```

---

## 5. `POST /webhooks/safepay`

Receives payment-provider webhook events.

The endpoint:

1. Receives the raw webhook payload.
2. Reads the provider signature.
3. Verifies the signature using the configured webhook secret.
4. Rejects forged or invalid requests.
5. Checks whether the webhook event was already processed.
6. Processes valid payment/subscription events.
7. Updates the tenant's billing state.
8. Records the webhook as processed.

### Required Header

```text
X-Sfp-Signature: <signature>
```

Duplicate webhook events are safely ignored to prevent duplicate subscription updates.

---

# Billing Flow

The overall billing architecture follows this flow:

```text
Client
  │
  │ X-Tenant-ID
  │ Idempotency-Key
  ▼
FastAPI
  │
  ▼
Tenant Identification
  │
  ▼
QuotaService
  │
  │ "Is this tenant allowed?"
  ▼
MeterService
  │
  │ "What did the tenant use?"
  ▼
UsageEvent
  │
  ▼
CostService
  │
  │ "How much does it cost?"
  ▼
Billing / Usage Dashboard
```

Payment processing is handled separately:

```text
Payment Provider
      │
      │ Webhook
      ▼
/webhooks/safepay
      │
      ▼
PaymentProvider
      │
      ▼
Signature Verification
      │
      ▼
ProcessedWebhook
      │
      ▼
Update Tenant Billing State
```

---

# Idempotency Design

A single AI request can produce multiple usage events.

For example:

```text
Original Idempotency Key:
request-123
```

The system generates unique event keys:

```text
request-123-api
request-123-in
request-123-cache
request-123-out
request-123-reason
```

This allows each usage type to be stored independently while maintaining exactly-once behavior for each billable event.

---

# Automated Test Suite

The project includes an automated test suite designed around the Capstone acceptance requirements.

Run all tests with:

```bash
pytest -v
```

### Test Coverage

#### `test_tenant.py`

Verifies:

* Tenant isolation
* Required `X-Tenant-ID` header
* Invalid tenant rejection
* Requests cannot access another tenant's data

#### `test_metering.py`

Verifies:

* Usage events are recorded correctly
* Database uniqueness constraints prevent duplicate events
* Repeated idempotency keys do not create duplicate charges
* Original usage events are safely returned after duplicate requests

#### `test_quotas.py`

Verifies:

* Usage can reach the exact plan limit
* Requests beyond the limit are rejected
* Free-tier users receive `402 Payment Required`
* Paid-tier users receive `429 Too Many Requests`

#### `test_cost.py`

Verifies:

* Exact AI token pricing
* Cached input tokens are cheaper than regular input tokens
* Reasoning tokens use the same price as output tokens
* Cost calculations return integer micro-units
* Different token categories are priced independently

#### `test_webhooks.py`

Verifies:

* Valid webhook signatures are accepted
* Forged signatures are rejected
* Valid payment events update the database correctly
* Duplicate webhook events are ignored
* Replayed events cannot cause duplicate processing

---

# Key Design Principles

This project follows several important backend and billing principles:

* **Tenant isolation at the API boundary**
* **Database-enforced uniqueness**
* **Idempotent billing operations**
* **Quota validation before billable work**
* **Integer-based money calculations**
* **Centralized pricing configuration**
* **Provider abstraction**
* **Cryptographic webhook verification**
* **Webhook replay protection**
* **Automated acceptance testing**

The result is a billing engine that separates **authorization, usage metering, cost calculation, and payment processing** into clear responsibilities while keeping the core architecture extensible for additional payment providers.
