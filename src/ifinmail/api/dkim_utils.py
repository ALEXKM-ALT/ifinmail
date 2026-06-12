import logging
import shutil
import subprocess
import tempfile

logger = logging.getLogger("ifinmail.dkim_utils")


def generate_dkim_key(bits: int = 1024) -> tuple[str, str]:
    tmpdir = tempfile.mkdtemp()
    try:
        priv_path = f"{tmpdir}/dkim_private.pem"
        pub_path = f"{tmpdir}/dkim_public.pem"
        subprocess.run(
            ["openssl", "genrsa", "-out", priv_path, str(bits)],
            capture_output=True, check=True,
        )
        subprocess.run(
            ["openssl", "rsa", "-in", priv_path, "-pubout", "-out", pub_path],
            capture_output=True, check=True,
        )
        with open(priv_path) as f:
            priv = f.read()
        with open(pub_path) as f:
            pub = f.read()
        return priv, pub
    except FileNotFoundError:
        logger.error("openssl not found; cannot generate DKIM key")
        raise
    except subprocess.CalledProcessError as e:
        logger.error("openssl failed: %s", e.stderr.decode())
        raise
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def dkim_dns_record(public_key_pem: str) -> str:
    """Convert a PEM-encoded RSA public key to a DKIM DNS TXT record value."""
    b64 = "".join(public_key_pem.strip().splitlines()[1:-1])
    return f"v=DKIM1; h=sha256; k=rsa; p={b64}"


def dkim_sign_message(
    msg_bytes: bytes,
    domain: str,
    selector: str = "default",
    private_key_pem: str | None = None,
    db_session=None,
) -> bytes:
    """Sign an email message with DKIM. Looks up the key from DB if not provided."""
    import dkim

    if private_key_pem is None and db_session is not None:
        from ifinmail.db.models import Domain

        dom = db_session.query(Domain).filter(Domain.domain == domain).first()
        if dom and dom.dkim_private_key:
            private_key_pem = dom.dkim_private_key
            selector = dom.dkim_selector or "default"

    if not private_key_pem:
        return msg_bytes

    header_names = [b"from", b"subject", b"date", b"message-id", b"to", b"cc", b"mime-version", b"content-type"]
    try:
        sig = dkim.sign(
            message=msg_bytes,
            selector=selector.encode(),
            domain=domain.encode(),
            privkey=private_key_pem.encode(),
            include_headers=header_names,
            length=False,
        )
        return sig + msg_bytes
    except Exception as e:
        logger.warning("DKIM signing failed for %s: %s", domain, e)
        return msg_bytes
