from fastapi import APIRouter, Request, HTTPException
from typing import Dict
import os
import secrets
import hashlib
import logging

from ..persistence import get_db
from ..config import config
from ..tenancy import get_request_tenant_id

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/billing", tags=["billing"])


@router.get("/status")
async def billing_status(request: Request):
    """
    Return billing status for the current tenant.
    """
    tenant_id = getattr(request.state, "tenant_id", None)
    if not tenant_id:
        if not config.DEMO_MODE:
            raise HTTPException(
                status_code=401,
                detail="No tenant context for billing status"
            )
        tenant_id = config.DEMO_TENANT_ID

    db = get_db()
    tenant = db.get_tenant(tenant_id)
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")

    from .plans import get_plan_limits
    limits = get_plan_limits(tenant["plan"])
    usage_today = db.get_tenant_usage(tenant_id)

    return {
        "tenant_id": tenant_id,
        "status": tenant["status"],
        "plan": tenant["plan"],
        "usage": {
            "today": usage_today
        },
        "limits": {
            "requests_per_month": limits.requests_per_month,
            "requests_per_day": limits.requests_per_day,
            "requests_per_minute": limits.requests_per_minute
        }
    }


@router.post("/checkout")
async def create_checkout(request: Request):
    """
    Create a Stripe Checkout session for a plan subscription.

    Body: { tenant_id, plan, success_url, cancel_url }
    Returns: { checkout_url }
    """
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON body")

    tenant_id = body.get("tenant_id", "")
    plan = (body.get("plan") or "starter").lower().strip()
    success_url = body.get("success_url", "")
    cancel_url = body.get("cancel_url", "")

    # Optionally verify Clerk token to extract email for the checkout session
    email = ""
    try:
        from ..middleware.auth import get_token_from_header, verify_clerk_token
        token = get_token_from_header(request)
        if token:
            claims = verify_clerk_token(token) or {}
            email = claims.get("email", "")
    except Exception:
        pass

    # Free plan: no payment needed — redirect straight to success
    if plan == "free":
        return {"checkout_url": success_url}

    plan_upper = plan.upper()
    price_id = os.getenv(f"STRIPE_PRICE_{plan_upper}", "")
    payment_link = os.getenv(f"STRIPE_PAYMENT_LINK_{plan_upper}", "")
    stripe_secret = os.getenv("STRIPE_SECRET_KEY", "")

    # Prefer a proper Checkout Session when we have a price ID + secret key
    if price_id and stripe_secret:
        try:
            import stripe
            stripe.api_key = stripe_secret
            session = stripe.checkout.Session.create(
                payment_method_types=["card"],
                line_items=[{"price": price_id, "quantity": 1}],
                mode="subscription",
                success_url=success_url,
                cancel_url=cancel_url,
                customer_email=email or None,
                metadata={"tenant_id": tenant_id, "plan": plan},
            )
            return {"checkout_url": session.url}
        except Exception as e:
            logger.error(f"Stripe checkout session creation failed: {e}")
            raise HTTPException(status_code=503, detail="Payment processing unavailable")

    # Fall back to a pre-configured Stripe payment link
    if payment_link:
        url = payment_link
        if tenant_id:
            separator = "&" if "?" in url else "?"
            url += f"{separator}client_reference_id={tenant_id}"
        return {"checkout_url": url}

    raise HTTPException(
        status_code=503,
        detail=f"No Stripe configuration found for plan '{plan}'. "
               f"Set STRIPE_PRICE_{plan_upper} or STRIPE_PAYMENT_LINK_{plan_upper}.",
    )


@router.post("/api-keys")
async def create_api_key(request: Request, body: Dict = None):
    """Create a new API key for the authenticated tenant."""
    tenant_id = get_request_tenant_id(request)

    if not tenant_id:
        if not config.DEMO_MODE:
            raise HTTPException(status_code=401, detail="Authentication required")
        tenant_id = config.DEMO_TENANT_ID

    name = (body or {}).get("name") or "API Key"

    raw_key = secrets.token_hex(32)
    key_hash = hashlib.sha256(raw_key.encode()).hexdigest()

    db = get_db()
    api_key = db.create_api_key(
        tenant_id=tenant_id,
        name=name,
        key_hash=key_hash,
    )

    return {
        "api_key": raw_key,
        "api_key_id": api_key["id"],
        "tenant_id": tenant_id,
        "warning": "Store this key now. It will not be shown again.",
    }


@router.delete("/api-keys/{key_id}")
async def delete_api_key(request: Request, key_id: str):
    """Delete an API key owned by the authenticated tenant."""
    tenant_id = get_request_tenant_id(request)

    if not tenant_id:
        if not config.DEMO_MODE:
            raise HTTPException(status_code=401, detail="Authentication required")
        tenant_id = config.DEMO_TENANT_ID

    db = get_db()
    keys = db.list_api_keys(tenant_id)
    if not any(str(k.get("id")) == str(key_id) for k in keys):
        raise HTTPException(status_code=404, detail="API key not found")

    deleted = db.delete_api_key(key_id, tenant_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="API key not found")

    return {"deleted": True, "key_id": key_id}


@router.get("/api-keys")
async def list_api_keys(request: Request):
    """
    List API keys for the current tenant.
    """
    tenant_id = getattr(request.state, "tenant_id", None)
    if not tenant_id:
        if not config.DEMO_MODE:
            raise HTTPException(
                status_code=401,
                detail="No tenant context for API keys"
            )
        tenant_id = config.DEMO_TENANT_ID

    db = get_db()
    keys = db.list_api_keys(tenant_id)
    return {
        "keys": keys,
        "total": len(keys),
    }
