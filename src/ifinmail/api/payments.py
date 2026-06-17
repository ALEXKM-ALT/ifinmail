import base64
import hashlib
import json
import logging
from datetime import UTC, datetime

import httpx
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from ifinmail.api.auth import get_current_user
from ifinmail.api.config import settings
from ifinmail.db.models import User

logger = logging.getLogger("ifinmail.payments")

router = APIRouter(prefix="/payments", tags=["payments"])

_mpesa_requests: dict[str, dict] = {}


class MpesaSTKPush(BaseModel):
    phone: str
    amount: int
    account_ref: str = "ifinmail-topup"
    transaction_desc: str = "ifinmail account top-up"


class MpesaSTKPushResponse(BaseModel):
    success: bool
    checkout_request_id: str | None = None
    message: str


class PaymentStatusResponse(BaseModel):
    success: bool
    status: str
    amount: int = 0
    phone: str = ""
    transaction_id: str = ""
    result_code: int | None = None
    result_desc: str = ""


class BillingPlanResponse(BaseModel):
    name: str
    price_mobile: int
    price_card: int
    emails_per_day: int
    storage_mb: int
    features: list[str]


BILLING_PLANS = [
    {
        "name": "starter",
        "price_mobile": 50000,
        "price_card": 500,
        "emails_per_day": 500,
        "storage_mb": 500,
        "features": ["1 domain", "10 mailboxes", "Basic API access"],
    },
    {
        "name": "business",
        "price_mobile": 200000,
        "price_card": 2000,
        "emails_per_day": 2000,
        "storage_mb": 2048,
        "features": ["5 domains", "100 mailboxes", "Full API access", "Webhooks"],
    },
    {
        "name": "enterprise",
        "price_mobile": 1000000,
        "price_card": 10000,
        "emails_per_day": 10000,
        "storage_mb": 10240,
        "features": ["Unlimited domains", "Unlimited mailboxes", "AI features", "Priority support", "SSO"],
    },
]


def _generate_password(shortcode: str, passkey: str, timestamp: str) -> str:
    s = f"{shortcode}{passkey}{timestamp}"
    return base64.b64encode(hashlib.sha256(s.encode()).digest()).decode()


def _get_timestamp() -> str:
    now = datetime.now(UTC)
    return now.strftime("%Y%m%d%H%M%S")


def _get_mpesa_base_url() -> str:
    if settings.mpesa_environment == "production":
        return "https://api.safaricom.co.ke"
    return "https://sandbox.safaricom.co.ke"


async def _get_mpesa_token() -> str:
    url = f"{_get_mpesa_base_url()}/oauth/v1/generate?grant_type=client_credentials"
    auth = base64.b64encode(f"{settings.mpesa_consumer_key}:{settings.mpesa_consumer_secret}".encode()).decode()
    async with httpx.AsyncClient() as client:
        resp = await client.get(url, headers={"Authorization": f"Basic {auth}"})
        data = resp.json()
        return data.get("access_token", "")


@router.get("/plans", response_model=list[BillingPlanResponse])
def get_plans():
    return BILLING_PLANS


@router.post("/mpesa/stkpush", response_model=MpesaSTKPushResponse)
async def mpesa_stk_push(
    req: MpesaSTKPush,
    user: User = Depends(get_current_user),
):
    if not settings.mpesa_consumer_key or settings.mpesa_environment == "sandbox":
        checkout_id = hashlib.md5(f"{req.phone}{req.amount}{datetime.now(UTC).isoformat()}".encode()).hexdigest()[:16]
        _mpesa_requests[checkout_id] = {
            "status": "pending",
            "amount": req.amount,
            "phone": req.phone,
            "user_id": user.id,
            "created_at": datetime.now(UTC).isoformat(),
        }
        return MpesaSTKPushResponse(
            success=True, checkout_request_id=checkout_id, message="STK push sent (sandbox mode)"
        )

    token = await _get_mpesa_token()
    timestamp = _get_timestamp()
    password = _generate_password(settings.mpesa_shortcode, settings.mpesa_passkey, timestamp)
    callback_url = f"{settings.app_url}/payments/mpesa/callback"

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{_get_mpesa_base_url()}/mpesa/stkpush/v1/processrequest",
            json={
                "BusinessShortCode": settings.mpesa_shortcode,
                "Password": password,
                "Timestamp": timestamp,
                "TransactionType": "CustomerPayBillOnline",
                "Amount": req.amount,
                "PartyA": req.phone,
                "PartyB": settings.mpesa_shortcode,
                "PhoneNumber": req.phone,
                "CallBackURL": callback_url,
                "AccountReference": req.account_ref,
                "TransactionDesc": req.transaction_desc,
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        data = resp.json()
        if data.get("ResponseCode") == "0":
            checkout_id = data["CheckoutRequestID"]
            _mpesa_requests[checkout_id] = {
                "status": "pending",
                "amount": req.amount,
                "phone": req.phone,
                "user_id": user.id,
                "created_at": datetime.now(UTC).isoformat(),
            }
            return MpesaSTKPushResponse(success=True, checkout_request_id=checkout_id, message="STK push sent")
        return MpesaSTKPushResponse(
            success=False, checkout_request_id=None, message=data.get("errorMessage", "STK push failed")
        )


@router.post("/mpesa/callback")
async def mpesa_callback(payload: dict):
    logger.info("M-Pesa callback received: %s", json.dumps(payload)[:200])
    try:
        body = payload.get("Body", {})
        stk = body.get("stkCallback", {})
        checkout_id = stk.get("CheckoutRequestID", "")
        result_code = stk.get("ResultCode")
        result_desc = stk.get("ResultDesc", "")
        if checkout_id in _mpesa_requests:
            _mpesa_requests[checkout_id]["status"] = "completed" if result_code == 0 else "failed"
            _mpesa_requests[checkout_id]["result_code"] = result_code
            _mpesa_requests[checkout_id]["result_desc"] = result_desc
            if result_code == 0:
                items = stk.get("CallbackMetadata", {}).get("Item", [])
                for item in items:
                    if item.get("Name") == "MpesaReceiptNumber":
                        _mpesa_requests[checkout_id]["transaction_id"] = item.get("Value", "")
    except Exception as e:
        logger.error("M-Pesa callback parse error: %s", e)
    return {"ResultCode": 0, "ResultDesc": "Success"}


@router.get("/mpesa/status/{checkout_request_id}", response_model=PaymentStatusResponse)
def mpesa_status(
    checkout_request_id: str,
    user: User = Depends(get_current_user),
):
    req_data = _mpesa_requests.get(checkout_request_id)
    if not req_data or req_data["user_id"] != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Transaction not found")
    return PaymentStatusResponse(
        success=req_data["status"] == "completed",
        status=req_data["status"],
        amount=req_data.get("amount", 0),
        phone=req_data.get("phone", ""),
        transaction_id=req_data.get("transaction_id", ""),
        result_code=req_data.get("result_code"),
        result_desc=req_data.get("result_desc", ""),
    )
