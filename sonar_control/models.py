from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ChannelState:
    key: str
    label: str
    volume: int
    muted: bool
