"""beyin — turn your fav content into queryable local memory."""

__version__ = "0.3.7"


def _configure_ssl() -> None:
    """Append custom CA certs to the default bundle when BEYIN_SSL_CERT is set.

    Corporate proxies often use a self-signed root CA.  Setting SSL_CERT_FILE
    to *only* that cert breaks connections to standard hosts because the
    default root CAs are no longer trusted.  This helper builds a combined
    bundle (certifi defaults + custom certs) and points the relevant env vars
    at it so every HTTP library picks it up transparently.

    BEYIN_SSL_CERT accepts a single path or multiple paths separated by colons:
        export BEYIN_SSL_CERT=/path/to/RootCA.crt:/path/to/IntermediateCA.crt
    """
    import os

    cert_paths_raw = os.environ.get("BEYIN_SSL_CERT")
    if not cert_paths_raw:
        return

    # Already configured in a previous import — nothing to do.
    if os.environ.get("_BEYIN_SSL_CONFIGURED"):
        return

    from pathlib import Path

    cert_paths = [
        Path(p.strip()).expanduser()
        for p in cert_paths_raw.split(":")
        if p.strip()
    ]
    cert_paths = [p for p in cert_paths if p.is_file()]
    if not cert_paths:
        return

    try:
        import certifi

        base_bundle = Path(certifi.where()).read_text().rstrip()
    except Exception:
        return

    custom_certs = []
    for cp in cert_paths:
        content = cp.read_text().strip()
        if content not in base_bundle:
            custom_certs.append(content)

    if not custom_certs:
        combined_path = certifi.where()
    else:
        from beyin.paths import beyin_home

        combined = beyin_home() / "ca-bundle.pem"
        combined.parent.mkdir(parents=True, exist_ok=True)
        combined.write_text(base_bundle + "\n" + "\n".join(custom_certs) + "\n")
        combined_path = str(combined)

    os.environ["SSL_CERT_FILE"] = combined_path
    os.environ["REQUESTS_CA_BUNDLE"] = combined_path
    os.environ["CURL_CA_BUNDLE"] = combined_path

    # httpx uses certifi.where() directly instead of SSL_CERT_FILE.
    # Monkey-patch it so all httpx-based clients (e.g. huggingface_hub)
    # pick up the combined bundle automatically.
    certifi.where = lambda: combined_path

    os.environ["_BEYIN_SSL_CONFIGURED"] = "1"


_configure_ssl()
