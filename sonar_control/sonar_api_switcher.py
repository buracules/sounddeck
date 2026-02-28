from __future__ import annotations

import json
from dataclasses import dataclass
from urllib.error import HTTPError
from urllib.parse import quote
from urllib.request import Request, urlopen

from .endpoints import discover_sonar_api_base


@dataclass
class SwitchResult:
    stream_id: str
    device_id: str
    device_name: str


@dataclass
class DeviceOption:
    id: str
    name: str


@dataclass
class DeviceSelection:
    stream_id: str
    current_device_id: str
    options: list[DeviceOption]


class SonarApiSwitcher:
    """
    Switch Sonar stream redirection devices through Sonar's local HTTP API.

    Observed endpoints:
      GET  /audiodevices
      GET  /streamRedirections
      PUT  /streamRedirections/{id}/deviceId/{deviceId}
    """

    BASE_URL = "http://127.0.0.1:7011"
    CHANNEL_STREAM_HINTS: dict[str, tuple[str, ...]] = {
        "game": ("game", "gameRender", "gaming"),
        "chatRender": ("chatrender", "chat_render", "chat", "voicechat"),
        "media": ("media", "aux", "auxiliary"),
        "chatCapture": ("chatcapture", "chat_capture", "mic", "microphone", "capture"),
    }

    def __init__(self, base_url: str | None = None) -> None:
        self._base_url = (base_url or discover_sonar_api_base(self.BASE_URL)).rstrip("/")

    def get_selection(self, channel_key: str) -> DeviceSelection:
        stream = self._resolve_stream_for_channel(channel_key)
        if not stream:
            raise RuntimeError(f"No Sonar API stream mapping for channel '{channel_key}'")
        stream_id = str(stream.get("streamRedirectionId") or "")
        if not stream_id:
            raise RuntimeError(f"Sonar stream for '{channel_key}' has no streamRedirectionId")

        data_flow = self._stream_data_flow(stream_id, stream)
        candidates = self._candidate_devices(data_flow=data_flow)
        options = [DeviceOption(id=d["id"], name=d["friendlyName"]) for d in candidates]
        current_id = str(stream.get("deviceId") or "")
        return DeviceSelection(stream_id=stream_id, current_device_id=current_id, options=options)

    def set_device(self, channel_key: str, device_id: str) -> SwitchResult:
        selection = self.get_selection(channel_key)
        selected = next((opt for opt in selection.options if opt.id == device_id), None)
        if not selected:
            raise RuntimeError(f"Device id not available for {channel_key}: {device_id}")

        self._put_stream_device(selection.stream_id, selected.id)
        return SwitchResult(stream_id=selection.stream_id, device_id=selected.id, device_name=selected.name)

    def switch(self, channel_key: str, direction: str) -> SwitchResult:
        stream = self._resolve_stream_for_channel(channel_key)
        if not stream:
            raise RuntimeError(f"No Sonar API stream mapping for channel '{channel_key}'")
        stream_id = str(stream.get("streamRedirectionId") or "")
        if not stream_id:
            raise RuntimeError(f"Sonar stream for '{channel_key}' has no streamRedirectionId")

        data_flow = self._stream_data_flow(stream_id, stream)
        candidates = self._candidate_devices(data_flow=data_flow)
        if len(candidates) < 2:
            raise RuntimeError(f"Not enough {data_flow} output devices to switch")

        current_id = str(stream.get("deviceId") or "")
        index = self._index_of(candidates, current_id)
        step = -1 if direction == "prev" else 1
        target = candidates[(index + step) % len(candidates)]

        self._put_stream_device(stream_id, target["id"])
        return SwitchResult(stream_id=stream_id, device_id=target["id"], device_name=target["friendlyName"])

    def _resolve_stream_for_channel(self, channel_key: str) -> dict[str, object] | None:
        streams = self._get_streams()
        if not streams:
            return None

        hints = tuple(x.lower() for x in self.CHANNEL_STREAM_HINTS.get(channel_key, (channel_key,)))

        # Prefer direct stream match (e.g. game/chatRender/media) when Sonar exposes per-channel streams.
        for stream in streams:
            stream_id = str(stream.get("streamRedirectionId") or "").lower()
            for field in ("name", "streamName", "streamId", "channel"):
                value = str(stream.get(field) or "").lower()
                if any(hint in value for hint in hints):
                    return stream
            if any(hint == stream_id for hint in hints):
                return stream

        # Fallback when per-channel stream is not discoverable.
        # Sonar commonly exposes a shared render stream named "monitoring"
        # for game/chat/media, and a capture stream named "mic".
        if channel_key == "chatCapture":
            fallback_ids = ("mic",)
        elif channel_key in {"game", "chatRender", "media"}:
            fallback_ids = ("monitoring",)
        else:
            fallback_ids = ()
        for stream in streams:
            stream_id = str(stream.get("streamRedirectionId") or "")
            if stream_id in fallback_ids:
                return stream
        return None

    def _candidate_devices(self, data_flow: str) -> list[dict[str, str]]:
        devices = self._get_json("/audiodevices")
        if not isinstance(devices, list):
            return []

        out: list[dict[str, str]] = []
        for dev in devices:
            if not isinstance(dev, dict):
                continue
            if str(dev.get("dataFlow")) != data_flow:
                continue
            if bool(dev.get("isVad")):
                continue
            if str(dev.get("state", "")).lower() != "active":
                continue
            device_id = str(dev.get("id") or "")
            friendly = str(dev.get("friendlyName") or device_id)
            if device_id:
                out.append({"id": device_id, "friendlyName": friendly})
        return out

    def _get_stream(self, stream_id: str) -> dict[str, object] | None:
        for item in self._get_streams():
            if isinstance(item, dict) and str(item.get("streamRedirectionId")) == stream_id:
                return item
        return None

    def _get_streams(self) -> list[dict[str, object]]:
        streams = self._get_json("/streamRedirections")
        if not isinstance(streams, list):
            return []
        return [x for x in streams if isinstance(x, dict)]

    @staticmethod
    def _stream_data_flow(stream_id: str, stream: dict[str, object]) -> str:
        sid = stream_id.lower().strip()
        if sid in {"monitoring", "streaming"}:
            return "render"
        if sid in {"mic", "chatcapture"}:
            return "capture"

        data_flow = str(stream.get("dataFlow") or "").lower()
        if data_flow in {"capture", "render"}:
            return data_flow

        lowered = " ".join(str(v).lower() for v in stream.values())
        if "capture" in lowered or "mic" in lowered:
            return "capture"
        return "render"

    def _put_stream_device(self, stream_id: str, device_id: str) -> None:
        encoded_device_id = quote(device_id, safe="{}.-")
        path = f"/streamRedirections/{stream_id}/deviceId/{encoded_device_id}"
        req = Request(self._base_url + path, data=b"{}", method="PUT", headers={"Content-Type": "application/json"})
        try:
            with urlopen(req, timeout=4) as resp:
                _ = resp.read()
        except HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"Sonar API PUT failed ({exc.code}): {body[:220]}") from exc
        except Exception as exc:
            raise RuntimeError(f"Sonar API PUT failed: {exc}") from exc

    def _get_json(self, path: str) -> object:
        req = Request(self._base_url + path, method="GET")
        try:
            with urlopen(req, timeout=4) as resp:
                raw = resp.read().decode("utf-8", errors="replace")
                return json.loads(raw)
        except HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"Sonar API GET {path} failed ({exc.code}): {body[:220]}") from exc
        except Exception as exc:
            raise RuntimeError(f"Sonar API GET {path} failed: {exc}") from exc

    @staticmethod
    def _index_of(devices: list[dict[str, str]], current_id: str) -> int:
        for idx, dev in enumerate(devices):
            if dev.get("id") == current_id:
                return idx
        return 0
