import base64
import json
import logging
import struct
import urllib.error
import urllib.request
from dataclasses import dataclass

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

from ifinmail.api.database import SessionLocal
from ifinmail.api.vapid import create_vapid_jwt
from ifinmail.db.models import PushSubscription

logger = logging.getLogger("ifinmail.push")


@dataclass
class PushSubscriptionInfo:
    endpoint: str
    p256dh: bytes
    auth: bytes


def _decode_b64(s: str) -> bytes:
    return base64.urlsafe_b64decode(s + "===")


def _encrypt_payload(payload: bytes, p256dh: bytes, auth: bytes) -> tuple[bytes, bytes, bytes]:
    salt = AESGCM.generate_key(bit_size=128)
    server_key = ec.generate_private_key(ec.SECP256R1())
    server_pub = server_key.public_key().public_bytes(
        serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint
    )
    shared_secret = server_key.exchange(ec.ECDH(), ec.EllipticCurvePublicKey.from_encoded_point(ec.SECP256R1(), p256dh))
    prk = HKDF(algorithm=hashes.SHA256(), length=32, salt=None, info=b"Content-Encoding: auth\0").derive(auth)
    ikm = HKDF(algorithm=hashes.SHA256(), length=32, salt=salt, info=b"Content-Encoding: aes128gcm\0").derive(
        prk + shared_secret
    )
    key, nonce = ikm[:16], ikm[16:]

    aesgcm = AESGCM(key)
    pt = struct.pack(">I", len(payload)) + payload + b"\x00\x10"
    ct = aesgcm.encrypt(nonce, pt, None)

    header = b"\0" + struct.pack(">I", len(server_pub)) + server_pub + salt
    return header + ct, salt, server_pub


def _push_send(sub: PushSubscriptionInfo, payload: bytes | None, vapid_jwt: str) -> bool:
    headers = {
        "TTL": "86400",
        "Content-Type": "application/octet-stream",
        "Authorization": f"WebPush {vapid_jwt}",
    }
    if payload:
        headers["Content-Encoding"] = "aes128gcm"
        body, salt, server_pub = _encrypt_payload(payload, sub.p256dh, sub.auth)
    else:
        body = b""

    req = urllib.request.Request(sub.endpoint, data=body, headers=headers, method="POST")
    try:
        resp = urllib.request.urlopen(req, timeout=15)
        logger.debug("Push sent to %s: HTTP %d", sub.endpoint[:60], resp.status)
        return True
    except urllib.error.HTTPError as exc:
        logger.warning("Push HTTP %d for %s: %s", exc.code, sub.endpoint[:60], exc.read()[:200])
        return exc.code not in (404, 410)
    except Exception as exc:
        logger.warning("Push failed for %s: %s", sub.endpoint[:60], exc)
        return True


def notify_user(user_id: int, event: str, data: dict | None = None) -> None:
    payload = json.dumps({"event": event, "data": data or {}}).encode()
    db = SessionLocal()
    try:
        subs = db.query(PushSubscription).filter(PushSubscription.user_id == user_id).all()
        if not subs:
            return
        from ifinmail.db.models import User

        user = db.query(User).filter(User.id == user_id).first()
        subject = user.email if user else "noreply@ifinmail.local"
        vapid_jwt = create_vapid_jwt(subject)
        for sub in subs:
            info = PushSubscriptionInfo(
                endpoint=sub.endpoint,
                p256dh=_decode_b64(sub.p256dh_key),
                auth=_decode_b64(sub.auth_key),
            )
            _push_send(info, payload, vapid_jwt)
    except Exception:
        logger.exception("notify_user push failed for user %d", user_id)
    finally:
        db.close()
