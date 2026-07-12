from __future__ import annotations

import argparse
import json
from pathlib import Path

from sounddeck.application import SonarControlApplication
from sounddeck.ipc_probe import SonarIpcProbe


def main() -> None:
    parser = argparse.ArgumentParser(description="Sonar Control Panel")
    parser.add_argument(
        "--capture-ipc",
        metavar="OUT",
        help="Capture Sonar/GG IPC probe results to JSON file.",
    )
    parser.add_argument(
        "--replay-ipc",
        metavar="PAYLOAD",
        help="Replay a JSON payload to /v2/subAppActions.",
    )
    parser.add_argument(
        "--ipc-base",
        metavar="URL",
        help="Optional explicit IPC base URL, e.g. https://127.0.0.1:1530",
    )
    ui_group = parser.add_mutually_exclusive_group()
    ui_group.add_argument(
        "--compact-ui",
        action="store_true",
        help="Start with compact tray-style mixer UI.",
    )
    ui_group.add_argument(
        "--full-ui",
        action="store_true",
        help="Start with full mixer UI.",
    )
    args = parser.parse_args()

    probe = SonarIpcProbe()

    if args.capture_ipc:
        out = probe.capture(Path(args.capture_ipc))
        print(f"IPC capture written to: {out}")
        return

    if args.replay_ipc:
        result = probe.replay(Path(args.replay_ipc), ipc_base=args.ipc_base)
        print(json.dumps(result.__dict__, indent=2))
        return

    compact_mode = True
    if args.full_ui:
        compact_mode = False
    elif args.compact_ui:
        compact_mode = True
    SonarControlApplication(compact_mode=compact_mode).run()


if __name__ == "__main__":
    main()
