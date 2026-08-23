from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, UniqueConstraint
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.database import Base


class Plan(Base):
    __tablename__ = "plans"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, nullable=False)  # e.g., "Free", "Pro"
    api_call_limit = Column(Integer, nullable=False)
    ai_token_limit = Column(Integer, nullable=False)


class Tenant(Base):
    __tablename__ = "tenants"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    plan_id = Column(Integer, ForeignKey("plans.id"), nullable=False)
    payment_provider_customer_id = Column(String, unique=True, nullable=True)  # For sandbox provider later

    plan = relationship("Plan")
    subscription = relationship("Subscription", back_populates="tenant", uselist=False)


class Subscription(Base):
    __tablename__ = "subscriptions"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), unique=True, nullable=False)
    status = Column(String, nullable=False)  # e.g., "active", "past_due"

    tenant = relationship("Tenant", back_populates="subscription")


class UsageEvent(Base):
    __tablename__ = "usage_events"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False)
    usage_type = Column(String, nullable=False)  # "api_call" or "ai_token"
    quantity = Column(Integer, nullable=False)
    idempotency_key = Column(String, nullable=False)
    timestamp = Column(DateTime(timezone=True), server_default=func.now())

    # This is critical for the capstone: It prevents the database from ever accepting
    # a duplicate idempotency key for the same tenant.
    __table_args__ = (
        UniqueConstraint('tenant_id', 'idempotency_key', name='_tenant_idempotency_uc'),
    )