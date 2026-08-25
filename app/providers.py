import hmac
import hashlib
import json
from abc import ABC, abstractmethod


class PaymentProvider(ABC):
    """
    Abstract interface for payment providers.
    This decouples our billing engine from Stripe or Safepay specifically.
    """

    @abstractmethod
    def verify_webhook(self, payload: bytes, signature_header: str, secret: str) -> dict:
        """Verifies the webhook signature and returns the parsed JSON event."""
        pass


class SafepayProvider(PaymentProvider):
    """Concrete implementation for Safepay (Sandbox)."""

    def verify_webhook(self, payload: bytes, signature_header: str, secret: str) -> dict:
        if not signature_header:
            raise ValueError("Missing X-Sfp-Signature header")

        # Safepay uses standard HMAC SHA256 for signature verification
        expected_signature = hmac.new(
            key=secret.encode('utf-8'),
            msg=payload,
            digestmod=hashlib.sha256
        ).hexdigest()

        # We use compare_digest to prevent timing attacks!
        if not hmac.compare_digest(signature_header, expected_signature):
            raise ValueError("Invalid webhook signature. Possible forgery attempt.")

        return json.loads(payload)


# Initialize our chosen provider
payment_provider = SafepayProvider()