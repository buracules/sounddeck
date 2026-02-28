from __future__ import annotations

import json
from dataclasses import dataclass
from urllib.error import HTTPError
from urllib.parse import quote
from urllib.request import Request, urlopen

from .endpoints import discover_sonar_api_base


@dataclass
class AppSession:
    session_id: str
    process_id: int
    process_name: str
    display_name: str
    role: str
    data_flow: str
    state: str


class AudioRoutingClient:
    BASE_URL = "http://127.0.0.1:7011"

    def __init__(self, base_url: str | None = None) -> None:
        self._base_url = (base_url or discover_sonar_api_base(self.BASE_URL)).rstrip("/")

    def list_sessions(self) -> list[AppSession]:
        raw = self._get_json("/audioDeviceRouting")
        if not isinstance(raw, list):
            return []

        out: list[AppSession] = []
        seen: set[str] = set()
        for route in raw:
            if not isinstance(route, dict):
                continue
            role = str(route.get("role") or "")
            data_flow = str(route.get("dataFlow") or "")
            sessions = route.get("audioSessions")
            if not isinstance(sessions, list):
                continue
            for session in sessions:
                if not isinstance(session, dict):
                    continue
                sid = str(session.get("id") or "")
                if not sid or sid in seen:
                    continue
                pid = int(session.get("processId") or 0)
                pname = str(session.get("processName") or "")
                display = str(session.get("displayName") or pname or sid)
                if pid == 0 and pname.lower() == "idle":
                    continue
                seen.add(sid)
                out.append(
                    AppSession(
                        session_id=sid,
                        process_id=pid,
                        process_name=pname,
                        display_name=display,
                        role=role,
                        data_flow=data_flow,
                        state=str(session.get("state") or ""),
                    )
                )
        out.sort(key=lambda s: (s.process_name.lower(), s.process_id))
        return out

    def route_process(self, process_id: int, target_role: str) -> None:
        role = target_role.strip()
        if process_id <= 0:
            raise RuntimeError(f"Invalid process id: {process_id}")

        routes = self._get_json("/audioDeviceRouting")
        if not isinstance(routes, list):
            raise RuntimeError("Invalid /audioDeviceRouting response")

        target_device_id = ""
        for item in routes:
            if not isinstance(item, dict):
                continue
            if str(item.get("dataFlow")) != "render":
                continue
            if str(item.get("role")) != role:
                continue
            value = str(item.get("deviceId") or "").strip()
            if value:
                target_device_id = value
                break

        if not target_device_id:
            raise RuntimeError(f"No render device found for role '{role}'")

        encoded_device = quote(target_device_id, safe="")
        path = f"/audioDeviceRouting/render/{encoded_device}/{process_id}"
        req = Request(
            self._base_url + path,
            data=b"{}",
            method="PUT",
            headers={"Content-Type": "application/json"},
        )
        try:
            with urlopen(req, timeout=4):
                return
        except HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"PUT {path} failed ({exc.code}): {body[:220]}") from exc
        except Exception as exc:
            raise RuntimeError(f"PUT {path} failed: {exc}") from exc

    def _get_json(self, path: str) -> object:
        req = Request(self._base_url + path, method="GET")
        try:
            with urlopen(req, timeout=4) as resp:
                return json.loads(resp.read().decode("utf-8", errors="replace"))
        except HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"GET {path} failed ({exc.code}): {body[:220]}") from exc
        except Exception as exc:
            raise RuntimeError(f"GET {path} failed: {exc}") from exc
