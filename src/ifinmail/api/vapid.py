import base64
import json
import os
import time

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa

_CONFIG_PATH = os.environ.get(
    "VAPID_KEYS_PATH",
    os.path.join(os.path.dirname(__file__), "..", "..", "vapid_keys.json"),
)


def _ensure_keys() -> tuple[str, str]:
    path = os.path.abspath(_CONFIG_PATH)
    if os.path.exists(path):
        with open(path) as f:
            data = json.load(f)
            return data["public_key"], data["private_key"]
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public_key_pem = (
        private_key.public_key()
        .public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo)
        .decode()
    )
    private_key_pem = private_key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    ).decode()
    with open(path, "w") as f:
        json.dump({"public_key": public_key_pem, "private_key": private_key_pem}, f)
    return public_key_pem, private_key_pem


def get_vapid_public_key_b64() -> str:
    pem, _ = _ensure_keys()
    lines = pem.strip().split("\n")
    b64 = "".join(line for line in lines if not line.startswith("-----"))
    return b64


def create_vapid_jwt(subject: str) -> str:
    _, private_key_pem = _ensure_keys()
    private_key = serialization.load_pem_private_key(private_key_pem.encode(), password=None)
    header = {"typ": "JWT", "alg": "RS256"}
    now = int(time.time())
    payload = {"aud": "https://push.googleapis.com", "exp": now + 43200, "sub": f"mailto:{subject}"}

    def _b64(data: bytes) -> str:
        return base64.urlsafe_b64encode(data).rstrip(b"=").decode()

    header_b64 = _b64(json.dumps(header, separators=(",", ":")).encode())
    payload_b64 = _b64(json.dumps(payload, separators=(",", ":")).encode())
    sig = private_key.sign(f"{header_b64}.{payload_b64}".encode(), padding.PKCS1v15(), hashes.SHA256())
    sig_b64 = _b64(sig)
    return f"{header_b64}.{payload_b64}.{sig_b64}"
