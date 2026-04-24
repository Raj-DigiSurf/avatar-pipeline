"""
Windows SSL fix — disable certificate revocation check that hangs boto3/httpx.

Import this BEFORE boto3 or supabase:
    from pipeline.ssl_fix import patch_ssl
    patch_ssl()

Only applies on Windows. No-op on Linux/macOS.

Root cause: Windows SChannel performs OCSP/CRL revocation checks that hang
when the revocation endpoint is unreachable. boto3 and httpx (supabase) both
inherit this behavior from Python's ssl module on Windows.
"""

import os
import platform
import ssl
import logging

log = logging.getLogger(__name__)
_patched = False


def patch_ssl():
    """Patch SSL to skip revocation checks on Windows."""
    global _patched
    if _patched:
        return
    _patched = True

    if platform.system() != "Windows":
        return

    # Force pip's certifi CA bundle instead of Windows cert store.
    # This bypasses SChannel entirely, avoiding the revocation check hang.
    try:
        import certifi
        ca_path = certifi.where()
        os.environ["SSL_CERT_FILE"] = ca_path
        os.environ["REQUESTS_CA_BUNDLE"] = ca_path
        # boto3/botocore reads AWS_CA_BUNDLE
        os.environ.setdefault("AWS_CA_BUNDLE", ca_path)
        log.debug("SSL patched for Windows: using certifi CA bundle at %s", ca_path)
    except ImportError:
        # Fallback: disable verify entirely (less safe, but works)
        os.environ["PYTHONHTTPSVERIFY"] = "0"
        os.environ["AWS_CA_BUNDLE"] = ""
        log.warning("certifi not installed — SSL verification disabled on Windows")
