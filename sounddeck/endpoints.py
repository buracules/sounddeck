from __future__ import annotations

import json
import ssl
from urllib.request import Request, urlopen


def discover_sonar_api_base(default: str = "http://127.0.0.1:7011") -> str:
    """
    Discover Sonar's local web API base URL via GG IPC metadata.
    Falls back to the historical default if discovery fails.
    """
    req = Request("https://127.0.0.1:6327/subApps", method="GET")
    ssl_ctx = ssl.create_default_context()
    ssl_ctx.check_hostname = False
    ssl_ctx.verify_mode = ssl.CERT_NONE
    try:
        with urlopen(req, context=ssl_ctx, timeout=2.5) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
    except Exception:
        return default

    try:
        payload = json.loads(raw)
    except Exception:
        return default

    if not isinstance(payload, dict):
        return default
    sub_apps = payload.get("subApps")
    if not isinstance(sub_apps, dict):
        return default
    sonar = sub_apps.get("sonar")
    if not isinstance(sonar, dict):
        return default
    metadata = sonar.get("metadata")
    if not isinstance(metadata, dict):
        return default
    web_server = metadata.get("webServerAddress")
    if isinstance(web_server, str) and web_server.startswith(("http://", "https://")):
        return web_server.rstrip("/")

    return default
