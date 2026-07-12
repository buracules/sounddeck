from __future__ import annotations

import json
import re
import ssl
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


@dataclass
class ProbeResult:
    method: str
    url: str
    ok: bool
    status: int | None
    response: Any
    error: str | None = None
    request_body: Any | None = None


class SonarIpcProbe:
    def __init__(self) -> None:
        self._ssl_ctx = ssl.create_default_context()
        self._ssl_ctx.check_hostname = False
        self._ssl_ctx.verify_mode = ssl.CERT_NONE
        self._gg_error_log = Path(r"C:\ProgramData\SteelSeries\GG\logs\gg-errorlog.txt")

    def capture(self, out_path: Path) -> Path:
        out_path.parent.mkdir(parents=True, exist_ok=True)

        snapshot: dict[str, Any] = {
            "captured_at_utc": datetime.now(timezone.utc).isoformat(),
            "guesses": {
                "ipc_base": self._discover_ipc_base(),
                "sonar_base": self._discover_sonar_base(),
            },
            "results": [],
        }

        results: list[ProbeResult] = []
        results.append(self._request_json("GET", "https://127.0.0.1:6327/subApps"))
        results.append(self._request_json("GET", "https://127.0.0.1:6327/keyboardShortcuts"))

        sonar_base = snapshot["guesses"]["sonar_base"]
        if isinstance(sonar_base, str) and sonar_base:
            results.append(self._request_json("GET", f"{sonar_base}/keyboardShortcuts"))

        ipc_base = snapshot["guesses"]["ipc_base"]
        if isinstance(ipc_base, str) and ipc_base:
            results.append(self._request_json("GET", f"{ipc_base}/subApps"))
            results.append(self._request_json("GET", f"{ipc_base}/devices"))
            results.append(self._request_json("POST", f"{ipc_base}/subAppActions", {}))
            results.append(self._request_json("POST", f"{ipc_base}/v2/subAppActions", {}))
            results.append(
                self._request_json(
                    "POST",
                    f"{ipc_base}/v2/subAppActions",
                    {"subAppName": "sonar"},
                )
            )
            results.append(
                self._request_json(
                    "POST",
                    f"{ipc_base}/v2/subAppActions",
                    {"subAppName": "sonar", "subAppActions": []},
                )
            )

            device_ids = self._extract_device_ids(results)
            action_names = (
                "getPreviousPlaybackDevice",
                "getNextPlaybackDevice",
                "getPreviousChatCaptureDevice",
                "getNextChatCaptureDevice",
                "getPreviousMediaPlaybackDevice",
                "getNextMediaPlaybackDevice",
            )
            for device_id in device_ids:
                for action_name in action_names:
                    results.append(
                        self._request_json(
                            "GET",
                            f"{ipc_base}/subAppActions/{device_id}/{action_name}/bindableActions",
                        )
                    )

        snapshot["results"] = [asdict(item) for item in results]
        out_path.write_text(json.dumps(snapshot, indent=2), encoding="utf-8")
        return out_path

    def replay(self, payload_path: Path, ipc_base: str | None = None) -> ProbeResult:
        payload = json.loads(payload_path.read_text(encoding="utf-8"))
        base = ipc_base or self._discover_ipc_base()
        if not base:
            return ProbeResult(
                method="POST",
                url="/v2/subAppActions",
                ok=False,
                status=None,
                response={},
                error="Unable to discover IPC base URL",
            )
        return self._request_json("POST", f"{base}/v2/subAppActions", payload)

    def _discover_sonar_base(self) -> str | None:
        result = self._request_json("GET", "https://127.0.0.1:6327/subApps")
        if not result.ok or not isinstance(result.response, dict):
            return None

        sub_apps = result.response.get("subApps")
        if not isinstance(sub_apps, dict):
            return None
        sonar = sub_apps.get("sonar")
        if not isinstance(sonar, dict):
            return None
        metadata = sonar.get("metadata")
        if not isinstance(metadata, dict):
            return None
        web_server = metadata.get("webServerAddress")
        return web_server if isinstance(web_server, str) else None

    def _discover_ipc_base(self) -> str | None:
        if not self._gg_error_log.exists():
            return "https://127.0.0.1:1530"

        lines = self._gg_error_log.read_text(encoding="utf-8", errors="replace").splitlines()
        pattern = re.compile(r"Making IPC POST request to (https://127\.0\.0\.1:\d+)/v2/subAppActions")
        for line in reversed(lines):
            match = pattern.search(line)
            if match:
                return match.group(1)

        return "https://127.0.0.1:1530"

    def _extract_device_ids(self, results: list[ProbeResult]) -> list[int]:
        for item in results:
            if item.method != "GET" or not item.url.endswith("/devices"):
                continue
            if not isinstance(item.response, dict):
                continue
            devices = item.response.get("devices")
            if not isinstance(devices, list):
                continue
            ids: list[int] = []
            for device in devices:
                if isinstance(device, dict):
                    value = device.get("id")
                    if isinstance(value, int):
                        ids.append(value)
            if ids:
                return ids
        return []

    def _request_json(self, method: str, url: str, payload: Any | None = None) -> ProbeResult:
        data = None
        headers = {}
        if payload is not None:
            data = json.dumps(payload).encode("utf-8")
            headers["Content-Type"] = "application/json"

        req = Request(url, data=data, headers=headers, method=method)
        request_body = payload
        try:
            with urlopen(req, context=self._ssl_ctx if url.startswith("https://") else None, timeout=6) as resp:
                raw = resp.read().decode("utf-8", errors="replace")
                parsed = self._parse_json(raw)
                return ProbeResult(method, url, True, resp.status, parsed, request_body=request_body)
        except HTTPError as exc:
            raw = exc.read().decode("utf-8", errors="replace")
            parsed = self._parse_json(raw)
            return ProbeResult(
                method=method,
                url=url,
                ok=False,
                status=exc.code,
                response=parsed,
                error=None,
                request_body=request_body,
            )
        except URLError as exc:
            return ProbeResult(
                method=method,
                url=url,
                ok=False,
                status=None,
                response={},
                error=str(exc.reason),
                request_body=request_body,
            )
        except Exception as exc:
            return ProbeResult(
                method=method,
                url=url,
                ok=False,
                status=None,
                response={},
                error=str(exc),
                request_body=request_body,
            )

    @staticmethod
    def _parse_json(value: str) -> Any:
        try:
            return json.loads(value)
        except Exception:
            return value
